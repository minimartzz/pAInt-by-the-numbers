"""
Model Deploy
============
Deply FLUX.1-scnell as a Modal image. The model weights (~16GB) are downloaded
once into a Modal and reused across all subsequent cold starts

Endpoint:  POST /transform
Body (JSON):
  {
    "prompt":       "Van Gogh oil painting style, swirling brushstrokes",
    "image_b64":    "<base64-encoded PNG/JPEG>",          # optional source image
    "steps":        4,                                     # default 4 (1-8)
    "guidance":     0.0,                                   # default 0.0 (schnell)
    "width":        1024,                                  # default 1024
    "height":       1024                                   # default 1024
  }
"""
import io
import time
import base64
import modal
from pathlib import Path

# ========================================
# IMAGE + VOLUME DEFINITION
# ========================================
CACHE_DIR = Path("/cache")
cuda_version = "12.6.3"
image = (
  modal.Image.from_registry(
    f"nvidia/cuda:{cuda_version}-devel-ubuntu24.04",
    add_python="3.11"
  )
  .entrypoint([])
  .pip_install(
    "torch==2.7.0",
    "torchvision",
    "diffusers>=0.33.0",
    "transformers>=4.51.0",
    "accelerate>=1.6.0",
    "sentencepiece",
    "pillow>=10.0.0",
    "huggingface_hub>=0.30.0",
    "hf-xet",
    "para-attn=0.3.32"
  )
  .env({
    "HF_XET_HIGH_PERFORMANCE": "1",      # Enables HF's fast transfer
    "TORCHINDUCTOR_FX_GRAPH_CACHE": "1", # Persist torch inductor FC graph cache across restsarts
    # Persistent caches stored in CACHE_DIR
    "TORCHINDUCTOR_CACHE_DIR": str(CACHE_DIR / ".inductor_cache"),
    "TRITON_CACHE_DIR":        str(CACHE_DIR / ".inductor_cache"),
    "CUDA_CACHE_PATH":         str(CACHE_DIR / ".inductor_cache"),
    "HF_HUB_CACHE":            str(CACHE_DIR / ".inductor_cache")
  })
)

# ---- Volume -----------------------------
model_volume = modal.Volume.from_name("flux-schnell-weights", create_if_missing=True)
cache_volume  = modal.Volume.from_name("flux-schnell-cache",   create_if_missing=True)
MODEL_DIR = "/vol/models/flux-schnell"
MODEL_ID = "black-forest-labs/FLUX.1-schnell"

app = modal.App("flux-pbn")

# ========================================
# DOWNLOAD MODEL WEIGHTS
# ========================================
@app.function(
  image=image,
  volumes={MODEL_DIR: model_volume},
  timeout=900,
  secrets=[modal.Secret.from_name("huggingface-secret")]
)
def download_weights():
  from huggingface_hub import snapshot_download
  import os

  print(f"[WEIGHTS] Download {MODEL_ID} -> {MODEL_DIR}")
  snapshot_download(
    repo_id=MODEL_ID,
    local_dir=MODEL_DIR,
    token=os.environ.get("HF_TOKEN"),
    ignore_patterns=["*.md", "*.txt"]
  )
  model_volume.commit()
  print("[WEIGHTS] Download complete.")

# ========================================
# FLUX MODEL
# ========================================
@app.cls(
  image=image,
  gpu="A10G",
  volumes={
    MODEL_DIR: model_volume,
    CACHE_DIR: cache_volume,
  },
  timeout=300,
  scaledown_window=300,
  secrets=[modal.Secret.from_name("huggingface-secret")],
  enable_memory_snapshot=True
)
class FluxModel:
  # ---- Load Weights ---------------------
  @modal.enter(snap=True)
  def load(self):
    import torch
    from diffusers import FluxPipeline

    print("[FLUX - CPU] Loading FLUX.1-schnell weights to CPU...")
    self.pipe = FluxPipeline.from_pretrained(
      MODEL_DIR,
      torch_dtype=torch.bfloat16,
      use_safetensors=True
    ).to("cpu")

    # Prepare mega-cache path
    mega_cache_dir = CACHE_DIR / ".mega_cache"
    mega_cache_dir.mkdir(parents=True, exist_ok=True)
    self.mega_cache_path = mega_cache_dir / "flux_schnell_mega"

    print("[FLUX - CPU] Weights loaded to CPU - snapshot will be taken from here...")
  
  # ---- Move model to CUDA: Load from snapshot ---------------
  @modal.enter(snap=False)
  def setup(self):
    import torch

    print("[FLUX - GPU] Moving pipeline to GPU...")
    self.pipe.to("cuda")

    # Load compiled torch graph from mega_cache
    self._load_mega_cache()

    # Apply performance optimisations
    self._optimize()

    # Trigger compilation of torch graph
    # Can be slow on first boot because compilation of torch code takes time
    # Subsequent boots take from caches
    self._compile_warmup()

    # Persist the mega-cache
    self._save_mega_cache()

    print("[FLUX - GPU] Pipeline ready...")
  
  # ---- Optimisation Helpers ----------------------
  def _optimize(self):
    import torch
    from para_attn.first_block_cache.diffusers_adapters import apply_cache_on_pipe

    # First Block Caching - skips denoising steps where the activations
    #   haven't changed much. Looks at the variance in the model's outputs
    #   didn't move more than the threshold then skip that step => Faster
    #   performance (higher = faster performance but more quality loss)
    apply_cache_on_pipe(
      self.pipe,
      threshold=0.12
    )

    # Fused QKV - Concatenate the Q, K, V weight matrices so attention is
    #   one large matmul instead of separate operations
    self.pipe.transformer.fuse_qkv_projections()
    self.pipe.vae.fuse_qkv_projections()

    # Channels-last format - Moves the channels to the last dimensions. Generally,
    #   shown to improve performance
    self.pipe.transformer.to(memory_format=torch.channels_last)
    self.pipe.vae.to(memory_format=torch.channels_last)

    # Copying torch inductor config from Modal article
    cfg = torch._inductor.config
    cfg.conv_1x1_as_mm                          = True
    cfg.coordinate_descent_tuning               = True
    cfg.coordinate_descent_check_all_directions = True
    cfg.epilogue_fusion                         = False
    cfg.shape_padding                           = True

    # Compile
    self.pipe.transformer = torch.compile(
      self.pipe.transformer,
      mode="max-autotune-no-cudagraphs",
      dynamic=True,
    )
    self.pipe.vae.decode = torch.compile(
      self.pipe.vae.decode,
      mode="max-autotune-no-cudagraphs",
      dynamic=True,
    )

  def _compile_warmup(self):
    """Runs a dummy inference to trigger torch.compile"""
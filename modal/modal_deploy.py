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
    # Monkey-patch to handle a known para-attn + dynamic shapes bug:
    # torch inductor's remove_noop_ops pass crashes on SymFloat objects.
    from torch._inductor.dc_passes import post_grad
    if not hasattr(post_grad, "_orig_same_meta"):
      post_grad._orig_same_meta = post_grad.same_meta # Save the original implementation

      def _safe_same_meta(n1, n2):
        try:
          return post_grad._orig_same_meta(n1, n2)
        except AttributeError as e:
          if "SymFloat" in str(e) and "size" in str(e):
            return False
          raise
      
      post_grad.same_meta = _safe_same_meta # Monkey-patch: Update function at runtime
    
    print("[COMPILE] Trigger torch compile (warmup pass 1/2)...")
    self.pipe(
      "warmup",
      height=1024,
      width=1024,
      num_images_per_prompt=1,
      num_inference_steps=1
    )

    print("[COMPILE] Trigger torch compile (warmup pass 2/2 - dynamic batch)...")
    self.pipe(
      "warmup",
      height=1024,
      width=1024,
      num_images_per_prompt=2,
      num_inference_steps=1
    )
  
  def _load_mega_cache(self):
    """Restores serialised torch compiler artifacts from cache"""
    try:
      if self.mega_cache_path.exists():
        print("[LOAD] Loading torch mega-cache...")
        with open(self.mega_cache_path, "rb") as f:
          data = f.read()
        if data:
          import torch
          torch.compiler.load_cache_artifacts(data)
        else:
          print("[LOAD] Mega-cache file empty, will regenerate")
    except Exception as e:
      print(f"[LOAD] Could not load mega-cache (will regenerate): {e}")
  
  def _save_mega_cache(self):
    """Serialise compiled torch artifacts to the cache volume for next boot"""
    try:
      import torch
      print("[SAVE] Saving torch mega-cache...")
      artifacts, _ = torch.compiler.save_cache_artifacts()
      with open(self.mega_cache_path, "wb") as f:
        f.write(artifacts)
      cache_volume.commit()
      print("[SAVE] Mega-cache saved")
    except Exception as e:
      print(f"Could not save mega-cache: {e}")

  # ---- Web Endpoint ------------------------------
  @modal.fastapi_endpoint(method="POST", label="flux-transform")
  def transform(self, request: dict) -> dict:
    """
    POST /transform

    Supports two modes:
      - text2img: No image provided -> generates from prompt alone 
      - img2img: Image provided -> style-transfer based on prompt and uploaded image
    """
    import torch
    from PIL import Image
    from diffusers import FluxImg2ImgPipeline

    prompt    = request.get("prompt", "")
    image_b64 = request.get("image_b64")
    steps     = min(max(int(request.get("steps", 4)), 1), 8)
    guidance  = float(request.get("guidance", 0.0))
    width     = int(request.get("width", 1024))
    height    = int(request.get("height", 1024))
    strength  = float(request.get("strength", 0.75))

    if not prompt:
      return {"error": "A prompt is required"}, 400
    
    torch.cuda.synchronize()
    start = time.perf_counter()
    mode = "text2img"

    if image_b64:
      mode = "img2img"
      img_bytes = base64.b64decode(image_b64)
      source_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
      source_image = source_image.resize((width, height))

      # Load compiled model from self.pipe
      img2img_pipe = FluxImg2ImgPipeline(
        **{k: getattr(self.pipe, k) for k in [
          "scheduler", "vae", "text_encoder", "tokenizer",
          "text_encoder_2", "tokenizer_2", "transformer"
        ]}
      )
      img2img_pipe.to("cuda")

      result = img2img_pipe(
        prompt=prompt,
        image=source_image,
        strength=strength,
        num_inference_steps=steps,
        guidance_scale=guidance,
        generator=torch.Generator("cuda").manual_seed(0)
      )
    else:
      result = self.pipe(
        prompt=prompt,
        num_inference_steps=steps,
        guidance_scale=guidance,
        width=width,
        height=height,
        generator=torch.Generator("cuda").manual_seed(0),
        max_sequence_length=256,
      )
    
    torch.cuda.synchronize()
    duration = round(time.perf_counter() - start, 2)

    buf = io.BytesIO()
    result.images[0].save(buf, format="PNG")
    output_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return {
      "image_b64": output_b64,
      "metadata": {
        "model": "FLUX.1-schnell",
        "prompt": prompt,
        "steps": steps,
        "guidance": guidance,
        "width": width,
        "height": height,
        "strength": strength if image_b64 else None,
        "mode": mode,
        "duration_seconds": duration
      }
    }
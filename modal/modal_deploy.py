"""
modal_deploy.py
---------------
Deploys FLUX.1-schnell as a serverless image style-transfer endpoint on Modal.

Requirements:
  pip install modal
  modal token new          # authenticate once
  modal deploy modal_deploy.py

The model weights (~16 GB) are downloaded once into a Modal Volume and reused
across all subsequent cold starts — avoiding a 3-minute download on every boot.

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

Response (JSON):
  {
    "image_b64":  "<base64-encoded PNG>",
    "metadata": {
      "model":    "FLUX.1-schnell",
      "prompt":   "...",
      "steps":    4,
      "width":    1024,
      "height":   1024,
      "mode":     "img2img" | "txt2img",
      "duration_seconds": 4.2
    }
  }
"""

import io
import time
import base64
import modal

# ---------------------------------------------------------------------------
# Image: install all Python deps into the container
# ---------------------------------------------------------------------------
flux_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch==2.3.1",
        "torchvision",
        "diffusers>=0.30.0",
        "transformers>=4.44.0",
        "accelerate>=0.33.0",
        "sentencepiece",
        "pillow>=10.0.0",
        "huggingface_hub>=0.24.0",
    )
)

# ---------------------------------------------------------------------------
# Volume: cache model weights so cold starts don't re-download 16 GB
# ---------------------------------------------------------------------------
model_volume = modal.Volume.from_name("flux-schnell-weights", create_if_missing=True)
MODEL_DIR = "/vol/models/flux-schnell"
MODEL_ID = "black-forest-labs/FLUX.1-schnell"

app = modal.App("flux-style-transfer")


# ---------------------------------------------------------------------------
# One-time setup: download weights into the Volume
# Run manually with:  modal run modal_deploy.py::download_weights
# ---------------------------------------------------------------------------
@app.function(
    image=flux_image,
    volumes={MODEL_DIR: model_volume},
    timeout=900,            # 15 min — enough for the initial 16 GB download
    secrets=[modal.Secret.from_name("huggingface-secret")],  # HF_TOKEN
)
def download_weights():
    from huggingface_hub import snapshot_download
    import os

    print(f"Downloading {MODEL_ID} → {MODEL_DIR}")
    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=MODEL_DIR,
        token=os.environ.get("HF_TOKEN"),
        ignore_patterns=["*.md", "*.txt"],
    )
    model_volume.commit()
    print("Download complete.")


# ---------------------------------------------------------------------------
# Inference function — runs on an A10 GPU (24 GB VRAM, fits FLUX.1-schnell)
# ---------------------------------------------------------------------------
@app.cls(
    image=flux_image,
    gpu="A10G",
    volumes={MODEL_DIR: model_volume},
    timeout=120,
    container_idle_timeout=60,   # keep warm for 60 s between requests
    secrets=[modal.Secret.from_name("huggingface-secret")],
)
class FluxModel:

    @modal.enter()
    def load_model(self):
        """Called once when the container starts — loads pipeline into GPU VRAM."""
        import torch
        from diffusers import FluxPipeline

        print("Loading FLUX.1-schnell pipeline …")
        self.pipe = FluxPipeline.from_pretrained(
            MODEL_DIR,
            torch_dtype=torch.bfloat16,
        )
        self.pipe.to("cuda")
        print("Pipeline loaded and ready.")

    @modal.web_endpoint(method="POST", label="flux-transform")
    def transform(self, request: dict) -> dict:
        """
        Accepts a JSON body and returns a styled image as base64.

        Supports two modes:
          - txt2img: no image_b64 provided — generates from prompt alone
          - img2img: image_b64 provided — uses image + prompt for style transfer
            (uses FluxImg2ImgPipeline internally)
        """
        import torch
        from PIL import Image
        from diffusers import FluxImg2ImgPipeline

        prompt      = request.get("prompt", "")
        image_b64   = request.get("image_b64")
        steps       = min(max(int(request.get("steps", 4)), 1), 8)
        guidance    = float(request.get("guidance", 0.0))
        width       = int(request.get("width", 1024))
        height      = int(request.get("height", 1024))
        strength    = float(request.get("strength", 0.75))  # img2img only

        if not prompt:
            return {"error": "prompt is required"}, 400

        start = time.perf_counter()
        mode = "txt2img"

        if image_b64:
            # ---- img2img: style-transfer the uploaded image ----
            mode = "img2img"
            img_bytes = base64.b64decode(image_b64)
            source_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            source_image = source_image.resize((width, height))

            img2img_pipe = FluxImg2ImgPipeline(
                **{k: getattr(self.pipe, k) for k in [
                    "scheduler", "vae", "text_encoder", "tokenizer",
                    "text_encoder_2", "tokenizer_2", "transformer",
                ]}
            )
            img2img_pipe.to("cuda")

            result = img2img_pipe(
                prompt=prompt,
                image=source_image,
                strength=strength,
                num_inference_steps=steps,
                guidance_scale=guidance,
                generator=torch.Generator("cuda").manual_seed(0),
            )
        else:
            # ---- txt2img: pure text-to-image generation ----
            result = self.pipe(
                prompt=prompt,
                num_inference_steps=steps,
                guidance_scale=guidance,
                width=width,
                height=height,
                generator=torch.Generator("cuda").manual_seed(0),
                max_sequence_length=256,
            )

        duration = round(time.perf_counter() - start, 2)

        # Encode output image to base64 PNG
        output_image = result.images[0]
        buf = io.BytesIO()
        output_image.save(buf, format="PNG")
        output_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        return {
            "image_b64": output_b64,
            "metadata": {
                "model":            "FLUX.1-schnell",
                "prompt":           prompt,
                "steps":            steps,
                "guidance":         guidance,
                "width":            width,
                "height":           height,
                "strength":         strength if image_b64 else None,
                "mode":             mode,
                "duration_seconds": duration,
            },
        }

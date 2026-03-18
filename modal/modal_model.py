"""
modal_model.py
--------------
Deploys FLUX.1-schnell as a serverless image for image transformation on Modal.

Model weights are downloaded once and stored in a Model Volume.
Prevents cold starts from happening since weights can be reused.

Endpoint: POST /transform
Body (JSON):
  {
    "prompt":     "<Custom prompt>",
    "image_b64":  "<base64-encoded PNG/JPEG>",
    "steps":      4,
    "guidance":   0.0,
    "width":      <img-height>
    "height":     <img-width>
  }

Response (JSON):
  {
    "image_b64":  "<base64-encoded PNG>",
    "metadata": {
      "model":            "FLUX.1-schnell",
      "steps":            4,
      "width":            <img-height>
      "height":           <img-width>
      "mode":             "img2img"
      "duration_seconds": <time-taken-in-seconds>
    }
  }
"""

import io
import time
import base64
import modal

# ==================================================
# IMAGE: Install Python container dependencies
# ==================================================
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

# ==================================================
# VOLUME: Cache model weights to prevent cold start
# ==================================================
model_volume = modal.Volume.from_name("flux-schnell-weights", create_if_missing=True)
MODEL_DIR = "vol/models/flux-schnell"
MODEL_ID = "black-forest-labs/FLUX.1-schnell"

app = modal.App("flux-style-pbn")

# Download the model weights
@app.function(
  image=flux_image,
  volumes={MODEL_DIR: model_volume},
  timeout=900, # 15 mins
  secrets=[modal.Secret.from_name("huggingface-secret")]
)
def download_weights():
  from huggingface_hub import snapshot_download
  import os
  print(f"Downloading {MODEL_ID} -> {MODEL_DIR}")
  snapshot_download(
    repo_id=MODEL_ID,
    local_dir=MODEL_DIR,
    token=os.environ.get("HF_TOKEN")
  )
  model_volume.commit()
  print("Download complete.")

# ==================================================
# INFERENCE: Runs model on A10 GPU (24GB VRAM)
# ==================================================
@
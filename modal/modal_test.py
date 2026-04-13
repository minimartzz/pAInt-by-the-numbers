import requests, base64
from PIL import Image
import io

ENDPOINT = "https://minimartzz--flux-transform.modal.run"

resp = requests.post(ENDPOINT, json={
  "prompt": "Van Gogh oil painting, swirling brushstrokes, vivid blues and yellows",
  "steps": 4,
  "width": 1024,
  "height": 1024,
})

data = resp.json()
img = Image.open(io.BytesIO(base64.b64decode(data["image_b64"])))
img.save("output.png")
print(data["metadata"])
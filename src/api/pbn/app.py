from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl, Field
from utils import (
  load_image,
  upload_image,
  superpixel_segmentation,
  get_colours,
  create_canvas
)

app = FastAPI(title="Paint-by-Numbers API")

# ==================== CORS Setup ====================
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_methods=["*"],
  allow_headers=["*"]
)

# ==================== Request Schema ====================
class PBNRequest(BaseModel):
  image_url: HttpUrl
  filename: str
  k_colours: int = Field(default=10, ge=4, le=50) # Minimum 4, Max 50
  # Image loading
  encoding: str = Field(default="BGR")
  # Superpixel segmentation
  n_segments: int = Field(default=200)
  compactness: int = Field(default=10)
  sigma: int = Field(default=1)
  # Canvas creation
  min_area_ratio: float = Field(default=0.0005)


# ==================== Default Response Formats ====================
def failed_response(message: str, status_code: int = 500):
  return JSONResponse(
    status_code=status_code,
    content={
      "status": "failed",
      "message": message
    }
  )


# ==================== API Server ====================
@app.post("/process-default")
async def process_default(request: PBNRequest):
  try:
    # Load the image
    image = load_image(request.image_url, request.encoding)
    if image is None:
      return failed_response(
        message="Failed to load image from URL",
        status_code=404
      )
    
    # Superpixel segmentation
    try:
      superpixel_img = superpixel_segmentation(
        img=image,
        n_segments=request.n_segments,
        compactness=request.compactness,
        sigma=request.sigma
      )
    except Exception as e:
      return failed_response(
        message=f"Failed to simplify image: {str(e)}",
        status_code=500
      )
    
    # K-Means colours
    try:
      new_img, colour_names, rgb_values, labels = get_colours(
        img=superpixel_img,
        n_clusters=request.k_colours
      )
    except Exception as e:
      return failed_response(
        message=f"Failed to extract colours: {str(e)}",
        status_code=500
      )

    # Create the PBN canvas
    try:
      canvas = create_canvas(
        img=superpixel_img,
        labels=labels,
        n_clusters=request.k_colours,
        min_area_ratio=request.min_area_ratio
      )
    except Exception as e:
      return failed_response(
        message=f"Failed to create PBN canvas: {str(e)}",
        status_code=500
      )

    # Upload both processed image and PBN canvas back to store
    try:
      res_new_img, new_img_src_url = upload_image(
        img=new_img,
        filename=request.filename,
        type="NEW"
      )
      res_canvas, canvas_src_url = upload_image(
        img=canvas,
        filename=request.filename,
        type="PBN"
      )
    except Exception as e:
      return failed_response(
        message=f"Failed to upload images: {str(e)}",
        status_code=500
      )
    
    # Successful response
    return {
      "status": "success",
      "message": "Successfully processed image! 🥳",
      "data": {
        "new_img_url": new_img_src_url,
        "pbn_url": canvas_src_url,
        "colour_names": colour_names,
        "rgb_values": rgb_values
      }
    }
  except Exception as e:
    return failed_response(
      message=f"An unexpected system error occurred: {str(e)}",
      status_code=500
    )

if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port=1000)
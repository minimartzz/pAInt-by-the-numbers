"""
Function calls for image processing
"""
import os
import cv2
import numpy as np
import colornames
import requests
import secrets
import cloudinary
import cloudinary.uploader

from dotenv import load_dotenv
from cloudinary import CloudinaryImage
from sklearn.cluster import KMeans
from skimage.segmentation import slic
from skimage.color import label2rgb

load_dotenv()

# ==================== Cloudinary Functions ====================
cloudinary.config(
  cloud_name = os.getenv('CLOUDINARY_CLOUD'),
  api_key = os.getenv('CLOUDINARY_API_KEY'),
  api_secret = os.getenv('CLOUDINARY_SECRET_KEY'),
  secure = True
)

def load_image(url: str, encoding: str="BGR") -> np.array:
  """
  Retrieves the image from a Cloudinary store based on URL

  Args:
    url (str): Cloudinary URL
    encoding (str, optional): "RGB" or "BGR" depending on colour encoding. Defaults to "BGR".

  Returns:
    np.array: Loaded image to process
  """
  response = requests.get(url)

  if response.status_code == 200:
    image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if encoding == "RGB":
      image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    return image
  else:
    print(f"Failed to retrieve iamge. Status code: {response.status_code}")
    return None

def upload_image(img: np.array, filename: str, type: str):
  token = secrets.token_hex(8)
  name = f"{filename}_{token}_{type}"

  # Encode image into memory buffer
  success, buffer = cv2.imencode('.png', img)
  if not success:
    print("Could not encode image")
    return None
  
  image_bytes = buffer.tobytes()

  # Upload to Cloudinary
  response = cloudinary.uploader.upload(
    image_bytes,
    public_id=name,
    overwrite=True,
    resource_type="image"
  )
  src_url = CloudinaryImage(name).build_url()

  return response, src_url


# ==================== Image Processing Functions ====================
def superpixel_segmentation(
  img: np.array,
  n_segments: int = 200,
  compactness: int = 10,
  sigma: int = 1
) -> np.array:
  """
  Simplifies a loaded image using superpixel segmentation method

  Args:
    img (np.array): Loaded image to process
    n_segments (int, optional): Number of segments to produce. Defaults to 200.
    compactness (int, optional): Defines how close segments are. Defaults to 10.
    sigma (int, optional): Difference. Defaults to 1.

  Returns:
    np.array: Processed image
  """
  height, width, _ = img.shape
  segments = slic(
    img,
    n_segments=n_segments,
    compactness=compactness,
    sigma=sigma,
    start_label=1
  )

  superpixel_img = label2rgb(
    segments,
    img,
    kind='avg'
  )

  return superpixel_img


def get_colours(
  img: np.array,
  n_clusters: int = 10
) -> (np.array, dict, dict, np.array):
  """
  Runs KMeans algorithm to get the colours used to recreate the original image

  Args:
    img (np.array): Image to process
    n_clusters (int, optional): Number of colours used to recreate the image. Defaults to 10.

  Returns:
    np.array: Processed image
    dict: idx: Colour name. Dictionary of indices, corresponding colour name
    dict: idx: RGB values. Dictionary of indices, corresponding RGB values
    labels: Assigned cluster center by index
  """
  height, width, _ = img.shape
  pixel_list = img.reshape((img.shape[0] * img.shape[1], 3))

  clt = KMeans(n_clusters=n_clusters, n_init="auto")
  clt.fit(pixel_list)

  # Extract colours
  d_colours = clt.cluster_centers_.astype('uint8') # Cluster centers - RGB values
  labels = clt.labels_ # Assigned cluster center by index
  new_img = d_colours[labels] # Extracted colours

  # Reshape back to original image
  new_img = new_img.reshape((height, width, 3))

  # Get the colour names
  d_colours_l = d_colours.tolist()
  colour_names = {}
  rgb_values = {}
  for i, colour in enumerate(d_colours_l):
    colour_names[i+1] = colornames.find(colour[0], colour[1], colour[2])
    rgb_values[i+1] = colour

  return new_img, colour_names, rgb_values, labels


def create_canvas(
  img: np.array,
  labels: np.array,
  n_clusters: int = 10,
  min_area_ratio: float = 0.0005,
) -> np.array:
  """
  Transforms the processed image into the PBN canvas

  Args:
    img (np.array): A loaded image
    labels (np.array): The cluster labels for each pixel in the image
    n_clusters (int, optional): Number of colours used to recreate the image. Defaults to 10.
    min_area_ratio (float, optional): Minimum size of an area in the image to be considered a colour in the canvas. Defaults to 0.0005.

  Returns:
    np.array: PBN canvas
  """
  height, width, _ = img.shape

  # Define scales for text details
  scale = max(height, width) / 1000.0
  font_scale = 0.6 * scale
  font_thickness = max(1, int(1 * scale))
  contour_thickness = max(1, int(1 * scale))

  # Define the minimum threshold for colour areas
  # keeps only those areas which are `min_area_ratio`% of the entire image size
  min_area_threshold = int((height * width) * min_area_ratio)

  # PBN canvas
  labels_grid = labels.reshape((height, width))
  canvas = np.ones((height, width, 3), dtype='uint8') * 255
  label_position_mask = np.zeros((height, width), dtype='uint8')

  for colour_id in range(n_clusters):
    # Binary mask - 255 if matches, 0 if not
    mask = np.where(labels_grid == colour_id, 255, 0).astype('uint8')

    # Find the contours
    contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
      if cv2.contourArea(contour) > min_area_threshold:
        # Draw the contours on the canvas
        cv2.drawContours(canvas, [contour], -1, (150, 150, 150), contour_thickness)

        # Try the center region for each cluster for each colour
        M = cv2.moments(contour)
        if M["m00"] != 0:
          center_X = int(M["m10"] / M["m00"])
          center_Y = int(M["m01"] / M["m00"])
        else:
          center_X, center_Y = contour[0][0]

        # Check if point is within the contour
        # dist >0: inside, <0: outside, =0: on edge
        # if outside, find distance that is furthest from all contour boundaries
        if cv2.pointPolygonTest(contour, pt=(center_X, center_Y), measureDist=False) < 0:
          dist_mask = np.zeros((height, width), dtype='uint8')
          cv2.drawContours(dist_mask, [contour], -1, 255, -1)
          dist_transform = cv2.distanceTransform(
            dist_mask,
            distanceType=cv2.DIST_L2,
            maskSize=3
          )
          _, _, _, max_loc = cv2.minMaxLoc(dist_transform)
          center_X, center_Y = max_loc
        
        # Text settings
        current_font_scale = font_scale
        placed = False

        # trying 3 sizes of fonts scaled accordingly
        for s in [1.0, 0.7, 0.4]:
          temp_scale = current_font_scale * s
          text = str(colour_id+1)
          (text_width, text_height), _ = cv2.getTextSize(
            text,
            fontFace=cv2.FONT_HERSHEY_SIMPLEX,
            fontScale=temp_scale,
            thickness=font_thickness
          )

          text_x, text_y = center_X - (text_width // 2), center_Y + (text_height // 2)

          # boundary check
          if text_x < 0 or text_x + text_width >= width or text_y - text_height < 0 or text_y >= height:
            continue
          
          # overlap check
          roi = label_position_mask[text_y-text_height:text_y, text_x:text_x+text_height]
          if np.any(roi):
            continue

          # containment check
          corners = [(text_x, text_y), (text_x+text_width, text_y), (text_x, text_y-text_height), (text_x+text_width, text_y-text_height)]
          if all(cv2.pointPolygonTest(contour, pt, False) >= 0 for pt in corners):
            cv2.putText(
              canvas,
              text=text,
              org=(text_x, text_y),
              fontFace=cv2.FONT_HERSHEY_SIMPLEX,
              fontScale=temp_scale,
              color=(0, 0, 0),
              thickness=font_thickness
            )
            label_position_mask[text_y-text_height:text_y, text_x:text_x+text_width] = 255
            placed = True
            break
        
        # If still not placed, force into best spot with smallest font
        if not placed:
          small_scale = current_font_scale * 0.3
          cv2.putText(
            canvas,
            text=str(colour_id+1),
            org=(center_X, center_Y),
            fontFace=cv2.FONT_HERSHEY_SIMPLEX,
            fontScale=small_scale,
            color=(50, 50, 50),
            thickness=1
          )

  return canvas
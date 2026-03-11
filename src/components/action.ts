"use server";

import { v2 as cloudinary } from "cloudinary";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

// Configure Cloudinary
cloudinary.config({
  cloud_name: process.env.CLOUDINARY_CLOUD,
  api_key: process.env.CLOUDINARY_API_KEY,
  api_secret: process.env.CLOUDINARY_SECRET_KEY,
  secure: true,
});

export async function uploadImageAction(formData: FormData) {
  const file = formData.get("image") as File;

  if (!file) {
    throw new Error("No file provided");
  }

  // Convert file to buffer
  const arrayBuffer = await file.arrayBuffer();
  const buffer = Buffer.from(arrayBuffer);

  // Upload to Cloudinary
  return new Promise<{ url: string }>((resolve, reject) => {
    cloudinary.uploader
      .upload_stream({ folder: "pbn-uploads" }, (error, result) => {
        if (error) {
          reject(error);
          return;
        }
        resolve({ url: result!.secure_url });
      })
      .end(buffer);
  });
}

export async function generateDefault(formData: FormData) {
  const payload = {
    k_colours: parseInt(formData.get("k_colours") as string),
    encoding: formData.get("encoding"),
    filename: formData.get("filename"),
    image_url: formData.get("imageUrl"),
    n_segments: parseInt(formData.get("segments") as string),
    compactness: parseInt(formData.get("compactness") as string),
    sigma: parseInt(formData.get("sigma") as string),
    min_area_ratio: parseFloat(formData.get("min_area") as string),
  };

  // TODO: Change this in Prod
  const response = await fetch("http://localhost:1000/process-default", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) throw new Error("process-default API request failed");

  const data = await response.json();

  // Store in cookies before redirecting (include original image URL for results page)
  const cookieData = { ...data, original_image_url: payload.image_url };
  (await cookies()).set("api_response", JSON.stringify(cookieData), {
    httpOnly: true,
    maxAge: 60,
    path: "/",
  });

  redirect("/results");
}

"use server";

import { v2 as cloudinary } from "cloudinary";

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

"use client";
import { uploadImageAction } from "@/components/action";
import { Button } from "@/components/ui/button";
import { Loader2, UploadCloud, X } from "lucide-react";
import Image from "next/image";
import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { toast } from "sonner";

interface ImageDropzoneProps {
  setUploadedImageUrl: React.Dispatch<React.SetStateAction<string | null>>;
}

const ImageDropzone = ({ setUploadedImageUrl }: ImageDropzoneProps) => {
  const [preview, setPreview] = useState<string | null>(null);
  const [status, setStatus] = useState<
    "idle" | "uploading" | "success" | "error"
  >("idle");
  const [progress, setProgress] = useState(0);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    // Set preview
    setPreview(URL.createObjectURL(file));
    setStatus("uploading");

    // Upload
    startUpload(file);
  }, []);

  // react-dropzone controls
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [] },
    maxFiles: 1,
    multiple: false,
    disabled: status === "uploading",
  });

  const startUpload = async (file: File) => {
    const formData = new FormData();
    formData.append("image", file);

    // Fake progress bar (server actions don't stream progress)
    setProgress(0);
    const interval = setInterval(() => {
      setProgress((prev) => (prev >= 90 ? prev : prev + 10));
    }, 200);

    try {
      const result = await uploadImageAction(formData);
      clearInterval(interval);
      setProgress(100);
      setPreview(result.url);
      setUploadedImageUrl(result.url);
      setStatus("success");
      toast.success("Image uploaded successfully!");
    } catch (error) {
      console.error("Failed to upload image:", error);
      clearInterval(interval);
      setUploadedImageUrl(null);
      setStatus("error");
      toast.error("Failed to upload image. Please try again.");
    }
  };

  const removeImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    setPreview(null);
    setUploadedImageUrl(null);
    setStatus("idle");
    setProgress(0);
  };

  return (
    <div className="w-full mt-10 p-8 bg-accent-main rounded-2xl">
      {status !== "success" ? (
        // Standard view
        <div
          {...getRootProps({ className: "dropzone" })}
          className={`flex-centered flex-col w-full h-100 rounded-2xl border-3 border-dashed
          transition-all duration-300 cursor-pointer
          bg-accent-soft border-gray-500
          ${isDragActive ? "scale-[1.02] shadow-xl ring-3 ring-gray-500 border-none" : "hover:border-gray-400 hover:border-dashed"}`}
        >
          <input {...getInputProps()} />

          {status === "idle" ? (
            <div className="flex flex-col items-center space-y-4 text-center p-4">
              <div className="p-4 rounded-full bg-background shadow-sm text-foreground">
                <UploadCloud size={32} />
              </div>
              <div className="space-y-1">
                <p className="text-lg font-medium text-foreground">
                  {isDragActive
                    ? "Drop your image here"
                    : "Click or drage image to upload"}
                </p>
                <p className="text-sm text-gray-500">JPG, PNG (Max 10MB)</p>
              </div>
              <Button
                type="button"
                className="bg-orange-400 text-foreground hover:bg-orange-500"
              >
                Select File
              </Button>
            </div>
          ) : (
            // Image is uploading
            <div className="flex flex-col items-center space-y-4 w-full max-w-xs">
              <div className="relative w-16 h-16 rounded-lg overflow-hidden shadow-md">
                {preview && (
                  <Image
                    src={preview}
                    alt="Uploaded image"
                    layout="fill"
                    className="opacity-50"
                  />
                )}
                <div className="absolute inset-0 flex items-center justify-center">
                  <Loader2
                    className={`animate-spin text-accent-main`}
                    size={24}
                  />
                </div>
              </div>
              <div className="w-full space-y-2">
                <div className="flex justify-between text-sm font-medium text-gray-500">
                  <span>Uploading...</span>
                  <span>{progress}%</span>
                </div>
                <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 bg-orange-400`}
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        // Successful upload
        <div className="relative w-full aspect-video rounded-2xl overflow-hidden shadow-lg border border-gray-200 bg-white group animate-in fade-in zoom-in duration-300">
          <Image
            src={preview!}
            alt="Uploaded image"
            className="object-contain"
            fill
          />

          <div className="absolute top-4 right-4">
            <Button type="button" onClick={removeImage} title="Remove image">
              <X size={20} />
            </Button>
          </div>
        </div>
      )}

      {status === "error" && (
        <p className="mt-4 text-center text-destructive text-sm">
          Upload failed. Please try again.
        </p>
      )}
    </div>
  );
};

export default ImageDropzone;

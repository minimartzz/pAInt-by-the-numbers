"use client";
import ImageDropzone from "@/components/ImageDropzone";
import PBNConfiguration from "@/components/PBNConfiguration";
import { Button } from "@/components/ui/button";
import { Loader2 } from "lucide-react";
import Form from "next/form";
import { useActionState, useState } from "react";
import { toast } from "sonner";

const PBNForm = () => {
  const [uploadedImageUrl, setUploadedImageUrl] = useState<string | null>(null);

  const handleSubmit = async (prevState: any, formData: FormData) => {
    // TODO: OpenAI handling to trigger different API
    try {
      // Append the uploaded image
      if (!uploadedImageUrl) {
        toast.error("Please upload an image first.");
        return;
      }
      formData.append("imageUrl", uploadedImageUrl);

      if (!("segments" in formData)) {
        formData.append("segments", "200");
        formData.append("compactness", "10");
        formData.append("sigma", "1");
        formData.append("min_area", "0.0001");
      }

      console.log(formData);
      return { success: true, message: "Success" };
    } catch (error) {
      return { success: false, message: "Error" };
    }
  };

  const [state, formAction, isPending] = useActionState(handleSubmit, {
    success: false,
    message: "Error",
  });

  return (
    <Form action={formAction} className="w-full">
      {/* Configurations */}
      <PBNConfiguration />

      {/* Image Dropzone Component */}
      <ImageDropzone setUploadedImageUrl={setUploadedImageUrl} />

      {/* Submit Button */}
      <Button
        type="submit"
        disabled={isPending}
        className="w-full flex-centered gap-2 mt-8 bg-orange-400 hover:bg-accent-main hover:cursor-pointer"
      >
        {isPending ? (
          <div>
            <Loader2 className="animate-spin" size={18} />
            Generating Canvas...
          </div>
        ) : (
          <p className="font-semibold textlg">"🖼️ Generate Your Canvas"</p>
        )}
      </Button>
    </Form>
  );
};

export default PBNForm;

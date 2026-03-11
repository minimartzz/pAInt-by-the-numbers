import ResultsClient from "@/components/results/ResultsClient";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const Page = async () => {
  const cookieStore = await cookies();
  const raw = cookieStore.get("api_response")?.value;

  if (!raw) redirect("/");

  const parsed = JSON.parse(raw);

  // Validate we have the minimum required fields
  if (!parsed.data || !parsed.original_image_url) redirect("/");

  return (
    <ResultsClient
      originalImageUrl={parsed.original_image_url}
      data={parsed.data}
    />
  );
};

export default Page;

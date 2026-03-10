import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const Page = async () => {
  const cookieStore = await cookies();
  const raw = cookieStore.get("api_response")?.value;

  if (!raw) redirect("/");

  const data = JSON.parse(raw);

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-4">Results</h1>
      <pre className="bg-gray-100 rounded p-4 text-sm">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
};

export default Page;

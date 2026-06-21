import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { toast, Toaster } from "sonner";
import { getBlueprints, createBlueprint } from "@/api/blueprints";
import GenerateButton from "@/components/GenerateButton";
import ProgressBar from "@/components/ProgressBar";
import DownloadPanel from "@/components/DownloadPanel";

export default function App() {
  const [progress, setProgress] = useState(0);

  // Performance: Fetches data and caches it
  const {
    data: blueprints,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["blueprints"],
    queryFn: async () => {
      const res = await getBlueprints();
      // SECURITY & UX: Ensure we always return an array, even if API gives weird data
      if (Array.isArray(res.data)) return res.data;
      // If your API returns { data: { blueprints: [...] } }, adjust this accordingly
      if (res.data?.data && Array.isArray(res.data.data)) return res.data.data;

      console.warn("API did not return an array. Received:", res.data);
      return [];
    },
  });

  // UX: Handle blueprint creation
  const mutation = useMutation({
    mutationFn: (newData) => createBlueprint(newData),
    onSuccess: () => {
      toast.success("Blueprint created successfully!");
      setProgress(100);
    },
    onError: () => {
      toast.error("Failed to create blueprint.");
    },
  });

  const handleGenerate = () => {
    setProgress(0);
    const interval = setInterval(() => {
      setProgress((prev) => (prev < 90 ? prev + 10 : prev));
    }, 200);

    mutation.mutate(
      { name: "New Custom Blueprint" },
      {
        onSettled: () => clearInterval(interval),
      },
    );
  };

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8 text-gray-900">
        Blueprint Manager
      </h1>

      <div className="mb-8">
        <GenerateButton
          onClick={handleGenerate}
          isLoading={mutation.isPending}
        />
        {mutation.isPending && (
          <div className="mt-4">
            <ProgressBar progress={progress} />
          </div>
        )}
      </div>

      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-gray-700">Your Blueprints</h2>

        {/* UX: Handle Loading State */}
        {isLoading && <p className="text-gray-500">Loading blueprints...</p>}

        {/* UX: Handle Error State gracefully without crashing the app */}
        {isError && (
          <div className="p-4 bg-red-50 text-red-700 rounded-lg border border-red-200">
            <p className="font-medium">Failed to load blueprints.</p>
            <p className="text-sm mt-1">
              Make sure your backend is running on the correct port.
            </p>
          </div>
        )}

        {/* SECURITY/UX: Safely map only if blueprints is a valid array */}
        {!isLoading &&
        !isError &&
        Array.isArray(blueprints) &&
        blueprints.length > 0
          ? blueprints.map((bp, idx) => (
              <DownloadPanel key={bp.id || idx} blueprint={bp} />
            ))
          : !isLoading &&
            !isError && (
              <p className="text-gray-500">
                No blueprints found. Generate one!
              </p>
            )}
      </div>

      <Toaster richColors position="bottom-right" />
    </div>
  );
}

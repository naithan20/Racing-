import { getKaggleConnectionStatus } from "@/data/dataSources";
import { KaggleConnectionCard } from "@/components/settings/KaggleConnectionCard";

// See src/app/data-explorer/page.tsx for why this is forced dynamic.
export const dynamic = "force-dynamic";

export default async function DataConnectionsPage() {
  const kaggle = await getKaggleConnectionStatus();

  return (
    <div className="mx-auto max-w-[800px] space-y-6 px-4 py-6 sm:px-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Data connections</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Connect accounts once here, then use them from{" "}
          <a href="/data-sources" className="text-accent hover:underline">
            Data sources
          </a>
          . Connection status is shown here; stored credentials themselves are never displayed.
        </p>
      </div>

      <KaggleConnectionCard connected={kaggle.connected} connectedAt={kaggle.connectedAt} />
    </div>
  );
}

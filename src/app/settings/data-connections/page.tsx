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
        <p className="mt-2 text-xs text-text-muted">
          This is an advanced, optional step — the one-tap free setup on{" "}
          <a href="/data-sources" className="text-accent hover:underline">
            Data sources
          </a>{" "}
          tries Kaggle&apos;s public download anonymously first and only needs this if that&apos;s rejected. The
          form below writes to a local file and only works in local development. On a deployment (Vercel), set
          <code className="mx-1 rounded bg-bg-elevated px-1 py-0.5">KAGGLE_USERNAME</code> and
          <code className="mx-1 rounded bg-bg-elevated px-1 py-0.5">KAGGLE_KEY</code> as environment variables
          instead, the same way <code className="rounded bg-bg-elevated px-1 py-0.5">DATABASE_URL</code> is
          configured — RacingEdge never stores credentials in the database.
        </p>
      </div>

      <KaggleConnectionCard connected={kaggle.connected} connectedAt={kaggle.connectedAt} />
    </div>
  );
}

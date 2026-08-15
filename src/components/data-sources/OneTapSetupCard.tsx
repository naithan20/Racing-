"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { startOneTapImportAction } from "@/actions/serverlessImport";
import type { DataSourceCard as DataSourceCardData } from "@/data/dataSources";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

/**
 * The primary onboarding path (requirement: "tap Add Free Historical Data,
 * select a predefined dataset, let RacingEdge handle the rest"). Runs
 * entirely server-side through the serverless pipeline (src/lib/serverlessImport/)
 * — no Kaggle account, no terminal, no file downloaded to the user's
 * phone. Kaggle's advanced/optional credential connection (Settings ->
 * Data Connections) stays a fallback for if the anonymous attempt is
 * rejected, never a precondition shown here.
 */
export function OneTapSetupCard({ card }: { card: DataSourceCardData }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { source } = card;
  const alreadyImported = card.lastSyncAt !== null;
  const jobInProgress = card.activeJobId !== null;

  async function handleClick() {
    setPending(true);
    setError(null);
    const result = await startOneTapImportAction({ sourceId: source.id, provenanceStatus: "COMMUNITY_UNVERIFIED" });
    setPending(false);
    if (result.ok && result.jobId) {
      router.push(`/data-sources/jobs/${result.jobId}`);
    } else {
      setError(result.message ?? "Could not start setup.");
    }
  }

  return (
    <Card className="border-accent/40">
      <CardHeader className="flex items-start justify-between gap-3">
        <div>
          <CardTitle>Add free historical data</CardTitle>
          <p className="mt-1 text-xs text-text-secondary">
            One tap, runs entirely on the server — no Kaggle account, no terminal, nothing downloaded to your
            phone. RacingEdge downloads, reads, maps columns automatically, and imports {source.name}.
          </p>
        </div>
        <Badge tone="positive">FREE</Badge>
      </CardHeader>
      <CardBody className="flex flex-col gap-3">
        <div className="rounded-md border border-border-subtle bg-bg-elevated p-3">
          <p className="text-sm font-medium text-text-primary">{source.name}</p>
          <p className="mt-1 text-xs text-text-secondary">{source.description}</p>
          <p className="mt-2 text-xs text-text-muted">
            Coverage: {source.regions.join(", ")} · {source.historicalCoverage}
          </p>
        </div>

        {jobInProgress ? (
          <button
            type="button"
            onClick={() => router.push(`/data-sources/jobs/${card.activeJobId}`)}
            className="self-start rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
          >
            View progress ({card.activeJobStatus?.replaceAll("_", " ")})
          </button>
        ) : (
          <button
            type="button"
            onClick={handleClick}
            disabled={pending}
            className="self-start rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {pending ? "Setting up… this can take up to a minute" : alreadyImported ? "Set up again" : "Set up free UK/Ireland racing data"}
          </button>
        )}

        {error && <p className="text-sm text-negative">{error}</p>}

        <p className="text-xs text-text-muted">
          Tries Kaggle&apos;s public dataset download anonymously first. If Kaggle requires authentication for
          this dataset, you&apos;ll see that stated plainly here — connecting Kaggle is an optional advanced
          step (Settings → Data Connections), never required to try this.
        </p>
      </CardBody>
    </Card>
  );
}

"use client";

import { useActionState, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { startImportJobFormAction, disconnectKaggleAction, syncSourceAction } from "@/actions/dataSources";
import { INITIAL_IMPORT_JOB_FORM_STATE } from "@/actions/state";
import type { DataSourceCard as DataSourceCardData } from "@/data/dataSources";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { UrlSourceForm } from "@/components/data-sources/UrlSourceForm";
import { formatDate } from "@/lib/format";

const PROVENANCE_OPTIONS = [
  { value: "VERIFIED_OPEN", label: "Verified open licence" },
  { value: "PUBLIC_RESEARCH", label: "Public / research use" },
  { value: "COMMUNITY_UNVERIFIED", label: "Community — licence not checked" },
  { value: "USER_SUPPLIED", label: "User supplied" },
  { value: "UNKNOWN", label: "Unknown" },
];

const VERIFICATION_TONE: Record<string, "positive" | "warning" | "neutral" | "negative"> = {
  VERIFIED: "positive",
  AVAILABLE_BUT_UNVERIFIED: "warning",
  REQUIRES_CONNECTION: "neutral",
  UNAVAILABLE: "negative",
};

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-text-muted">{label}</p>
      <p className="mt-0.5 text-sm text-text-primary">{value}</p>
    </div>
  );
}

export function SourceCard({ card }: { card: DataSourceCardData }) {
  const { source } = card;
  const [showImportForm, setShowImportForm] = useState(false);
  const [confirmedUrl, setConfirmedUrl] = useState("");
  const [formState, formAction, pending] = useActionState(startImportJobFormAction, INITIAL_IMPORT_JOB_FORM_STATE);

  const isUrlBased = source.downloadMechanism === "USER_URL" || source.downloadMechanism === "DIRECT_DOWNLOAD";
  const canSubmit = !isUrlBased || confirmedUrl !== "";
  const needsConnection = card.connectionStatus === "NOT_CONNECTED" || card.connectionStatus === "ERROR";
  const hasImportedBefore = card.lastSyncAt !== null;
  const jobInProgress = card.activeJobId !== null;

  return (
    <Card>
      <CardHeader className="flex items-start justify-between gap-3">
        <div>
          <CardTitle>{source.name}</CardTitle>
          <p className="mt-1 text-xs text-text-secondary">{source.description}</p>
        </div>
        <Badge tone={VERIFICATION_TONE[source.verificationStatus]}>{source.verificationStatus.replaceAll("_", " ")}</Badge>
      </CardHeader>
      <CardBody className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Field label="Coverage" value={source.regions.join(", ")} />
          <Field label="Historical coverage" value={source.historicalCoverage} />
          <Field label="Cost" value="FREE" />
          <Field label="Auth required" value={source.authMechanism === "none" ? "No" : "Yes"} />
          <Field label="Connection status" value={card.connectionStatus.replaceAll("_", " ")} />
          <Field label="Last sync" value={card.lastSyncAt ? formatDate(card.lastSyncAt) : "Never"} />
        </div>

        {source.expectedFields.length > 0 && (
          <div>
            <p className="text-xs uppercase tracking-wide text-text-muted">Expected fields</p>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {source.expectedFields.map((f) => (
                <Badge key={f} tone="neutral">
                  {f}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {source.note && <p className="rounded-md border border-border-subtle bg-bg-elevated p-2.5 text-xs text-text-secondary">{source.note}</p>}

        {hasImportedBefore && (
          <div className="grid grid-cols-2 gap-3 rounded-md border border-border-subtle bg-bg-elevated p-3 sm:grid-cols-3">
            <Field label="Races imported" value={String(card.racesImported ?? 0)} />
            <Field label="Runners imported" value={String(card.runnersImported ?? 0)} />
            <Field label="Dataset version" value={card.datasetVersionId ? card.datasetVersionId.slice(0, 10) + "…" : "—"} />
          </div>
        )}

        <div className="flex flex-wrap items-center gap-2">
          {jobInProgress ? (
            <Link
              href={`/data-sources/jobs/${card.activeJobId}`}
              className="rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
            >
              View progress ({card.activeJobStatus?.replaceAll("_", " ")})
            </Link>
          ) : (
            <>
              {needsConnection ? (
                <Link
                  href="/settings/data-connections"
                  className="rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
                >
                  Connect
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => setShowImportForm((v) => !v)}
                  className="rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90"
                >
                  Import
                </button>
              )}

              {hasImportedBefore && !needsConnection && (
                <SyncButton sourceId={source.id} />
              )}

              {hasImportedBefore && (
                <Link href="/data-quality" className="rounded-md border border-border px-4 py-1.5 text-sm text-text-secondary hover:bg-bg-hover">
                  View data quality
                </Link>
              )}

              {source.authMechanism === "kaggle" && card.connectionStatus === "CONNECTED" && (
                <button
                  type="button"
                  onClick={() => disconnectKaggleAction()}
                  className="ml-auto rounded-md border border-border px-3 py-1.5 text-xs text-text-muted hover:bg-bg-hover"
                  title="Disconnects the Kaggle account (shared across every Kaggle source)"
                >
                  Disconnect Kaggle
                </button>
              )}
            </>
          )}
        </div>

        {showImportForm && !needsConnection && !jobInProgress && (
          <form action={formAction} className="flex flex-col gap-3 rounded-md border border-border-subtle bg-bg-elevated p-3">
            <input type="hidden" name="sourceId" value={source.id} />

            <label className="flex flex-col gap-1 text-xs text-text-secondary">
              Provenance / licence confidence
              <select
                name="provenanceStatus"
                required
                defaultValue={source.downloadMechanism === "KAGGLE" ? "COMMUNITY_UNVERIFIED" : "UNKNOWN"}
                className="rounded-md border border-border bg-bg-panel px-2 py-1.5 text-sm text-text-primary"
              >
                {PROVENANCE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>

            {source.downloadMechanism === "KAGGLE" && (
              <label className="flex flex-col gap-1 text-xs text-text-secondary">
                Kaggle dataset (owner/dataset-slug)
                <input
                  type="text"
                  name="kaggleDatasetRef"
                  required
                  defaultValue={source.kaggleDatasetRef ?? ""}
                  placeholder="owner/dataset-slug"
                  className="rounded-md border border-border bg-bg-panel px-2 py-1.5 text-sm text-text-primary"
                />
              </label>
            )}

            {isUrlBased && (
              <>
                <UrlSourceForm onConfirmed={setConfirmedUrl} />
                <input type="hidden" name="downloadUrl" value={confirmedUrl} />
              </>
            )}

            {source.downloadMechanism === "LOCAL_FILE" && (
              <label className="flex flex-col gap-1 text-xs text-text-secondary">
                File path (advanced — on the server running RacingEdge)
                <input
                  type="text"
                  name="localFilePath"
                  required
                  placeholder="/path/to/dataset.db"
                  className="rounded-md border border-border bg-bg-panel px-2 py-1.5 text-sm text-text-primary"
                />
              </label>
            )}

            <label className="flex flex-col gap-1 text-xs text-text-secondary">
              Label (optional)
              <input
                type="text"
                name="sourceLabel"
                placeholder={source.name}
                className="rounded-md border border-border bg-bg-panel px-2 py-1.5 text-sm text-text-primary"
              />
            </label>

            {formState.status === "error" && <p className="text-xs text-negative">{formState.message}</p>}

            <button
              type="submit"
              disabled={pending || !canSubmit}
              title={!canSubmit ? "Preview and confirm the URL first" : undefined}
              className="self-start rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {pending ? "Starting…" : "Start import"}
            </button>
          </form>
        )}
      </CardBody>
    </Card>
  );
}

function SyncButton({ sourceId }: { sourceId: string }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  return (
    <div className="flex flex-col gap-1">
      <button
        type="button"
        disabled={pending}
        onClick={async () => {
          setPending(true);
          setError(null);
          const result = await syncSourceAction(sourceId, "COMMUNITY_UNVERIFIED");
          setPending(false);
          if (result.ok && result.jobId) {
            router.push(`/data-sources/jobs/${result.jobId}`);
          } else {
            setError(result.message ?? "Could not start sync.");
          }
        }}
        className="rounded-md border border-border px-4 py-1.5 text-sm text-text-secondary hover:bg-bg-hover disabled:opacity-50"
      >
        {pending ? "Syncing…" : "Sync"}
      </button>
      {error && <p className="text-xs text-negative">{error}</p>}
    </div>
  );
}

"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { trainBaselineModelAction } from "@/actions/model";
import { Badge } from "@/components/ui/Badge";
import { classifyDatasetLevel, datasetLevelLabel } from "@/lib/datasetLevel";
import { formatDate } from "@/lib/format";

type LogEntry = { ts: string; step: string; message: string };

const TERMINAL_STATUSES = new Set(["COMPLETED", "FAILED"]);

export interface JobProgressData {
  id: string;
  status: string;
  progressPercent: number;
  currentStepLabel: string | null;
  errorMessage: string | null;
  racesImported: number | null;
  runnersImported: number | null;
  datasetVersionId: string | null;
  log: LogEntry[];
  completion: {
    coverageStart: string | null;
    coverageEnd: string | null;
    completenessScore: number | null;
    leakageAuditStatus: "PASSED" | "FAILED" | null;
  } | null;
}

export function JobProgressView({ job }: { job: JobProgressData }) {
  const router = useRouter();
  const isActive = !TERMINAL_STATUSES.has(job.status);

  useEffect(() => {
    if (!isActive) return;
    const interval = setInterval(() => router.refresh(), 2000);
    return () => clearInterval(interval);
  }, [isActive, router]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Badge tone={job.status === "COMPLETED" ? "positive" : job.status === "FAILED" ? "negative" : "accent"}>
          {job.status.replaceAll("_", " ")}
        </Badge>
        {job.currentStepLabel && <span className="text-sm text-text-secondary">{job.currentStepLabel}</span>}
      </div>

      <div className="h-2 w-full overflow-hidden rounded-full bg-bg-elevated">
        <div
          className="h-full rounded-full bg-accent transition-[width]"
          style={{ width: `${Math.max(job.progressPercent, isActive ? 4 : job.progressPercent)}%` }}
        />
      </div>

      {job.status === "FAILED" && job.errorMessage && (
        <div className="rounded-md border border-negative/40 bg-negative-soft p-3 text-sm text-negative">{job.errorMessage}</div>
      )}

      {job.status === "COMPLETED" && <CompletedSummary job={job} />}

      <div className="rounded-md border border-border-subtle">
        <div className="border-b border-border-subtle bg-bg-elevated px-3 py-2 text-xs font-medium uppercase tracking-wide text-text-muted">
          Progress log
        </div>
        <ul className="max-h-80 overflow-y-auto divide-y divide-border-subtle/60">
          {job.log.length === 0 && <li className="px-3 py-2 text-sm text-text-muted">No log entries yet.</li>}
          {job.log
            .slice()
            .reverse()
            .map((entry, i) => (
              <li key={i} className="px-3 py-2 text-sm">
                <span className="text-xs text-text-muted">{new Date(entry.ts).toLocaleTimeString()}</span>{" "}
                <span className="font-mono text-xs text-accent">{entry.step}</span>
                <p className="mt-0.5 text-text-secondary">{entry.message}</p>
              </li>
            ))}
        </ul>
      </div>
    </div>
  );
}

function CompletedSummary({ job }: { job: JobProgressData }) {
  const [pending, startTransition] = useTransition();
  const [message, setMessage] = useState<string | null>(null);
  const level = classifyDatasetLevel(job.runnersImported ?? 0);
  const coverage =
    job.completion?.coverageStart && job.completion?.coverageEnd
      ? `${formatDate(job.completion.coverageStart)} – ${formatDate(job.completion.coverageEnd)}`
      : "—";

  return (
    <div className="space-y-3 rounded-md border border-positive/40 bg-positive-soft p-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Stat label="Races imported" value={String(job.racesImported ?? 0)} />
        <Stat label="Runners imported" value={String(job.runnersImported ?? 0)} />
        <Stat label="Coverage" value={coverage} />
        <Stat label="Data completeness score" value={job.completion?.completenessScore != null ? `${job.completion.completenessScore}%` : "—"} />
        <Stat label="Leakage audit" value={job.completion?.leakageAuditStatus ?? "—"} />
        <Stat label="Dataset level" value={datasetLevelLabel(level)} />
      </div>
      <div className="flex items-center gap-3">
        <button
          type="button"
          disabled={pending}
          onClick={() =>
            startTransition(async () => {
              const result = await trainBaselineModelAction();
              setMessage(result.message);
            })
          }
          className="rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {pending ? "Starting…" : "Train Baseline Model"}
        </button>
        {message && <span className="text-xs text-text-secondary">{message}</span>}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-text-muted">{label}</p>
      <p className="mt-0.5 font-tabular text-lg text-text-primary">{value}</p>
    </div>
  );
}

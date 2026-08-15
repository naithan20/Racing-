"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";

import { confirmMappingAction, type MappingUpdate } from "@/actions/dataSources";
import { confirmOneTapMappingAction } from "@/actions/serverlessImport";
import type { MappingReviewColumn } from "@/data/dataSources";

export function MappingReviewForm({
  jobId,
  columns,
  autoMappedCount,
  canonicalRoles,
  serverless = false,
}: {
  jobId: string;
  columns: MappingReviewColumn[];
  autoMappedCount: number;
  canonicalRoles: readonly string[];
  /** SERVERLESS_NODE jobs confirm through confirmOneTapMappingAction (re-downloads + re-parses in-request) instead of confirmMappingAction (patches a file for the detached Python subprocess to pick up). */
  serverless?: boolean;
}) {
  const router = useRouter();
  const [selections, setSelections] = useState<Record<string, string>>(() =>
    Object.fromEntries(columns.map((c) => [`${c.table}.${c.column}`, c.proposedRole ?? ""]))
  );
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const totalFields = autoMappedCount + columns.length;

  function handleSubmit() {
    setError(null);
    const updates: Record<string, MappingUpdate> = {};
    for (const col of columns) {
      const key = `${col.table}.${col.column}`;
      const role = selections[key];
      updates[key] = { role: role === "" ? null : role, confirmed: role !== "" };
    }
    startTransition(async () => {
      const result = serverless ? await confirmOneTapMappingAction(jobId, updates) : await confirmMappingAction(jobId, updates);
      if (result.ok) {
        router.push(`/data-sources/jobs/${jobId}`);
        router.refresh();
      } else {
        setError(result.message ?? "Could not confirm the mapping.");
      }
    });
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-text-secondary">
        {autoMappedCount} field{autoMappedCount === 1 ? "" : "s"} mapped automatically. {columns.length} field
        {columns.length === 1 ? "" : "s"} of {totalFields} need confirmation before importing.
      </p>

      <div className="overflow-x-auto rounded-md border border-border-subtle">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-border-subtle bg-bg-elevated text-left text-xs uppercase tracking-wide text-text-muted">
              <th className="px-3 py-2 font-medium">External field</th>
              <th className="px-3 py-2 font-medium">Example values</th>
              <th className="px-3 py-2 font-medium">Confidence</th>
              <th className="px-3 py-2 font-medium">RacingEdge field</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((col) => {
              const key = `${col.table}.${col.column}`;
              return (
                <tr key={key} className="border-b border-border-subtle last:border-b-0">
                  <td className="px-3 py-2 font-mono text-xs text-text-primary">
                    {col.table}.{col.column}
                  </td>
                  <td className="px-3 py-2 text-xs text-text-muted">{col.sampleValues.join(", ") || "—"}</td>
                  <td className="px-3 py-2 text-xs text-text-muted">{col.confidence.toUpperCase()}</td>
                  <td className="px-3 py-2">
                    <select
                      value={selections[key] ?? ""}
                      onChange={(e) => setSelections((prev) => ({ ...prev, [key]: e.target.value }))}
                      className="rounded-md border border-border bg-bg-panel px-2 py-1 text-sm text-text-primary"
                    >
                      <option value="">(leave unmapped)</option>
                      {canonicalRoles.map((role) => (
                        <option key={role} value={role}>
                          {role.replaceAll("_", " ")}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {error && <p className="text-sm text-negative">{error}</p>}

      <button
        type="button"
        onClick={handleSubmit}
        disabled={pending}
        className="rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {pending ? "Confirming…" : "Confirm mapping and continue import"}
      </button>
    </div>
  );
}

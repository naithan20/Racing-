"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { formatDecimalOdds, formatNumber, formatPercent } from "@/lib/format";
import { ConfidenceBadge, ValueEdgeBadge } from "@/components/ui/Badge";
import { NotConfigured } from "@/components/ui/NotConfigured";
import type { EvidenceDensityLabel } from "@/generated/prisma/enums";

export interface RunnerRow {
  runnerId: string;
  horseName: string;
  clothNumber: number | null;
  headgear: string | null;
  nonRunner: boolean;
  oddsDecimal: number | null;
  oddsFractional: string | null;
  winProbability: number | null;
  placeProbability: number | null;
  placeBasisPlaces: number | null;
  confidence: number | null;
  fairOddsDecimal: number | null;
  valueEdge: number | null;
  officialRating: number | null;
  weightLbs: number | null;
  draw: number | null;
  form: string;
  paceStyle: string;
  transitionScore: number | null;
  lateSustainability: number | null;
  evidenceDensity: number | null;
  evidenceLabel: EvidenceDensityLabel | null;
}

type SortKey = keyof Pick<
  RunnerRow,
  | "horseName"
  | "oddsDecimal"
  | "winProbability"
  | "placeProbability"
  | "confidence"
  | "fairOddsDecimal"
  | "valueEdge"
  | "officialRating"
  | "weightLbs"
  | "draw"
  | "evidenceDensity"
>;

const COLUMNS: { key: SortKey; label: string }[] = [
  { key: "horseName", label: "Horse" },
  { key: "oddsDecimal", label: "Odds" },
  { key: "winProbability", label: "Win %" },
  { key: "placeProbability", label: "Place %" },
  { key: "confidence", label: "Confidence" },
  { key: "fairOddsDecimal", label: "Fair Odds" },
  { key: "oddsDecimal", label: "Market Odds" },
  { key: "valueEdge", label: "Value Edge" },
  { key: "officialRating", label: "OR" },
  { key: "weightLbs", label: "Weight" },
  { key: "draw", label: "Draw" },
  { key: "evidenceDensity", label: "Evidence" },
];

function compareValues(a: string | number | null, b: string | number | null): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  if (typeof a === "string" || typeof b === "string") return String(a).localeCompare(String(b));
  return a - b;
}

export function RunnerTable({ rows }: { rows: RunnerRow[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("oddsDecimal");
  const [sortDir, setSortDir] = useState<1 | -1>(1);

  const sortedRows = useMemo(() => {
    return [...rows].sort((a, b) => compareValues(a[sortKey], b[sortKey]) * sortDir);
  }, [rows, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === 1 ? -1 : 1));
    } else {
      setSortKey(key);
      setSortDir(1);
    }
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full min-w-[1400px] text-sm">
        <thead>
          <tr className="border-b border-border bg-bg-elevated text-left text-xs uppercase tracking-wide text-text-muted">
            {COLUMNS.map((col, i) => (
              <th key={`${col.key}-${i}`} className="whitespace-nowrap px-3 py-2 font-medium">
                <button
                  type="button"
                  onClick={() => toggleSort(col.key)}
                  className="flex items-center gap-1 hover:text-text-secondary"
                >
                  {col.label}
                  {sortKey === col.key && <span>{sortDir === 1 ? "▲" : "▼"}</span>}
                </button>
              </th>
            ))}
            <th className="px-3 py-2 font-medium">Form</th>
            <th className="px-3 py-2 font-medium">Pace Style</th>
            <th className="px-3 py-2 font-medium">Transition</th>
            <th className="px-3 py-2 font-medium">Late Sustain.</th>
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row) => (
            <tr
              key={row.runnerId}
              className="border-b border-border-subtle last:border-b-0 hover:bg-bg-hover"
            >
              <td className="whitespace-nowrap px-3 py-2.5">
                <Link href={`/runners/${row.runnerId}`} className="text-accent hover:underline">
                  {row.clothNumber ? `${row.clothNumber}. ` : ""}
                  {row.horseName}
                </Link>
                {row.headgear && <span className="ml-1 text-xs text-text-muted">({row.headgear})</span>}
                {row.nonRunner && <span className="ml-1 text-xs text-negative">NR</span>}
              </td>
              <td className="whitespace-nowrap px-3 py-2.5 font-tabular text-text-primary">
                {formatDecimalOdds(row.oddsDecimal)}
                {row.oddsFractional && (
                  <span className="ml-1 text-xs text-text-muted">({row.oddsFractional})</span>
                )}
              </td>
              <td className="px-3 py-2.5">
                {row.winProbability !== null ? formatPercent(row.winProbability) : <NotConfigured compact />}
              </td>
              <td className="px-3 py-2.5">
                {row.placeProbability !== null ? (
                  <span title={`Based on top ${row.placeBasisPlaces ?? "?"} places`}>
                    {formatPercent(row.placeProbability)}
                  </span>
                ) : (
                  <NotConfigured compact />
                )}
              </td>
              <td className="px-3 py-2.5">
                <ConfidenceBadge value={row.confidence} />
              </td>
              <td className="px-3 py-2.5 font-tabular">
                {row.fairOddsDecimal !== null ? formatDecimalOdds(row.fairOddsDecimal) : <NotConfigured compact />}
              </td>
              <td className="whitespace-nowrap px-3 py-2.5 font-tabular text-text-secondary">
                {formatDecimalOdds(row.oddsDecimal)}
              </td>
              <td className="px-3 py-2.5">
                <ValueEdgeBadge value={row.valueEdge} />
              </td>
              <td className="px-3 py-2.5 font-tabular text-text-secondary">{row.officialRating ?? "—"}</td>
              <td className="px-3 py-2.5 font-tabular text-text-secondary">
                {row.weightLbs !== null ? `${row.weightLbs}lb` : "—"}
              </td>
              <td className="px-3 py-2.5 font-tabular text-text-secondary">{row.draw ?? "—"}</td>
              <td className="px-3 py-2.5 text-text-secondary">
                {row.evidenceDensity !== null ? (
                  <span title={row.evidenceLabel ?? undefined}>{formatPercent(row.evidenceDensity, 0)}</span>
                ) : (
                  "—"
                )}
              </td>
              <td className="whitespace-nowrap px-3 py-2.5 font-tabular text-text-secondary">{row.form}</td>
              <td className="whitespace-nowrap px-3 py-2.5 text-text-secondary">{row.paceStyle}</td>
              <td className="px-3 py-2.5 font-tabular text-text-secondary">{formatNumber(row.transitionScore, 2)}</td>
              <td className="px-3 py-2.5 font-tabular text-text-secondary">{formatNumber(row.lateSustainability, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

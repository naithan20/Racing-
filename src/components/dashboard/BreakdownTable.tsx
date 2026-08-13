import type { BreakdownBucket } from "@/backtesting/breakdown";
import { formatPercent } from "@/lib/format";

export function BreakdownTable({ title, buckets }: { title: string; buckets: BreakdownBucket[] }) {
  return (
    <div>
      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted">{title}</p>
      {buckets.length === 0 ? (
        <p className="text-sm text-text-muted">No settled data for this breakdown yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border border-border-subtle">
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-b border-border-subtle bg-bg-elevated text-left text-xs uppercase tracking-wide text-text-muted">
                <th className="px-3 py-1.5 font-medium">Bucket</th>
                <th className="px-3 py-1.5 font-medium">N</th>
                <th className="px-3 py-1.5 font-medium">Win %</th>
                <th className="px-3 py-1.5 font-medium">Exp. wins</th>
                <th className="px-3 py-1.5 font-medium">Brier</th>
                <th className="px-3 py-1.5 font-medium">ROI</th>
              </tr>
            </thead>
            <tbody>
              {buckets.map((b) => (
                <tr key={b.bucketLabel} className="border-b border-border-subtle last:border-b-0">
                  <td className="px-3 py-1.5 text-text-primary">{b.bucketLabel}</td>
                  <td className="px-3 py-1.5 font-tabular text-text-secondary">{b.sampleSize}</td>
                  <td className="px-3 py-1.5 font-tabular text-text-secondary">{formatPercent(b.winStrikeRate, 1)}</td>
                  <td className="px-3 py-1.5 font-tabular text-text-secondary">
                    {b.expectedWins !== null ? b.expectedWins.toFixed(1) : "—"} / {b.actualWins ?? "—"}
                  </td>
                  <td className="px-3 py-1.5 font-tabular text-text-secondary">
                    {b.brierScoreValue !== null ? b.brierScoreValue.toFixed(3) : "—"}
                  </td>
                  <td className="px-3 py-1.5 font-tabular text-text-secondary">
                    {b.roiPercentValue !== null ? `${b.roiPercentValue.toFixed(1)}%` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

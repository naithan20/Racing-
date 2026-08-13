import { getPerformanceData } from "@/data/queries";
import { roiPercent } from "@/backtesting/scoring";
import { PERFORMANCE_BREAKDOWN_DIMENSIONS } from "@/backtesting/types";
import { formatPercent } from "@/lib/format";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { NotConfigured } from "@/components/ui/NotConfigured";

function MetricTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-md border border-border-subtle bg-bg-elevated p-3">
      <p className="text-xs uppercase tracking-wide text-text-muted">{label}</p>
      <p className="mt-1 font-tabular text-xl text-text-primary">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-text-muted">{hint}</p>}
    </div>
  );
}

export default async function DashboardPage() {
  const results = await getPerformanceData();
  const settled = results.filter((r) => r.finishingPosition !== null || r.finishStatus === "PU");

  const numberOfSelections = results.length;
  const wins = results.filter((r) => r.finishingPosition === 1).length;
  const places = results.filter((r) => r.placeOutcome === true).length;
  const totalStakedWin = numberOfSelections; // 1pt win stake per selection, notional
  const totalPnlWin = results.reduce((sum, r) => sum + (r.profitLossWinStake ?? 0), 0);
  const roi = numberOfSelections > 0 ? roiPercent(totalStakedWin, totalPnlWin) : null;

  const hasAnyModelProbability = results.some((r) => r.runner.predictionSnapshots[0]?.winProbability != null);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Model performance dashboard</h1>
        <p className="mt-1 max-w-3xl text-sm text-text-secondary">
          The objective is to identify mispriced probability, not to maximise winners — a short-priced
          winner can be a bad bet, and a big-priced loser can be a good one. Calibration and edge-quality
          metrics below require model probabilities, which Phase 1 does not yet produce.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Summary (from recorded results)</CardTitle>
        </CardHeader>
        <CardBody className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <MetricTile label="Selections recorded" value={numberOfSelections.toString()} />
          <MetricTile label="Wins" value={wins.toString()} />
          <MetricTile label="Places" value={places.toString()} hint="per bookmaker place terms" />
          <MetricTile
            label="Win strike rate"
            value={numberOfSelections > 0 ? formatPercent(wins / numberOfSelections, 1) : "—"}
          />
          <MetricTile
            label="Place strike rate"
            value={numberOfSelections > 0 ? formatPercent(places / numberOfSelections, 1) : "—"}
          />
          <MetricTile
            label="ROI (win, 1pt)"
            value={roi !== null ? `${roi.toFixed(1)}%` : "—"}
            hint={`${settled.length} settled`}
          />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Model calibration &amp; edge quality</CardTitle>
        </CardHeader>
        <CardBody className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {[
            "Expected vs actual wins",
            "Expected vs actual places",
            "Calibration",
            "Brier score",
            "Log loss",
            "Average model odds",
            "Closing line value",
          ].map((label) => (
            <MetricTile key={label} label={label} value="—" />
          ))}
        </CardBody>
        {!hasAnyModelProbability && (
          <CardBody className="border-t border-border-subtle pt-3">
            <NotConfigured />
            <span className="ml-2 text-xs text-text-muted">
              No PredictionSnapshot in the database yet carries a non-null winProbability — these metrics
              activate automatically once Phase 2 starts writing real predictions.
            </span>
          </CardBody>
        )}
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Performance breakdown</CardTitle>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <table className="w-full min-w-[700px] text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-left text-xs uppercase tracking-wide text-text-muted">
                <th className="py-2 pr-3 font-medium">Dimension</th>
                <th className="py-2 pr-3 font-medium">Selections</th>
                <th className="py-2 pr-3 font-medium">Win %</th>
                <th className="py-2 pr-3 font-medium">Place %</th>
                <th className="py-2 pr-3 font-medium">ROI</th>
                <th className="py-2 font-medium">Brier score</th>
              </tr>
            </thead>
            <tbody>
              {PERFORMANCE_BREAKDOWN_DIMENSIONS.map((dim) => (
                <tr key={dim} className="border-b border-border-subtle last:border-b-0">
                  <td className="py-2 pr-3 text-text-primary">{dim.replaceAll("_", " ")}</td>
                  <td className="py-2 pr-3 text-text-muted">—</td>
                  <td className="py-2 pr-3 text-text-muted">—</td>
                  <td className="py-2 pr-3 text-text-muted">—</td>
                  <td className="py-2 pr-3 text-text-muted">—</td>
                  <td className="py-2 text-text-muted">—</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}

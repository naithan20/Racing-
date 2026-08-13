import Link from "next/link";

import { getBacktestAvailableDates, getBacktestPredictionsForDate } from "@/data/queries";
import { formatDate, formatDecimalOdds, formatPercent } from "@/lib/format";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge, ConfidenceBadge } from "@/components/ui/Badge";
import { SyntheticModelBanner } from "@/components/model/SyntheticModelBanner";
import { BacktestDatePicker } from "@/components/backtest/BacktestDatePicker";

function parseDateParam(value: string | undefined, fallback: string | undefined): Date {
  const raw = value ?? fallback;
  if (!raw) return new Date();
  const parsed = new Date(`${raw}T00:00:00Z`);
  return Number.isNaN(parsed.getTime()) ? new Date() : parsed;
}

export default async function BacktestModePage({ searchParams }: PageProps<"/backtest">) {
  const params = await searchParams;
  const dateParam = Array.isArray(params.date) ? params.date[0] : params.date;

  const availableDates = await getBacktestAvailableDates();
  const selectedDate = parseDateParam(dateParam, availableDates[availableDates.length - 1]);
  const selectedDateLabel = selectedDate.toISOString().slice(0, 10);

  const races = availableDates.length > 0 ? await getBacktestPredictionsForDate(selectedDate) : [];
  const isSynthetic = races.some((r) => r.runners.some((run) => run.predictionSnapshots[0]?.modelVersionRef?.isSynthetic));

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Backtest Mode</h1>
          <p className="mt-1 max-w-3xl text-sm text-text-secondary">
            Research view for avoiding hindsight bias: pick a historical date and see exactly what the
            model predicted BEFORE those races, using only odds and form data that existed as of that
            date — then compare against what actually happened.
          </p>
        </div>
        {availableDates.length > 0 && <BacktestDatePicker dates={availableDates} selected={selectedDateLabel} />}
      </div>

      {availableDates.length === 0 ? (
        <Card>
          <CardBody className="text-sm text-text-secondary">
            No backtested predictions yet. Run <code className="rounded bg-bg-elevated px-1 py-0.5">npm run model:backtest</code>{" "}
            to generate as-of-date predictions for a historical window.
          </CardBody>
        </Card>
      ) : (
        <>
          {isSynthetic && <SyntheticModelBanner />}

          {races.length === 0 ? (
            <Card>
              <CardBody className="text-sm text-text-secondary">No races with backtested predictions on this date.</CardBody>
            </Card>
          ) : (
            races.map((race) => (
              <Card key={race.id}>
                <CardHeader className="flex flex-wrap items-center justify-between gap-2">
                  <CardTitle>
                    {race.raceTime} {race.racecourse} — {race.raceName}
                  </CardTitle>
                  <div className="flex gap-1.5">
                    <Badge>{race.flatJumps}</Badge>
                    <Badge>{race.raceStatus}</Badge>
                  </div>
                </CardHeader>
                <CardBody className="overflow-x-auto p-0">
                  <table className="w-full min-w-[900px] text-sm">
                    <thead>
                      <tr className="border-b border-border-subtle bg-bg-elevated text-left text-xs uppercase tracking-wide text-text-muted">
                        <th className="px-3 py-2 font-medium">Horse</th>
                        <th className="px-3 py-2 font-medium">Predicted win %</th>
                        <th className="px-3 py-2 font-medium">Predicted place %</th>
                        <th className="px-3 py-2 font-medium">Confidence</th>
                        <th className="px-3 py-2 font-medium">Actual finish</th>
                        <th className="px-3 py-2 font-medium">SP</th>
                        <th className="px-3 py-2 font-medium">Outcome</th>
                      </tr>
                    </thead>
                    <tbody>
                      {race.runners.map((runner) => {
                        const snapshot = runner.predictionSnapshots[0] ?? null;
                        const won = runner.result?.finishingPosition === 1;
                        const placed = runner.result?.placeOutcome === true;
                        return (
                          <tr key={runner.id} className="border-b border-border-subtle last:border-b-0 hover:bg-bg-hover">
                            <td className="px-3 py-2">
                              <Link href={`/runners/${runner.id}`} className="text-accent hover:underline">
                                {runner.horse.name}
                              </Link>
                            </td>
                            <td className="px-3 py-2 font-tabular">{snapshot ? formatPercent(snapshot.winProbability) : "—"}</td>
                            <td className="px-3 py-2 font-tabular">{snapshot ? formatPercent(snapshot.placeProbability) : "—"}</td>
                            <td className="px-3 py-2">
                              <ConfidenceBadge value={snapshot?.modelConfidence ?? null} />
                            </td>
                            <td className="px-3 py-2 font-tabular text-text-primary">
                              {runner.result?.finishingPosition ?? runner.result?.finishStatus ?? "—"}
                            </td>
                            <td className="px-3 py-2 font-tabular text-text-secondary">
                              {formatDecimalOdds(runner.result?.startingPriceDecimal ?? null)}
                            </td>
                            <td className="px-3 py-2">
                              {won ? (
                                <Badge tone="positive">Won</Badge>
                              ) : placed ? (
                                <Badge tone="accent">Placed</Badge>
                              ) : runner.result ? (
                                <Badge tone="neutral">Unplaced</Badge>
                              ) : (
                                <span className="text-text-muted">—</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </CardBody>
              </Card>
            ))
          )}

          <p className="text-xs text-text-muted">
            Showing {formatDate(selectedDate)}. Predictions here are the same immutable PredictionSnapshot
            rows shown elsewhere in the app — generated using only race and form data dated strictly
            before each race, never the result itself.
          </p>
        </>
      )}
    </div>
  );
}

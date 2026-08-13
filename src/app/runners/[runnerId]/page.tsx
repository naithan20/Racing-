import Link from "next/link";
import { notFound } from "next/navigation";

import { getRunnerDetail } from "@/data/queries";
import { decimalToFractional } from "@/lib/odds";
import { formatDate, formatDecimalOdds, formatDistance, formatNumber, formatPercent } from "@/lib/format";
import { courseRecord, courseDistanceRecord, distanceRecord, goingRecord } from "@/lib/formAggregates";
import { paceRoleLabel } from "@/pace/types";
import { computeRunnerBadges, RUNNER_BADGE_LABELS } from "@/lib/badges";
import { buildExplanation } from "@/lib/explain";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge, ConfidenceBadge, ValueEdgeBadge } from "@/components/ui/Badge";
import { NotConfigured } from "@/components/ui/NotConfigured";
import { OddsHistoryChart, type OddsPoint } from "@/components/runners/OddsHistoryChart";
import { describePlaceBasis } from "@/value/place";
import { SyntheticModelBanner } from "@/components/model/SyntheticModelBanner";

function RecordRow({ label, summary }: { label: string; summary: { runs: number; wins: number; places: number; winPercentage: number | null; placePercentage: number | null } }) {
  return (
    <div className="flex items-center justify-between border-b border-border-subtle py-2 text-sm last:border-b-0">
      <span className="text-text-secondary">{label}</span>
      <span className="font-tabular text-text-primary">
        {summary.wins}-{summary.places}-{summary.runs}{" "}
        <span className="text-text-muted">
          ({formatPercent(summary.winPercentage, 0)} win / {formatPercent(summary.placePercentage, 0)} place)
        </span>
      </span>
    </div>
  );
}

export default async function RunnerDetailPage({ params }: PageProps<"/runners/[runnerId]">) {
  const { runnerId } = await params;
  const data = await getRunnerDetail(runnerId);
  if (!data) notFound();
  const { runner, formEntries } = data;

  const snapshot = runner.predictionSnapshots.find((s) => s.snapshotType === "PRE_RACE") ?? null;
  const evidence = runner.horse.evidenceProfile;
  const pace = runner.paceProfile;
  const modelVersion = snapshot?.modelVersionRef ?? null;

  const oddsPoints: OddsPoint[] = runner.marketPrices.map((mp) => ({
    timestamp: mp.timestamp.toISOString(),
    label: new Date(mp.timestamp).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }),
    oddsDecimal: mp.winOddsDecimal,
    bookmaker: mp.bookmaker.name,
  }));

  const cRecord = courseRecord(formEntries, runner.race.racecourse);
  const dRecord = distanceRecord(formEntries, runner.race.distanceFurlongs);
  const gRecord = runner.race.going ? goingRecord(formEntries, runner.race.going) : null;
  const cdRecord = courseDistanceRecord(formEntries, runner.race.racecourse, runner.race.distanceFurlongs);

  const ratingMovement =
    formEntries.length > 0 && formEntries[0].officialRating !== null && runner.officialRating !== null
      ? runner.officialRating - formEntries[0].officialRating
      : null;

  const badges = computeRunnerBadges({
    valueEdgeAbsolute: snapshot?.valueEdgeAbsolute ?? null,
    modelConfidence: snapshot?.modelConfidence ?? null,
    evidenceDensityScore: evidence?.evidenceDensityScore ?? null,
    paceCollapseProbability: pace?.paceCollapseProbability ?? null,
    draw: runner.draw,
    fieldSize: runner.race.numberOfRunners,
  });

  const siblingRunners = runner.race.runners.filter((r) => r.id !== runner.id);
  const fieldAccelIndices = siblingRunners
    .map((r) => r.paceProfile?.relativeAccelerationIndex)
    .filter((v): v is number => v !== null && v !== undefined);
  const fieldFinishSpeedIndices = siblingRunners
    .map((r) => r.paceProfile?.finishingSpeedIndex)
    .filter((v): v is number => v !== null && v !== undefined);
  const fieldWeights = siblingRunners
    .map((r) => r.weightLbsTotal)
    .filter((v): v is number => v !== null && v !== undefined);

  const bestRecentOfficialRating =
    formEntries.length > 0
      ? Math.max(...formEntries.slice(0, 5).map((f) => f.officialRating ?? -Infinity).filter((v) => v > -Infinity), -Infinity)
      : -Infinity;

  const explanation = buildExplanation({
    recentFinishingPositions: formEntries.slice(0, 6).map((f) => ({ position: f.finishingPosition, fieldSize: f.fieldSize })),
    courseRecord: cRecord,
    distanceRecord: dRecord,
    goingRecord: gRecord ?? { runs: 0, wins: 0, places: 0, winPercentage: null, placePercentage: null },
    ratingMovement,
    currentOfficialRating: runner.officialRating,
    bestRecentOfficialRating: bestRecentOfficialRating > -Infinity ? bestRecentOfficialRating : null,
    weightLbs: runner.weightLbsTotal,
    fieldWeightsLbs: fieldWeights,
    relativeAccelerationIndex: pace?.relativeAccelerationIndex ?? null,
    fieldRelativeAccelerationIndices: fieldAccelIndices,
    finishingSpeedIndex: pace?.finishingSpeedIndex ?? null,
    fieldFinishingSpeedIndices: fieldFinishSpeedIndices,
    firstTimeHeadgear: runner.firstTimeHeadgear,
    evidenceDensityScore: evidence?.evidenceDensityScore ?? null,
    careerStartsToDate: formEntries.length,
    courseStartsToDate: cRecord.runs,
    paceCollapseProbability: pace?.paceCollapseProbability ?? null,
    projectedRole: pace?.projectedRole ?? null,
  });

  return (
    <div className="flex flex-col gap-6">
      {modelVersion?.isSynthetic && <SyntheticModelBanner />}

      <div>
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <Link href="/races" className="hover:text-text-secondary">
            Races
          </Link>
          <span>/</span>
          <Link href={`/races/${runner.raceId}`} className="hover:text-text-secondary">
            {runner.race.racecourse} {runner.race.raceTime}
          </Link>
          <span>/</span>
          <span>{runner.horse.name}</span>
        </div>
        <h1 className="mt-1 text-lg font-semibold text-text-primary">{runner.horse.name}</h1>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {runner.headgear && <Badge tone="accent">{runner.headgear}</Badge>}
          {runner.firstTimeHeadgear && <Badge tone="warning">First-time headgear</Badge>}
          {runner.nonRunner && <Badge tone="negative">Non-runner</Badge>}
          {evidence?.evidenceDensityLabel && <Badge>Evidence: {evidence.evidenceDensityLabel}</Badge>}
          {badges.map((b) => (
            <Badge key={b} tone={b === "LOW_CONFIDENCE" || b === "PACE_RISK" || b === "DRAW_RISK" ? "warning" : "positive"}>
              {RUNNER_BADGE_LABELS[b]}
            </Badge>
          ))}
          {modelVersion && (
            <span className="ml-1 self-center text-xs text-text-muted">
              model: {modelVersion.name} ({modelVersion.version})
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Model output</CardTitle>
          </CardHeader>
          <CardBody className="flex flex-col gap-2 text-sm">
            <div className="flex justify-between">
              <span className="text-text-secondary">Win probability</span>
              {snapshot?.winProbability !== null && snapshot?.winProbability !== undefined ? (
                formatPercent(snapshot.winProbability)
              ) : (
                <NotConfigured compact />
              )}
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Place probability</span>
              {snapshot?.placeProbability !== null && snapshot?.placeProbability !== undefined ? (
                <span>{formatPercent(snapshot.placeProbability)}</span>
              ) : (
                <NotConfigured compact />
              )}
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Model confidence</span>
              <ConfidenceBadge value={snapshot?.modelConfidence ?? null} />
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Fair odds</span>
              {snapshot?.fairOddsDecimal ? formatDecimalOdds(snapshot.fairOddsDecimal) : <NotConfigured compact />}
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Value edge</span>
              <ValueEdgeBadge value={snapshot?.valueEdgeAbsolute ?? null} />
            </div>
            <p className="mt-1 text-xs text-text-muted">
              {describePlaceBasis(
                { places: snapshot?.placeBasisPlaces ?? runner.race.bookmakerPlaces ?? 3, eachWayFraction: 0.2 },
                runner.race.numberOfRunners
              )}
            </p>
            {snapshot && snapshot.placeProbabilityBands.length > 0 && (
              <div className="mt-2 border-t border-border-subtle pt-2">
                <p className="mb-1 text-xs text-text-muted">Place probability by depth</p>
                <div className="flex flex-wrap gap-2">
                  {[...snapshot.placeProbabilityBands]
                    .sort((a, b) => a.topN - b.topN)
                    .map((band) => (
                      <span key={band.topN} className="rounded bg-bg-hover px-1.5 py-0.5 text-xs text-text-secondary">
                        top{band.topN}: {formatPercent(band.probabilityCalibrated, 0)}
                      </span>
                    ))}
                </div>
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Market</CardTitle>
          </CardHeader>
          <CardBody className="flex flex-col gap-2 text-sm">
            <div className="flex justify-between">
              <span className="text-text-secondary">Current odds</span>
              <span className="font-tabular">
                {formatDecimalOdds(runner.currentOddsDecimal)}
                {runner.currentOddsDecimal && (
                  <span className="ml-1 text-text-muted">({decimalToFractional(runner.currentOddsDecimal)})</span>
                )}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Opening odds</span>
              <span className="font-tabular">{formatDecimalOdds(runner.openingOddsDecimal)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Starting price</span>
              <span className="font-tabular">{formatDecimalOdds(runner.startingPriceDecimal)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Favourite rank</span>
              <span className="font-tabular">{runner.favouriteRank ?? "—"}</span>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Ratings &amp; weight</CardTitle>
          </CardHeader>
          <CardBody className="flex flex-col gap-2 text-sm">
            <div className="flex justify-between">
              <span className="text-text-secondary">Official rating</span>
              <span className="font-tabular">{runner.officialRating ?? "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Rating movement</span>
              <span className="font-tabular">
                {ratingMovement === null ? "—" : ratingMovement > 0 ? `+${ratingMovement}` : ratingMovement}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Weight carried</span>
              <span className="font-tabular">{runner.weightLbsTotal ? `${runner.weightLbsTotal}lb` : "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Draw</span>
              <span className="font-tabular">{runner.draw ?? "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Days since last run</span>
              <span className="font-tabular">{runner.daysSinceLastRun ?? "—"}</span>
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Course / distance / going record</CardTitle>
          </CardHeader>
          <CardBody>
            <RecordRow label={`Course (${runner.race.racecourse})`} summary={cRecord} />
            <RecordRow label={`Distance (${formatDistance(runner.race.distanceFurlongs)})`} summary={dRecord} />
            {gRecord && <RecordRow label={`Going (${runner.race.going})`} summary={gRecord} />}
            <RecordRow label="Course + distance" summary={cdRecord} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Historical odds</CardTitle>
          </CardHeader>
          <CardBody>
            <OddsHistoryChart points={oddsPoints} />
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Pace behaviour</CardTitle>
        </CardHeader>
        <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-text-muted">Projected role</p>
            <p className="mt-1 text-sm text-text-primary">{pace ? paceRoleLabel(pace.projectedRole) : "—"}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-text-muted">1. Position acquisition</p>
            <p className="mt-1 text-sm text-text-secondary">Usual early pos: {formatNumber(pace?.usualEarlyPosition ?? null, 1)}</p>
            <p className="text-sm text-text-secondary">Quick break rate: {formatPercent(pace?.breaksQuicklyRate ?? null, 0)}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-text-muted">2. Transition speed</p>
            <p className="mt-1 text-sm text-text-secondary">3f→2f: {formatNumber(pace?.positionChange3fTo2f ?? null, 2)}</p>
            <p className="text-sm text-text-secondary">2f→1f: {formatNumber(pace?.positionChange2fTo1f ?? null, 2)}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-text-muted">3. Late sustainability</p>
            <p className="mt-1 text-sm text-text-secondary">Finishing speed: {formatNumber(pace?.finishingSpeedIndex ?? null, 2)}</p>
            <p className="text-sm text-text-secondary">Stays on strongly: {formatPercent(pace?.staysOnStronglyRate ?? null, 0)}</p>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Form timeline</CardTitle>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-left text-xs uppercase tracking-wide text-text-muted">
                <th className="py-1.5 pr-3 font-medium">Date</th>
                <th className="py-1.5 pr-3 font-medium">Course</th>
                <th className="py-1.5 pr-3 font-medium">Dist</th>
                <th className="py-1.5 pr-3 font-medium">Going</th>
                <th className="py-1.5 pr-3 font-medium">Class</th>
                <th className="py-1.5 pr-3 font-medium">Pos</th>
                <th className="py-1.5 pr-3 font-medium">SP</th>
                <th className="py-1.5 pr-3 font-medium">OR</th>
                <th className="py-1.5 pr-3 font-medium">Jockey</th>
                <th className="py-1.5 font-medium">Comment</th>
              </tr>
            </thead>
            <tbody>
              {formEntries.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-3 text-text-muted">
                    No prior form recorded.
                  </td>
                </tr>
              ) : (
                formEntries.map((f) => (
                  <tr key={f.id} className="border-b border-border-subtle last:border-b-0">
                    <td className="py-1.5 pr-3 text-text-secondary">{formatDate(f.raceDate)}</td>
                    <td className="py-1.5 pr-3 text-text-primary">{f.course}</td>
                    <td className="py-1.5 pr-3 font-tabular text-text-secondary">{formatDistance(f.distanceFurlongs)}</td>
                    <td className="py-1.5 pr-3 text-text-secondary">{f.going ?? "—"}</td>
                    <td className="py-1.5 pr-3 font-tabular text-text-secondary">{f.raceClass ?? "—"}</td>
                    <td className="py-1.5 pr-3 font-tabular text-text-primary">
                      {f.finishingPosition ?? f.finishStatus ?? "—"}
                      {f.fieldSize ? <span className="text-text-muted">/{f.fieldSize}</span> : null}
                    </td>
                    <td className="py-1.5 pr-3 font-tabular text-text-secondary">{formatDecimalOdds(f.startingPriceDecimal)}</td>
                    <td className="py-1.5 pr-3 font-tabular text-text-secondary">{f.officialRating ?? "—"}</td>
                    <td className="py-1.5 pr-3 text-text-secondary">{f.jockeyName ?? "—"}</td>
                    <td className="py-1.5 text-text-secondary">{f.raceComment ?? "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Why the model likes / dislikes this horse</CardTitle>
        </CardHeader>
        <CardBody className="flex flex-col gap-4">
          {!snapshot || snapshot.winProbability === null ? (
            <p className="text-sm text-text-muted">
              No rule-based rationale has been generated yet — a model prediction is required first. It is
              always derived from concrete, traceable feature comparisons, never free-form generated text.
            </p>
          ) : (
            <>
              <div>
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-positive">Positive factors</p>
                {explanation.positiveFactors.length === 0 ? (
                  <p className="text-sm text-text-muted">No notable positive factors identified.</p>
                ) : (
                  <ul className="list-inside list-disc space-y-1 text-sm text-text-secondary">
                    {explanation.positiveFactors.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-negative">Negative factors</p>
                {explanation.negativeFactors.length === 0 ? (
                  <p className="text-sm text-text-muted">No notable negative factors identified.</p>
                ) : (
                  <ul className="list-inside list-disc space-y-1 text-sm text-text-secondary">
                    {explanation.negativeFactors.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-warning">Model uncertainty</p>
                {explanation.modelUncertainty.length === 0 ? (
                  <p className="text-sm text-text-muted">No specific uncertainty flags.</p>
                ) : (
                  <ul className="list-inside list-disc space-y-1 text-sm text-text-secondary">
                    {explanation.modelUncertainty.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                )}
              </div>
              <p className="text-xs text-text-muted">
                Model association / importance, not causal effect. Each statement above is generated from a
                fixed threshold on a specific data field — see src/lib/explain.ts.
              </p>
            </>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

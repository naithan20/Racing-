import { getModelVersions, getPerformanceData, getPredictionsForModelVersion } from "@/data/queries";
import { brierScore, calibrationBuckets, logLoss, roiPercent } from "@/backtesting/scoring";
import {
  ageBandLabel,
  confidenceBandLabel,
  distanceBandLabel,
  evidenceBandLabel,
  fieldSizeBandLabel,
  groupAndSummarize,
  oddsBandLabel,
  type EvaluableRow,
} from "@/backtesting/breakdown";
import { formatDate, formatPercent } from "@/lib/format";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { NotConfigured } from "@/components/ui/NotConfigured";
import { ModelSelector } from "@/components/dashboard/ModelSelector";
import { CalibrationChart } from "@/components/dashboard/CalibrationChart";
import { BreakdownTable } from "@/components/dashboard/BreakdownTable";
import { FeatureImportance } from "@/components/dashboard/FeatureImportance";
import { SyntheticModelBanner } from "@/components/model/SyntheticModelBanner";

function MetricTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-md border border-border-subtle bg-bg-elevated p-3">
      <p className="text-xs uppercase tracking-wide text-text-muted">{label}</p>
      <p className="mt-1 font-tabular text-xl text-text-primary">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-text-muted">{hint}</p>}
    </div>
  );
}

interface EvaluableRowWithMeta extends EvaluableRow {
  flatJumps: string;
  raceClass: number | null;
  fieldSize: number;
  going: string | null;
  course: string;
  distanceFurlongs: number;
  age: number | null;
  evidenceDensity: number | null;
  confidence: number | null;
  oddsDecimal: number | null;
}

export default async function DashboardPage({ searchParams }: PageProps<"/dashboard">) {
  const params = await searchParams;
  const modelParam = Array.isArray(params.model) ? params.model[0] : params.model;

  const [legacyResults, modelVersions] = await Promise.all([getPerformanceData(), getModelVersions()]);

  const selectedModel = modelParam
    ? (modelVersions.find((m) => m.id === modelParam) ?? modelVersions[0])
    : modelVersions[0];

  const predictions = selectedModel ? await getPredictionsForModelVersion(selectedModel.id) : [];

  const evaluable: EvaluableRowWithMeta[] = predictions
    .filter((p) => p.winProbability !== null && p.runner.result?.finishingPosition !== undefined && p.runner.result !== null)
    .map((p) => ({
      winProbability: p.winProbability as number,
      won: p.runner.result!.finishingPosition === 1,
      startingPriceDecimal: p.runner.result!.startingPriceDecimal,
      oddsDecimal: p.runner.result!.startingPriceDecimal ?? p.runner.currentOddsDecimal,
      flatJumps: p.runner.race.flatJumps,
      raceClass: p.runner.race.raceClass,
      fieldSize: p.runner.race.numberOfRunners,
      going: p.runner.race.going,
      course: p.runner.race.racecourse,
      distanceFurlongs: p.runner.race.distanceFurlongs,
      age: p.runner.ageAtRace,
      evidenceDensity: p.runner.horse.evidenceProfile?.evidenceDensityScore ?? null,
      confidence: p.modelConfidence,
    }));

  const pairs = evaluable.map((e) => ({ predictedProbability: e.winProbability, outcome: e.won }));
  const brier = brierScore(pairs);
  const ll = logLoss(pairs);
  const buckets = calibrationBuckets(pairs);
  const expectedWins = evaluable.reduce((s, e) => s + e.winProbability, 0);
  const actualWins = evaluable.filter((e) => e.won).length;
  const winStrikeRate = evaluable.length > 0 ? actualWins / evaluable.length : null;
  const staked = evaluable.filter((e) => e.startingPriceDecimal !== null).length;
  const profit = evaluable.reduce((s, e) => s + (e.startingPriceDecimal !== null ? (e.won ? e.startingPriceDecimal - 1 : -1) : 0), 0);
  const roi = staked > 0 ? roiPercent(staked, profit) : null;

  const featureImportance = selectedModel?.featureImportanceJson ? JSON.parse(selectedModel.featureImportanceJson) : [];
  const metrics = selectedModel?.metricsJson ? JSON.parse(selectedModel.metricsJson) : null;

  // Legacy Phase 1 "recorded results" summary (model-agnostic, all results).
  const numberOfSelections = legacyResults.length;
  const legacyWins = legacyResults.filter((r) => r.finishingPosition === 1).length;
  const legacyPlaces = legacyResults.filter((r) => r.placeOutcome === true).length;
  const legacyPnl = legacyResults.reduce((sum, r) => sum + (r.profitLossWinStake ?? 0), 0);
  const legacyRoi = numberOfSelections > 0 ? roiPercent(numberOfSelections, legacyPnl) : null;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Model performance dashboard</h1>
          <p className="mt-1 max-w-3xl text-sm text-text-secondary">
            The objective is to identify mispriced probability, not to maximise winners — a short-priced
            winner can be a bad bet, and a big-priced loser can be a good one. Metrics below are
            recomputed live from stored PredictionSnapshot + ResultEntry rows for the selected model.
          </p>
        </div>
        {modelVersions.length > 0 && (
          <ModelSelector
            models={modelVersions.map((m) => ({ id: m.id, name: m.name, version: m.version, algorithm: m.algorithm, isSynthetic: m.isSynthetic }))}
            selectedId={selectedModel?.id ?? ""}
          />
        )}
      </div>

      {!selectedModel ? (
        <Card>
          <CardBody className="text-sm text-text-secondary">
            No trained model versions yet. Run <code className="rounded bg-bg-elevated px-1 py-0.5">npm run model:train</code>{" "}
            to train the Phase 2 baseline models.
          </CardBody>
        </Card>
      ) : (
        <>
          {selectedModel.isSynthetic && <SyntheticModelBanner />}

          <Card>
            <CardHeader className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle>Model: {selectedModel.name}</CardTitle>
              <div className="flex flex-wrap gap-1.5">
                <Badge>{selectedModel.algorithm}</Badge>
                <Badge>calibration: {selectedModel.calibrationMethod}</Badge>
                <Badge>features {selectedModel.featureSetVersion}</Badge>
              </div>
            </CardHeader>
            <CardBody className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <MetricTile
                label="Training period"
                value={`${formatDate(selectedModel.trainingStartDate)} – ${formatDate(selectedModel.trainingEndDate)}`}
              />
              <MetricTile label="Training races" value={selectedModel.trainingRaceCount.toString()} hint={`${selectedModel.trainingRowCount} rows`} />
              <MetricTile
                label="Test period"
                value={selectedModel.testStartDate ? `${formatDate(selectedModel.testStartDate)} – ${formatDate(selectedModel.testEndDate!)}` : "—"}
              />
              <MetricTile label="Evaluable predictions" value={evaluable.length.toString()} hint="settled, this model" />
              <MetricTile label="Brier score" value={brier !== null ? brier.toFixed(4) : "—"} hint="lower is better" />
              <MetricTile label="Log loss" value={ll !== null ? ll.toFixed(4) : "—"} hint="lower is better" />
            </CardBody>
            <CardBody className="grid grid-cols-2 gap-3 border-t border-border-subtle pt-3 sm:grid-cols-3 lg:grid-cols-6">
              <MetricTile label="Win strike rate" value={formatPercent(winStrikeRate, 1)} />
              <MetricTile label="Expected vs actual wins" value={`${expectedWins.toFixed(1)} / ${actualWins}`} />
              <MetricTile label="Flat £1 win ROI" value={roi !== null ? `${roi.toFixed(1)}%` : "—"} hint={`${staked} staked`} />
              {metrics?.place && (
                <>
                  <MetricTile label="Place top3 Brier (test)" value={metrics.place.top3?.brier_score?.toFixed(3) ?? "—"} />
                  <MetricTile label="Place top3 strike rate (test)" value={formatPercent(metrics.place.top3?.win_strike_rate ?? null, 1)} />
                  <MetricTile label="Monotonicity violations (test)" value={String(metrics.monotonicity_violations_test ?? "—")} />
                </>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Calibration — predicted probability vs actual strike rate</CardTitle>
            </CardHeader>
            <CardBody>
              <CalibrationChart buckets={buckets} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Performance breakdown (win model, settled predictions)</CardTitle>
            </CardHeader>
            <CardBody className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <BreakdownTable title="Flat / Jumps" buckets={groupAndSummarize(evaluable, (r) => r.flatJumps)} />
              <BreakdownTable title="Race class" buckets={groupAndSummarize(evaluable, (r) => (r.raceClass !== null ? `Class ${r.raceClass}` : null))} />
              <BreakdownTable title="Field size" buckets={groupAndSummarize(evaluable, (r) => fieldSizeBandLabel(r.fieldSize))} />
              <BreakdownTable title="Odds band" buckets={groupAndSummarize(evaluable, (r) => oddsBandLabel(r.oddsDecimal))} />
              <BreakdownTable title="Evidence density band" buckets={groupAndSummarize(evaluable, (r) => evidenceBandLabel(r.evidenceDensity))} />
              <BreakdownTable title="Model confidence band" buckets={groupAndSummarize(evaluable, (r) => confidenceBandLabel(r.confidence))} />
              <BreakdownTable title="Course" buckets={groupAndSummarize(evaluable, (r) => r.course)} />
              <BreakdownTable title="Going" buckets={groupAndSummarize(evaluable, (r) => r.going)} />
              <BreakdownTable title="Distance band" buckets={groupAndSummarize(evaluable, (r) => distanceBandLabel(r.distanceFurlongs))} />
              <BreakdownTable title="Age group" buckets={groupAndSummarize(evaluable, (r) => ageBandLabel(r.age))} />
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Feature importance ({selectedModel.algorithm})</CardTitle>
            </CardHeader>
            <CardBody>
              <FeatureImportance items={featureImportance} />
            </CardBody>
          </Card>
        </>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Summary (all recorded results, model-agnostic)</CardTitle>
        </CardHeader>
        <CardBody className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <MetricTile label="Selections recorded" value={numberOfSelections.toString()} />
          <MetricTile label="Wins" value={legacyWins.toString()} />
          <MetricTile label="Places" value={legacyPlaces.toString()} hint="per bookmaker place terms" />
          <MetricTile label="Win strike rate" value={numberOfSelections > 0 ? formatPercent(legacyWins / numberOfSelections, 1) : "—"} />
          <MetricTile label="Place strike rate" value={numberOfSelections > 0 ? formatPercent(legacyPlaces / numberOfSelections, 1) : "—"} />
          <MetricTile label="ROI (win, 1pt)" value={legacyRoi !== null ? `${legacyRoi.toFixed(1)}%` : "—"} />
        </CardBody>
        {evaluable.length === 0 && (
          <CardBody className="border-t border-border-subtle pt-3">
            <NotConfigured />
            <span className="ml-2 text-xs text-text-muted">
              No settled predictions for the selected model yet — run <code>npm run model:backtest</code>.
            </span>
          </CardBody>
        )}
      </Card>
    </div>
  );
}

/**
 * Standard probabilistic scoring rules for calibration analysis.
 *
 * These are well-established statistical formulas (not a racing model) used
 * to judge how well-calibrated the model's probabilities were versus what
 * actually happened. They operate on (predictedProbability, outcome) pairs
 * supplied by the caller — this module has no opinion on where those come
 * from.
 */

export class ScoringInputError extends Error {}

function assertProbability(p: number): void {
  if (!Number.isFinite(p) || p < 0 || p > 1) {
    throw new ScoringInputError(`Probability must be in [0, 1], got ${p}`);
  }
}

export interface PredictionOutcomePair {
  predictedProbability: number;
  outcome: boolean;
}

/** Mean squared error between predicted probability and the binary outcome. Lower is better. */
export function brierScore(pairs: PredictionOutcomePair[]): number | null {
  if (pairs.length === 0) return null;
  const total = pairs.reduce((sum, { predictedProbability, outcome }) => {
    assertProbability(predictedProbability);
    const actual = outcome ? 1 : 0;
    return sum + (predictedProbability - actual) ** 2;
  }, 0);
  return total / pairs.length;
}

/** Negative log-likelihood of the outcomes under the predicted probabilities. Lower is better. */
export function logLoss(pairs: PredictionOutcomePair[], epsilon = 1e-15): number | null {
  if (pairs.length === 0) return null;
  const total = pairs.reduce((sum, { predictedProbability, outcome }) => {
    assertProbability(predictedProbability);
    const clamped = Math.min(Math.max(predictedProbability, epsilon), 1 - epsilon);
    return sum + (outcome ? -Math.log(clamped) : -Math.log(1 - clamped));
  }, 0);
  return total / pairs.length;
}

export interface CalibrationBucket {
  bucketLabel: string;
  bucketMin: number;
  bucketMax: number;
  meanPredictedProbability: number | null;
  observedFrequency: number | null;
  sampleSize: number;
}

/**
 * Buckets predictions into probability bands and compares mean predicted
 * probability against observed frequency in each band — the standard
 * calibration-curve view.
 */
export function calibrationBuckets(
  pairs: PredictionOutcomePair[],
  bucketCount = 10
): CalibrationBucket[] {
  const buckets: CalibrationBucket[] = Array.from({ length: bucketCount }, (_, i) => {
    const bucketMin = i / bucketCount;
    const bucketMax = (i + 1) / bucketCount;
    return {
      bucketLabel: `${Math.round(bucketMin * 100)}-${Math.round(bucketMax * 100)}%`,
      bucketMin,
      bucketMax,
      meanPredictedProbability: null,
      observedFrequency: null,
      sampleSize: 0,
    };
  });

  const sums = buckets.map(() => ({ predictedSum: 0, outcomeSum: 0, count: 0 }));

  for (const { predictedProbability, outcome } of pairs) {
    assertProbability(predictedProbability);
    const index = Math.min(Math.floor(predictedProbability * bucketCount), bucketCount - 1);
    sums[index].predictedSum += predictedProbability;
    sums[index].outcomeSum += outcome ? 1 : 0;
    sums[index].count += 1;
  }

  return buckets.map((bucket, i) => {
    const { predictedSum, outcomeSum, count } = sums[i];
    if (count === 0) return bucket;
    return {
      ...bucket,
      meanPredictedProbability: predictedSum / count,
      observedFrequency: outcomeSum / count,
      sampleSize: count,
    };
  });
}

/** Simple ROI helper: total profit/loss divided by total staked, as a percentage. */
export function roiPercent(totalStaked: number, totalProfitLoss: number): number | null {
  if (totalStaked <= 0) return null;
  return (totalProfitLoss / totalStaked) * 100;
}

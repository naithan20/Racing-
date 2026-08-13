/**
 * Odds conversion and implied-probability utilities.
 *
 * These are pure, deterministic conversions between odds formats — no
 * racing model logic lives here.
 */

export class InvalidOddsError extends Error {}
export class InvalidProbabilityError extends Error {}

/** Decimal odds must represent a payout multiple greater than 1 (i.e. 1.01+). */
export function assertValidDecimalOdds(decimalOdds: number): void {
  if (!Number.isFinite(decimalOdds) || decimalOdds <= 1) {
    throw new InvalidOddsError(
      `Decimal odds must be a finite number greater than 1, got ${decimalOdds}`
    );
  }
}

/** Probability must be a finite value in the open interval (0, 1]. */
export function assertValidProbability(probability: number): void {
  if (!Number.isFinite(probability) || probability <= 0 || probability > 1) {
    throw new InvalidProbabilityError(
      `Probability must be a finite number in (0, 1], got ${probability}`
    );
  }
}

/**
 * Market-implied probability from decimal odds, before removing overround.
 * implied probability = 1 / decimal odds
 */
export function impliedProbability(decimalOdds: number): number {
  assertValidDecimalOdds(decimalOdds);
  return 1 / decimalOdds;
}

/** Fair decimal odds implied by a probability. */
export function probabilityToDecimalOdds(probability: number): number {
  assertValidProbability(probability);
  return 1 / probability;
}

/**
 * Sum of implied probabilities across a full market (book). A "fair" market
 * with no bookmaker margin sums to 1.0 (100%). Anything above is overround.
 */
export function bookPercentage(decimalOddsList: number[]): number {
  return decimalOddsList.reduce((sum, odds) => sum + impliedProbability(odds), 0);
}

/** Overround expressed as a percentage above 100%, e.g. 1.18 book -> 18. */
export function overroundPercentage(decimalOddsList: number[]): number {
  return (bookPercentage(decimalOddsList) - 1) * 100;
}

/**
 * Removes overround proportionally (Shin/basic normalisation is a modelling
 * choice for later; this is the simple proportional method) so implied
 * probabilities across the field sum to 1.0.
 */
export function normaliseImpliedProbabilities(decimalOddsList: number[]): number[] {
  const raw = decimalOddsList.map(impliedProbability);
  const total = raw.reduce((sum, p) => sum + p, 0);
  if (total <= 0) return raw;
  return raw.map((p) => p / total);
}

/**
 * Converts decimal odds to the nearest simple fractional representation,
 * e.g. 3.5 -> "5/2". Uses a bounded continued-fraction approximation so the
 * result stays a recognisable bookmaker-style fraction rather than an
 * unreduced ratio.
 */
export function decimalToFractional(decimalOdds: number, maxDenominator = 100): string {
  assertValidDecimalOdds(decimalOdds);
  const fractionalValue = decimalOdds - 1;
  const { numerator, denominator } = approximateFraction(fractionalValue, maxDenominator);
  return `${numerator}/${denominator}`;
}

/** Parses fractional odds like "5/2", "5-2" or "evens"/"evs" into decimal odds. */
export function fractionalToDecimal(fractional: string): number {
  const normalised = fractional.trim().toLowerCase();
  if (normalised === "evens" || normalised === "evs" || normalised === "even") {
    return 2;
  }
  const match = normalised.match(/^(\d+(?:\.\d+)?)\s*[/\-]\s*(\d+(?:\.\d+)?)$/);
  if (!match) {
    throw new InvalidOddsError(`Cannot parse fractional odds: "${fractional}"`);
  }
  const numerator = Number(match[1]);
  const denominator = Number(match[2]);
  if (denominator === 0) {
    throw new InvalidOddsError(`Fractional odds denominator cannot be zero: "${fractional}"`);
  }
  return numerator / denominator + 1;
}

function gcd(a: number, b: number): number {
  let x = Math.abs(a);
  let y = Math.abs(b);
  while (y) {
    [x, y] = [y, x % y];
  }
  return x || 1;
}

/** Best rational approximation of a non-negative decimal value within a denominator bound. */
function approximateFraction(
  value: number,
  maxDenominator: number
): { numerator: number; denominator: number } {
  if (value <= 0) return { numerator: 0, denominator: 1 };

  let bestNumerator = Math.round(value);
  let bestDenominator = 1;
  let bestError = Math.abs(value - bestNumerator);

  for (let denominator = 1; denominator <= maxDenominator; denominator++) {
    const numerator = Math.round(value * denominator);
    if (numerator <= 0) continue;
    const error = Math.abs(value - numerator / denominator);
    if (error < bestError - 1e-9) {
      bestError = error;
      bestNumerator = numerator;
      bestDenominator = denominator;
    }
  }

  const divisor = gcd(bestNumerator, bestDenominator);
  return { numerator: bestNumerator / divisor, denominator: bestDenominator / divisor };
}

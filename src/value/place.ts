/**
 * Each-way / place-term handling.
 *
 * IMPORTANT: "place" never means a fixed "top 3" in this application. It
 * always means "top N", where N is the number of places a specific
 * bookmaker is actually paying on a specific race — see RacePlaceTerms.
 * Every place-probability figure surfaced in the UI must be traceable back
 * to the bookmaker + places it was computed against.
 */

import { assertValidDecimalOdds } from "@/lib/odds";

export interface EachWayTerms {
  /** Number of places paid, e.g. 3, 4, 5. Never assume 3. */
  places: number;
  /** e.g. 0.25 for 1/4 odds, 0.2 for 1/5 odds */
  eachWayFraction: number;
  extraPlaces?: boolean;
}

export class InvalidPlaceTermsError extends Error {}

export function assertValidEachWayTerms(terms: EachWayTerms): void {
  if (!Number.isInteger(terms.places) || terms.places < 1) {
    throw new InvalidPlaceTermsError(`places must be a positive integer, got ${terms.places}`);
  }
  if (!Number.isFinite(terms.eachWayFraction) || terms.eachWayFraction <= 0 || terms.eachWayFraction >= 1) {
    throw new InvalidPlaceTermsError(
      `eachWayFraction must be in (0, 1), got ${terms.eachWayFraction}`
    );
  }
}

/**
 * Human-readable, always-explicit description of what a place probability
 * was computed against. UI components must use this rather than inventing
 * their own "placed" language.
 */
export function describePlaceBasis(terms: EachWayTerms, numberOfRunners?: number): string {
  const runnersPart = numberOfRunners ? ` of ${numberOfRunners} runners` : "";
  const extra = terms.extraPlaces ? " (extra places)" : "";
  return `Place probability based on top ${terms.places}${runnersPart}${extra}`;
}

/** The decimal odds paid on the each-way "place" part of the bet. */
export function placeOddsDecimal(winOddsDecimal: number, eachWayFraction: number): number {
  assertValidDecimalOdds(winOddsDecimal);
  if (eachWayFraction <= 0 || eachWayFraction >= 1) {
    throw new InvalidPlaceTermsError(`eachWayFraction must be in (0, 1), got ${eachWayFraction}`);
  }
  return 1 + (winOddsDecimal - 1) * eachWayFraction;
}

export interface EachWaySettlement {
  wonWinPart: boolean;
  placedPart: boolean;
  /** Total returned across both the win and place halves of the bet. */
  totalReturn: number;
  /** Profit/loss on a `stakePerPart` each-way bet (stakePerPart on win + stakePerPart on place). */
  profitLoss: number;
}

/**
 * Settles a standard each-way bet: `stakePerPart` on the win part and
 * `stakePerPart` on the place part (total outlay = 2 * stakePerPart).
 */
export function settleEachWayBet(
  stakePerPart: number,
  winOddsDecimal: number,
  terms: EachWayTerms,
  outcome: { won: boolean; placed: boolean }
): EachWaySettlement {
  assertValidDecimalOdds(winOddsDecimal);
  assertValidEachWayTerms(terms);
  if (!Number.isFinite(stakePerPart) || stakePerPart <= 0) {
    throw new InvalidPlaceTermsError(`stakePerPart must be positive, got ${stakePerPart}`);
  }

  // A win also counts as a place for settlement purposes.
  const placed = outcome.won || outcome.placed;

  const winReturn = outcome.won ? stakePerPart * winOddsDecimal : 0;
  const placeReturn = placed ? stakePerPart * placeOddsDecimal(winOddsDecimal, terms.eachWayFraction) : 0;
  const totalReturn = winReturn + placeReturn;
  const totalStake = stakePerPart * 2;

  return {
    wonWinPart: outcome.won,
    placedPart: placed,
    totalReturn,
    profitLoss: totalReturn - totalStake,
  };
}

/**
 * Settles a win-only bet.
 */
export function settleWinBet(
  stake: number,
  winOddsDecimal: number,
  won: boolean
): { totalReturn: number; profitLoss: number } {
  assertValidDecimalOdds(winOddsDecimal);
  if (!Number.isFinite(stake) || stake <= 0) {
    throw new InvalidPlaceTermsError(`stake must be positive, got ${stake}`);
  }
  const totalReturn = won ? stake * winOddsDecimal : 0;
  return { totalReturn, profitLoss: totalReturn - stake };
}

/**
 * Whether a runner's finishing position counts as "placed" under a specific
 * bookmaker's terms. This is the only correct way to derive placeOutcome —
 * never hardcode `finishingPosition <= 3`.
 */
export function isPlacedUnderTerms(finishingPosition: number | null, terms: EachWayTerms): boolean {
  if (finishingPosition === null) return false;
  return finishingPosition >= 1 && finishingPosition <= terms.places;
}

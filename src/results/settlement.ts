/**
 * Result settlement.
 *
 * Converts a raw finishing position + starting price into the stored
 * ResultEntry fields (place outcome, profit/loss). This module never reads
 * or writes PredictionSnapshot rows — pre-race predictions are immutable
 * once locked, and settlement must not be able to alter them. See
 * `assertSnapshotMutable` below for the guard used by API routes.
 */

import { type EachWayTerms, isPlacedUnderTerms, settleEachWayBet, settleWinBet } from "@/value/place";

export class ImmutableSnapshotError extends Error {}

/**
 * Guards against ever overwriting a locked pre-race PredictionSnapshot.
 * Call this before any update to a PredictionSnapshot row. Snapshots are
 * locked by default (see schema) precisely so that results cannot
 * retroactively alter what the model said before the race.
 */
export function assertSnapshotMutable(snapshot: { isLocked: boolean }): void {
  if (snapshot.isLocked) {
    throw new ImmutableSnapshotError(
      "PredictionSnapshot is locked and cannot be modified. Pre-race predictions are immutable once recorded."
    );
  }
}

export interface RunnerResultInput {
  finishingPosition: number | null;
  finishStatus: string | null;
  startingPriceDecimal: number | null;
  /** Bookmaker place terms this settlement is judged against; null if none apply/available. */
  placeTerms: EachWayTerms | null;
  /** Notional stake used to express profit/loss as a per-point figure. Defaults to 1. */
  stake?: number;
}

export interface RunnerResultComputed {
  placeOutcome: boolean | null;
  profitLossWinStake: number | null;
  profitLossEachWayStake: number | null;
}

/**
 * Derives placeOutcome and profit/loss figures from a finishing position.
 * Returns nulls where the inputs don't allow a figure to be computed (e.g.
 * non-runner, or no starting price recorded yet).
 */
export function computeRunnerResult(input: RunnerResultInput): RunnerResultComputed {
  const stake = input.stake ?? 1;
  const won = input.finishingPosition === 1;

  const placeOutcome = input.placeTerms
    ? isPlacedUnderTerms(input.finishingPosition, input.placeTerms)
    : null;

  const profitLossWinStake =
    input.startingPriceDecimal != null
      ? settleWinBet(stake, input.startingPriceDecimal, won).profitLoss
      : null;

  const profitLossEachWayStake =
    input.startingPriceDecimal != null && input.placeTerms && placeOutcome != null
      ? settleEachWayBet(stake, input.startingPriceDecimal, input.placeTerms, {
          won,
          placed: placeOutcome,
        }).profitLoss
      : null;

  return { placeOutcome, profitLossWinStake, profitLossEachWayStake };
}

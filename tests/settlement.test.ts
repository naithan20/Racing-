import { describe, expect, it } from "vitest";

import { assertSnapshotMutable, computeRunnerResult, ImmutableSnapshotError } from "@/results/settlement";

describe("computeRunnerResult", () => {
  const terms = { places: 4, eachWayFraction: 0.2 };

  it("derives placeOutcome and profit/loss for a winner", () => {
    const result = computeRunnerResult({
      finishingPosition: 1,
      finishStatus: "WON",
      startingPriceDecimal: 6,
      placeTerms: terms,
    });
    expect(result.placeOutcome).toBe(true);
    expect(result.profitLossWinStake).toBeCloseTo(5, 10); // 1pt win stake at 6.0
    expect(result.profitLossEachWayStake).not.toBeNull();
  });

  it("derives a losing placeOutcome for a runner outside the paid places", () => {
    const result = computeRunnerResult({
      finishingPosition: 5,
      finishStatus: "RAN",
      startingPriceDecimal: 8,
      placeTerms: terms,
    });
    expect(result.placeOutcome).toBe(false);
    expect(result.profitLossWinStake).toBeCloseTo(-1, 10);
  });

  it("returns null placeOutcome when no place terms are available", () => {
    const result = computeRunnerResult({
      finishingPosition: 2,
      finishStatus: "RAN",
      startingPriceDecimal: 5,
      placeTerms: null,
    });
    expect(result.placeOutcome).toBeNull();
    expect(result.profitLossEachWayStake).toBeNull();
  });

  it("returns null profit/loss when starting price is unknown", () => {
    const result = computeRunnerResult({
      finishingPosition: 1,
      finishStatus: "WON",
      startingPriceDecimal: null,
      placeTerms: terms,
    });
    expect(result.profitLossWinStake).toBeNull();
    expect(result.profitLossEachWayStake).toBeNull();
  });

  it("respects a custom stake", () => {
    const result = computeRunnerResult({
      finishingPosition: 1,
      finishStatus: "WON",
      startingPriceDecimal: 3,
      placeTerms: terms,
      stake: 10,
    });
    expect(result.profitLossWinStake).toBeCloseTo(20, 10); // 10 * (3 - 1)
  });
});

describe("assertSnapshotMutable — prediction immutability guard", () => {
  it("throws when the snapshot is locked", () => {
    expect(() => assertSnapshotMutable({ isLocked: true })).toThrow(ImmutableSnapshotError);
  });

  it("allows mutation only when explicitly unlocked", () => {
    expect(() => assertSnapshotMutable({ isLocked: false })).not.toThrow();
  });
});

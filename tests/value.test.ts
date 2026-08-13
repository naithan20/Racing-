import { describe, expect, it } from "vitest";

import { assessValue, selectBestPlaceProbability, selectBestWinValue } from "@/value/engine";

describe("assessValue", () => {
  it("returns null when the model probability is not yet configured", () => {
    expect(assessValue(null, 5)).toBeNull();
    expect(assessValue(undefined, 5)).toBeNull();
  });

  it("computes a positive edge when model probability exceeds market implied probability", () => {
    // Market implies 25% (odds 4.0); model says 40% -> positive edge.
    const assessment = assessValue(0.4, 4);
    expect(assessment).not.toBeNull();
    expect(assessment!.marketImpliedProbability).toBeCloseTo(0.25, 10);
    expect(assessment!.valueEdgeAbsolute).toBeCloseTo(0.15, 10);
    expect(assessment!.hasPositiveEdge).toBe(true);
    expect(assessment!.fairOddsDecimal).toBeCloseTo(2.5, 10);
  });

  it("computes a negative edge when model probability is below market implied probability", () => {
    const assessment = assessValue(0.1, 4); // market implies 25%
    expect(assessment!.valueEdgeAbsolute).toBeLessThan(0);
    expect(assessment!.hasPositiveEdge).toBe(false);
  });
});

describe("selectBestWinValue", () => {
  it("returns null when no candidate has both a probability and a price", () => {
    expect(
      selectBestWinValue([{ runnerId: "a", winProbability: null, placeProbability: null, modelConfidence: null, winOddsDecimal: 5 }])
    ).toBeNull();
  });

  it("picks the candidate with the largest positive edge, not the shortest price", () => {
    const candidates = [
      { runnerId: "fav", winProbability: 0.3, placeProbability: null, modelConfidence: null, winOddsDecimal: 2.0 }, // implied 50%, edge -0.2
      { runnerId: "value", winProbability: 0.3, placeProbability: null, modelConfidence: null, winOddsDecimal: 5.0 }, // implied 20%, edge +0.1
    ];
    const best = selectBestWinValue(candidates);
    expect(best?.runnerId).toBe("value");
  });
});

describe("selectBestPlaceProbability", () => {
  it("picks the highest place probability regardless of price", () => {
    const candidates = [
      { runnerId: "a", winProbability: null, placeProbability: 0.4, modelConfidence: null, winOddsDecimal: 20 },
      { runnerId: "b", winProbability: null, placeProbability: 0.7, modelConfidence: null, winOddsDecimal: 2 },
    ];
    expect(selectBestPlaceProbability(candidates)?.runnerId).toBe("b");
  });

  it("returns null when nothing has a place probability", () => {
    expect(
      selectBestPlaceProbability([
        { runnerId: "a", winProbability: null, placeProbability: null, modelConfidence: null, winOddsDecimal: 2 },
      ])
    ).toBeNull();
  });
});

import { describe, expect, it } from "vitest";

import { brierScore, calibrationBuckets, logLoss, roiPercent } from "@/backtesting/scoring";

describe("brierScore", () => {
  it("is 0 for perfect predictions", () => {
    expect(brierScore([{ predictedProbability: 1, outcome: true }])).toBeCloseTo(0, 10);
    expect(brierScore([{ predictedProbability: 0, outcome: false }])).toBeCloseTo(0, 10);
  });

  it("is 1 for maximally wrong predictions", () => {
    expect(brierScore([{ predictedProbability: 1, outcome: false }])).toBeCloseTo(1, 10);
  });

  it("returns null for an empty set", () => {
    expect(brierScore([])).toBeNull();
  });
});

describe("logLoss", () => {
  it("is low for a confident correct prediction and high for a confident wrong one", () => {
    const goodLoss = logLoss([{ predictedProbability: 0.99, outcome: true }])!;
    const badLoss = logLoss([{ predictedProbability: 0.99, outcome: false }])!;
    expect(goodLoss).toBeLessThan(badLoss);
  });

  it("returns null for an empty set", () => {
    expect(logLoss([])).toBeNull();
  });
});

describe("calibrationBuckets", () => {
  it("buckets predictions and reports mean predicted vs observed frequency", () => {
    const buckets = calibrationBuckets(
      [
        { predictedProbability: 0.85, outcome: true },
        { predictedProbability: 0.82, outcome: false },
        { predictedProbability: 0.15, outcome: false },
      ],
      10
    );
    const highBucket = buckets.find((b) => b.bucketLabel === "80-90%")!;
    expect(highBucket.sampleSize).toBe(2);
    expect(highBucket.meanPredictedProbability).toBeCloseTo((0.85 + 0.82) / 2, 10);
    expect(highBucket.observedFrequency).toBeCloseTo(0.5, 10);
  });
});

describe("roiPercent", () => {
  it("computes percentage return on stake", () => {
    expect(roiPercent(100, 20)).toBeCloseTo(20, 10);
    expect(roiPercent(100, -35)).toBeCloseTo(-35, 10);
  });

  it("returns null for zero or negative total staked", () => {
    expect(roiPercent(0, 10)).toBeNull();
  });
});

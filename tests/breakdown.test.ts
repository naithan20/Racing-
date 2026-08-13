import { describe, expect, it } from "vitest";

import {
  ageBandLabel,
  confidenceBandLabel,
  distanceBandLabel,
  evidenceBandLabel,
  fieldSizeBandLabel,
  groupAndSummarize,
  oddsBandLabel,
  summarizeRows,
  type EvaluableRow,
} from "@/backtesting/breakdown";

describe("bucket label functions", () => {
  it("oddsBandLabel buckets correctly at boundaries", () => {
    expect(oddsBandLabel(1.5)).toContain("<2");
    expect(oddsBandLabel(2)).toBe("2-4");
    expect(oddsBandLabel(4)).toBe("4-8");
    expect(oddsBandLabel(8)).toBe("8-16");
    expect(oddsBandLabel(16)).toBe("16+");
    expect(oddsBandLabel(null)).toBeNull();
  });

  it("confidenceBandLabel buckets correctly", () => {
    expect(confidenceBandLabel(0.1)).toContain("low");
    expect(confidenceBandLabel(0.4)).toContain("mid-low");
    expect(confidenceBandLabel(0.6)).toContain("mid-high");
    expect(confidenceBandLabel(0.9)).toContain("high");
  });

  it("evidenceBandLabel spans very low to very high", () => {
    expect(evidenceBandLabel(0.05)).toBe("very low");
    expect(evidenceBandLabel(0.95)).toBe("very high");
  });

  it("distanceBandLabel classifies sprint vs staying", () => {
    expect(distanceBandLabel(6)).toContain("sprint");
    expect(distanceBandLabel(24)).toContain("staying");
  });

  it("ageBandLabel classifies young vs old", () => {
    expect(ageBandLabel(3)).toBe("2-3yo");
    expect(ageBandLabel(9)).toBe("8yo+");
  });

  it("fieldSizeBandLabel classifies small vs large fields", () => {
    expect(fieldSizeBandLabel(5)).toContain("small");
    expect(fieldSizeBandLabel(15)).toContain("large");
  });
});

describe("summarizeRows", () => {
  it("computes strike rate, expected/actual wins, and ROI from flat-stake backing", () => {
    const rows: EvaluableRow[] = [
      { winProbability: 0.5, won: true, startingPriceDecimal: 3 }, // profit +2
      { winProbability: 0.5, won: false, startingPriceDecimal: 4 }, // profit -1
    ];
    const summary = summarizeRows(rows);
    expect(summary.sampleSize).toBe(2);
    expect(summary.winStrikeRate).toBeCloseTo(0.5, 10);
    expect(summary.actualWins).toBe(1);
    expect(summary.expectedWins).toBeCloseTo(1.0, 10);
    // total staked = 2, total profit = 2 - 1 = 1 -> ROI 50%
    expect(summary.roiPercentValue).toBeCloseTo(50, 6);
  });

  it("handles an empty row set gracefully", () => {
    const summary = summarizeRows([]);
    expect(summary.sampleSize).toBe(0);
    expect(summary.winStrikeRate).toBeNull();
    expect(summary.roiPercentValue).toBeNull();
  });
});

describe("groupAndSummarize", () => {
  it("groups rows by the bucket function and summarizes each group independently", () => {
    const rows = [
      { winProbability: 0.5, won: true, startingPriceDecimal: 2, group: "A" },
      { winProbability: 0.2, won: false, startingPriceDecimal: 5, group: "A" },
      { winProbability: 0.9, won: true, startingPriceDecimal: 1.5, group: "B" },
    ];
    const buckets = groupAndSummarize(rows, (r) => r.group);
    expect(buckets.map((b) => b.bucketLabel)).toEqual(["A", "B"]);
    expect(buckets.find((b) => b.bucketLabel === "A")?.sampleSize).toBe(2);
    expect(buckets.find((b) => b.bucketLabel === "B")?.sampleSize).toBe(1);
  });

  it("excludes rows whose bucket function returns null", () => {
    const rows = [
      { winProbability: 0.5, won: true, startingPriceDecimal: 2, group: "A" },
      { winProbability: 0.5, won: true, startingPriceDecimal: 2, group: null },
    ];
    const buckets = groupAndSummarize(rows, (r) => r.group);
    expect(buckets).toHaveLength(1);
    expect(buckets[0].sampleSize).toBe(1);
  });
});

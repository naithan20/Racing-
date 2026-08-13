import { describe, expect, it } from "vitest";

import { BADGE_THRESHOLDS, computeRunnerBadges } from "@/lib/badges";

const baseInput = {
  valueEdgeAbsolute: null,
  modelConfidence: null,
  evidenceDensityScore: null,
  paceCollapseProbability: null,
  draw: null,
  fieldSize: 10,
};

describe("computeRunnerBadges", () => {
  it("flags HIGH_VALUE when the edge exceeds the threshold", () => {
    const badges = computeRunnerBadges({ ...baseInput, valueEdgeAbsolute: BADGE_THRESHOLDS.highValueEdge + 0.01 });
    expect(badges).toContain("HIGH_VALUE");
  });

  it("does not flag HIGH_VALUE at or below the threshold", () => {
    const atThreshold = computeRunnerBadges({ ...baseInput, valueEdgeAbsolute: BADGE_THRESHOLDS.highValueEdge });
    expect(atThreshold).not.toContain("HIGH_VALUE");
  });

  it("flags LOW_CONFIDENCE below the threshold, not at or above it", () => {
    const below = computeRunnerBadges({ ...baseInput, modelConfidence: BADGE_THRESHOLDS.lowConfidence - 0.01 });
    const at = computeRunnerBadges({ ...baseInput, modelConfidence: BADGE_THRESHOLDS.lowConfidence });
    expect(below).toContain("LOW_CONFIDENCE");
    expect(at).not.toContain("LOW_CONFIDENCE");
  });

  it("flags HIGH_EVIDENCE above the threshold", () => {
    const badges = computeRunnerBadges({ ...baseInput, evidenceDensityScore: BADGE_THRESHOLDS.highEvidenceDensity + 0.01 });
    expect(badges).toContain("HIGH_EVIDENCE");
  });

  it("flags PACE_RISK above the pace collapse threshold", () => {
    const badges = computeRunnerBadges({ ...baseInput, paceCollapseProbability: BADGE_THRESHOLDS.paceCollapseRisk + 0.01 });
    expect(badges).toContain("PACE_RISK");
  });

  it("flags DRAW_RISK only for extreme draws in large fields", () => {
    const extremeInLargeField = computeRunnerBadges({ ...baseInput, draw: 1, fieldSize: 16 });
    const extremeInSmallField = computeRunnerBadges({ ...baseInput, draw: 1, fieldSize: 6 });
    const middleInLargeField = computeRunnerBadges({ ...baseInput, draw: 8, fieldSize: 16 });

    expect(extremeInLargeField).toContain("DRAW_RISK");
    expect(extremeInSmallField).not.toContain("DRAW_RISK"); // field too small
    expect(middleInLargeField).not.toContain("DRAW_RISK"); // draw not extreme
  });

  it("returns no badges when every input is null/neutral", () => {
    expect(computeRunnerBadges(baseInput)).toEqual([]);
  });

  it("can return multiple badges at once", () => {
    const badges = computeRunnerBadges({
      valueEdgeAbsolute: 0.2,
      modelConfidence: 0.1,
      evidenceDensityScore: 0.9,
      paceCollapseProbability: 0.6,
      draw: 1,
      fieldSize: 16,
    });
    expect(badges).toEqual(
      expect.arrayContaining(["HIGH_VALUE", "LOW_CONFIDENCE", "HIGH_EVIDENCE", "PACE_RISK", "DRAW_RISK"])
    );
  });
});

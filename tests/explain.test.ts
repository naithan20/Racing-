import { describe, expect, it } from "vitest";

import { buildExplanation, type ExplanationInput } from "@/lib/explain";

const emptyRecord = { runs: 0, wins: 0, places: 0, winPercentage: null, placePercentage: null };

function baseInput(overrides: Partial<ExplanationInput> = {}): ExplanationInput {
  return {
    recentFinishingPositions: [],
    courseRecord: emptyRecord,
    distanceRecord: emptyRecord,
    goingRecord: emptyRecord,
    ratingMovement: null,
    currentOfficialRating: null,
    bestRecentOfficialRating: null,
    weightLbs: null,
    fieldWeightsLbs: [],
    relativeAccelerationIndex: null,
    fieldRelativeAccelerationIndices: [],
    finishingSpeedIndex: null,
    fieldFinishingSpeedIndices: [],
    firstTimeHeadgear: false,
    evidenceDensityScore: null,
    careerStartsToDate: 0,
    courseStartsToDate: 0,
    paceCollapseProbability: null,
    projectedRole: null,
    ...overrides,
  };
}

describe("buildExplanation", () => {
  it("cites competitive recent finishes when enough exist", () => {
    const result = buildExplanation(
      baseInput({
        recentFinishingPositions: [
          { position: 1, fieldSize: 8 },
          { position: 2, fieldSize: 8 },
          { position: 3, fieldSize: 8 },
          { position: 6, fieldSize: 8 },
        ],
      })
    );
    expect(result.positiveFactors.some((f) => f.includes("competitive"))).toBe(true);
  });

  it("does not cite competitive finishes when the window is too small", () => {
    const result = buildExplanation(
      baseInput({ recentFinishingPositions: [{ position: 1, fieldSize: 8 }] })
    );
    expect(result.positiveFactors.some((f) => f.includes("competitive"))).toBe(false);
  });

  it("cites a distance win record when there are enough runs and at least 2 wins", () => {
    const result = buildExplanation(
      baseInput({ distanceRecord: { runs: 5, wins: 2, places: 3, winPercentage: 0.4, placePercentage: 0.6 } })
    );
    expect(result.positiveFactors.some((f) => f.includes("distance"))).toBe(true);
  });

  it("flags a weak going record as negative when there is evidence but no placed finishes", () => {
    const result = buildExplanation(
      baseInput({ goingRecord: { runs: 3, wins: 0, places: 0, winPercentage: 0, placePercentage: 0 } })
    );
    expect(result.negativeFactors.some((f) => f.toLowerCase().includes("going"))).toBe(true);
  });

  it("flags a well-in rating as positive", () => {
    const result = buildExplanation(baseInput({ currentOfficialRating: 90, bestRecentOfficialRating: 95 }));
    expect(result.positiveFactors.some((f) => f.includes("below its best recent form"))).toBe(true);
  });

  it("does not flag well-in when the gap is below the threshold", () => {
    const result = buildExplanation(baseInput({ currentOfficialRating: 94, bestRecentOfficialRating: 95 }));
    expect(result.positiveFactors.some((f) => f.includes("below its best recent form"))).toBe(false);
  });

  it("flags weight advantage and disadvantage relative to the field", () => {
    const lighter = buildExplanation(baseInput({ weightLbs: 120, fieldWeightsLbs: [130, 130, 130, 130] }));
    const heavier = buildExplanation(baseInput({ weightLbs: 140, fieldWeightsLbs: [130, 130, 130, 130] }));
    expect(lighter.positiveFactors.some((f) => f.includes("less than today's field average"))).toBe(true);
    expect(heavier.negativeFactors.some((f) => f.includes("more than today's field average"))).toBe(true);
  });

  it("flags top-20% transition speed as positive and bottom-20% as negative", () => {
    const top = buildExplanation(
      baseInput({ relativeAccelerationIndex: 10, fieldRelativeAccelerationIndices: [1, 2, 3, 4, 5] })
    );
    const bottom = buildExplanation(
      baseInput({ relativeAccelerationIndex: 0, fieldRelativeAccelerationIndices: [1, 2, 3, 4, 5] })
    );
    expect(top.positiveFactors.some((f) => f.includes("Transition-speed"))).toBe(true);
    expect(bottom.negativeFactors.some((f) => f.includes("Transition-speed"))).toBe(true);
  });

  it("flags first-time headgear as both a negative factor and an uncertainty flag", () => {
    const result = buildExplanation(baseInput({ firstTimeHeadgear: true }));
    expect(result.negativeFactors.some((f) => f.includes("first time"))).toBe(true);
    expect(result.modelUncertainty.some((f) => f.includes("headgear"))).toBe(true);
  });

  it("flags low evidence density as model uncertainty", () => {
    const result = buildExplanation(baseInput({ evidenceDensityScore: 0.1, careerStartsToDate: 1 }));
    expect(result.modelUncertainty.some((f) => f.includes("prior run"))).toBe(true);
  });

  it("flags no course experience as model uncertainty", () => {
    const result = buildExplanation(baseInput({ courseStartsToDate: 0 }));
    expect(result.modelUncertainty.some((f) => f.includes("No previous run at this course"))).toBe(true);
  });

  it("returns empty arrays (not undefined) when nothing applies", () => {
    const result = buildExplanation(baseInput({ evidenceDensityScore: 0.9, courseStartsToDate: 2 }));
    expect(Array.isArray(result.positiveFactors)).toBe(true);
    expect(Array.isArray(result.negativeFactors)).toBe(true);
    expect(Array.isArray(result.modelUncertainty)).toBe(true);
  });
});

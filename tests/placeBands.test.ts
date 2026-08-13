import { describe, expect, it } from "vitest";

import { selectPlaceBand } from "@/value/placeBands";

describe("selectPlaceBand", () => {
  const bands = [
    { topN: 2, probabilityCalibrated: 0.2 },
    { topN: 3, probabilityCalibrated: 0.3 },
    { topN: 4, probabilityCalibrated: 0.4 },
    { topN: 5, probabilityCalibrated: 0.5 },
    { topN: 6, probabilityCalibrated: 0.6 },
  ];

  it("returns an exact match when available", () => {
    const result = selectPlaceBand(bands, 4);
    expect(result).toEqual({ probability: 0.4, topN: 4, exact: true });
  });

  it("falls back to the nearest band when no exact match exists", () => {
    const result = selectPlaceBand(bands, 1);
    expect(result?.exact).toBe(false);
    expect(result?.topN).toBe(2); // nearest to 1
  });

  it("falls back to the nearest band for a place count above the max modelled depth", () => {
    const result = selectPlaceBand(bands, 8);
    expect(result?.exact).toBe(false);
    expect(result?.topN).toBe(6); // nearest to 8
  });

  it("returns null when no bands are available", () => {
    expect(selectPlaceBand([], 3)).toBeNull();
  });

  it("picks the closer of two equidistant bands deterministically", () => {
    // 4.5 is equidistant between top4 (0.4) and top5 (0.5); either is a
    // defensible nearest match — assert it picks one of them, not neither.
    const result = selectPlaceBand(bands, 4.5);
    expect([4, 5]).toContain(result?.topN);
  });
});

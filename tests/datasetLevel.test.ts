import { describe, expect, it } from "vitest";

import { classifyDatasetLevel, datasetLevelLabel } from "@/lib/datasetLevel";

describe("classifyDatasetLevel", () => {
  it("is EXPERIMENTAL below 25,000 runners", () => {
    expect(classifyDatasetLevel(0)).toBe("EXPERIMENTAL");
    expect(classifyDatasetLevel(24_999)).toBe("EXPERIMENTAL");
  });

  it("is RESEARCH between 25,000 and 99,999 runners", () => {
    expect(classifyDatasetLevel(25_000)).toBe("RESEARCH");
    expect(classifyDatasetLevel(99_999)).toBe("RESEARCH");
  });

  it("is LARGE_RESEARCH at 100,000+ runners", () => {
    expect(classifyDatasetLevel(100_000)).toBe("LARGE_RESEARCH");
    expect(classifyDatasetLevel(1_000_000)).toBe("LARGE_RESEARCH");
  });
});

describe("datasetLevelLabel", () => {
  it("has a human label for every level", () => {
    expect(datasetLevelLabel("EXPERIMENTAL")).toBe("Experimental");
    expect(datasetLevelLabel("RESEARCH")).toBe("Research");
    expect(datasetLevelLabel("LARGE_RESEARCH")).toBe("Large research");
  });
});

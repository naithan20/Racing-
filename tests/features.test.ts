import { describe, expect, it } from "vitest";

import { FEATURE_DEFINITIONS, findFeatureDefinition } from "@/features/definitions";
import {
  buildFeatureRow,
  FeatureValueTypeMismatchError,
  readFeatureValue,
  UnknownFeatureKeyError,
} from "@/features/store";

describe("feature definitions", () => {
  it("has no duplicate keys", () => {
    const keys = FEATURE_DEFINITIONS.map((d) => d.key);
    expect(new Set(keys).size).toBe(keys.length);
  });

  it("covers each documented category", () => {
    const categories = new Set(FEATURE_DEFINITIONS.map((d) => d.category));
    expect(categories).toContain("PACE_POSITION_ACQUISITION");
    expect(categories).toContain("PACE_TRANSITION_SPEED");
    expect(categories).toContain("PACE_LATE_SUSTAINABILITY");
    expect(categories).toContain("EVIDENCE_UNCERTAINTY");
  });

  it("keeps pace concepts as distinct keys rather than one combined score", () => {
    expect(findFeatureDefinition("usual_early_position")).toBeDefined();
    expect(findFeatureDefinition("relative_acceleration_index")).toBeDefined();
    expect(findFeatureDefinition("finishing_speed_index")).toBeDefined();
    expect(findFeatureDefinition("combined_pace_score")).toBeUndefined();
  });
});

describe("buildFeatureRow", () => {
  it("builds a numeric row for a NUMERIC definition", () => {
    const row = buildFeatureRow("official_rating", { type: "NUMERIC", value: 142 });
    expect(row).toEqual({ key: "official_rating", numericValue: 142, textValue: null, booleanValue: null });
  });

  it("builds a boolean row for a BOOLEAN definition", () => {
    const row = buildFeatureRow("trainer_change_flag", { type: "BOOLEAN", value: true });
    expect(row).toEqual({ key: "trainer_change_flag", numericValue: null, textValue: null, booleanValue: true });
  });

  it("builds a text row for a TEXT definition", () => {
    const row = buildFeatureRow("recent_form_trend", { type: "TEXT", value: "improving" });
    expect(row).toEqual({ key: "recent_form_trend", numericValue: null, textValue: "improving", booleanValue: null });
  });

  it("rejects an unknown feature key", () => {
    expect(() => buildFeatureRow("not_a_real_feature", { type: "NUMERIC", value: 1 })).toThrow(
      UnknownFeatureKeyError
    );
  });

  it("rejects a value type that doesn't match the definition", () => {
    expect(() => buildFeatureRow("official_rating", { type: "TEXT", value: "high" })).toThrow(
      FeatureValueTypeMismatchError
    );
  });
});

describe("readFeatureValue", () => {
  it("reads back the stored value regardless of which column it was in", () => {
    expect(readFeatureValue({ key: "x", numericValue: 5, textValue: null, booleanValue: null })).toBe(5);
    expect(readFeatureValue({ key: "x", numericValue: null, textValue: "y", booleanValue: null })).toBe("y");
    expect(readFeatureValue({ key: "x", numericValue: null, textValue: null, booleanValue: false })).toBe(false);
    expect(readFeatureValue({ key: "x", numericValue: null, textValue: null, booleanValue: null })).toBeNull();
  });
});

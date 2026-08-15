import { describe, expect, it } from "vitest";

import {
  buildRoleToColumn,
  computeMappingProposal,
  DEFAULT_HANDICAP_TYPE,
  DEFAULT_SURFACE,
  mapRecordsToRaces,
  normalizeColumnName,
  proposeRole,
} from "@/lib/serverlessImport/columnMapper";

describe("normalizeColumnName", () => {
  it("lowercases and collapses non-alphanumerics to underscores", () => {
    expect(normalizeColumnName("Race Date")).toBe("race_date");
    expect(normalizeColumnName("Horse-Name!!")).toBe("horse_name");
    expect(normalizeColumnName("  OR ")).toBe("or");
  });
});

describe("proposeRole", () => {
  it("gives high confidence to an exact canonical name", () => {
    expect(proposeRole("race_date")).toEqual({ role: "race_date", confidence: "high" });
    expect(proposeRole("Course")).toEqual({ role: "course", confidence: "high" });
  });

  it("gives medium confidence to a substring match, preferring the longest token", () => {
    expect(proposeRole("horse_id_number")).toEqual({ role: "horse_id", confidence: "medium" });
  });

  it("gives low confidence to an ambiguous abbreviation", () => {
    expect(proposeRole("OR")).toEqual({ role: "official_rating", confidence: "low" });
    expect(proposeRole("SP")).toEqual({ role: "starting_price", confidence: "low" });
  });

  it("leaves an unrecognized column unmapped", () => {
    expect(proposeRole("some_totally_unknown_field")).toEqual({ role: null, confidence: "unmapped" });
  });
});

describe("computeMappingProposal", () => {
  const headers = ["race_date", "course", "OR", "unknown_field"];
  const records = [
    { race_date: "2020-01-01", course: "Ascot", OR: "85", unknown_field: "" },
    { race_date: "2020-01-02", course: "Newbury", OR: "90", unknown_field: "x" },
  ];

  it("separates auto-mapped (high confidence) from needs-review columns", () => {
    const proposal = computeMappingProposal(records, headers);
    expect(proposal.autoMappedCount).toBe(2); // race_date, course
    expect(proposal.columnsNeedingReview.map((c) => c.column)).toEqual(["OR"]);
  });

  it("collects up to 3 non-empty sample values", () => {
    const proposal = computeMappingProposal(records, headers);
    const orColumn = proposal.columns.find((c) => c.column === "OR");
    expect(orColumn?.sampleValues).toEqual(["85", "90"]);
  });
});

describe("buildRoleToColumn", () => {
  it("includes high-confidence columns without needing confirmation", () => {
    const roleToColumn = buildRoleToColumn([{ column: "race_date", proposedRole: "race_date", confidence: "high", sampleValues: [] }]);
    expect(roleToColumn).toEqual({ race_date: "race_date" });
  });

  it("excludes a non-high-confidence column that has not been confirmed", () => {
    const roleToColumn = buildRoleToColumn([{ column: "OR", proposedRole: "official_rating", confidence: "low", sampleValues: [] }]);
    expect(roleToColumn).toEqual({});
  });

  it("includes a non-high-confidence column once explicitly confirmed via an override", () => {
    const roleToColumn = buildRoleToColumn(
      [{ column: "OR", proposedRole: "official_rating", confidence: "low", sampleValues: [] }],
      { OR: { role: "official_rating", confirmed: true } }
    );
    expect(roleToColumn).toEqual({ official_rating: "OR" });
  });

  it("respects an override that corrects the role entirely", () => {
    const roleToColumn = buildRoleToColumn(
      [{ column: "pos", proposedRole: "finishing_position", confidence: "low", sampleValues: [] }],
      { pos: { role: "draw", confirmed: true } }
    );
    expect(roleToColumn).toEqual({ draw: "pos" });
  });
});

describe("mapRecordsToRaces", () => {
  const roleToColumn = {
    race_date: "date",
    race_time: "time",
    course: "track",
    horse_name: "runner",
    finishing_position: "pos",
    starting_price: "sp",
  };

  it("groups runner rows sharing (date, time, course) into one race", () => {
    const records = [
      { date: "2020-05-01", time: "14:30", track: "Ascot", runner: "Sample Star", pos: "1", sp: "3.5" },
      { date: "2020-05-01", time: "14:30", track: "Ascot", runner: "Second Runner", pos: "2", sp: "5.0" },
      { date: "2020-05-01", time: "15:05", track: "Ascot", runner: "Other Race Horse", pos: "1", sp: "2.0" },
    ];
    const { races, droppedRowCount } = mapRecordsToRaces(records, roleToColumn);
    expect(droppedRowCount).toBe(0);
    expect(races).toHaveLength(2);
    expect(races[0].runners).toHaveLength(2);
    expect(races[0].runners[0].horseName).toBe("Sample Star");
    expect(races[0].runners[0].finishingPosition).toBe(1);
    expect(races[0].runners[0].startingPriceDecimal).toBe(3.5);
  });

  it("applies the documented fixed defaults for surface and handicap type", () => {
    expect(DEFAULT_SURFACE).toBe("TURF");
    expect(DEFAULT_HANDICAP_TYPE).toBe("NON_HANDICAP");
  });

  it("infers flat_jumps from text, defaulting to FLAT when unmapped", () => {
    const withFlatJumps = mapRecordsToRaces(
      [{ date: "2020-05-01", time: "14:30", track: "Ascot", runner: "A", jumps_col: "National Hunt" }],
      { ...roleToColumn, flat_jumps: "jumps_col" }
    );
    expect(withFlatJumps.races[0].flatJumps).toBe("JUMPS");

    const withoutFlatJumps = mapRecordsToRaces(
      [{ date: "2020-05-01", time: "14:30", track: "Ascot", runner: "A" }],
      roleToColumn
    );
    expect(withoutFlatJumps.races[0].flatJumps).toBe("FLAT");
  });

  it("drops rows with an unparseable/missing race date rather than fabricating one", () => {
    const records = [{ date: "01/05/2020", time: "14:30", track: "Ascot", runner: "A" }]; // non-ISO date
    const { races, droppedRowCount } = mapRecordsToRaces(records, roleToColumn);
    expect(races).toHaveLength(0);
    expect(droppedRowCount).toBe(1);
  });

  it("drops rows with no mapped course", () => {
    const records = [{ date: "2020-05-01", time: "14:30", runner: "A" }];
    const { races, droppedRowCount } = mapRecordsToRaces(records, roleToColumn);
    expect(races).toHaveLength(0);
    expect(droppedRowCount).toBe(1);
  });

  it("groups by race_id when mapped, even if date/time/course repeat differently", () => {
    const records = [
      { rid: "R1", date: "2020-05-01", time: "14:30", track: "Ascot", runner: "A" },
      { rid: "R1", date: "2020-05-01", time: "14:30", track: "Ascot", runner: "B" },
      { rid: "R2", date: "2020-05-01", time: "14:30", track: "Ascot", runner: "C" },
    ];
    const { races } = mapRecordsToRaces(records, { ...roleToColumn, race_id: "rid" });
    expect(races).toHaveLength(2);
    expect(races[0].runners).toHaveLength(2);
    expect(races[1].runners).toHaveLength(1);
  });

  it("defaults numberOfRunners to the actual runner count when field_size isn't mapped", () => {
    const records = [
      { date: "2020-05-01", time: "14:30", track: "Ascot", runner: "A" },
      { date: "2020-05-01", time: "14:30", track: "Ascot", runner: "B" },
    ];
    const { races } = mapRecordsToRaces(records, roleToColumn);
    expect(races[0].numberOfRunners).toBe(2);
  });
});

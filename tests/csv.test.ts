import { describe, expect, it } from "vitest";

import { parseCsv, parseCsvToRecords } from "@/lib/csv";
import {
  CSV_IMPORT_TEMPLATE_HEADER,
  groupImportRowsByRace,
  validateCsvRecords,
} from "@/data/importSchema";

describe("parseCsv", () => {
  it("parses simple comma-separated rows", () => {
    const rows = parseCsv("a,b,c\n1,2,3\n");
    expect(rows).toEqual([
      ["a", "b", "c"],
      ["1", "2", "3"],
    ]);
  });

  it("handles quoted fields containing commas", () => {
    const rows = parseCsv('name,note\n"Sample Star","Good, honest sort"\n');
    expect(rows[1]).toEqual(["Sample Star", "Good, honest sort"]);
  });

  it("handles escaped quotes inside quoted fields", () => {
    const rows = parseCsv('name\n"Say ""hello"""\n');
    expect(rows[1]).toEqual(['Say "hello"']);
  });

  it("handles embedded newlines inside quoted fields", () => {
    const rows = parseCsv('name,comment\nA,"line one\nline two"\n');
    expect(rows[1]).toEqual(["A", "line one\nline two"]);
  });

  it("handles a file with no trailing newline", () => {
    const rows = parseCsv("a,b\n1,2");
    expect(rows).toEqual([
      ["a", "b"],
      ["1", "2"],
    ]);
  });
});

describe("parseCsvToRecords", () => {
  it("maps rows to header-keyed records", () => {
    const records = parseCsvToRecords("horse_name,age\nSample Star,5\n");
    expect(records).toEqual([{ horse_name: "Sample Star", age: "5" }]);
  });

  it("returns an empty array for header-only input", () => {
    expect(parseCsvToRecords("horse_name,age\n")).toEqual([]);
  });
});

describe("validateCsvRecords", () => {
  const validRecord = {
    race_date: "2026-08-13",
    race_time: "14:35",
    racecourse: "Ascot",
    country: "GB",
    race_name: "Test Chase",
    flat_jumps: "JUMPS",
    surface: "TURF",
    distance_furlongs: "24",
    handicap_type: "HANDICAP",
    number_of_runners: "8",
    horse_name: "Sample Star",
  };

  it("accepts a minimally valid row", () => {
    const { validRows, errors } = validateCsvRecords([validRecord]);
    expect(errors).toHaveLength(0);
    expect(validRows).toHaveLength(1);
    expect(validRows[0].distance_furlongs).toBe(24); // coerced to number
  });

  it("rejects a row missing a required field", () => {
    const withoutHorseName: Record<string, string> = { ...validRecord };
    delete withoutHorseName.horse_name;
    const { validRows, errors } = validateCsvRecords([withoutHorseName]);
    expect(validRows).toHaveLength(0);
    expect(errors).toHaveLength(1);
    expect(errors[0].row).toBe(2); // header + 1-indexed
  });

  it("rejects an invalid enum value", () => {
    const { validRows, errors } = validateCsvRecords([{ ...validRecord, flat_jumps: "SIDEWAYS" }]);
    expect(validRows).toHaveLength(0);
    expect(errors).toHaveLength(1);
  });

  it("reports one error per invalid row while keeping valid rows", () => {
    const invalid: Record<string, string> = { ...validRecord };
    delete invalid.horse_name;
    const { validRows, errors } = validateCsvRecords([validRecord, invalid]);
    expect(validRows).toHaveLength(1);
    expect(errors).toHaveLength(1);
  });
});

describe("groupImportRowsByRace", () => {
  it("groups multiple runner rows sharing date/time/course into one race", () => {
    const { validRows } = validateCsvRecords([
      {
        race_date: "2026-08-13",
        race_time: "14:35",
        racecourse: "Ascot",
        country: "GB",
        race_name: "Test Chase",
        flat_jumps: "JUMPS",
        surface: "TURF",
        distance_furlongs: "24",
        handicap_type: "HANDICAP",
        number_of_runners: "2",
        horse_name: "Sample Star",
      },
      {
        race_date: "2026-08-13",
        race_time: "14:35",
        racecourse: "Ascot",
        country: "GB",
        race_name: "Test Chase",
        flat_jumps: "JUMPS",
        surface: "TURF",
        distance_furlongs: "24",
        handicap_type: "HANDICAP",
        number_of_runners: "2",
        horse_name: "Second Runner",
      },
    ]);

    const races = groupImportRowsByRace(validRows);
    expect(races).toHaveLength(1);
    expect(races[0].runners).toHaveLength(2);
    expect(races[0].runners.map((r) => r.horseName)).toEqual(["Sample Star", "Second Runner"]);
  });

  it("keeps the template header and validator in sync", () => {
    const headerKeys = CSV_IMPORT_TEMPLATE_HEADER.split(",");
    const { errors } = validateCsvRecords([
      Object.fromEntries(headerKeys.map((k) => [k, ""])) as Record<string, string>,
    ]);
    // All fields blank should fail on the required ones, not throw/crash.
    expect(errors.length).toBeGreaterThan(0);
  });
});

/**
 * Data import schema — Phase 1.
 *
 * RacingEdge supports three input paths: manual entry through the UI, CSV
 * import, and JSON import. This module is the single source of truth for
 * what a valid import row/document looks like, and is used by both the CSV
 * and JSON import routes so validation never drifts between the two.
 *
 * CSV format: one row per RUNNER. Race-level fields are repeated on every
 * row belonging to that race; rows sharing the same
 * (race_date, race_time, racecourse) are grouped into a single race.
 *
 * JSON format: `{ "races": [ { ...race fields, "runners": [ ... ] } ] }`.
 *
 * Nothing in this module invents probabilities or scores — it only shapes
 * and validates raw inputs.
 */

import { z } from "zod";

export const FLAT_JUMPS_VALUES = ["FLAT", "JUMPS"] as const;
export const SURFACE_VALUES = ["TURF", "ALL_WEATHER", "DIRT"] as const;
export const HANDICAP_TYPE_VALUES = ["HANDICAP", "NON_HANDICAP"] as const;

const numberFromString = z
  .union([z.string(), z.number()])
  .transform((v) => (typeof v === "string" ? v.trim() : v))
  .refine((v) => v !== "", { message: "must not be empty" })
  .transform((v) => Number(v))
  .refine((v) => Number.isFinite(v), { message: "must be a valid number" });

const optionalNumberFromString = z
  .union([z.string(), z.number()])
  .optional()
  .transform((v) => (v === undefined || v === "" ? undefined : Number(v)))
  .refine((v) => v === undefined || Number.isFinite(v), { message: "must be a valid number" });

const optionalBooleanFromString = z
  .union([z.string(), z.boolean()])
  .optional()
  .transform((v) => {
    if (v === undefined || v === "") return undefined;
    if (typeof v === "boolean") return v;
    return ["true", "1", "yes", "y"].includes(v.trim().toLowerCase());
  });

/** One row of a runner-level CSV import. */
export const RaceCardImportRowSchema = z.object({
  race_date: z.string().min(1, "race_date is required"),
  race_time: z.string().min(1, "race_time is required"),
  racecourse: z.string().min(1, "racecourse is required"),
  country: z.string().min(1, "country is required"),
  race_name: z.string().min(1, "race_name is required"),
  flat_jumps: z.enum(FLAT_JUMPS_VALUES),
  surface: z.enum(SURFACE_VALUES),
  distance_furlongs: numberFromString,
  race_class: optionalNumberFromString,
  grade_group: z.string().optional(),
  handicap_type: z.enum(HANDICAP_TYPE_VALUES),
  age_restriction: z.string().optional(),
  sex_restriction: z.string().optional(),
  number_of_runners: numberFromString,
  going: z.string().optional(),
  each_way_fraction: optionalNumberFromString,
  bookmaker_places: optionalNumberFromString,

  horse_name: z.string().min(1, "horse_name is required"),
  horse_country_bred: z.string().optional(),
  age: optionalNumberFromString,
  sex: z.string().optional(),
  sire_name: z.string().optional(),
  dam_name: z.string().optional(),
  damsire_name: z.string().optional(),

  draw: optionalNumberFromString,
  cloth_number: optionalNumberFromString,
  weight_lbs: optionalNumberFromString,
  official_rating: optionalNumberFromString,
  jockey_name: z.string().optional(),
  jockey_claim_lbs: optionalNumberFromString,
  trainer_name: z.string().optional(),
  headgear: z.string().optional(),
  first_time_headgear: optionalBooleanFromString,
  days_since_last_run: optionalNumberFromString,
  current_odds_decimal: optionalNumberFromString,
  starting_price_decimal: optionalNumberFromString,
});

export type RaceCardImportRow = z.infer<typeof RaceCardImportRowSchema>;

/** JSON import: race + nested runners. */
export const RunnerImportSchema = z.object({
  horseName: z.string().min(1),
  horseCountryBred: z.string().optional(),
  age: z.number().optional(),
  sex: z.string().optional(),
  sireName: z.string().optional(),
  damName: z.string().optional(),
  damsireName: z.string().optional(),
  draw: z.number().optional(),
  clothNumber: z.number().optional(),
  weightLbs: z.number().optional(),
  officialRating: z.number().optional(),
  jockeyName: z.string().optional(),
  jockeyClaimLbs: z.number().optional(),
  trainerName: z.string().optional(),
  headgear: z.string().optional(),
  firstTimeHeadgear: z.boolean().optional(),
  daysSinceLastRun: z.number().optional(),
  currentOddsDecimal: z.number().optional(),
  startingPriceDecimal: z.number().optional(),
});

export const RaceImportSchema = z.object({
  raceDate: z.string().min(1),
  raceTime: z.string().min(1),
  racecourse: z.string().min(1),
  country: z.string().min(1),
  raceName: z.string().min(1),
  flatJumps: z.enum(FLAT_JUMPS_VALUES),
  surface: z.enum(SURFACE_VALUES),
  distanceFurlongs: z.number(),
  raceClass: z.number().optional(),
  gradeGroup: z.string().optional(),
  handicapType: z.enum(HANDICAP_TYPE_VALUES),
  ageRestriction: z.string().optional(),
  sexRestriction: z.string().optional(),
  numberOfRunners: z.number(),
  going: z.string().optional(),
  eachWayFraction: z.number().optional(),
  bookmakerPlaces: z.number().optional(),
  runners: z.array(RunnerImportSchema).min(1, "at least one runner is required"),
});

export const JsonImportDocumentSchema = z.object({
  races: z.array(RaceImportSchema).min(1, "at least one race is required"),
});

export type RaceImport = z.infer<typeof RaceImportSchema>;
export type RunnerImport = z.infer<typeof RunnerImportSchema>;
export type JsonImportDocument = z.infer<typeof JsonImportDocumentSchema>;

export interface RowValidationError {
  row: number;
  message: string;
}

export interface CsvValidationResult {
  validRows: RaceCardImportRow[];
  errors: RowValidationError[];
}

/** Validates raw CSV records (already header-keyed) against the import schema. */
export function validateCsvRecords(records: Record<string, string>[]): CsvValidationResult {
  const validRows: RaceCardImportRow[] = [];
  const errors: RowValidationError[] = [];

  records.forEach((record, index) => {
    const result = RaceCardImportRowSchema.safeParse(record);
    if (result.success) {
      validRows.push(result.data);
    } else {
      const message = result.error.issues
        .map((issue) => `${issue.path.join(".")}: ${issue.message}`)
        .join("; ");
      errors.push({ row: index + 2, message }); // +2 = header row + 1-indexing
    }
  });

  return { validRows, errors };
}

/** Groups validated CSV rows (one per runner) back into race + runners. */
export function groupImportRowsByRace(rows: RaceCardImportRow[]): RaceImport[] {
  const races = new Map<string, RaceImport>();

  for (const row of rows) {
    const key = `${row.race_date}|${row.race_time}|${row.racecourse}`;
    let race = races.get(key);
    if (!race) {
      race = {
        raceDate: row.race_date,
        raceTime: row.race_time,
        racecourse: row.racecourse,
        country: row.country,
        raceName: row.race_name,
        flatJumps: row.flat_jumps,
        surface: row.surface,
        distanceFurlongs: row.distance_furlongs,
        raceClass: row.race_class,
        gradeGroup: row.grade_group,
        handicapType: row.handicap_type,
        ageRestriction: row.age_restriction,
        sexRestriction: row.sex_restriction,
        numberOfRunners: row.number_of_runners,
        going: row.going,
        eachWayFraction: row.each_way_fraction,
        bookmakerPlaces: row.bookmaker_places,
        runners: [],
      };
      races.set(key, race);
    }

    race.runners.push({
      horseName: row.horse_name,
      horseCountryBred: row.horse_country_bred,
      age: row.age,
      sex: row.sex,
      sireName: row.sire_name,
      damName: row.dam_name,
      damsireName: row.damsire_name,
      draw: row.draw,
      clothNumber: row.cloth_number,
      weightLbs: row.weight_lbs,
      officialRating: row.official_rating,
      jockeyName: row.jockey_name,
      jockeyClaimLbs: row.jockey_claim_lbs,
      trainerName: row.trainer_name,
      headgear: row.headgear,
      firstTimeHeadgear: row.first_time_headgear,
      daysSinceLastRun: row.days_since_last_run,
      currentOddsDecimal: row.current_odds_decimal,
      startingPriceDecimal: row.starting_price_decimal,
    });
  }

  return Array.from(races.values());
}

export const CSV_IMPORT_TEMPLATE_HEADER = [
  "race_date",
  "race_time",
  "racecourse",
  "country",
  "race_name",
  "flat_jumps",
  "surface",
  "distance_furlongs",
  "race_class",
  "grade_group",
  "handicap_type",
  "age_restriction",
  "sex_restriction",
  "number_of_runners",
  "going",
  "each_way_fraction",
  "bookmaker_places",
  "horse_name",
  "horse_country_bred",
  "age",
  "sex",
  "sire_name",
  "dam_name",
  "damsire_name",
  "draw",
  "cloth_number",
  "weight_lbs",
  "official_rating",
  "jockey_name",
  "jockey_claim_lbs",
  "trainer_name",
  "headgear",
  "first_time_headgear",
  "days_since_last_run",
  "current_odds_decimal",
  "starting_price_decimal",
].join(",");

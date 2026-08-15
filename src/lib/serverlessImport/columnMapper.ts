/**
 * Column-role heuristics + row mapping for the serverless ("one-tap")
 * import pipeline — a faithful TypeScript port of
 * `python/racingedge_data/inspector.py`'s `ROLE_RULES`/`propose_role` and
 * `python/racingedge_data/importers/free_dataset_importer.py`'s row ->
 * race/runner defaulting logic, so an arbitrary free CSV (unknown exact
 * column names — Kaggle download, a pasted URL, Betfair SP export) gets the
 * SAME mapping confidence and the SAME defaulting behaviour whether it runs
 * through the Python CLI pipeline or this Node pipeline. Kept in sync by
 * hand (there's no shared runtime between Python and Node here) — if you
 * change one, change the other.
 *
 * Nothing here fabricates or infers a MISSING field's value. A canonical
 * field with no plausible source column is left undefined for every row,
 * exactly like the Python importer.
 */

export type MappingConfidence = "high" | "medium" | "low" | "unmapped";

interface RoleRule {
  exact: string[];
  contains: string[];
  abbrev: string[];
}

// Ported 1:1 from inspector.py's ROLE_RULES.
const ROLE_RULES: Record<string, RoleRule> = {
  race_id: { exact: ["race_id", "raceid", "event_id"], contains: ["race_id"], abbrev: ["rid"] },
  race_date: { exact: ["race_date", "date", "meeting_date"], contains: ["race_date", "off_date"], abbrev: [] },
  race_time: { exact: ["race_time", "off_time"], contains: ["race_time", "off_time"], abbrev: ["off"] },
  course: { exact: ["course", "track", "venue"], contains: ["course", "track", "venue"], abbrev: [] },
  country: { exact: ["country", "region"], contains: ["country"], abbrev: [] },
  race_name: { exact: ["race_name"], contains: ["race_name"], abbrev: [] },
  race_type: { exact: ["race_type", "type"], contains: ["race_type"], abbrev: [] },
  race_class: { exact: ["race_class", "class"], contains: ["race_class"], abbrev: ["rclass"] },
  distance: {
    exact: ["distance", "distance_f", "distance_furlongs", "distance_yards", "distance_m"],
    contains: ["distance", "dist_"],
    abbrev: ["dist"],
  },
  going: { exact: ["going", "ground"], contains: ["going"], abbrev: [] },
  flat_jumps: { exact: ["flat_jumps", "discipline", "code"], contains: ["flat_jumps"], abbrev: [] },
  field_size: {
    exact: ["field_size", "number_of_runners", "num_runners"],
    contains: ["field_size", "num_runners"],
    abbrev: ["nr"],
  },
  horse_name: { exact: ["horse_name", "horse", "runner_name", "runner"], contains: ["horse"], abbrev: [] },
  horse_id: { exact: ["horse_id", "horseid"], contains: ["horse_id"], abbrev: [] },
  draw: { exact: ["draw", "stall_number"], contains: ["draw"], abbrev: ["stall"] },
  weight: { exact: ["weight", "weight_lbs"], contains: ["weight"], abbrev: ["lbs", "wgt"] },
  age: { exact: ["age"], contains: ["age"], abbrev: [] },
  sex: { exact: ["sex", "gender"], contains: ["sex"], abbrev: [] },
  official_rating: {
    exact: ["official_rating", "rating"],
    contains: ["official_rating", "rating"],
    abbrev: ["or", "ofr"],
  },
  jockey: { exact: ["jockey", "jockey_name"], contains: ["jockey"], abbrev: [] },
  trainer: { exact: ["trainer", "trainer_name"], contains: ["trainer"], abbrev: [] },
  sire: { exact: ["sire", "sire_name"], contains: ["sire"], abbrev: [] },
  dam: { exact: ["dam", "dam_name"], contains: ["dam"], abbrev: [] },
  damsire: { exact: ["damsire"], contains: ["damsire"], abbrev: [] },
  headgear: { exact: ["headgear", "equipment"], contains: ["headgear"], abbrev: ["hg"] },
  finishing_position: {
    exact: ["finishing_position", "finish_position", "position"],
    contains: ["finish_pos", "finishing_position"],
    abbrev: ["pos", "place"],
  },
  beaten_distance: {
    exact: ["beaten_distance", "distance_beaten"],
    contains: ["beaten_distance", "beaten"],
    abbrev: ["btn"],
  },
  starting_price: {
    exact: ["starting_price", "starting_price_decimal", "sp_decimal"],
    contains: ["starting_price"],
    abbrev: ["sp", "odds", "price"],
  },
  bsp: { exact: ["bsp", "betfair_sp"], contains: ["bsp"], abbrev: [] },
  comment: { exact: ["comment", "comments"], contains: ["comment"], abbrev: ["note"] },
  sectional: { exact: ["sectional", "sectionals", "sectional_times"], contains: ["sectional"], abbrev: ["split"] },
  non_runner: { exact: ["non_runner", "withdrawn"], contains: ["non_runner"], abbrev: ["nr_flag"] },
};

export const CANONICAL_ROLES = Object.keys(ROLE_RULES);

export function normalizeColumnName(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export function proposeRole(columnName: string): { role: string | null; confidence: MappingConfidence } {
  const normalized = normalizeColumnName(columnName);
  if (!normalized) return { role: null, confidence: "unmapped" };

  for (const [role, rules] of Object.entries(ROLE_RULES)) {
    if (rules.exact.includes(normalized)) return { role, confidence: "high" };
  }

  // Among "contains" matches, prefer the longest matching token (e.g.
  // "horse_id_number" resolves to horse_id, not horse_name).
  let best: { role: string; token: string } | null = null;
  for (const [role, rules] of Object.entries(ROLE_RULES)) {
    for (const token of rules.contains) {
      if (normalized.includes(token) && (best === null || token.length > best.token.length)) {
        best = { role, token };
      }
    }
  }
  if (best) return { role: best.role, confidence: "medium" };

  for (const [role, rules] of Object.entries(ROLE_RULES)) {
    if (rules.abbrev.includes(normalized)) return { role, confidence: "low" };
  }

  return { role: null, confidence: "unmapped" };
}

export interface ProposedColumn {
  column: string;
  proposedRole: string | null;
  confidence: MappingConfidence;
  sampleValues: string[];
}

export interface MappingProposal {
  columns: ProposedColumn[];
  autoMappedCount: number;
  columnsNeedingReview: ProposedColumn[];
}

/** Profiles every header in a parsed CSV and proposes a role for each — the Node equivalent of inspector.py's `_profile_dataframe` (minus dtype/likely_kind, which this pipeline doesn't need). */
export function computeMappingProposal(records: Record<string, string>[], headers: string[]): MappingProposal {
  const columns: ProposedColumn[] = headers.map((column) => {
    const { role, confidence } = proposeRole(column);
    const sampleValues: string[] = [];
    for (const record of records) {
      const value = record[column];
      if (value !== undefined && value !== "" && sampleValues.length < 3) sampleValues.push(value.slice(0, 60));
      if (sampleValues.length >= 3) break;
    }
    return { column, proposedRole: role, confidence, sampleValues };
  });

  const autoMapped = columns.filter((c) => c.proposedRole !== null && c.confidence === "high");
  const needsReview = columns.filter((c) => c.proposedRole !== null && c.confidence !== "high");

  return { columns, autoMappedCount: autoMapped.length, columnsNeedingReview: needsReview };
}

// ---------------------------------------------------------------------------
// Row mapping — column-role mapping -> canonical race/runner rows
// ---------------------------------------------------------------------------

export interface MappedRunner {
  horseName: string;
  sex?: string;
  sireName?: string;
  damName?: string;
  damsireName?: string;
  draw?: number;
  weightLbs?: number;
  officialRating?: number;
  jockeyName?: string;
  trainerName?: string;
  headgear?: string;
  nonRunner: boolean;
  finishingPosition?: number;
  beatenDistanceLengths?: number;
  startingPriceDecimal?: number;
  bspDecimal?: number;
}

export interface MappedRace {
  raceDate: Date;
  raceTime: string;
  racecourse: string;
  country: string;
  raceName: string;
  raceType?: string;
  flatJumps: "FLAT" | "JUMPS";
  distanceFurlongs: number;
  raceClass?: number;
  numberOfRunners: number;
  going?: string;
  runners: MappedRunner[];
}

/** Builds `role -> column` from a mapping proposal, applying any human review updates. Matches free_dataset_importer.load_and_validate_mapping's filter: a column is used only if its role is set AND (confidence is "high" OR it's been explicitly confirmed). */
export function buildRoleToColumn(
  columns: ProposedColumn[],
  reviewOverrides?: Record<string, { role: string | null; confirmed: boolean }>
): Record<string, string> {
  const roleToColumn: Record<string, string> = {};
  for (const col of columns) {
    const override = reviewOverrides?.[col.column];
    const role = override ? override.role : col.proposedRole;
    const confirmed = override ? override.confirmed : col.confidence === "high";
    if (role === null || role === undefined) continue;
    if (col.confidence !== "high" && !confirmed) continue;
    roleToColumn[role] = col.column;
  }
  return roleToColumn;
}

/** Strict ISO 8601 only — matches csv_provider.parse_race_date's behaviour exactly (no guessing between DD/MM and MM/DD for ambiguous formats). Returns null (never fabricates a date) if unparseable. */
function parseRaceDate(value: string): Date | null {
  const trimmed = value.trim();
  if (!/^\d{4}-\d{2}-\d{2}/.test(trimmed)) return null;
  const date = new Date(trimmed);
  return Number.isNaN(date.getTime()) ? null : date;
}

function asNumber(value: string | undefined): number | undefined {
  if (value === undefined || value.trim() === "") return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

function asString(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  const trimmed = value.trim();
  return trimmed === "" ? undefined : trimmed;
}

function get(record: Record<string, string>, roleToColumn: Record<string, string>, role: string): string | undefined {
  const column = roleToColumn[role];
  if (column === undefined) return undefined;
  return record[column];
}

function raceGroupKey(record: Record<string, string>, roleToColumn: Record<string, string>): string {
  const raceId = get(record, roleToColumn, "race_id");
  if (raceId) return `id:${raceId}`;
  const date = get(record, roleToColumn, "race_date") ?? "";
  const time = get(record, roleToColumn, "race_time") ?? "";
  const course = get(record, roleToColumn, "course") ?? "";
  return `composite:${date}|${time}|${course}`;
}

function rowToRunner(record: Record<string, string>, roleToColumn: Record<string, string>): MappedRunner | null {
  const horseName = asString(get(record, roleToColumn, "horse_name"));
  if (!horseName) return null;

  const nonRunnerRaw = asString(get(record, roleToColumn, "non_runner"));
  const nonRunner = nonRunnerRaw ? ["true", "1", "yes", "y"].includes(nonRunnerRaw.toLowerCase()) : false;

  return {
    horseName,
    sex: asString(get(record, roleToColumn, "sex")),
    sireName: asString(get(record, roleToColumn, "sire")),
    damName: asString(get(record, roleToColumn, "dam")),
    damsireName: asString(get(record, roleToColumn, "damsire")),
    draw: asNumber(get(record, roleToColumn, "draw")),
    weightLbs: asNumber(get(record, roleToColumn, "weight")),
    officialRating: asNumber(get(record, roleToColumn, "official_rating")),
    jockeyName: asString(get(record, roleToColumn, "jockey")),
    trainerName: asString(get(record, roleToColumn, "trainer")),
    headgear: asString(get(record, roleToColumn, "headgear")),
    nonRunner,
    finishingPosition: asNumber(get(record, roleToColumn, "finishing_position")),
    beatenDistanceLengths: asNumber(get(record, roleToColumn, "beaten_distance")),
    startingPriceDecimal: asNumber(get(record, roleToColumn, "starting_price")),
    bspDecimal: asNumber(get(record, roleToColumn, "bsp")),
  };
}

/** Ported from free_dataset_importer._row_to_race: surface and handicap_type have no canonical role at all (free datasets essentially never carry a clean column for either) so they are FIXED, DOCUMENTED defaults — never inferred — exactly matching the Python importer. Callers that need a different default (e.g. a source known to be all-weather) can post-process the result; this function never guesses from context. */
export const DEFAULT_SURFACE = "TURF" as const;
export const DEFAULT_HANDICAP_TYPE = "NON_HANDICAP" as const;

function rowToRace(
  firstRecord: Record<string, string>,
  roleToColumn: Record<string, string>,
  runners: MappedRunner[]
): MappedRace | null {
  const rawDate = get(firstRecord, roleToColumn, "race_date");
  if (!rawDate) return null;
  const raceDate = parseRaceDate(rawDate);
  if (!raceDate) return null;

  const course = asString(get(firstRecord, roleToColumn, "course"));
  if (!course) return null;

  const raceTime = asString(get(firstRecord, roleToColumn, "race_time")) ?? "00:00";
  const flatJumpsRaw = (asString(get(firstRecord, roleToColumn, "flat_jumps")) ?? "flat").toLowerCase();
  const flatJumps: "FLAT" | "JUMPS" =
    flatJumpsRaw.includes("jump") || ["nh", "national hunt"].includes(flatJumpsRaw) ? "JUMPS" : "FLAT";

  return {
    raceDate,
    raceTime,
    racecourse: course,
    country: asString(get(firstRecord, roleToColumn, "country")) ?? "",
    raceName: asString(get(firstRecord, roleToColumn, "race_name")) ?? `${course} ${raceDate.toISOString().slice(0, 10)}`,
    raceType: asString(get(firstRecord, roleToColumn, "race_type")),
    flatJumps,
    distanceFurlongs: asNumber(get(firstRecord, roleToColumn, "distance")) ?? 0,
    raceClass: asNumber(get(firstRecord, roleToColumn, "race_class")),
    numberOfRunners: asNumber(get(firstRecord, roleToColumn, "field_size")) ?? runners.length,
    going: asString(get(firstRecord, roleToColumn, "going")),
    runners,
  };
}

/** Groups mapped rows (one per runner, race fields repeated) back into races — the Node equivalent of MappedTableProvider.fetch_races' grouping loop. Rows whose race can't be built (missing course/unparseable date) are silently dropped, matching Python's `_flush()` returning None on ValueError; the caller should report the drop count. */
export function mapRecordsToRaces(
  records: Record<string, string>[],
  roleToColumn: Record<string, string>
): { races: MappedRace[]; droppedRowCount: number } {
  const races: MappedRace[] = [];
  let droppedRowCount = 0;

  let currentKey: string | null = null;
  let currentFirstRecord: Record<string, string> | null = null;
  let currentRunners: MappedRunner[] = [];

  const flush = () => {
    if (currentFirstRecord === null) return;
    const race = rowToRace(currentFirstRecord, roleToColumn, currentRunners);
    if (race) races.push(race);
    else droppedRowCount += currentRunners.length || 1;
  };

  for (const record of records) {
    const key = raceGroupKey(record, roleToColumn);
    if (key !== currentKey) {
      flush();
      currentKey = key;
      currentFirstRecord = record;
      currentRunners = [];
    }
    const runner = rowToRunner(record, roleToColumn);
    if (runner) currentRunners.push(runner);
  }
  flush();

  return { races, droppedRowCount };
}

import { CSV_IMPORT_TEMPLATE_HEADER } from "@/data/importSchema";

const EXAMPLE_ROW_FIELDS = [
  "2026-08-13", // race_date
  "14:35", // race_time
  "Ascot", // racecourse
  "GB", // country
  "Example Handicap Chase", // race_name
  "JUMPS", // flat_jumps
  "TURF", // surface
  "24", // distance_furlongs
  "3", // race_class
  "", // grade_group
  "HANDICAP", // handicap_type
  "5yo+", // age_restriction
  "", // sex_restriction
  "8", // number_of_runners
  "Good to Soft", // going
  "0.2", // each_way_fraction
  "4", // bookmaker_places
  "Example Horse", // horse_name
  "IRE", // horse_country_bred
  "8", // age
  "GELDING", // sex
  "", // sire_name
  "", // dam_name
  "", // damsire_name
  "4", // draw
  "1", // cloth_number
  "154", // weight_lbs
  "142", // official_rating
  "R. Jockey", // jockey_name
  "", // jockey_claim_lbs
  "J. Trainer", // trainer_name
  "", // headgear
  "", // first_time_headgear
  "", // days_since_last_run
  "4.5", // current_odds_decimal
  "", // starting_price_decimal
];

const EXAMPLE_ROW = EXAMPLE_ROW_FIELDS.join(",");

export function GET() {
  const body = `${CSV_IMPORT_TEMPLATE_HEADER}\n${EXAMPLE_ROW}\n`;
  return new Response(body, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": 'attachment; filename="racingedge-import-template.csv"',
    },
  });
}

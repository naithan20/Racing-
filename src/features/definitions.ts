/**
 * Canonical Feature Store definitions.
 *
 * This is the flexible, self-describing feature catalogue referenced in the
 * project brief. It intentionally does NOT assign weights or combine
 * features into a score — it only documents what each feature key means, its
 * category and its value type, so a future model has a stable input surface
 * to read from.
 *
 * Seeded into FeatureDefinition by prisma/seed.ts. Extend this list as new
 * features are identified; never repurpose an existing key's meaning.
 */

import { FeatureCategory, FeatureValueType } from "@/generated/prisma/enums";

export interface FeatureDefinitionSeed {
  key: string;
  category: FeatureCategory;
  label: string;
  description: string;
  valueType: FeatureValueType;
  unit?: string;
}

export const FEATURE_DEFINITIONS: FeatureDefinitionSeed[] = [
  // --- CURRENT ABILITY ---
  {
    key: "recent_form_trend",
    category: FeatureCategory.CURRENT_ABILITY,
    label: "Recent form trend",
    description: "Direction of recent finishing/rating trend across the last N runs.",
    valueType: FeatureValueType.TEXT,
  },
  {
    key: "recent_finishing_positions",
    category: FeatureCategory.CURRENT_ABILITY,
    label: "Recent finishing positions",
    description: "Encoded sequence of the horse's most recent finishing positions.",
    valueType: FeatureValueType.TEXT,
  },
  {
    key: "weighted_recent_form_rating",
    category: FeatureCategory.CURRENT_ABILITY,
    label: "Weighted recent form rating",
    description: "Recency-weighted average of recent performance ratings.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "form_consistency_index",
    category: FeatureCategory.CURRENT_ABILITY,
    label: "Consistency",
    description: "Dispersion of recent performance ratings; lower = more consistent.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "improvement_decline_trajectory",
    category: FeatureCategory.CURRENT_ABILITY,
    label: "Improvement/decline trajectory",
    description: "Slope of performance ratings over recent runs.",
    valueType: FeatureValueType.NUMERIC,
  },

  // --- CLASS ---
  {
    key: "current_class",
    category: FeatureCategory.CLASS,
    label: "Current class",
    description: "Class level of today's race.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "class_movement",
    category: FeatureCategory.CLASS,
    label: "Class rise/drop",
    description: "Change in class versus the horse's previous run (positive = rise).",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "performance_by_class",
    category: FeatureCategory.CLASS,
    label: "Performance by class",
    description: "Historical strike rate/rating at this class level.",
    valueType: FeatureValueType.TEXT,
  },
  {
    key: "previous_race_strength",
    category: FeatureCategory.CLASS,
    label: "Strength of previous races",
    description: "Quality index of the fields the horse has recently run against.",
    valueType: FeatureValueType.NUMERIC,
  },

  // --- HANDICAP ---
  {
    key: "official_rating",
    category: FeatureCategory.HANDICAP,
    label: "Official rating",
    description: "Current official handicap mark.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "rating_movement",
    category: FeatureCategory.HANDICAP,
    label: "Rating movement",
    description: "Change in official rating since the last run.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "mark_vs_last_winning_mark",
    category: FeatureCategory.HANDICAP,
    label: "Mark vs last winning mark",
    description: "Difference between the current mark and the mark last won off.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "mark_vs_peak_mark",
    category: FeatureCategory.HANDICAP,
    label: "Mark vs peak performance",
    description: "Difference between the current mark and the horse's career-best mark.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "penalty_lbs",
    category: FeatureCategory.HANDICAP,
    label: "Penalty",
    description: "Weight penalty applied for a qualifying win, in lbs.",
    valueType: FeatureValueType.NUMERIC,
    unit: "lbs",
  },
  {
    key: "well_in_status",
    category: FeatureCategory.HANDICAP,
    label: "Well-in status",
    description: "Whether the horse is assessed as favourably treated by the handicapper.",
    valueType: FeatureValueType.BOOLEAN,
  },

  // --- WEIGHT ---
  {
    key: "weight_carried_lbs",
    category: FeatureCategory.WEIGHT,
    label: "Actual weight carried",
    description: "Total weight carried today, in lbs.",
    valueType: FeatureValueType.NUMERIC,
    unit: "lbs",
  },
  {
    key: "weight_relative_to_field",
    category: FeatureCategory.WEIGHT,
    label: "Weight relative to field",
    description: "Weight carried relative to the field average.",
    valueType: FeatureValueType.NUMERIC,
    unit: "lbs",
  },
  {
    key: "weight_for_age_allowance",
    category: FeatureCategory.WEIGHT,
    label: "Weight-for-age allowance",
    description: "Allowance received/given based on age versus field.",
    valueType: FeatureValueType.NUMERIC,
    unit: "lbs",
  },
  {
    key: "jockey_claim_lbs",
    category: FeatureCategory.WEIGHT,
    label: "Jockey claim",
    description: "Apprentice/conditional claim deducted from the weight.",
    valueType: FeatureValueType.NUMERIC,
    unit: "lbs",
  },

  // --- COURSE ---
  {
    key: "course_win_percentage",
    category: FeatureCategory.COURSE,
    label: "Course win %",
    description: "Win percentage at this course.",
    valueType: FeatureValueType.NUMERIC,
    unit: "%",
  },
  {
    key: "course_place_percentage",
    category: FeatureCategory.COURSE,
    label: "Course place %",
    description: "Place percentage at this course.",
    valueType: FeatureValueType.NUMERIC,
    unit: "%",
  },
  {
    key: "course_distance_record",
    category: FeatureCategory.COURSE,
    label: "Course-distance record",
    description: "Record specifically at this course and distance combination.",
    valueType: FeatureValueType.TEXT,
  },

  // --- DISTANCE ---
  {
    key: "distance_win_percentage",
    category: FeatureCategory.DISTANCE,
    label: "Distance win %",
    description: "Win percentage at today's distance.",
    valueType: FeatureValueType.NUMERIC,
    unit: "%",
  },
  {
    key: "distance_place_percentage",
    category: FeatureCategory.DISTANCE,
    label: "Distance place %",
    description: "Place percentage at today's distance.",
    valueType: FeatureValueType.NUMERIC,
    unit: "%",
  },
  {
    key: "distance_change_furlongs",
    category: FeatureCategory.DISTANCE,
    label: "Distance change",
    description: "Change in distance versus the horse's previous run, in furlongs.",
    valueType: FeatureValueType.NUMERIC,
    unit: "furlongs",
  },
  {
    key: "stamina_speed_suitability",
    category: FeatureCategory.DISTANCE,
    label: "Stamina/speed suitability",
    description: "Assessed suitability of today's distance to the horse's profile.",
    valueType: FeatureValueType.TEXT,
  },

  // --- GROUND ---
  {
    key: "going_win_percentage",
    category: FeatureCategory.GROUND,
    label: "Going win %",
    description: "Win percentage on today's going.",
    valueType: FeatureValueType.NUMERIC,
    unit: "%",
  },
  {
    key: "going_place_percentage",
    category: FeatureCategory.GROUND,
    label: "Going place %",
    description: "Place percentage on today's going.",
    valueType: FeatureValueType.NUMERIC,
    unit: "%",
  },
  {
    key: "changing_ground_conditions",
    category: FeatureCategory.GROUND,
    label: "Changing ground conditions",
    description: "Whether the going has materially changed since declarations.",
    valueType: FeatureValueType.BOOLEAN,
  },
  {
    key: "surface_preference",
    category: FeatureCategory.GROUND,
    label: "Surface preference",
    description: "Turf/all-weather/dirt preference indicated by past form.",
    valueType: FeatureValueType.CATEGORY,
  },

  // --- DRAW ---
  {
    key: "draw_number",
    category: FeatureCategory.DRAW,
    label: "Draw number",
    description: "Starting stall number.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "draw_percentile",
    category: FeatureCategory.DRAW,
    label: "Draw percentile within field",
    description: "Draw expressed as a percentile of today's field size.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "draw_bias_course_distance_fieldsize",
    category: FeatureCategory.DRAW,
    label: "Historical draw bias",
    description: "Historical draw bias for this exact course/distance/field-size combination.",
    valueType: FeatureValueType.TEXT,
  },
  {
    key: "draw_running_style_interaction",
    category: FeatureCategory.DRAW,
    label: "Draw x running style interaction",
    description: "Interaction between draw position and the horse's likely running style.",
    valueType: FeatureValueType.TEXT,
  },

  // --- PACE: POSITION ACQUISITION ---
  {
    key: "usual_early_position",
    category: FeatureCategory.PACE_POSITION_ACQUISITION,
    label: "Usual early position",
    description: "Typical early-race running position.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "quick_break_ability",
    category: FeatureCategory.PACE_POSITION_ACQUISITION,
    label: "Ability to break quickly",
    description: "Assessed ability to break well from the stalls/start.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "slow_start_frequency",
    category: FeatureCategory.PACE_POSITION_ACQUISITION,
    label: "Frequency of slow starts",
    description: "Proportion of recent runs featuring a slow start.",
    valueType: FeatureValueType.NUMERIC,
    unit: "%",
  },
  {
    key: "energy_cost_of_position",
    category: FeatureCategory.PACE_POSITION_ACQUISITION,
    label: "Energy required to obtain preferred position",
    description: "Relative energy expenditure typically needed to reach the preferred early position.",
    valueType: FeatureValueType.NUMERIC,
  },

  // --- PACE: TRANSITION SPEED ---
  {
    key: "position_change_3f_to_2f",
    category: FeatureCategory.PACE_TRANSITION_SPEED,
    label: "Position change 3f -> 2f",
    description: "Change in running position between the 3-furlong and 2-furlong markers.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "position_change_2f_to_1f",
    category: FeatureCategory.PACE_TRANSITION_SPEED,
    label: "Position change 2f -> 1f",
    description: "Change in running position between the 2-furlong and 1-furlong markers.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "relative_acceleration_index",
    category: FeatureCategory.PACE_TRANSITION_SPEED,
    label: "Relative acceleration",
    description: "Relative speed during the mid-race acceleration phase versus the field.",
    valueType: FeatureValueType.NUMERIC,
  },

  // --- PACE: LATE SUSTAINABILITY ---
  {
    key: "finishing_speed_index",
    category: FeatureCategory.PACE_LATE_SUSTAINABILITY,
    label: "Finishing speed",
    description: "Sustained speed in the closing stages of the race.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "position_change_final_furlong",
    category: FeatureCategory.PACE_LATE_SUSTAINABILITY,
    label: "Position change final furlong",
    description: "Change in running position across the final furlong.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "weakens_late_rate",
    category: FeatureCategory.PACE_LATE_SUSTAINABILITY,
    label: "Tendency to weaken late",
    description: "Proportion of recent runs where the horse weakened in the closing stages.",
    valueType: FeatureValueType.NUMERIC,
    unit: "%",
  },
  {
    key: "stays_on_strongly_rate",
    category: FeatureCategory.PACE_LATE_SUSTAINABILITY,
    label: "Tendency to stay on strongly",
    description: "Proportion of recent runs where the horse finished strongly.",
    valueType: FeatureValueType.NUMERIC,
    unit: "%",
  },

  // --- PACE: RACE SHAPE (field-level context) ---
  {
    key: "likely_early_pace",
    category: FeatureCategory.PACE_RACE_SHAPE,
    label: "Likely early pace",
    description: "Assessed overall early pace of today's race.",
    valueType: FeatureValueType.CATEGORY,
  },
  {
    key: "competition_for_lead",
    category: FeatureCategory.PACE_RACE_SHAPE,
    label: "Competition for the lead",
    description: "Number/strength of confirmed pace horses contesting the lead.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "pace_pressure_index",
    category: FeatureCategory.PACE_RACE_SHAPE,
    label: "Pace pressure",
    description: "Overall pressure on the early pace across the whole field.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "pace_collapse_probability",
    category: FeatureCategory.PACE_RACE_SHAPE,
    label: "Pace collapse probability",
    description: "Likelihood the early pace collapses, favouring hold-up runners.",
    valueType: FeatureValueType.NUMERIC,
  },

  // --- TRAINER / JOCKEY ---
  {
    key: "trainer_form_strike_rate",
    category: FeatureCategory.TRAINER_JOCKEY,
    label: "Trainer form",
    description: "Trainer strike rate over a recent rolling window.",
    valueType: FeatureValueType.NUMERIC,
    unit: "%",
  },
  {
    key: "jockey_form_strike_rate",
    category: FeatureCategory.TRAINER_JOCKEY,
    label: "Jockey form",
    description: "Jockey strike rate over a recent rolling window.",
    valueType: FeatureValueType.NUMERIC,
    unit: "%",
  },
  {
    key: "trainer_jockey_combo_strike_rate",
    category: FeatureCategory.TRAINER_JOCKEY,
    label: "Trainer/jockey combination",
    description: "Strike rate for this specific trainer-jockey pairing.",
    valueType: FeatureValueType.NUMERIC,
    unit: "%",
  },
  {
    key: "trainer_course_record",
    category: FeatureCategory.TRAINER_JOCKEY,
    label: "Trainer course record",
    description: "Trainer's record at today's course.",
    valueType: FeatureValueType.TEXT,
  },
  {
    key: "jockey_course_record",
    category: FeatureCategory.TRAINER_JOCKEY,
    label: "Jockey course record",
    description: "Jockey's record at today's course.",
    valueType: FeatureValueType.TEXT,
  },
  {
    key: "trainer_change_flag",
    category: FeatureCategory.TRAINER_JOCKEY,
    label: "Trainer change",
    description: "Whether the horse has changed trainers since its last run.",
    valueType: FeatureValueType.BOOLEAN,
  },
  {
    key: "runs_for_current_trainer",
    category: FeatureCategory.TRAINER_JOCKEY,
    label: "Runs for current trainer",
    description: "Number of runs the horse has had under its current trainer.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "seasonal_pattern_flag",
    category: FeatureCategory.TRAINER_JOCKEY,
    label: "Seasonal pattern",
    description: "Whether the horse/trainer shows a notable seasonal pattern.",
    valueType: FeatureValueType.TEXT,
  },
  {
    key: "layoff_days",
    category: FeatureCategory.TRAINER_JOCKEY,
    label: "Layoff",
    description: "Days since the horse's previous run.",
    valueType: FeatureValueType.NUMERIC,
    unit: "days",
  },
  {
    key: "quick_turnaround_flag",
    category: FeatureCategory.TRAINER_JOCKEY,
    label: "Quick turnaround",
    description: "Whether today's run follows an unusually quick turnaround.",
    valueType: FeatureValueType.BOOLEAN,
  },

  // --- HEADGEAR / EQUIPMENT ---
  {
    key: "first_time_headgear_flag",
    category: FeatureCategory.HEADGEAR_EQUIPMENT,
    label: "First-time headgear",
    description: "Whether the horse is wearing a piece of headgear for the first time.",
    valueType: FeatureValueType.BOOLEAN,
  },
  {
    key: "previous_headgear_response",
    category: FeatureCategory.HEADGEAR_EQUIPMENT,
    label: "Previous response to same headgear",
    description: "How the horse performed the last time it wore the same headgear.",
    valueType: FeatureValueType.TEXT,
  },
  {
    key: "wind_surgery_flag",
    category: FeatureCategory.HEADGEAR_EQUIPMENT,
    label: "Gelding / wind surgery",
    description: "Whether the horse has been gelded or had wind surgery, if known.",
    valueType: FeatureValueType.TEXT,
  },

  // --- PEDIGREE ---
  {
    key: "pedigree_distance_preference",
    category: FeatureCategory.PEDIGREE,
    label: "Pedigree distance preference",
    description: "Distance preference suggested by sire/damsire progeny statistics.",
    valueType: FeatureValueType.TEXT,
  },
  {
    key: "pedigree_ground_preference",
    category: FeatureCategory.PEDIGREE,
    label: "Pedigree ground preference",
    description: "Going preference suggested by sire/damsire progeny statistics.",
    valueType: FeatureValueType.TEXT,
  },
  {
    key: "age_development_curve",
    category: FeatureCategory.PEDIGREE,
    label: "Age development curve",
    description: "Expected stage of physical/experience development for the horse's age.",
    valueType: FeatureValueType.TEXT,
  },
  {
    key: "race_experience_count",
    category: FeatureCategory.PEDIGREE,
    label: "Race experience",
    description: "Total number of career starts.",
    valueType: FeatureValueType.NUMERIC,
  },

  // --- EVIDENCE / UNCERTAINTY ---
  {
    key: "evidence_density_score",
    category: FeatureCategory.EVIDENCE_UNCERTAINTY,
    label: "Evidence density",
    description:
      "How much reliable historical information exists for this horse. High evidence density means higher confidence in the estimate — it does NOT imply a higher win probability.",
    valueType: FeatureValueType.NUMERIC,
  },
  {
    key: "model_uncertainty_note",
    category: FeatureCategory.EVIDENCE_UNCERTAINTY,
    label: "Uncertainty note",
    description: "Free-text note on specific sources of uncertainty for this runner.",
    valueType: FeatureValueType.TEXT,
  },
];

export function findFeatureDefinition(key: string): FeatureDefinitionSeed | undefined {
  return FEATURE_DEFINITIONS.find((definition) => definition.key === key);
}

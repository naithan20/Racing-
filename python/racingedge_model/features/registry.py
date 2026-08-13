"""Feature metadata registry.

Documents, per feature GROUP (not one entry per individual feature — with
~140 features that would be pure repetition), what the group's features
mean, how they're calculated, what DB fields they read, and how missing
data is handled. This is the auditability requirement: anyone should be
able to look up any feature key here and see exactly where its value came
from and what it means when absent.

`FEATURE_SET_VERSION` (config.py) should be bumped whenever a calculation
method changes materially.
"""

from __future__ import annotations

from racingedge_model.features import (
    age_experience,
    class_features,
    course_distance_going,
    current_form,
    draw,
    evidence,
    headgear_changes,
    pace,
    rating,
    trainer_jockey,
    weight,
)

FEATURE_GROUPS = [
    {
        "group": "current_form",
        "category": "CURRENT_ABILITY",
        "calculation_method": (
            "Rolling/windowed statistics (last 3/5/10 runs) over the horse's own "
            "prior FormEntry rows, sorted most-recent-first. Includes recency-"
            "weighted percentile (exponential decay, 3-run half-life), simple "
            "linear-regression trend slopes, and layoff flags from the current "
            "race's declared daysSinceLastRun."
        ),
        "source_fields": [
            "FormEntry.finishingPosition", "FormEntry.fieldSize",
            "FormEntry.beatenDistanceLengths", "FormEntry.finishingSpeedPercentage",
            "FormEntry.raceDate", "Runner.daysSinceLastRun",
        ],
        "missing_behaviour": (
            "All rate/trend features are NaN when the horse has zero prior runs "
            "(first_time_out_flag=1). Count features (wins/places-in-last-N) "
            "default to 0 once starts>0, since 0 is a genuine observed fact, "
            "not a missing value."
        ),
        "feature_keys": current_form.FEATURE_KEYS,
    },
    {
        "group": "rating",
        "category": "HANDICAP",
        "calculation_method": (
            "Official rating vs the pre-race declared field (percentile, gap to "
            "mean/top); mark movement vs prior FormEntry ratings; heuristic "
            "'well-in' flag (current OR >= 3lb below the horse's best mark in "
            "its last 5 runs)."
        ),
        "source_fields": ["Runner.officialRating (whole declared field)", "FormEntry.officialRating", "Race.handicapType"],
        "missing_behaviour": (
            "NaN when this runner has no official rating declared. 'penalty_lbs' "
            "is not modelled anywhere upstream and always returns 0 with "
            "penalty_lbs_available=0, rather than silently implying no penalty."
        ),
        "feature_keys": rating.FEATURE_KEYS,
    },
    {
        "group": "weight",
        "category": "WEIGHT",
        "calculation_method": (
            "Declared weight vs the pre-race field (percentile, gap to mean/top "
            "weight); jockey claim netted off for effective weight."
        ),
        "source_fields": ["Runner.weightLbsTotal (whole declared field)", "Runner.jockeyClaimLbs", "Runner.ageAtRace"],
        "missing_behaviour": (
            "NaN when weight is not declared. weight_for_age_allowance is not "
            "modelled (no conditions-book data in this schema) and always "
            "returns 0 with weight_for_age_allowance_available=0."
        ),
        "feature_keys": weight.FEATURE_KEYS,
    },
    {
        "group": "class",
        "category": "CLASS",
        "calculation_method": (
            "Class movement vs the most recent prior run (sign convention: "
            "class 1 = highest quality, so class_change = prev - current; "
            "positive = risen in class). Success/place rate restricted to prior "
            "runs at the SAME class; class-adjusted recent form restricted to "
            "prior runs at this class or harder."
        ),
        "source_fields": ["Race.raceClass", "FormEntry.raceClass", "FormEntry.finishingPosition"],
        "missing_behaviour": "NaN when raceClass is unset on today's race, or when there are no prior runs at a comparable class.",
        "feature_keys": class_features.FEATURE_KEYS,
    },
    {
        "group": "course_distance_going",
        "category": "COURSE",  # also covers DISTANCE and GROUND
        "calculation_method": (
            "Record (starts/wins/places/rates) filtered to prior FormEntry rows "
            "matching today's course, distance (±1.5f band), and going exactly. "
            "Going similarity is a recency-weighted average of "
            "1 - |going-softness difference| across prior runs. Surface record "
            "is approximated via flat/jumps type, since FormEntry does not "
            "capture turf-vs-all-weather explicitly."
        ),
        "source_fields": [
            "FormEntry.course", "FormEntry.distanceFurlongs", "FormEntry.going",
            "FormEntry.flatJumps", "FormEntry.officialRating",
        ],
        "missing_behaviour": (
            "Counts default to 0 with zero prior evidence; rate features (win "
            "%, place %) are NaN rather than 0 when starts=0, since a 0% rate "
            "implies evidence of failure, not absence of evidence. "
            "stamina_uncertainty_flag defaults to 1 (uncertain) when there is "
            "no prior distance evidence at all."
        ),
        "feature_keys": course_distance_going.FEATURE_KEYS,
    },
    {
        "group": "draw",
        "category": "DRAW",
        "calculation_method": (
            "Draw percentile/bucket within today's declared field. Draw bias is "
            f"computed from the GLOBAL (all-horses) prior-runs table, bucketed "
            "by (course, 2-furlong distance band, field-size band), and is only "
            "reported when the bucket has at least MIN_SAMPLES_DRAW_BIAS prior "
            "runs — see config.py."
        ),
        "source_fields": ["Runner.draw (whole declared field)", "Race.numberOfRunners", "global prior Runner/Race/Result history"],
        "missing_behaviour": (
            "draw_bias_win_rate is NaN and draw_bias_available=0 whenever the "
            "relevant course/distance/field-size bucket has fewer than "
            "MIN_SAMPLES_DRAW_BIAS prior runs — this is a hard gate, not a soft "
            "preference, per the project brief."
        ),
        "feature_keys": draw.FEATURE_KEYS,
    },
    {
        "group": "pace",
        "category": "PACE_POSITION_ACQUISITION",  # spans all 4 PACE_* categories
        "calculation_method": (
            "Position acquisition / transition speed / late sustainability are "
            "each derived independently from the horse's own prior FormEntry "
            "position3fOut/2fOut/1fOut and finishingPosition fields, expressed "
            "as percentile-of-field to be comparable across different field "
            "sizes. These three concepts are never combined into a single pace "
            "score. Race-shape features instead use TODAY's declared field's "
            "RunnerPaceProfile.projectedRole values (legitimate pre-race "
            "information about the whole field)."
        ),
        "source_fields": [
            "FormEntry.position3fOut/position2fOut/position1fOut/finishingPosition/fieldSize",
            "RunnerPaceProfile.projectedRole (today's declared field)",
        ],
        "missing_behaviour": (
            "pace_features_available=0 when the horse has fewer than "
            "MIN_RUNS_FOR_PACE_FEATURES prior runs with positional data; "
            "individual sub-features are NaN rather than defaulted, so a model "
            "can distinguish 'no pace history' from 'flat pace tendency'."
        ),
        "feature_keys": pace.FEATURE_KEYS,
    },
    {
        "group": "trainer_jockey",
        "category": "TRAINER_JOCKEY",
        "calculation_method": (
            "Rolling win-rate over trailing 14/30-day windows before the race "
            "date, computed from the GLOBAL prior-runs table (needs trainer/"
            "jockey identity across ALL horses, not just this one). Every rate "
            "is smoothed towards a population prior with "
            "TRAINER_JOCKEY_SMOOTHING_PRIOR_RUNS virtual runs — see "
            "features/common.py:smoothed_rate."
        ),
        "source_fields": ["Runner.trainerName", "Runner.jockeyName", "Race.date", "Race.racecourse", "global prior Runner/Race/Result history"],
        "missing_behaviour": (
            "Run counts are 0 (a true fact) when a trainer/jockey has no prior "
            "runs in the window; smoothed rates fall back to the population "
            "prior rather than an undefined 0/0 rate."
        ),
        "feature_keys": trainer_jockey.FEATURE_KEYS,
    },
    {
        "group": "headgear_changes",
        "category": "HEADGEAR_EQUIPMENT",
        "calculation_method": (
            "First-time/repeated headgear read directly from the declared "
            "Runner row. Prior response to the SAME headgear code computed "
            "from FormEntry. Trainer-change detection compares today's "
            "declared trainer against the trainer recorded on this horse's "
            "most recent prior run in the global history table (FormEntry has "
            "no trainer field)."
        ),
        "source_fields": ["Runner.headgear", "Runner.firstTimeHeadgear", "FormEntry.headgear", "global prior Runner.trainerName for this horse"],
        "missing_behaviour": (
            "wind_surgery_flag is not modelled anywhere in this schema/dataset "
            "and always returns 0 with wind_surgery_flag_available=0."
        ),
        "feature_keys": headgear_changes.FEATURE_KEYS,
    },
    {
        "group": "age_experience",
        "category": "PEDIGREE",  # closest existing FeatureCategory to "age/experience"
        "calculation_method": (
            "Declared age; career start count and 12-month start count from "
            "prior FormEntry rows; experience banding via fixed thresholds "
            "(unraced / <=3 lightly-raced / <=9 moderate / 10+ exposed)."
        ),
        "source_fields": ["Runner.ageAtRace", "FormEntry.raceDate", "Race.flatJumps", "Race.distanceFurlongs"],
        "missing_behaviour": "horse_age is NaN if not declared; experience counts default to 0 for an unraced horse.",
        "feature_keys": age_experience.FEATURE_KEYS,
    },
    {
        "group": "evidence",
        "category": "EVIDENCE_UNCERTAINTY",
        "calculation_method": (
            "Transparent weighted sum of 7 sub-scores (career starts, recent "
            "starts, course/distance evidence, sectional/comment/rating-history "
            "availability, trainer/jockey sample adequacy) — see "
            "features/evidence.py module docstring for exact weights. This is "
            "evidence CONFIDENCE, not win probability — the two are "
            "deliberately independent."
        ),
        "source_fields": ["derived from current_form/course_distance_going/trainer_jockey outputs"],
        "missing_behaviour": "Never NaN — a horse with zero history simply scores at the floor of the scale (near 0).",
        "feature_keys": evidence.FEATURE_KEYS,
    },
]


def all_feature_keys() -> list[str]:
    keys: list[str] = []
    for group in FEATURE_GROUPS:
        keys.extend(group["feature_keys"])
    return keys


def feature_group_for(key: str) -> dict | None:
    for group in FEATURE_GROUPS:
        if key in group["feature_keys"]:
            return group
    return None

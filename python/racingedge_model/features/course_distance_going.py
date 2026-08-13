"""COURSE, DISTANCE and GOING/SURFACE features.

All computed from the horse's own prior FormEntry rows (already filtered to
raceDate < as_of_date by the caller).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from racingedge_model.features.common import record_summary
from racingedge_model.going import going_softness_index

DISTANCE_TOLERANCE_FURLONGS = 1.5

FEATURE_KEYS = [
    "course_starts",
    "course_wins",
    "course_places",
    "course_win_rate",
    "course_place_rate",
    "course_distance_starts",
    "course_distance_wins",
    "course_distance_places",
    "distance_starts",
    "distance_wins",
    "distance_places",
    "distance_win_rate",
    "distance_place_rate",
    "distance_change_furlongs",
    "best_recent_or_near_distance",
    "stamina_uncertainty_flag",
    "going_starts",
    "going_wins",
    "going_places",
    "going_win_rate",
    "going_place_rate",
    "going_similarity_score",
    "going_change_flag",
    "race_type_starts",
    "race_type_wins",
    "race_type_places",
    "race_type_win_rate",
    "race_type_place_rate",
]


def compute_course_distance_going_features(
    horse_prior_form: pd.DataFrame,
    course: str,
    distance_furlongs: float,
    going: str | None,
    flat_jumps: str,
) -> dict:
    out: dict = {k: np.nan for k in FEATURE_KEYS}
    n = len(horse_prior_form)
    if n == 0:
        # No prior evidence at all — every count is legitimately 0, and every
        # rate is legitimately "unavailable" (NaN), not 0. This is the
        # "evidence density" distinction in feature form.
        for count_key in (
            "course_starts", "course_wins", "course_places",
            "course_distance_starts", "course_distance_wins", "course_distance_places",
            "distance_starts", "distance_wins", "distance_places",
            "going_starts", "going_wins", "going_places",
            "race_type_starts", "race_type_wins", "race_type_places",
        ):
            out[count_key] = 0
        return out

    course_form = horse_prior_form[horse_prior_form["course"] == course]
    course_rec = record_summary(course_form)
    out["course_starts"] = course_rec.starts
    out["course_wins"] = course_rec.wins
    out["course_places"] = course_rec.places
    out["course_win_rate"] = course_rec.win_rate_raw if course_rec.available else np.nan
    out["course_place_rate"] = course_rec.place_rate_raw if course_rec.available else np.nan

    within_distance = horse_prior_form["distanceFurlongs"].sub(distance_furlongs).abs() <= DISTANCE_TOLERANCE_FURLONGS
    distance_form = horse_prior_form[within_distance]
    distance_rec = record_summary(distance_form)
    out["distance_starts"] = distance_rec.starts
    out["distance_wins"] = distance_rec.wins
    out["distance_places"] = distance_rec.places
    out["distance_win_rate"] = distance_rec.win_rate_raw if distance_rec.available else np.nan
    out["distance_place_rate"] = distance_rec.place_rate_raw if distance_rec.available else np.nan

    cd_form = course_form[course_form["distanceFurlongs"].sub(distance_furlongs).abs() <= DISTANCE_TOLERANCE_FURLONGS]
    cd_rec = record_summary(cd_form)
    out["course_distance_starts"] = cd_rec.starts
    out["course_distance_wins"] = cd_rec.wins
    out["course_distance_places"] = cd_rec.places

    out["distance_change_furlongs"] = float(distance_furlongs - horse_prior_form["distanceFurlongs"].iloc[0])
    max_prior_distance = horse_prior_form["distanceFurlongs"].max()
    if pd.notna(max_prior_distance):
        near_max = horse_prior_form[
            horse_prior_form["distanceFurlongs"].sub(max_prior_distance).abs() <= DISTANCE_TOLERANCE_FURLONGS
        ]
        if len(near_max) > 0 and near_max["officialRating"].notna().any():
            out["best_recent_or_near_distance"] = float(near_max["officialRating"].dropna().max())
        # Stepping up more than 25% beyond the furthest distance previously
        # attempted is flagged as stamina-uncertain — transparent threshold.
        out["stamina_uncertainty_flag"] = int(distance_furlongs > max_prior_distance * 1.25)
    else:
        out["stamina_uncertainty_flag"] = 1  # no distance evidence at all = uncertain by definition

    if going:
        going_form = horse_prior_form[horse_prior_form["going"] == going]
        going_rec = record_summary(going_form)
        out["going_starts"] = going_rec.starts
        out["going_wins"] = going_rec.wins
        out["going_places"] = going_rec.places
        out["going_win_rate"] = going_rec.win_rate_raw if going_rec.available else np.nan
        out["going_place_rate"] = going_rec.place_rate_raw if going_rec.available else np.nan

        today_softness = going_softness_index(going)
        prior_goings = horse_prior_form["going"].dropna()
        if len(prior_goings) > 0:
            similarities = 1 - prior_goings.map(going_softness_index).sub(today_softness).abs()
            weights = np.exp(-np.arange(len(similarities)) * (np.log(2) / 3))
            out["going_similarity_score"] = float(np.average(similarities, weights=weights[: len(similarities)]))

            last_going_softness = going_softness_index(prior_goings.iloc[0])
            out["going_change_flag"] = int(abs(today_softness - last_going_softness) > 0.25)

    # FormEntry does not capture turf-vs-all-weather surface directly (see
    # module docstring on the schema); flatJumps is used as the closest
    # available proxy for "race type" record.
    type_form = horse_prior_form[horse_prior_form["flatJumps"] == flat_jumps]
    type_rec = record_summary(type_form)
    out["race_type_starts"] = type_rec.starts
    out["race_type_wins"] = type_rec.wins
    out["race_type_places"] = type_rec.places
    out["race_type_win_rate"] = type_rec.win_rate_raw if type_rec.available else np.nan
    out["race_type_place_rate"] = type_rec.place_rate_raw if type_rec.available else np.nan

    return out

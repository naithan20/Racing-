"""TRAINER / JOCKEY features.

`global_prior_runs` is a global (all-horses) table of prior runs — Runner
joined to Race and ResultEntry — already filtered by the caller to
raceDate < as_of_date, with columns: raceDate, trainerName, jockeyName,
course, finishingPosition.

Every rate here is smoothed towards a population prior (see
features/common.py:smoothed_rate) so a trainer/jockey with only 1-2 runs in
a window doesn't produce a spurious 0% or 100% figure.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from racingedge_model.config import TRAINER_JOCKEY_SMOOTHING_PRIOR_RUNS
from racingedge_model.features.common import record_summary

FEATURE_KEYS = [
    "trainer_strike_rate_14d",
    "trainer_runs_14d",
    "trainer_strike_rate_30d",
    "trainer_runs_30d",
    "trainer_place_rate_30d",
    "jockey_strike_rate_14d",
    "jockey_runs_14d",
    "jockey_strike_rate_30d",
    "jockey_runs_30d",
    "trainer_jockey_combo_rate",
    "trainer_jockey_combo_runs",
    "trainer_course_rate",
    "trainer_course_runs",
    "jockey_course_rate",
    "jockey_course_runs",
]


def compute_trainer_jockey_features(
    global_prior_runs: pd.DataFrame,
    trainer_name: str | None,
    jockey_name: str | None,
    course: str,
    as_of_date: pd.Timestamp,
) -> dict:
    out: dict = {k: np.nan for k in FEATURE_KEYS}
    if global_prior_runs.empty:
        return out

    if trainer_name:
        trainer_runs = global_prior_runs[global_prior_runs["trainerName"] == trainer_name]
        for days, suffix in ((14, "14d"), (30, "30d")):
            window = trainer_runs[trainer_runs["raceDate"] >= as_of_date - pd.Timedelta(days=days)]
            rec = record_summary(window)
            out[f"trainer_runs_{suffix}"] = rec.starts
            out[f"trainer_strike_rate_{suffix}"] = rec.win_rate_smoothed

        window_30 = trainer_runs[trainer_runs["raceDate"] >= as_of_date - pd.Timedelta(days=30)]
        rec_30 = record_summary(window_30)
        out["trainer_place_rate_30d"] = rec_30.place_rate_smoothed

        course_runs = trainer_runs[trainer_runs["course"] == course]
        rec_course = record_summary(course_runs)
        out["trainer_course_runs"] = rec_course.starts
        out["trainer_course_rate"] = rec_course.win_rate_smoothed

    if jockey_name:
        jockey_runs = global_prior_runs[global_prior_runs["jockeyName"] == jockey_name]
        for days, suffix in ((14, "14d"), (30, "30d")):
            window = jockey_runs[jockey_runs["raceDate"] >= as_of_date - pd.Timedelta(days=days)]
            rec = record_summary(window)
            out[f"jockey_runs_{suffix}"] = rec.starts
            out[f"jockey_strike_rate_{suffix}"] = rec.win_rate_smoothed

        course_runs = jockey_runs[jockey_runs["course"] == course]
        rec_course = record_summary(course_runs)
        out["jockey_course_runs"] = rec_course.starts
        out["jockey_course_rate"] = rec_course.win_rate_smoothed

    if trainer_name and jockey_name:
        combo_runs = global_prior_runs[
            (global_prior_runs["trainerName"] == trainer_name) & (global_prior_runs["jockeyName"] == jockey_name)
        ]
        rec_combo = record_summary(combo_runs)
        out["trainer_jockey_combo_runs"] = rec_combo.starts
        out["trainer_jockey_combo_rate"] = rec_combo.win_rate_smoothed

    return out

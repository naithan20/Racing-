"""HEADGEAR / EQUIPMENT and TRAINER-CHANGE features.

`horse_prior_global_runs` is this horse's own prior rows from the global
Runner/Race/Result history (NOT FormEntry) because trainer identity per
historical run is only captured on the Runner table.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_KEYS = [
    "first_time_headgear_flag",
    "repeated_headgear_flag",
    "prior_headgear_win_rate",
    "prior_headgear_runs",
    "trainer_change_flag",
    "runs_for_current_trainer",
    "first_run_for_trainer_flag",
    "second_run_for_trainer_flag",
    "wind_surgery_flag",
    "wind_surgery_flag_available",
]


def compute_headgear_and_change_features(
    headgear: str | None,
    first_time_headgear: bool,
    horse_prior_form: pd.DataFrame,
    horse_prior_global_runs: pd.DataFrame,
    trainer_name: str | None,
) -> dict:
    out: dict = {k: np.nan for k in FEATURE_KEYS}

    # Not modelled anywhere in the current schema/dataset.
    out["wind_surgery_flag"] = 0
    out["wind_surgery_flag_available"] = 0

    out["first_time_headgear_flag"] = int(bool(first_time_headgear))
    out["repeated_headgear_flag"] = int(bool(headgear) and not first_time_headgear)

    if headgear and len(horse_prior_form) > 0:
        same_headgear = horse_prior_form[horse_prior_form["headgear"] == headgear]
        out["prior_headgear_runs"] = len(same_headgear)
        if len(same_headgear) > 0:
            out["prior_headgear_win_rate"] = float((same_headgear["finishingPosition"] == 1).mean())

    if trainer_name is not None and not horse_prior_global_runs.empty and "trainerName" in horse_prior_global_runs.columns:
        runs_for_trainer = int((horse_prior_global_runs["trainerName"] == trainer_name).sum())
        out["runs_for_current_trainer"] = runs_for_trainer
        out["first_run_for_trainer_flag"] = int(runs_for_trainer == 0)
        out["second_run_for_trainer_flag"] = int(runs_for_trainer == 1)

        if len(horse_prior_global_runs) > 0:
            most_recent_trainer = horse_prior_global_runs.sort_values("raceDate", ascending=False)["trainerName"].iloc[0]
            out["trainer_change_flag"] = int(most_recent_trainer != trainer_name)
        else:
            out["trainer_change_flag"] = 0
    elif trainer_name is not None:
        out["runs_for_current_trainer"] = 0
        out["first_run_for_trainer_flag"] = 1
        out["second_run_for_trainer_flag"] = 0
        out["trainer_change_flag"] = 0

    return out

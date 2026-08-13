"""AGE / EXPERIENCE features."""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_KEYS = [
    "horse_age",
    "career_starts_to_date",
    "starts_last_12_months",
    "experience_band_unraced",
    "experience_band_lightly_raced",
    "experience_band_moderate",
    "experience_band_exposed",
    "lightly_raced_flag",
    "exposed_horse_flag",
    "age_x_jumps",
    "age_x_distance",
]


def compute_age_experience_features(
    age_at_race: float | None,
    horse_prior_form: pd.DataFrame,
    as_of_date: pd.Timestamp,
    flat_jumps: str,
    distance_furlongs: float,
) -> dict:
    out: dict = {k: np.nan for k in FEATURE_KEYS}

    n = len(horse_prior_form)
    out["career_starts_to_date"] = n
    if n > 0:
        recent_cutoff = as_of_date - pd.Timedelta(days=365)
        out["starts_last_12_months"] = int((horse_prior_form["raceDate"] >= recent_cutoff).sum())
    else:
        out["starts_last_12_months"] = 0

    band = "UNRACED" if n == 0 else "LIGHTLY_RACED" if n <= 3 else "MODERATE" if n <= 9 else "EXPOSED"
    out["experience_band_unraced"] = int(band == "UNRACED")
    out["experience_band_lightly_raced"] = int(band == "LIGHTLY_RACED")
    out["experience_band_moderate"] = int(band == "MODERATE")
    out["experience_band_exposed"] = int(band == "EXPOSED")
    out["lightly_raced_flag"] = int(band in ("UNRACED", "LIGHTLY_RACED"))
    out["exposed_horse_flag"] = int(band == "EXPOSED")

    if age_at_race is not None and not pd.isna(age_at_race):
        age_at_race = float(age_at_race)
        out["horse_age"] = age_at_race
        out["age_x_jumps"] = age_at_race * int(flat_jumps == "JUMPS")
        out["age_x_distance"] = age_at_race * distance_furlongs

    return out

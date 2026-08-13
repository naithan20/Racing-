"""DRAW features.

`global_prior_runs` is a global (all-horses) table of prior runs — Runner
joined to Race and ResultEntry — already filtered by the caller to
raceDate < as_of_date. Draw bias needs cross-horse population data, which
FormEntry (a per-horse table) cannot provide.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from racingedge_model.config import MIN_SAMPLES_DRAW_BIAS
from racingedge_model.features.common import percentile_rank

DISTANCE_BAND_WIDTH = 2.0

FEATURE_KEYS = [
    "draw_number",
    "draw_percentile",
    "draw_bucket_low",
    "draw_bucket_mid",
    "draw_bucket_high",
    "field_size",
    "draw_bias_win_rate",
    "draw_bias_available",
    "draw_bias_sample_size",
    "draw_x_leader_style",
]


def _distance_band(distance_furlongs: float) -> float:
    return round(distance_furlongs / DISTANCE_BAND_WIDTH) * DISTANCE_BAND_WIDTH


def _field_size_band(field_size: int) -> str:
    if field_size <= 8:
        return "SMALL"
    if field_size <= 14:
        return "MEDIUM"
    return "LARGE"


def compute_draw_features(
    draw: float | None,
    field_draws: pd.Series,
    field_size: int,
    course: str,
    distance_furlongs: float,
    global_prior_runs: pd.DataFrame,
    is_leader_style: bool,
) -> dict:
    out: dict = {k: np.nan for k in FEATURE_KEYS}
    out["field_size"] = field_size
    out["draw_bias_available"] = 0
    out["draw_bias_sample_size"] = 0

    if draw is None or pd.isna(draw):
        return out
    draw = float(draw)
    out["draw_number"] = draw

    others = field_draws.dropna()
    if len(others) > 1:
        draw_pct = percentile_rank(draw, others)
        out["draw_percentile"] = draw_pct
        out["draw_bucket_low"] = int(draw_pct is not None and draw_pct <= 1 / 3)
        out["draw_bucket_mid"] = int(draw_pct is not None and 1 / 3 < draw_pct <= 2 / 3)
        out["draw_bucket_high"] = int(draw_pct is not None and draw_pct > 2 / 3)
        out["draw_x_leader_style"] = float((1 - draw_pct) * int(is_leader_style)) if draw_pct is not None else np.nan

    if global_prior_runs.empty or "draw" not in global_prior_runs.columns:
        return out

    band = _distance_band(distance_furlongs)
    size_band = _field_size_band(field_size)
    bucket = global_prior_runs[
        (global_prior_runs["course"] == course)
        & (global_prior_runs["distanceFurlongs"].apply(_distance_band) == band)
        & (global_prior_runs["fieldSizeBand"] == size_band)
        & global_prior_runs["draw"].notna()
    ]

    sample_size = len(bucket)
    out["draw_bias_sample_size"] = sample_size
    if sample_size < MIN_SAMPLES_DRAW_BIAS or out["draw_percentile"] is None:
        # IMPORTANT: only use draw bias when sample size is sufficient.
        return out

    # Compare win rate for runners in the SAME draw tercile as this runner,
    # within this exact course/distance-band/field-size-band bucket.
    bucket = bucket.copy()
    bucket["draw_pct_in_race"] = bucket.groupby("raceId")["draw"].rank(pct=True)
    if out["draw_bucket_low"]:
        same_tercile = bucket[bucket["draw_pct_in_race"] <= 1 / 3]
    elif out["draw_bucket_high"]:
        same_tercile = bucket[bucket["draw_pct_in_race"] > 2 / 3]
    else:
        same_tercile = bucket[(bucket["draw_pct_in_race"] > 1 / 3) & (bucket["draw_pct_in_race"] <= 2 / 3)]

    if len(same_tercile) >= MIN_SAMPLES_DRAW_BIAS / 3:
        out["draw_bias_win_rate"] = float((same_tercile["finishingPosition"] == 1).mean())
        out["draw_bias_available"] = 1

    return out

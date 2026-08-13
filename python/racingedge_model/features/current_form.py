"""CURRENT FORM features.

All inputs are the horse's own prior FormEntry rows, already filtered by the
caller to `raceDate < as_of_date` (see features/build.py). Rows must be
sorted most-recent-first before being passed in.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from racingedge_model.config import FORM_WINDOWS
from racingedge_model.features.common import finishing_percentile, safe_slope

FEATURE_KEYS = [
    "form_last_run_position",
    "form_avg_position_last3",
    "form_avg_position_last5",
    "form_recency_weighted_percentile",
    "form_beaten_distance_trend",
    "form_topspeed_trend",
    "form_or_relative_recent",
    "form_improvement_slope",
    "form_consistency",
    "form_competitive_finishes_last5",
    "form_wins_last3",
    "form_wins_last5",
    "form_wins_last10",
    "form_places_last3",
    "form_places_last5",
    "form_places_last10",
    "days_since_last_run",
    "avg_days_between_runs",
    "quick_turnaround_flag",
    "long_layoff_flag",
    "first_time_out_flag",
    "career_runs_to_date",
]


def compute_current_form_features(
    horse_prior_form: pd.DataFrame, as_of_date: pd.Timestamp, days_since_last_run: float | None
) -> dict:
    """`horse_prior_form` must already be sorted descending by raceDate and
    contain only rows with raceDate < as_of_date."""

    n = len(horse_prior_form)
    out: dict = {k: np.nan for k in FEATURE_KEYS}
    out["career_runs_to_date"] = n
    out["first_time_out_flag"] = int(n == 0)

    # days_since_last_run is a pre-race DECLARED field on the current
    # Runner row (known before the race), not derived from FormEntry, so we
    # trust the caller's value directly rather than recomputing it — but we
    # cross-check against FormEntry when both are available (see build.py).
    out["days_since_last_run"] = days_since_last_run
    if days_since_last_run is not None and not pd.isna(days_since_last_run):
        out["quick_turnaround_flag"] = int(days_since_last_run < 10)
        out["long_layoff_flag"] = int(days_since_last_run > 180)

    if n == 0:
        return out

    positions = horse_prior_form["finishingPosition"]
    field_sizes = horse_prior_form["fieldSize"]
    percentiles = [
        finishing_percentile(p, f) for p, f in zip(positions, field_sizes, strict=True)
    ]
    percentiles_arr = np.array([p if p is not None else np.nan for p in percentiles])

    out["form_last_run_position"] = float(positions.iloc[0]) if pd.notna(positions.iloc[0]) else np.nan

    for window, key in ((3, "form_avg_position_last3"), (5, "form_avg_position_last5")):
        subset = positions.iloc[:window].dropna()
        out[key] = float(subset.mean()) if len(subset) > 0 else np.nan

    # Recency-weighted finishing percentile: exponential decay, half-life ~3 runs.
    weights = np.exp(-np.arange(n) * (np.log(2) / 3))
    valid = ~np.isnan(percentiles_arr)
    if valid.any():
        out["form_recency_weighted_percentile"] = float(
            np.sum(percentiles_arr[valid] * weights[valid]) / np.sum(weights[valid])
        )

    # Beaten-distance trend: slope over the last 5 runs (positive = beaten
    # distance is GROWING recently = form declining; caller should treat a
    # negative slope as improving form).
    recent_beaten = horse_prior_form["beatenDistanceLengths"].iloc[:5].tolist()
    out["form_beaten_distance_trend"] = safe_slope(recent_beaten)

    # "Topspeed trend" proxy — FormEntry.finishingSpeedPercentage is
    # documented in the Phase 1 schema as a Topspeed-style late-pace metric.
    # RPR/Timeform trends are left unavailable (NaN) because no historical
    # per-run rating is captured anywhere in the current schema — only a
    # single *current* value lives on Runner (racingPostRating /
    # timeformRating), which cannot be used here without lookahead.
    recent_speed = horse_prior_form["finishingSpeedPercentage"].iloc[:5].tolist()
    out["form_topspeed_trend"] = safe_slope(recent_speed)

    # OR-relative recent performance: average finishing percentile from the
    # last 3 runs (a horse consistently finishing in the top of the field
    # relative to its OR band is "running above its mark").
    recent_pct = percentiles_arr[:3]
    recent_pct = recent_pct[~np.isnan(recent_pct)]
    out["form_or_relative_recent"] = float(recent_pct.mean()) if len(recent_pct) > 0 else np.nan

    # Improvement/decline slope of finishing percentile over up to 5 runs.
    out["form_improvement_slope"] = safe_slope(percentiles_arr[:5].tolist())

    # Consistency: lower std = more consistent. Needs >= 2 runs.
    consistency_window = percentiles_arr[:5]
    consistency_window = consistency_window[~np.isnan(consistency_window)]
    out["form_consistency"] = float(consistency_window.std(ddof=0)) if len(consistency_window) >= 2 else np.nan

    # Competitive finish = top 3 or within ~5 lengths.
    last5 = horse_prior_form.iloc[:5]
    competitive = (last5["finishingPosition"] <= 3) | (last5["beatenDistanceLengths"] <= 5)
    out["form_competitive_finishes_last5"] = int(competitive.sum())

    for window in FORM_WINDOWS:
        subset = horse_prior_form.iloc[:window]
        out[f"form_wins_last{window}"] = int((subset["finishingPosition"] == 1).sum())
        out[f"form_places_last{window}"] = int((subset["finishingPosition"] <= 3).sum())

    if n >= 2:
        gaps = horse_prior_form["raceDate"].iloc[:10].sort_values().diff().dt.days.dropna()
        out["avg_days_between_runs"] = float(gaps.mean()) if len(gaps) > 0 else np.nan

    return out

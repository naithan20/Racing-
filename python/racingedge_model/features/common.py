"""Shared helpers used across feature groups: smoothing, record summaries,
and small numeric utilities. Centralising these keeps every feature group's
"how do we handle small samples" logic consistent and auditable in one
place, per the project's data-quality requirements.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from racingedge_model.config import DEFAULT_PLACE_RATE_PRIOR, DEFAULT_WIN_RATE_PRIOR, RECORD_SMOOTHING_PRIOR_RUNS


@dataclass
class RecordSummary:
    starts: int
    wins: int
    places: int
    win_rate_raw: float | None
    place_rate_raw: float | None
    win_rate_smoothed: float
    place_rate_smoothed: float
    available: bool  # True once starts > 0


def smoothed_rate(successes: int, trials: int, prior_rate: float, prior_weight: float) -> float:
    """Additive (Bayesian-ish) smoothing: blends the observed rate towards a
    population prior, weighted by `prior_weight` "virtual" trials. A trial
    count of 0 returns exactly the prior; large trial counts converge to the
    raw observed rate. This is what stops a single lucky/unlucky run from
    producing a 100%/0% feature value.
    """
    return (successes + prior_rate * prior_weight) / (trials + prior_weight)


def record_summary(
    df: pd.DataFrame,
    win_col: str = "finishingPosition",
    place_threshold: int = 3,
    prior_win_rate: float = DEFAULT_WIN_RATE_PRIOR,
    prior_place_rate: float = DEFAULT_PLACE_RATE_PRIOR,
    prior_weight: float = RECORD_SMOOTHING_PRIOR_RUNS,
) -> RecordSummary:
    starts = len(df)
    if starts == 0:
        return RecordSummary(
            starts=0,
            wins=0,
            places=0,
            win_rate_raw=None,
            place_rate_raw=None,
            win_rate_smoothed=prior_win_rate,
            place_rate_smoothed=prior_place_rate,
            available=False,
        )
    positions = df[win_col]
    wins = int((positions == 1).sum())
    places = int((positions <= place_threshold).sum())
    return RecordSummary(
        starts=starts,
        wins=wins,
        places=places,
        win_rate_raw=wins / starts,
        place_rate_raw=places / starts,
        win_rate_smoothed=smoothed_rate(wins, starts, prior_win_rate, prior_weight),
        place_rate_smoothed=smoothed_rate(places, starts, prior_place_rate, prior_weight),
        available=True,
    )


def percentile_rank(value: float, series: pd.Series) -> float | None:
    """Percentile of `value` within `series` (0 = lowest, 1 = highest).
    Returns None if the series is empty."""
    if len(series) == 0:
        return None
    return float((series < value).sum() + 0.5 * (series == value).sum()) / len(series)


def safe_slope(y: list[float] | np.ndarray, prefer_recent_first: bool = True) -> float | None:
    """Linear-regression slope of y against run index. Callers pass y in
    reverse-chronological order (most recent first); this function reverses
    it internally so the slope's sign means "recent trend" (positive =
    improving over time) rather than depending on caller order.
    """
    values = np.asarray(y, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) < 2:
        return None
    if prefer_recent_first:
        values = values[::-1]  # oldest -> newest
    x = np.arange(len(values), dtype=float)
    x_mean, y_mean = x.mean(), values.mean()
    denom = ((x - x_mean) ** 2).sum()
    if denom == 0:
        return None
    slope = ((x - x_mean) * (values - y_mean)).sum() / denom
    return float(slope)


def finishing_percentile(finishing_position: float, field_size: float) -> float | None:
    """1.0 = won, 0.0 = last. None if inputs are missing/degenerate."""
    if pd.isna(finishing_position) or pd.isna(field_size) or field_size <= 1:
        return None
    return float((field_size - finishing_position) / (field_size - 1))


def is_missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))

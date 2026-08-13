"""Place probability models: separate binary classifiers per place depth.

Per project requirement, place probability is NEVER derived as a crude
multiple of win probability. Instead we train five independent binary
classifiers — P(finish <= 2), P(finish <= 3), ..., P(finish <= 6) — each
using the same feature set and preprocessing as the win model.

Pipeline (each step documented, applied in this order):
  1. Raw model output — LightGBM classifier probability per depth, fit
     independently for each depth. LightGBM was chosen here (rather than
     logistic regression) because the win-model comparison showed it
     generalizes materially better at this feature-to-sample-size ratio —
     see MODEL_CARD.md.
  2. Calibration — Platt/isotonic, fit on the validation split only (see
     calibration.py), applied per depth.
  3. Race-level rescaling — exactly N runners finish in the top N (assuming
     a full field finishes), so calibrated probabilities for depth N are
     rescaled within each race so they sum to N:
         adjusted_i = calibrated_i * (N / sum(calibrated_j in race))
     This is the place-probability analogue of the win-probability
     normalization in normalize.py, and is a sanity/consistency adjustment,
     not a re-fit.
  4. Monotonicity enforcement — for each runner, P(top2) <= P(top3) <=
     P(top4) <= P(top5) <= P(top6) is enforced via a running maximum over
     increasing depth (a standard isotonic-style post-processing step).
     Any place depth that a bookmaker doesn't offer (e.g. depth 6 unused)
     is simply not looked up downstream — all five are always computed and
     stored (see PlaceProbabilityBand).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from racingedge_model.config import PLACE_DEPTHS
from racingedge_model.models.win_gbm import GbmWinModel


class PlaceModelSet:
    algorithm = "lightgbm_place_topN"

    def __init__(self, depths: list[int] | None = None, **model_overrides):
        self.depths = depths or PLACE_DEPTHS
        self.models: dict[int, GbmWinModel] = {d: GbmWinModel(**model_overrides) for d in self.depths}

    def fit(self, X: pd.DataFrame, targets: dict[int, pd.Series]) -> "PlaceModelSet":
        for depth in self.depths:
            self.models[depth].fit(X, targets[depth])
        return self

    def predict_proba(self, X: pd.DataFrame) -> dict[int, np.ndarray]:
        return {depth: self.models[depth].predict_proba_positive(X) for depth in self.depths}

    def feature_importance(self, depth: int) -> list[dict]:
        return self.models[depth].feature_importance()


def rescale_place_probabilities_within_race(
    probabilities: pd.Series, race_ids: pd.Series, depth: int
) -> pd.Series:
    """Rescales so predicted probabilities for this depth sum to `depth`
    within each race (exactly `depth` runners finish in the top `depth`,
    assuming a full field finishes and no non-finishers/void races)."""

    clipped = probabilities.clip(lower=1e-6, upper=1 - 1e-6)
    race_sums = clipped.groupby(race_ids).transform("sum")
    field_sizes = race_ids.groupby(race_ids).transform("count")
    target_sum = np.minimum(depth, field_sizes)
    scaled = clipped * (target_sum / race_sums)
    return scaled.clip(upper=0.999)


def enforce_monotonic_place_probabilities(probs_by_depth: dict[int, float]) -> dict[int, float]:
    """Per-runner monotonicity: P(top2) <= P(top3) <= ... via running max."""
    depths_sorted = sorted(probs_by_depth.keys())
    adjusted: dict[int, float] = {}
    running_max = 0.0
    for depth in depths_sorted:
        value = max(probs_by_depth[depth], running_max)
        adjusted[depth] = value
        running_max = value
    return adjusted


def enforce_monotonic_place_probabilities_df(prob_frames: dict[int, pd.Series]) -> dict[int, pd.Series]:
    """Vectorised row-wise version of enforce_monotonic_place_probabilities."""
    depths_sorted = sorted(prob_frames.keys())
    matrix = pd.concat([prob_frames[d] for d in depths_sorted], axis=1)
    matrix.columns = depths_sorted
    monotonic = matrix.cummax(axis=1)
    return {depth: monotonic[depth] for depth in depths_sorted}

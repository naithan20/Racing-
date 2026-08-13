"""Race-level win-probability normalization.

Method (documented per project requirement):
  1. The win model outputs an independent per-runner score — here, the raw
     probability from a binary classifier P(win | features), which does NOT
     sum to 1 across a race because each runner was scored independently.
  2. That score is already strictly positive (a classifier probability in
     (0, 1)), so no extra "make it positive" transform is needed beyond a
     small epsilon clip to guard against exact zeros.
  3. Normalize within each race:

         P(win_i) = score_i / sum(score_j for j in same race)

This is the simplest transparent approach that guarantees probabilities
within a race sum to (approximately) 1, and is exactly the method suggested
in the project brief. It does NOT change the ranking of runners within a
race (normalization is a monotonic per-race rescaling).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EPSILON = 1e-6


def normalize_win_probabilities(raw_scores: pd.Series, race_ids: pd.Series) -> pd.Series:
    if len(raw_scores) != len(race_ids):
        raise ValueError("raw_scores and race_ids must be the same length")
    clipped = raw_scores.clip(lower=EPSILON)
    race_sums = clipped.groupby(race_ids).transform("sum")
    return clipped / race_sums


def assert_probabilities_sum_to_one(normalized: pd.Series, race_ids: pd.Series, tolerance: float = 1e-6) -> None:
    sums = normalized.groupby(race_ids).sum()
    bad = sums[(sums - 1.0).abs() > tolerance]
    if len(bad) > 0:
        raise AssertionError(f"{len(bad)} race(s) do not sum to 1 after normalization: {bad.to_dict()}")

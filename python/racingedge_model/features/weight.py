"""WEIGHT features. All inputs are pre-race declared facts for today's race."""

from __future__ import annotations

import numpy as np
import pandas as pd

from racingedge_model.features.common import percentile_rank

FEATURE_KEYS = [
    "weight_carried_lbs",
    "weight_percentile_in_field",
    "weight_diff_from_field_mean",
    "weight_diff_to_top_weight",
    "jockey_claim_lbs",
    "effective_weight_after_claim",
    "weight_for_age_allowance",
    "weight_for_age_allowance_available",
    "age_weight_interaction",
]


def compute_weight_features(
    weight_lbs: float | None,
    jockey_claim_lbs: float | None,
    field_weights: pd.Series,
    age_at_race: float | None,
) -> dict:
    out: dict = {k: np.nan for k in FEATURE_KEYS}
    claim = float(jockey_claim_lbs) if jockey_claim_lbs and not pd.isna(jockey_claim_lbs) else 0.0
    out["jockey_claim_lbs"] = claim

    # Weight-for-age allowance tables are not modelled in this schema/
    # dataset (they depend on race conditions books not captured here).
    out["weight_for_age_allowance"] = 0.0
    out["weight_for_age_allowance_available"] = 0

    if weight_lbs is None or pd.isna(weight_lbs):
        return out
    weight_lbs = float(weight_lbs)
    out["weight_carried_lbs"] = weight_lbs
    out["effective_weight_after_claim"] = weight_lbs - claim

    others = field_weights.dropna()
    if len(others) > 0:
        out["weight_percentile_in_field"] = percentile_rank(weight_lbs, others)
        out["weight_diff_from_field_mean"] = weight_lbs - float(others.mean())
        out["weight_diff_to_top_weight"] = weight_lbs - float(others.max())

    if age_at_race is not None and not pd.isna(age_at_race) and len(others) > 0:
        out["age_weight_interaction"] = float(age_at_race) * (weight_lbs - float(others.mean()))

    return out

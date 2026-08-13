"""CLASS features.

Sign convention (UK/IRE style): class 1 is the HIGHEST quality, larger
numbers are lower quality. `class_change_from_prev` is defined as
(previous class - current class), so a POSITIVE value means the horse has
risen in class (harder task); NEGATIVE means dropped in class (easier).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from racingedge_model.features.common import finishing_percentile

FEATURE_KEYS = [
    "current_class",
    "class_change_from_prev",
    "avg_class_last3",
    "class_success_rate",
    "class_place_rate",
    "class_adjusted_recent_form",
]


def compute_class_features(current_class: float | None, horse_prior_form: pd.DataFrame) -> dict:
    out: dict = {k: np.nan for k in FEATURE_KEYS}
    if current_class is None or pd.isna(current_class):
        return out
    current_class = float(current_class)
    out["current_class"] = current_class

    prior_classes = horse_prior_form["raceClass"].dropna()
    if len(prior_classes) > 0:
        out["class_change_from_prev"] = float(prior_classes.iloc[0]) - current_class
    if len(prior_classes) >= 3:
        out["avg_class_last3"] = float(prior_classes.iloc[:3].mean())

    same_class = horse_prior_form[horse_prior_form["raceClass"] == current_class]
    if len(same_class) > 0:
        out["class_success_rate"] = float((same_class["finishingPosition"] == 1).mean())
        out["class_place_rate"] = float((same_class["finishingPosition"] <= 3).mean())

    # "this class or harder" = raceClass <= current_class (smaller number = harder).
    at_or_above = horse_prior_form[horse_prior_form["raceClass"] <= current_class]
    if len(at_or_above) > 0:
        percentiles = [
            finishing_percentile(p, f)
            for p, f in zip(at_or_above["finishingPosition"], at_or_above["fieldSize"], strict=True)
        ]
        percentiles = [p for p in percentiles if p is not None]
        if percentiles:
            out["class_adjusted_recent_form"] = float(np.mean(percentiles))

    return out

"""Baseline win Model B: gradient boosted trees (LightGBM).

Hyperparameters below are conservative, documented defaults chosen to
resist overfitting on a modest dataset (hundreds to low-thousands of
training rows) — NOT the result of a hyperparameter search. Tuning is
explicitly out of scope for this baseline; see MODEL_CARD.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier

from racingedge_model.config import RANDOM_SEED

HYPERPARAMETERS = {
    "n_estimators": 200,
    "learning_rate": 0.05,
    "num_leaves": 15,
    "min_child_samples": 20,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,
    "reg_lambda": 0.1,
    "random_state": RANDOM_SEED,
    "verbosity": -1,
}


class GbmWinModel:
    algorithm = "lightgbm"

    def __init__(self, **overrides):
        self.params = {**HYPERPARAMETERS, **overrides}
        self.model = LGBMClassifier(**self.params)
        self.feature_names_: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "GbmWinModel":
        self.feature_names_ = list(X.columns)
        self.model.fit(X.values, y.values)
        return self

    def predict_proba_positive(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X[self.feature_names_].values)[:, 1]

    def feature_importance(self) -> list[dict]:
        """Split-count-based importance — association, not causation."""
        importances = self.model.feature_importances_
        items = [
            {"feature": name, "importance": float(imp)}
            for name, imp in zip(self.feature_names_, importances, strict=True)
        ]
        total = sum(item["importance"] for item in items) or 1.0
        for item in items:
            item["importance_normalized"] = item["importance"] / total
        return sorted(items, key=lambda d: d["importance"], reverse=True)

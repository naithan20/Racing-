"""Baseline win Model A: L2-regularized logistic regression.

Deliberately simple and fully interpretable — every coefficient is a
directly-readable log-odds weight learned by maximum likelihood, not hand-
set. Features are standardized (zero mean, unit variance) before fitting so
coefficient magnitudes are comparable to each other.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from racingedge_model.config import RANDOM_SEED

HYPERPARAMETERS = {
    # L2 is scikit-learn's default penalty; passing it explicitly triggers a
    # deprecation warning as of sklearn 1.8 (use l1_ratio instead in the
    # future), so we simply omit it and rely on the default.
    # C=0.02 chosen via a one-off validation-set AUC comparison across
    # C in [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0] (see MODEL_CARD.md) — the
    # feature-to-training-row ratio is high (166 features vs ~1,100 rows),
    # so strong regularization is basic hygiene here, not profit-tuning.
    # This was picked once against validation AUC, never against test.
    "C": 0.02,
    "max_iter": 2000,
    "random_state": RANDOM_SEED,
}


class LogisticWinModel:
    algorithm = "logistic_regression"

    def __init__(self, **overrides):
        self.params = {**HYPERPARAMETERS, **overrides}
        self.scaler = StandardScaler()
        self.model = LogisticRegression(**self.params)
        self.feature_names_: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "LogisticWinModel":
        self.feature_names_ = list(X.columns)
        X_scaled = self.scaler.fit_transform(X.values)
        self.model.fit(X_scaled, y.values)
        return self

    def predict_proba_positive(self, X: pd.DataFrame) -> np.ndarray:
        X_scaled = self.scaler.transform(X[self.feature_names_].values)
        return self.model.predict_proba(X_scaled)[:, 1]

    def feature_importance(self) -> list[dict]:
        """Standardized-coefficient magnitude — association, not causation."""
        coefs = self.model.coef_[0]
        items = [
            {"feature": name, "coefficient": float(coef), "abs_coefficient": float(abs(coef))}
            for name, coef in zip(self.feature_names_, coefs, strict=True)
        ]
        return sorted(items, key=lambda d: d["abs_coefficient"], reverse=True)

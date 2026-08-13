"""Probability calibration: Platt (sigmoid) and isotonic.

Fit ONLY on the validation split — never on train (the model already saw
that) and never on test (that must stay a genuinely held-out final check).
`select_best_calibration` fits both methods on validation, compares Brier
score improvement over the raw (uncalibrated) model on that same
validation data, and returns whichever wins (or "none" if neither helps).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

EPS = 1e-6


class ProbabilityCalibrator:
    def __init__(self, method: str):
        if method not in ("sigmoid", "isotonic", "none"):
            raise ValueError(f"Unknown calibration method: {method}")
        self.method = method
        self._model = None

    def fit(self, raw_probs: np.ndarray, y_true: np.ndarray) -> "ProbabilityCalibrator":
        raw_probs = np.clip(np.asarray(raw_probs, dtype=float), EPS, 1 - EPS)
        y_true = np.asarray(y_true)
        if self.method == "sigmoid":
            logits = np.log(raw_probs / (1 - raw_probs)).reshape(-1, 1)
            self._model = LogisticRegression().fit(logits, y_true)
        elif self.method == "isotonic":
            self._model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(raw_probs, y_true)
        return self

    def transform(self, raw_probs: np.ndarray) -> np.ndarray:
        raw_probs = np.clip(np.asarray(raw_probs, dtype=float), EPS, 1 - EPS)
        if self.method == "none" or self._model is None:
            return raw_probs
        if self.method == "sigmoid":
            logits = np.log(raw_probs / (1 - raw_probs)).reshape(-1, 1)
            return self._model.predict_proba(logits)[:, 1]
        return np.asarray(self._model.predict(raw_probs), dtype=float)

    def to_dict(self) -> dict:
        if self.method == "sigmoid" and self._model is not None:
            return {"method": "sigmoid", "coef": self._model.coef_.tolist(), "intercept": self._model.intercept_.tolist()}
        if self.method == "isotonic" and self._model is not None:
            return {
                "method": "isotonic",
                "X_thresholds": self._model.X_thresholds_.tolist(),
                "y_thresholds": self._model.y_thresholds_.tolist(),
            }
        return {"method": "none"}


@dataclass
class CalibrationComparison:
    raw_brier: float
    sigmoid_brier: float
    isotonic_brier: float
    raw_log_loss: float
    sigmoid_log_loss: float
    isotonic_log_loss: float
    chosen_method: str


def select_best_calibration(
    raw_val_probs: np.ndarray, y_val: np.ndarray
) -> tuple[ProbabilityCalibrator, CalibrationComparison]:
    raw_val_probs = np.clip(np.asarray(raw_val_probs, dtype=float), EPS, 1 - EPS)
    y_val = np.asarray(y_val)

    sigmoid = ProbabilityCalibrator("sigmoid").fit(raw_val_probs, y_val)
    isotonic = ProbabilityCalibrator("isotonic").fit(raw_val_probs, y_val)

    sigmoid_pred = sigmoid.transform(raw_val_probs)
    isotonic_pred = isotonic.transform(raw_val_probs)

    comparison = CalibrationComparison(
        raw_brier=brier_score_loss(y_val, raw_val_probs),
        sigmoid_brier=brier_score_loss(y_val, sigmoid_pred),
        isotonic_brier=brier_score_loss(y_val, isotonic_pred),
        raw_log_loss=log_loss(y_val, raw_val_probs, labels=[0, 1]),
        sigmoid_log_loss=log_loss(y_val, sigmoid_pred, labels=[0, 1]),
        isotonic_log_loss=log_loss(y_val, isotonic_pred, labels=[0, 1]),
        chosen_method="none",
    )

    candidates = {"none": comparison.raw_brier, "sigmoid": comparison.sigmoid_brier, "isotonic": comparison.isotonic_brier}
    chosen = min(candidates, key=candidates.get)
    comparison.chosen_method = chosen

    if chosen == "sigmoid":
        return sigmoid, comparison
    if chosen == "isotonic":
        return isotonic, comparison
    return ProbabilityCalibrator("none"), comparison

"""Model artifact bundling: everything needed to go from raw feature rows
to calibrated win/place probabilities + confidence, saved as one joblib
file per served ModelVersion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from racingedge_model.calibration import ProbabilityCalibrator
from racingedge_model.config import ARTIFACTS_DIR, PLACE_DEPTHS
from racingedge_model.models.place_models import (
    PlaceModelSet,
    enforce_monotonic_place_probabilities_df,
    rescale_place_probabilities_within_race,
)
from racingedge_model.models.preprocessing import FeaturePreprocessor, OutOfDistributionDetector
from racingedge_model.normalize import normalize_win_probabilities


@dataclass
class WinModelBundle:
    """A single win model + its own calibrator — used for both the primary
    serving model and the comparison-only logistic model."""

    algorithm: str
    preprocessor: FeaturePreprocessor
    model: object  # LogisticWinModel | GbmWinModel
    calibrator: ProbabilityCalibrator

    def predict_raw(self, X_raw: pd.DataFrame) -> np.ndarray:
        X = self.preprocessor.transform(X_raw)
        return self.model.predict_proba_positive(X)

    def predict_calibrated(self, X_raw: pd.DataFrame) -> np.ndarray:
        return self.calibrator.transform(self.predict_raw(X_raw))


@dataclass
class ServingModelBundle:
    """The full primary serving model: win + place(s) + calibration +
    everything needed for the ModelConfidence sub-scores."""

    win_algorithm: str
    preprocessor: FeaturePreprocessor
    ood_detector: OutOfDistributionDetector
    win_model: object
    win_calibrator: ProbabilityCalibrator
    place_models: PlaceModelSet
    place_calibrators: dict[int, ProbabilityCalibrator]
    brier_by_type: dict[str, float] = field(default_factory=dict)
    # Secondary model (same preprocessor/features) kept only for the
    # ModelConfidence "model agreement" sub-score — not used to produce any
    # stored probability itself.
    secondary_win_model: object | None = None

    def predict_win_raw(self, X_raw: pd.DataFrame) -> np.ndarray:
        X = self.preprocessor.transform(X_raw)
        return self.win_model.predict_proba_positive(X)

    def predict_win_calibrated_normalized(self, X_raw: pd.DataFrame, race_ids: pd.Series) -> pd.Series:
        raw = self.predict_win_raw(X_raw)
        calibrated = self.win_calibrator.transform(raw)
        return normalize_win_probabilities(pd.Series(calibrated, index=X_raw.index), race_ids)

    def predict_place_bands(self, X_raw: pd.DataFrame, race_ids: pd.Series) -> dict[int, pd.DataFrame]:
        """Returns {depth: DataFrame(raw=..., calibrated=...)} BEFORE
        monotonicity enforcement (apply enforce_monotonic_place_probabilities_df
        across the returned 'calibrated' columns for the final stored value)."""
        X = self.preprocessor.transform(X_raw)
        raw_by_depth = self.place_models.predict_proba(X)
        out: dict[int, pd.DataFrame] = {}
        for depth in PLACE_DEPTHS:
            raw = pd.Series(raw_by_depth[depth], index=X_raw.index)
            calibrated = pd.Series(self.place_calibrators[depth].transform(raw.values), index=X_raw.index)
            calibrated = rescale_place_probabilities_within_race(calibrated, race_ids, depth)
            out[depth] = pd.DataFrame({"raw": raw, "calibrated": calibrated})
        return out

    def predict_secondary_win_raw(self, X_raw: pd.DataFrame) -> np.ndarray | None:
        if self.secondary_win_model is None:
            return None
        X = self.preprocessor.transform(X_raw)
        return self.secondary_win_model.predict_proba_positive(X)


def save_bundle(bundle: object, model_version_id: str) -> str:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS_DIR / f"{model_version_id}.joblib"
    joblib.dump(bundle, path)
    return str(path.relative_to(ARTIFACTS_DIR.parent))


def load_bundle(relative_path: str):
    from racingedge_model.config import PYTHON_DIR

    return joblib.load(PYTHON_DIR / relative_path)

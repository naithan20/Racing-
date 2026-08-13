"""Model Confidence — a transparent, rule-based 0-100 score.

CRITICAL: this is NOT win probability and is never derived from it. A horse
can have a low win probability and high confidence (e.g. a well-exposed
90-rated handicapper unlikely to beat a stronger field — we're quite SURE
it's unlikely to win) or a high win probability and low confidence (a
lightly-raced favourite with almost no form to judge it on).

Weighted sum of six transparent sub-scores (weights sum to 1.0, chosen for
interpretability — not fitted, exactly like evidence density):

  evidence_density              0.30  — features/evidence.py score (0-1)
  feature_completeness          0.20  — 1 - fraction of tracked features missing for this runner
  model_agreement                0.20  — 1 - |P_logistic - P_gbm| / 0.30, clipped [0,1]
  probability_stability           0.15  — 1 - |win-prob percentile - top2-prob percentile| within the race
  historical_calibration_quality   0.10  — 1 - min(validation Brier for this race's flat/jumps type / 0.25, 1)
  in_distribution                   0.05  — 1 - fraction of extreme (outside train 5th-95th pct) features

Historical calibration quality defaults to a neutral 0.5 sub-score when no
validation-split breakdown is available (e.g. a fresh model with no
recorded metrics yet).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WEIGHTS = {
    "evidence_density": 0.30,
    "feature_completeness": 0.20,
    "model_agreement": 0.20,
    "probability_stability": 0.15,
    "historical_calibration_quality": 0.10,
    "in_distribution": 0.05,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

MODEL_AGREEMENT_SCALE = 0.30
CALIBRATION_BRIER_SCALE = 0.25


def model_agreement_score(prob_a: pd.Series, prob_b: pd.Series) -> pd.Series:
    diff = (prob_a - prob_b).abs()
    return (1 - (diff / MODEL_AGREEMENT_SCALE)).clip(lower=0, upper=1)


def probability_stability_score(win_prob: pd.Series, top2_prob: pd.Series, race_ids: pd.Series) -> pd.Series:
    win_pct = win_prob.groupby(race_ids).rank(pct=True)
    top2_pct = top2_prob.groupby(race_ids).rank(pct=True)
    return (1 - (win_pct - top2_pct).abs()).clip(lower=0, upper=1)


def historical_calibration_quality_score(flat_jumps: pd.Series, brier_by_type: dict[str, float] | None) -> pd.Series:
    if not brier_by_type:
        return pd.Series(0.5, index=flat_jumps.index)
    return flat_jumps.map(lambda t: 1 - min(brier_by_type.get(t, CALIBRATION_BRIER_SCALE) / CALIBRATION_BRIER_SCALE, 1)).clip(
        lower=0, upper=1
    )


def compute_model_confidence(
    *,
    evidence_density_0_1: pd.Series,
    missing_fraction: pd.Series,
    win_prob_logistic: pd.Series,
    win_prob_gbm: pd.Series,
    win_prob: pd.Series,
    top2_prob: pd.Series,
    race_ids: pd.Series,
    flat_jumps: pd.Series,
    extreme_feature_fraction: pd.Series,
    brier_by_type: dict[str, float] | None = None,
) -> pd.DataFrame:
    sub = pd.DataFrame(index=evidence_density_0_1.index)
    sub["evidence_density"] = evidence_density_0_1.clip(0, 1)
    sub["feature_completeness"] = (1 - missing_fraction).clip(0, 1)
    sub["model_agreement"] = model_agreement_score(win_prob_logistic, win_prob_gbm)
    sub["probability_stability"] = probability_stability_score(win_prob, top2_prob, race_ids)
    sub["historical_calibration_quality"] = historical_calibration_quality_score(flat_jumps, brier_by_type)
    sub["in_distribution"] = (1 - extreme_feature_fraction).clip(0, 1)

    score_100 = sum(WEIGHTS[k] * sub[k] for k in WEIGHTS) * 100
    out = sub.copy()
    out["model_confidence_100"] = score_100.round(2)
    out["model_confidence"] = (score_100 / 100).round(4)
    return out

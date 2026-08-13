"""Evaluation metrics shared by train.py (held-out test evaluation) and
backtest.py (arbitrary date-range backtests). Mirrors the metric
definitions in src/backtesting/scoring.ts so Python and TypeScript agree.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score


def win_metrics(y_true: pd.Series, y_prob: pd.Series) -> dict:
    y_true = np.asarray(y_true)
    y_prob = np.clip(np.asarray(y_prob, dtype=float), 1e-6, 1 - 1e-6)
    n = len(y_true)
    metrics = {
        "n": n,
        "brier_score": float(brier_score_loss(y_true, y_prob)) if n > 0 else None,
        "log_loss": float(log_loss(y_true, y_prob, labels=[0, 1])) if n > 0 else None,
        "roc_auc": float(roc_auc_score(y_true, y_prob)) if n > 0 and len(set(y_true)) > 1 else None,
        "expected_wins": float(y_prob.sum()) if n > 0 else None,
        "actual_wins": int(y_true.sum()) if n > 0 else None,
        "win_strike_rate": float(y_true.mean()) if n > 0 else None,
        "avg_predicted_probability": float(y_prob.mean()) if n > 0 else None,
    }
    return metrics


def place_metrics(y_true: pd.Series, y_prob: pd.Series) -> dict:
    # Same shape as win_metrics but semantically for a given place depth.
    return win_metrics(y_true, y_prob) | {"metric_type": "place"}


def top_ranked_strike_rate(dataset: pd.DataFrame, prob_col: str, race_id_col: str, win_col: str) -> float | None:
    """Fraction of races where the model's single highest-probability
    selection actually won — the "top selection strike rate" metric."""
    if len(dataset) == 0:
        return None
    top_picks = dataset.loc[dataset.groupby(race_id_col)[prob_col].idxmax()]
    if len(top_picks) == 0:
        return None
    return float(top_picks[win_col].mean())


def calibration_buckets(y_true: pd.Series, y_prob: pd.Series, bucket_count: int = 10) -> list[dict]:
    y_true = np.asarray(y_true)
    y_prob = np.clip(np.asarray(y_prob, dtype=float), 0, 1)
    buckets = []
    for i in range(bucket_count):
        lo, hi = i / bucket_count, (i + 1) / bucket_count
        mask = (y_prob >= lo) & (y_prob < hi if i < bucket_count - 1 else y_prob <= hi)
        n = int(mask.sum())
        buckets.append(
            {
                "bucket_label": f"{round(lo * 100)}-{round(hi * 100)}%",
                "bucket_min": lo,
                "bucket_max": hi,
                "sample_size": n,
                "mean_predicted_probability": float(y_prob[mask].mean()) if n > 0 else None,
                "observed_frequency": float(y_true[mask].mean()) if n > 0 else None,
            }
        )
    return buckets


def roi_flat_stake(y_true: pd.Series, odds_decimal: pd.Series, stake: float = 1.0) -> dict:
    """Hypothetical flat-stake ROI backing every runner at its (historical)
    starting price — an EVALUATION output, never a training target."""
    valid = odds_decimal.notna() & y_true.notna()
    y = y_true[valid]
    odds = odds_decimal[valid]
    if len(y) == 0:
        return {"n": 0, "total_staked": None, "total_return": None, "roi_percent": None}
    total_staked = stake * len(y)
    total_return = float((y * odds * stake).sum())
    profit = total_return - total_staked
    return {
        "n": int(len(y)),
        "total_staked": total_staked,
        "total_return": total_return,
        "profit": profit,
        "roi_percent": float(profit / total_staked * 100) if total_staked > 0 else None,
    }

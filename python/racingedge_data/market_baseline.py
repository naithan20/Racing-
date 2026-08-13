"""Market-implied-probability baseline.

Not a trained model — normalizes each race's bookmaker decimal odds into
implied win probabilities, removing the bookmaker overround, exactly the
way RacingEdge's own model output gets normalized (`src/lib/odds.ts` /
`racingedge_model.normalize`). This is the benchmark the project's
requirements insist RacingEdge be measured against: the real question is
**"does RacingEdge add information beyond the market"**, not merely
"can it identify some winners" in isolation.

This module deliberately computes ONLY the market baseline and a
side-by-side comparison against an already-computed model probability
column — it does not train anything, tune anything, or attempt to beat the
market. Per the project's explicit Phase 3A constraints, combining
RacingEdge's own probability with the market probability as a joint
feature is infrastructure for LATER — `combined_features` below builds the
column but nothing here fits a model on it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from racingedge_model.evaluate import win_metrics


def implied_probability(odds_decimal: pd.Series | float) -> pd.Series | float:
    return 1.0 / odds_decimal


def normalize_market_probabilities(odds_decimal: pd.Series) -> pd.Series:
    """Removes bookmaker overround: raw implied probabilities (1/odds)
    normalized within one race so they sum to 1. Returns NaN for every row
    if the group's odds are missing/non-positive (can't safely normalize a
    field with incomplete odds coverage)."""

    raw = 1.0 / odds_decimal.astype(float)
    if raw.isna().any() or (odds_decimal <= 0).any():
        return pd.Series([np.nan] * len(odds_decimal), index=odds_decimal.index)
    total = raw.sum()
    if total <= 0 or pd.isna(total):
        return pd.Series([np.nan] * len(odds_decimal), index=odds_decimal.index)
    return raw / total


def compute_market_probabilities(
    dataset: pd.DataFrame, odds_col: str = "starting_price_decimal", race_id_col: str = "race_id"
) -> pd.Series:
    """Per-race normalized market-implied win probability for every row of
    a race-grouped runner-level dataset (same shape as
    `racingedge_model.dataset.build_training_dataset`'s output). A race
    where any runner is missing odds returns NaN for the whole race —
    partial market data cannot be safely normalized to sum to 1."""

    result = dataset.groupby(race_id_col, group_keys=False)[odds_col].apply(
        lambda s: normalize_market_probabilities(s)
    )
    return result.reindex(dataset.index)


def compare_market_vs_model(
    dataset: pd.DataFrame,
    model_prob_col: str,
    target_col: str = "WIN_TARGET",
    market_prob_col: str = "market_probability",
) -> dict:
    """Brier score / log loss / ROC-AUC for the market baseline and for an
    already-computed model probability column, on the SAME rows (rows
    where either is missing are excluded from both, so the comparison is
    apples-to-apples) — the headline "does RacingEdge add information
    beyond the market" comparison."""

    usable = dataset.dropna(subset=[model_prob_col, market_prob_col, target_col])
    market_metrics = win_metrics(usable[target_col], usable[market_prob_col])
    model_metrics = win_metrics(usable[target_col], usable[model_prob_col])

    return {
        "n_comparable_rows": len(usable),
        "market": market_metrics,
        "model": model_metrics,
        "model_beats_market_on_brier": (
            model_metrics["brier_score"] < market_metrics["brier_score"]
            if model_metrics["brier_score"] is not None and market_metrics["brier_score"] is not None
            else None
        ),
        "model_beats_market_on_log_loss": (
            model_metrics["log_loss"] < market_metrics["log_loss"]
            if model_metrics["log_loss"] is not None and market_metrics["log_loss"] is not None
            else None
        ),
    }


def combined_features(
    dataset: pd.DataFrame,
    model_prob_col: str,
    market_prob_col: str = "market_probability",
) -> pd.DataFrame:
    """Builds a `model_market_probability_gap` column (model minus market
    implied probability) — infrastructure for a FUTURE combined
    model/market feature, per the project's explicit instruction to build
    this plumbing without optimizing or assuming it will outperform either
    input alone. Nothing in this module fits or evaluates a combined
    model."""

    out = dataset.copy()
    out["model_market_probability_gap"] = out[model_prob_col] - out[market_prob_col]
    return out

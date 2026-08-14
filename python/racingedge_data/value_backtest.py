"""Value-cohort backtesting — Phase 3C section 18.

Given already-generated MODEL win probabilities and the eventual SP/BSP
for the same runners, this buckets runners into VALUE COHORTS by how far
the model's probability diverges from the market's (`value_edge_relative`,
same formula as `racingedge_model.value`), then reports the ACTUAL
outcome rate and flat-stake ROI observed within each cohort.

Two things this module deliberately does NOT do:

- It does not verify that `model_prob_col` was generated without access
  to the target race's own SP/BSP — that guarantee is the point-in-time
  feature architecture's job (`POINT_IN_TIME_ARCHITECTURE.md`,
  `racingedge_data.leakage_audit`), enforced upstream of this module, at
  feature-build time. This module only evaluates whatever probabilities
  it's handed.
- It does not fit, tune, or select anything to maximise the resulting
  ROI figures. Cohort boundaries are a fixed, documented lookup table
  (`DEFAULT_EDGE_BINS`), not something this module chooses from the data.

SP/BSP is used here strictly as the CLOSING/SP MARKET BENCHMARK for
post-hoc comparison (see `racingedge_data.providers.betfair_sp`) — never
as a model input.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from racingedge_model.evaluate import roi_flat_stake
from racingedge_model.value import market_implied_probability

# Fixed, documented value-edge buckets: (model_probability - market_implied)
# / market_implied. Chosen once, not derived from data, so cohort
# boundaries never drift toward whatever makes the backtest look best.
DEFAULT_EDGE_BINS = [-1.0, -0.5, -0.2, -0.1, 0.0, 0.1, 0.2, 0.5, float("inf")]
DEFAULT_EDGE_LABELS = [
    "<=-50%",
    "-50%..-20%",
    "-20%..-10%",
    "-10%..0%",
    "0%..10%",
    "10%..20%",
    "20%..50%",
    ">50%",
]

_COHORT_COLUMNS = [
    "cohort",
    "n",
    "avg_model_probability",
    "avg_market_implied_probability",
    "avg_fair_odds_decimal",
    "avg_market_odds_decimal",
    "actual_win_rate",
    "roi_percent_flat_stake",
]


def build_value_cohorts(
    dataset: pd.DataFrame,
    model_prob_col: str,
    market_odds_col: str,
    outcome_col: str,
    edge_bins: Optional[list[float]] = None,
    edge_labels: Optional[list[str]] = None,
) -> pd.DataFrame:
    """One row per value-edge cohort. Rows missing `model_prob_col`,
    `market_odds_col`, or `outcome_col` are excluded before bucketing
    (can't assess value without both a model probability and a market
    price). An empty cohort still appears in the output with `n=0` and
    every metric `None`, so a sparse dataset's gaps are visible rather
    than silently omitted."""

    edge_bins = edge_bins if edge_bins is not None else DEFAULT_EDGE_BINS
    edge_labels = edge_labels if edge_labels is not None else DEFAULT_EDGE_LABELS

    usable = dataset.dropna(subset=[model_prob_col, market_odds_col, outcome_col]).copy()
    if usable.empty:
        return pd.DataFrame(columns=_COHORT_COLUMNS)

    usable["_market_implied"] = market_implied_probability(usable[market_odds_col])
    usable["_edge_relative"] = (usable[model_prob_col] - usable["_market_implied"]) / usable["_market_implied"]
    usable["_fair_odds"] = 1.0 / usable[model_prob_col].where(
        (usable[model_prob_col] > 0) & (usable[model_prob_col] <= 1)
    )
    usable["_cohort"] = pd.cut(usable["_edge_relative"], bins=edge_bins, labels=edge_labels, include_lowest=True)

    rows = []
    for label in edge_labels:
        subset = usable.loc[usable["_cohort"] == label]
        n = int(len(subset))
        if n == 0:
            rows.append({col: (label if col == "cohort" else (0 if col == "n" else None)) for col in _COHORT_COLUMNS})
            continue
        roi = roi_flat_stake(subset[outcome_col], subset[market_odds_col])
        rows.append(
            {
                "cohort": label,
                "n": n,
                "avg_model_probability": round(float(subset[model_prob_col].mean()), 4),
                "avg_market_implied_probability": round(float(subset["_market_implied"].mean()), 4),
                "avg_fair_odds_decimal": (
                    round(float(subset["_fair_odds"].mean()), 2) if subset["_fair_odds"].notna().any() else None
                ),
                "avg_market_odds_decimal": round(float(subset[market_odds_col].mean()), 2),
                "actual_win_rate": round(float(subset[outcome_col].mean()), 4),
                "roi_percent_flat_stake": roi["roi_percent"],
            }
        )
    result = pd.DataFrame(rows, columns=_COHORT_COLUMNS)
    # Building a DataFrame from a list of dicts containing `None` coerces
    # numeric columns to float64, turning `None` into `NaN` — which
    # `to_dict()`/`json.dumps` would then render as the invalid-JSON token
    # `NaN` instead of `null`. Convert back to object dtype so an empty
    # cohort's `None` metrics stay genuinely `None`, not `NaN`.
    return result.astype(object).where(result.notna(), None)


def value_backtest_report(
    dataset: pd.DataFrame,
    model_prob_col: str,
    market_odds_col: str,
    outcome_col: str,
    edge_bins: Optional[list[float]] = None,
    edge_labels: Optional[list[str]] = None,
) -> dict:
    """Bundles `build_value_cohorts` with the count of usable rows and an
    explicit caveat string, ready to drop into a JSON backtest report
    alongside `racingedge_data.market_baseline.compare_market_vs_model`."""

    cohorts = build_value_cohorts(dataset, model_prob_col, market_odds_col, outcome_col, edge_bins, edge_labels)
    n_total = int(cohorts["n"].sum()) if len(cohorts) else 0
    return {
        "n_runners_with_model_and_market_odds": n_total,
        "cohorts": cohorts.to_dict(orient="records"),
        "caveat": (
            "Model probabilities here are assumed to have been generated without access to the "
            "target race's own SP/BSP — this module does not verify that itself; it relies on the "
            "point-in-time feature architecture upstream (see POINT_IN_TIME_ARCHITECTURE.md and "
            "racingedge_data.leakage_audit). SP/BSP used here is the CLOSING/SP MARKET BENCHMARK, "
            "used only for post-hoc comparison — never as a model input. Cohort boundaries are "
            "fixed and were not chosen to maximise these ROI figures."
        ),
    }

import numpy as np
import pandas as pd

from racingedge_data.market_baseline import (
    combined_features,
    compare_market_vs_model,
    compute_market_probabilities,
    normalize_market_probabilities,
)


class TestNormalizeMarketProbabilities:
    def test_removes_overround_and_sums_to_one(self):
        # Overround example: implied probabilities sum to > 1 before normalizing.
        odds = pd.Series([2.0, 4.0, 4.0])  # implied: 0.5, 0.25, 0.25 -> sums to 1.0 already
        normalized = normalize_market_probabilities(odds)
        assert np.isclose(normalized.sum(), 1.0)

    def test_typical_overround_case(self):
        odds = pd.Series([1.8, 3.0, 8.0])  # implied sum > 1 (bookmaker overround)
        raw_sum = (1 / odds).sum()
        assert raw_sum > 1.0
        normalized = normalize_market_probabilities(odds)
        assert np.isclose(normalized.sum(), 1.0)

    def test_missing_odds_returns_all_nan(self):
        odds = pd.Series([2.0, np.nan, 4.0])
        normalized = normalize_market_probabilities(odds)
        assert normalized.isna().all()

    def test_zero_or_negative_odds_returns_all_nan(self):
        odds = pd.Series([2.0, 0.0, 4.0])
        normalized = normalize_market_probabilities(odds)
        assert normalized.isna().all()


class TestComputeMarketProbabilities:
    def test_computes_per_race_grouped_probabilities(self):
        dataset = pd.DataFrame(
            {
                "race_id": ["r1", "r1", "r2", "r2", "r2"],
                "starting_price_decimal": [2.0, 2.0, 3.0, 3.0, 3.0],
            }
        )
        result = compute_market_probabilities(dataset)
        assert len(result) == 5
        r1_sum = result[dataset["race_id"] == "r1"].sum()
        r2_sum = result[dataset["race_id"] == "r2"].sum()
        assert np.isclose(r1_sum, 1.0)
        assert np.isclose(r2_sum, 1.0)

    def test_partial_missing_odds_excludes_whole_race(self):
        dataset = pd.DataFrame(
            {
                "race_id": ["r1", "r1", "r2", "r2"],
                "starting_price_decimal": [2.0, np.nan, 3.0, 4.0],
            }
        )
        result = compute_market_probabilities(dataset)
        assert result[dataset["race_id"] == "r1"].isna().all()
        assert not result[dataset["race_id"] == "r2"].isna().any()


class TestCompareMarketVsModel:
    def test_reports_metrics_for_both_and_a_comparison_flag(self):
        dataset = pd.DataFrame(
            {
                "WIN_TARGET": [1, 0, 0, 1, 0, 0],
                "model_probability": [0.5, 0.2, 0.1, 0.6, 0.15, 0.1],
                "market_probability": [0.4, 0.3, 0.1, 0.3, 0.2, 0.1],
            }
        )
        result = compare_market_vs_model(dataset, model_prob_col="model_probability")
        assert result["n_comparable_rows"] == 6
        assert result["market"]["brier_score"] is not None
        assert result["model"]["brier_score"] is not None
        assert result["model_beats_market_on_brier"] in (True, False)

    def test_excludes_rows_missing_either_probability(self):
        dataset = pd.DataFrame(
            {
                "WIN_TARGET": [1, 0, 0],
                "model_probability": [0.5, np.nan, 0.1],
                "market_probability": [0.4, 0.3, 0.1],
            }
        )
        result = compare_market_vs_model(dataset, model_prob_col="model_probability")
        assert result["n_comparable_rows"] == 2


class TestCombinedFeatures:
    def test_adds_gap_column_without_fitting_anything(self):
        dataset = pd.DataFrame({"model_probability": [0.5, 0.3], "market_probability": [0.4, 0.35]})
        result = combined_features(dataset, model_prob_col="model_probability")
        assert list(result["model_market_probability_gap"]) == [0.5 - 0.4, 0.3 - 0.35]
        # Original dataset is untouched (a copy was returned).
        assert "model_market_probability_gap" not in dataset.columns

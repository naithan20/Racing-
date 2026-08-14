import pandas as pd
import pytest

from racingedge_data.value_backtest import (
    DEFAULT_EDGE_LABELS,
    build_value_cohorts,
    value_backtest_report,
)


def _sample_dataset() -> pd.DataFrame:
    # Market implied = 1/odds. Edge relative = (model - market) / market.
    # pd.cut buckets are right-closed, so an edge of exactly 0.0 or -0.5
    # falls into the LOWER of its two adjacent bucket labels.
    #   row 0: odds=4.0 -> market=0.25, model=0.40 -> edge = +0.60 -> ">50%"
    #   row 1: odds=2.0 -> market=0.50, model=0.50 -> edge =  0.00 -> "-10%..0%" (boundary, right-closed)
    #   row 2: odds=10.0 -> market=0.10, model=0.05 -> edge = -0.50 -> "<=-50%" (boundary, right-closed)
    #   row 3: odds=5.0 -> market=0.20, model=0.20 -> edge = 0.00 -> "-10%..0%"
    return pd.DataFrame(
        {
            "model_probability": [0.40, 0.50, 0.05, 0.20],
            "sp": [4.0, 2.0, 10.0, 5.0],
            "won": [1, 0, 0, 0],
        }
    )


class TestBuildValueCohorts:
    def test_returns_one_row_per_defined_cohort(self):
        cohorts = build_value_cohorts(_sample_dataset(), "model_probability", "sp", "won")
        assert list(cohorts["cohort"]) == DEFAULT_EDGE_LABELS

    def test_total_n_matches_usable_rows(self):
        cohorts = build_value_cohorts(_sample_dataset(), "model_probability", "sp", "won")
        assert cohorts["n"].sum() == 4

    def test_rows_missing_model_or_market_are_excluded(self):
        df = _sample_dataset()
        df.loc[0, "model_probability"] = None
        cohorts = build_value_cohorts(df, "model_probability", "sp", "won")
        assert cohorts["n"].sum() == 3

    def test_positive_edge_cohort_contains_the_winning_row(self):
        cohorts = build_value_cohorts(_sample_dataset(), "model_probability", "sp", "won")
        top_cohort = cohorts[cohorts["cohort"] == ">50%"].iloc[0]
        assert top_cohort["n"] == 1
        assert top_cohort["actual_win_rate"] == pytest.approx(1.0)
        assert top_cohort["avg_market_odds_decimal"] == pytest.approx(4.0)

    def test_empty_cohort_has_none_metrics_not_missing_row(self):
        cohorts = build_value_cohorts(_sample_dataset(), "model_probability", "sp", "won")
        empty = cohorts[cohorts["cohort"] == "20%..50%"].iloc[0]
        assert empty["n"] == 0
        assert empty["actual_win_rate"] is None
        assert empty["roi_percent_flat_stake"] is None

    def test_all_rows_missing_returns_empty_dataframe_with_expected_columns(self):
        df = pd.DataFrame({"model_probability": [None], "sp": [None], "won": [None]})
        cohorts = build_value_cohorts(df, "model_probability", "sp", "won")
        assert len(cohorts) == 0
        assert "cohort" in cohorts.columns
        assert "roi_percent_flat_stake" in cohorts.columns

    def test_roi_reflects_actual_backing_result(self):
        # A single-runner cohort that wins at odds 4.0 with a flat £1 stake:
        # return = 4.0, staked = 1.0, profit = 3.0 -> ROI = 300%.
        df = pd.DataFrame({"model_probability": [0.40], "sp": [4.0], "won": [1]})
        cohorts = build_value_cohorts(df, "model_probability", "sp", "won")
        winning_cohort = cohorts[cohorts["n"] > 0].iloc[0]
        assert winning_cohort["roi_percent_flat_stake"] == pytest.approx(300.0)


class TestValueBacktestReport:
    def test_report_has_caveat_and_matches_cohort_total(self):
        report = value_backtest_report(_sample_dataset(), "model_probability", "sp", "won")
        assert report["n_runners_with_model_and_market_odds"] == 4
        assert "SP/BSP" in report["caveat"]
        assert len(report["cohorts"]) == len(DEFAULT_EDGE_LABELS)

    def test_report_on_empty_dataset_does_not_crash(self):
        df = pd.DataFrame({"model_probability": [], "sp": [], "won": []})
        report = value_backtest_report(df, "model_probability", "sp", "won")
        assert report["n_runners_with_model_and_market_odds"] == 0

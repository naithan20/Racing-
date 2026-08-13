import numpy as np
import pandas as pd

from racingedge_model.models.preprocessing import FeaturePreprocessor, OutOfDistributionDetector


def test_missing_values_get_an_indicator_column_and_are_imputed():
    train = pd.DataFrame({"a": [1.0, 2.0, np.nan, 4.0], "b": [10.0, 20.0, 30.0, 40.0]})
    pre = FeaturePreprocessor(["a", "b"]).fit(train)

    assert "a" in pre.indicator_columns_
    assert "b" not in pre.indicator_columns_

    test = pd.DataFrame({"a": [np.nan], "b": [99.0]})
    out = pre.transform(test)
    assert out["a__isnan"].iloc[0] == 1
    assert out["a"].iloc[0] == pre.medians_["a"]
    assert "b__isnan" not in out.columns


def test_missing_is_never_silently_treated_as_zero_when_column_has_no_zeros():
    # A win-rate-like column where 0 would be a meaningful (bad) value —
    # imputation must use the median, not zero, and the indicator must flag it.
    train = pd.DataFrame({"win_rate": [0.4, 0.5, 0.6, np.nan]})
    pre = FeaturePreprocessor(["win_rate"]).fit(train)
    out = pre.transform(pd.DataFrame({"win_rate": [np.nan]}))
    assert out["win_rate"].iloc[0] != 0
    assert out["win_rate__isnan"].iloc[0] == 1


def test_missing_fraction_counts_correctly():
    train = pd.DataFrame({"a": [1.0, 2.0], "b": [1.0, 2.0]})
    pre = FeaturePreprocessor(["a", "b"]).fit(train)
    row = pd.DataFrame({"a": [np.nan], "b": [5.0]})
    frac = pre.missing_fraction(row)
    assert frac.iloc[0] == 0.5


def test_out_of_distribution_detector_flags_extreme_values():
    train = pd.DataFrame({"x": list(range(100))})  # 0..99
    detector = OutOfDistributionDetector(["x"]).fit(train)
    extreme = pd.DataFrame({"x": [500]})
    normal = pd.DataFrame({"x": [50]})
    assert detector.extreme_fraction(extreme).iloc[0] == 1.0
    assert detector.extreme_fraction(normal).iloc[0] == 0.0

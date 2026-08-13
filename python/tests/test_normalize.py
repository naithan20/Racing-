import pandas as pd
import pytest

from racingedge_model.normalize import assert_probabilities_sum_to_one, normalize_win_probabilities


def test_normalized_probabilities_sum_to_one_per_race():
    scores = pd.Series([0.6, 0.3, 0.4, 0.2, 0.1])
    race_ids = pd.Series(["A", "A", "A", "B", "B"])
    normalized = normalize_win_probabilities(scores, race_ids)
    assert_probabilities_sum_to_one(normalized, race_ids)


def test_normalization_preserves_within_race_ranking():
    scores = pd.Series([0.6, 0.3, 0.1])
    race_ids = pd.Series(["A", "A", "A"])
    normalized = normalize_win_probabilities(scores, race_ids)
    assert normalized.iloc[0] > normalized.iloc[1] > normalized.iloc[2]


def test_assert_probabilities_sum_to_one_raises_on_bad_input():
    bad = pd.Series([0.9, 0.9])  # deliberately not normalized
    race_ids = pd.Series(["A", "A"])
    with pytest.raises(AssertionError):
        assert_probabilities_sum_to_one(bad, race_ids)


def test_normalize_handles_single_runner_race():
    scores = pd.Series([0.2])
    race_ids = pd.Series(["A"])
    normalized = normalize_win_probabilities(scores, race_ids)
    assert normalized.iloc[0] == pytest.approx(1.0)

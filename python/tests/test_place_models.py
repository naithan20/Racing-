import pandas as pd
import pytest

from racingedge_model.models.place_models import (
    enforce_monotonic_place_probabilities,
    enforce_monotonic_place_probabilities_df,
    rescale_place_probabilities_within_race,
)


def test_enforce_monotonic_fixes_a_violating_sequence():
    # top3 (0.30) is LESS than top2 (0.35) — physically impossible.
    raw = {2: 0.35, 3: 0.30, 4: 0.45, 5: 0.44, 6: 0.60}
    adjusted = enforce_monotonic_place_probabilities(raw)
    values = [adjusted[d] for d in sorted(adjusted)]
    assert values == sorted(values)
    assert adjusted[3] >= adjusted[2]
    assert adjusted[5] >= adjusted[4]


def test_enforce_monotonic_leaves_already_monotonic_sequence_unchanged():
    raw = {2: 0.1, 3: 0.2, 4: 0.3, 5: 0.4, 6: 0.5}
    adjusted = enforce_monotonic_place_probabilities(raw)
    assert adjusted == raw


def test_enforce_monotonic_df_matches_scalar_version_row_by_row():
    frames = {
        2: pd.Series([0.35, 0.1]),
        3: pd.Series([0.30, 0.2]),
        4: pd.Series([0.45, 0.3]),
        5: pd.Series([0.44, 0.4]),
        6: pd.Series([0.60, 0.5]),
    }
    result = enforce_monotonic_place_probabilities_df(frames)
    for row_idx in range(2):
        raw_row = {d: frames[d].iloc[row_idx] for d in frames}
        expected = enforce_monotonic_place_probabilities(raw_row)
        for d in frames:
            assert result[d].iloc[row_idx] == pytest.approx(expected[d])


def test_rescale_place_probabilities_sum_to_depth_within_race():
    probs = pd.Series([0.5, 0.5, 0.5, 0.5])
    race_ids = pd.Series(["A", "A", "A", "A"])
    rescaled = rescale_place_probabilities_within_race(probs, race_ids, depth=2)
    assert rescaled.sum() == pytest.approx(2.0, abs=1e-6)


def test_rescale_caps_target_sum_at_field_size():
    # 3-runner race, depth=6 requested but only 3 runners can ever place —
    # every runner is a "sure thing" to finish in the top 6. Each is scaled
    # towards 1.0 but clipped to 0.999 (see rescale_place_probabilities_
    # within_race) to avoid a literal-certainty probability, so the sum
    # lands just under 3.0 rather than exactly at it.
    probs = pd.Series([0.5, 0.5, 0.5])
    race_ids = pd.Series(["A", "A", "A"])
    rescaled = rescale_place_probabilities_within_race(probs, race_ids, depth=6)
    assert rescaled.sum() == pytest.approx(3.0, abs=0.01)
    assert (rescaled <= 0.999).all()

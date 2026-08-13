import math

from racingedge_model.config import PLACE_DEPTHS
from racingedge_model.dataset import WIN_TARGET_COL, compute_targets, place_target_col


def test_winner_scores_one_on_every_target():
    targets = compute_targets(1)
    assert targets[WIN_TARGET_COL] == 1
    for depth in PLACE_DEPTHS:
        assert targets[place_target_col(depth)] == 1


def test_midfield_finisher_scores_correctly_by_depth():
    # Finished 4th: not a winner, not top2/top3, but top4/top5/top6.
    targets = compute_targets(4)
    assert targets[WIN_TARGET_COL] == 0
    assert targets[place_target_col(2)] == 0
    assert targets[place_target_col(3)] == 0
    assert targets[place_target_col(4)] == 1
    assert targets[place_target_col(5)] == 1
    assert targets[place_target_col(6)] == 1


def test_non_finisher_scores_zero_on_every_target():
    for missing in (None, math.nan):
        targets = compute_targets(missing)
        assert targets[WIN_TARGET_COL] == 0
        for depth in PLACE_DEPTHS:
            assert targets[place_target_col(depth)] == 0


def test_last_place_finisher_in_large_field_scores_zero():
    targets = compute_targets(12)
    assert targets[WIN_TARGET_COL] == 0
    for depth in PLACE_DEPTHS:
        assert targets[place_target_col(depth)] == 0

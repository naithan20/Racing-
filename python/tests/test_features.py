import pandas as pd

from racingedge_model.config import MIN_SAMPLES_DRAW_BIAS
from racingedge_model.features.class_features import compute_class_features
from racingedge_model.features.current_form import compute_current_form_features
from racingedge_model.features.draw import compute_draw_features
from racingedge_model.features.evidence import WEIGHTS, compute_evidence_density
from racingedge_model.features.rating import compute_rating_features


def _form_row(**overrides):
    base = {
        "raceDate": pd.Timestamp("2026-01-01", tz="UTC"),
        "course": "Test Park",
        "distanceFurlongs": 10.0,
        "going": "Good",
        "raceClass": 4,
        "flatJumps": "FLAT",
        "fieldSize": 8,
        "finishingPosition": 3,
        "finishStatus": "RAN",
        "beatenDistanceLengths": 2.0,
        "startingPriceDecimal": 5.0,
        "officialRating": 80,
        "weightPounds": 130,
        "draw": 4,
        "jockeyName": "J. Test",
        "headgear": None,
        "raceComment": None,
        "position3fOut": 3,
        "position2fOut": 3,
        "position1fOut": 3,
        "finishingSpeedPercentage": 100.0,
        "paceClassification": "Prominent",
    }
    base.update(overrides)
    return base


class TestCurrentFormFeatures:
    def test_first_time_out_has_no_form_but_is_flagged(self):
        empty = pd.DataFrame(columns=["finishingPosition", "fieldSize", "raceDate", "beatenDistanceLengths", "finishingSpeedPercentage"])
        out = compute_current_form_features(empty, pd.Timestamp("2026-01-01", tz="UTC"), None)
        assert out["first_time_out_flag"] == 1
        assert out["career_runs_to_date"] == 0
        assert pd.isna(out["form_last_run_position"])

    def test_wins_and_places_counted_correctly(self):
        rows = [
            _form_row(raceDate=pd.Timestamp("2026-03-01", tz="UTC"), finishingPosition=1),
            _form_row(raceDate=pd.Timestamp("2026-02-01", tz="UTC"), finishingPosition=5),
            _form_row(raceDate=pd.Timestamp("2026-01-01", tz="UTC"), finishingPosition=2),
        ]
        df = pd.DataFrame(rows).sort_values("raceDate", ascending=False).reset_index(drop=True)
        out = compute_current_form_features(df, pd.Timestamp("2026-04-01", tz="UTC"), 31)
        assert out["form_wins_last3"] == 1
        assert out["form_places_last3"] == 2  # positions 1 and 2 are top-3
        assert out["form_last_run_position"] == 1

    def test_quick_turnaround_and_long_layoff_flags(self):
        empty = pd.DataFrame(columns=["finishingPosition", "fieldSize", "raceDate", "beatenDistanceLengths", "finishingSpeedPercentage"])
        quick = compute_current_form_features(empty, pd.Timestamp("2026-01-01", tz="UTC"), 5)
        assert quick["quick_turnaround_flag"] == 1
        assert quick["long_layoff_flag"] == 0

        layoff = compute_current_form_features(empty, pd.Timestamp("2026-01-01", tz="UTC"), 220)
        assert layoff["long_layoff_flag"] == 1
        assert layoff["quick_turnaround_flag"] == 0


class TestClassFeatures:
    def test_class_rise_is_positive_when_moving_to_a_lower_class_number(self):
        # Previous run was class 5 (easier); today is class 2 (harder) ->
        # class_change_from_prev = 5 - 2 = +3 (a rise in class).
        prior = pd.DataFrame([_form_row(raceClass=5)])
        out = compute_class_features(2, prior)
        assert out["class_change_from_prev"] == 3

    def test_class_drop_is_negative(self):
        prior = pd.DataFrame([_form_row(raceClass=2)])
        out = compute_class_features(5, prior)
        assert out["class_change_from_prev"] == -3

    def test_missing_current_class_returns_all_nan(self):
        prior = pd.DataFrame([_form_row(raceClass=2)])
        out = compute_class_features(None, prior)
        assert pd.isna(out["current_class"])


class TestRatingFeatures:
    def test_percentile_and_diffs_computed_against_declared_field(self):
        field = pd.Series([80.0, 90.0, 100.0, 70.0])  # this runner is 90
        out = compute_rating_features(90.0, field, pd.DataFrame(), "HANDICAP")
        assert out["or_diff_to_field_mean"] == 90.0 - field.mean()
        assert out["or_diff_to_top_rated"] == 90.0 - 100.0
        assert out["handicap_flag"] == 1

    def test_well_in_flag_set_when_below_recent_best_mark(self):
        prior = pd.DataFrame(
            [_form_row(officialRating=95, finishingPosition=1), _form_row(officialRating=90, finishingPosition=2)]
        )
        out = compute_rating_features(88.0, pd.Series([88.0]), prior, "HANDICAP")
        assert out["or_vs_best_recent_mark"] == 88.0 - 95.0
        assert out["well_in_flag"] == 1


class TestDrawFeatures:
    def test_draw_bias_withheld_below_minimum_sample_size(self):
        global_prior = pd.DataFrame(
            {
                "course": ["Test Park"] * 5,
                "distanceFurlongs": [10.0] * 5,
                "fieldSizeBand": ["MEDIUM"] * 5,
                "draw": [1, 2, 3, 4, 5],
                "raceId": ["r1", "r1", "r1", "r1", "r1"],
                "finishingPosition": [1, 2, 3, 4, 5],
            }
        )
        assert len(global_prior) < MIN_SAMPLES_DRAW_BIAS
        out = compute_draw_features(
            draw=2,
            field_draws=pd.Series([1, 2, 3, 4, 5, 6, 7, 8]),
            field_size=8,
            course="Test Park",
            distance_furlongs=10.0,
            global_prior_runs=global_prior,
            is_leader_style=False,
        )
        assert out["draw_bias_available"] == 0
        assert pd.isna(out["draw_bias_win_rate"])

    def test_draw_bucket_assignment(self):
        out = compute_draw_features(
            draw=1,
            field_draws=pd.Series(range(1, 13)),
            field_size=12,
            course="Test Park",
            distance_furlongs=6.0,
            global_prior_runs=pd.DataFrame(),
            is_leader_style=True,
        )
        assert out["draw_bucket_low"] == 1
        assert out["draw_bucket_high"] == 0


class TestEvidenceDensity:
    def test_weights_sum_to_one(self):
        assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

    def test_zero_history_gives_a_low_score(self):
        empty = pd.DataFrame(columns=["position3fOut", "paceClassification", "officialRating"])
        out = compute_evidence_density(0, 0, 0, empty, None, None)
        assert 0 <= out["evidence_density_score"] <= 1
        assert out["evidence_density_score"] < 0.1
        assert out["evidence_density_label"] == "VERY_LOW"

    def test_extensive_history_gives_a_high_score(self):
        rows = [_form_row() for _ in range(15)]
        df = pd.DataFrame(rows)
        out = compute_evidence_density(18, 8, 4, df, trainer_runs_30d=10, jockey_runs_30d=10)
        assert out["evidence_density_score"] > 0.8
        assert out["evidence_density_label"] in ("HIGH", "VERY_HIGH")

    def test_score_is_never_negative_or_above_one(self):
        rows = [_form_row() for _ in range(3)]
        out = compute_evidence_density(3, 1, 0, pd.DataFrame(rows), trainer_runs_30d=0, jockey_runs_30d=0)
        assert 0 <= out["evidence_density_score"] <= 1

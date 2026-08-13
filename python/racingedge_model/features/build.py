"""Feature pipeline orchestration.

`compute_runner_features` is the single entry point that combines every
feature group for one (runner, race) pair. It is deliberately given
ALREADY-FILTERED history (raceDate < as_of_date) by the caller — see
dataset.py and predict.py — and additionally asserts that invariant itself
as a defense-in-depth leakage check, since a leakage bug here would corrupt
every downstream model.
"""

from __future__ import annotations

import pandas as pd

from racingedge_model.features import (
    age_experience,
    class_features,
    course_distance_going,
    current_form,
    draw,
    evidence,
    headgear_changes,
    pace,
    rating,
    trainer_jockey,
    weight,
)


class LeakageError(RuntimeError):
    """Raised when a caller passes history that isn't safely in the past."""


def assert_no_leakage(as_of_date: pd.Timestamp, *history_frames: pd.DataFrame) -> None:
    for frame in history_frames:
        if frame is None or len(frame) == 0:
            continue
        if "raceDate" not in frame.columns:
            continue
        max_date = frame["raceDate"].max()
        if pd.notna(max_date) and max_date >= as_of_date:
            raise LeakageError(
                f"History frame contains a row on/after as_of_date={as_of_date} "
                f"(max raceDate={max_date}). This would leak future information."
            )


def build_global_prior_runs(
    runners_df: pd.DataFrame, races_df: pd.DataFrame, results_df: pd.DataFrame
) -> pd.DataFrame:
    """Flat (runner x race x result) table used for trainer/jockey and draw-
    bias features, which need cross-horse population data that the
    per-horse FormEntry table cannot provide."""

    merged = runners_df.merge(
        races_df[
            ["id", "date", "racecourse", "distanceFurlongs", "going", "flatJumps", "raceClass", "numberOfRunners"]
        ],
        left_on="raceId",
        right_on="id",
        suffixes=("", "_race"),
    ).merge(results_df[["runnerId", "finishingPosition"]], left_on="id", right_on="runnerId", how="left", suffixes=("", "_result"))

    merged = merged.rename(columns={"date": "raceDate", "racecourse": "course"})
    merged["fieldSizeBand"] = merged["numberOfRunners"].apply(
        lambda n: "SMALL" if n <= 8 else "MEDIUM" if n <= 14 else "LARGE"
    )
    return merged[
        [
            "id", "raceId", "horseId", "raceDate", "course", "distanceFurlongs", "going", "flatJumps",
            "raceClass", "numberOfRunners", "fieldSizeBand", "trainerName", "jockeyName", "draw",
            "weightLbsTotal", "officialRating", "headgear", "finishingPosition",
        ]
    ]


def compute_runner_features(
    *,
    as_of_date: pd.Timestamp,
    runner_row: pd.Series,
    race_row: pd.Series,
    field_official_ratings: pd.Series,
    field_weights: pd.Series,
    field_draws: pd.Series,
    field_pace_profiles: pd.DataFrame,
    this_runner_projected_role: str | None,
    horse_prior_form: pd.DataFrame,
    horse_prior_global_runs: pd.DataFrame,
    global_prior_runs: pd.DataFrame,
) -> dict:
    assert_no_leakage(as_of_date, horse_prior_form, horse_prior_global_runs, global_prior_runs)

    features: dict = {}

    features.update(
        current_form.compute_current_form_features(
            horse_prior_form, as_of_date, runner_row.get("daysSinceLastRun")
        )
    )
    features.update(
        rating.compute_rating_features(
            runner_row.get("officialRating"), field_official_ratings, horse_prior_form, race_row["handicapType"]
        )
    )
    features.update(
        weight.compute_weight_features(
            runner_row.get("weightLbsTotal"), runner_row.get("jockeyClaimLbs"), field_weights, runner_row.get("ageAtRace")
        )
    )
    features.update(class_features.compute_class_features(race_row.get("raceClass"), horse_prior_form))
    features.update(
        course_distance_going.compute_course_distance_going_features(
            horse_prior_form, race_row["racecourse"], race_row["distanceFurlongs"], race_row.get("going"), race_row["flatJumps"]
        )
    )
    is_leader_style = this_runner_projected_role in ("LEADER", "PRONOUNCED_PACE")
    features.update(
        draw.compute_draw_features(
            runner_row.get("draw"),
            field_draws,
            race_row["numberOfRunners"],
            race_row["racecourse"],
            race_row["distanceFurlongs"],
            global_prior_runs,
            is_leader_style,
        )
    )
    features.update(pace.compute_pace_history_features(horse_prior_form, this_runner_projected_role))
    features.update(pace.compute_race_shape_features(field_pace_profiles, this_runner_projected_role))
    features.update(
        trainer_jockey.compute_trainer_jockey_features(
            global_prior_runs, runner_row.get("trainerName"), runner_row.get("jockeyName"), race_row["racecourse"], as_of_date
        )
    )
    features.update(
        headgear_changes.compute_headgear_and_change_features(
            runner_row.get("headgear"),
            bool(runner_row.get("firstTimeHeadgear")),
            horse_prior_form,
            horse_prior_global_runs,
            runner_row.get("trainerName"),
        )
    )
    features.update(
        age_experience.compute_age_experience_features(
            runner_row.get("ageAtRace"), horse_prior_form, as_of_date, race_row["flatJumps"], race_row["distanceFurlongs"]
        )
    )
    features.update(
        evidence.compute_evidence_density(
            career_starts=features["career_runs_to_date"],
            starts_last_12_months=features["starts_last_12_months"],
            course_distance_starts=features["course_distance_starts"] or 0,
            horse_prior_form=horse_prior_form,
            trainer_runs_30d=features.get("trainer_runs_30d"),
            jockey_runs_30d=features.get("jockey_runs_30d"),
        )
    )

    return features


def build_features_for_race(
    *,
    race_row: pd.Series,
    race_runners: pd.DataFrame,
    all_form: pd.DataFrame,
    all_global_prior_runs: pd.DataFrame,
    all_pace_profiles: pd.DataFrame,
) -> pd.DataFrame:
    """One row per runner in `race_row`'s field, with every engineered
    feature. Shared by dataset.py (training) and pipeline.py (prediction/
    backtesting) so both use identical, leakage-safe logic.

    `all_form`, `all_global_prior_runs` may contain rows on/after the race
    date — they are filtered down to strictly-prior rows HERE, in one
    place, so callers cannot accidentally forget to filter.
    """

    as_of_date = race_row["date"]
    field_pace = all_pace_profiles[all_pace_profiles["runnerId"].isin(race_runners["id"])]

    prior_form_all = all_form[
        (all_form["horseId"].isin(race_runners["horseId"])) & (all_form["raceDate"] < as_of_date)
    ]
    prior_global_all = all_global_prior_runs[all_global_prior_runs["raceDate"] < as_of_date]

    rows: list[dict] = []
    for _, runner_row in race_runners.iterrows():
        horse_prior_form = (
            prior_form_all[prior_form_all["horseId"] == runner_row["horseId"]]
            .sort_values("raceDate", ascending=False)
            .reset_index(drop=True)
        )
        horse_prior_global = (
            prior_global_all[prior_global_all["horseId"] == runner_row["horseId"]]
            .sort_values("raceDate", ascending=False)
            .reset_index(drop=True)
        )
        this_pace = field_pace[field_pace["runnerId"] == runner_row["id"]]
        this_role = this_pace["projectedRole"].iloc[0] if len(this_pace) > 0 else None

        features = compute_runner_features(
            as_of_date=as_of_date,
            runner_row=runner_row,
            race_row=race_row,
            field_official_ratings=race_runners["officialRating"],
            field_weights=race_runners["weightLbsTotal"],
            field_draws=race_runners["draw"],
            field_pace_profiles=field_pace,
            this_runner_projected_role=this_role,
            horse_prior_form=horse_prior_form,
            horse_prior_global_runs=horse_prior_global,
            global_prior_runs=prior_global_all,
        )
        features["runner_id"] = runner_row["id"]
        features["horse_id"] = runner_row["horseId"]
        rows.append(features)

    return pd.DataFrame(rows)

"""Training dataset builder.

Builds a race-grouped, runner-level dataset: one row per (race, runner),
with all engineered features (leakage-safe — see features/build.py), target
labels, and metadata columns needed for evaluation/backtesting breakdowns.

Targets:
  WIN_TARGET  — 1 if the runner won, else 0
  PLACE_2..PLACE_6 — 1 if finishingPosition <= N, else 0

Non-finishers (finishingPosition is null — pulled up, unseated, etc.) score
0 on every target, including WIN_TARGET.

Bookmaker-specific place terms are NEVER used as a training target — see
PLACE_2..PLACE_6 above, which are defined purely from finishing position so
any bookmaker's terms can be derived from them later (see place model
prediction + monotonicity in models/place_models.py).
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from racingedge_model import db
from racingedge_model.config import PLACE_DEPTHS
from racingedge_model.features.build import build_features_for_race, build_global_prior_runs

WIN_TARGET_COL = "WIN_TARGET"


def place_target_col(n: int) -> str:
    return f"PLACE_{n}"


def compute_targets(finishing_position: float | None) -> dict:
    """Pure target-derivation logic, extracted so it's independently
    testable. Non-finishers (finishing_position is None/NaN) score 0 on
    every target, including WIN_TARGET."""
    won = int(pd.notna(finishing_position) and finishing_position == 1)
    row = {WIN_TARGET_COL: won}
    for depth in PLACE_DEPTHS:
        row[place_target_col(depth)] = int(pd.notna(finishing_position) and finishing_position <= depth)
    return row


class RaceData:
    """All tables loaded once, kept in memory for the duration of dataset building."""

    def __init__(self, conn: sqlite3.Connection):
        self.races = db.load_races_df(conn)
        self.runners = db.load_runners_df(conn)
        self.results = db.load_results_df(conn)
        self.form = db.load_form_entries_df(conn)
        self.pace_profiles = db.load_pace_profiles_df(conn)
        self.global_prior_runs = build_global_prior_runs(self.runners, self.races, self.results)

    def is_synthetic_race(self, racecourse: str) -> bool:
        return racecourse.startswith("Synthetic ")


def build_training_dataset(conn: sqlite3.Connection, verbose: bool = False) -> pd.DataFrame:
    data = RaceData(conn)

    resulted_races = data.races[data.races["raceStatus"] == "RESULTED"].sort_values("date")
    rows: list[dict] = []

    for _, race_row in resulted_races.iterrows():
        as_of_date = race_row["date"]
        race_runners = data.runners[data.runners["raceId"] == race_row["id"]]
        if len(race_runners) == 0:
            continue
        race_results = data.results[data.results["runnerId"].isin(race_runners["id"])]
        if len(race_results) == 0:
            continue

        features_df = build_features_for_race(
            race_row=race_row,
            race_runners=race_runners,
            all_form=data.form,
            all_global_prior_runs=data.global_prior_runs,
            all_pace_profiles=data.pace_profiles,
        ).set_index("runner_id")

        for _, runner_row in race_runners.iterrows():
            result_row = race_results[race_results["runnerId"] == runner_row["id"]]
            if len(result_row) == 0:
                continue
            result_row = result_row.iloc[0]
            finishing_position = result_row["finishingPosition"]
            features = features_df.loc[runner_row["id"]].to_dict()

            row = {
                "race_id": race_row["id"],
                "runner_id": runner_row["id"],
                "horse_id": runner_row["horseId"],
                "date": as_of_date,
                "racecourse": race_row["racecourse"],
                "country": race_row["country"],
                "field_size": race_row["numberOfRunners"],
                "flat_jumps": race_row["flatJumps"],
                "race_class": race_row["raceClass"],
                "going": race_row["going"],
                "distance_furlongs": race_row["distanceFurlongs"],
                "handicap_type": race_row["handicapType"],
                "finishing_position": finishing_position,
                "current_odds_decimal": runner_row["currentOddsDecimal"],
                "starting_price_decimal": result_row["startingPriceDecimal"],
                "is_synthetic": data.is_synthetic_race(race_row["racecourse"]),
                **compute_targets(finishing_position),
            }

            row.update(features)
            rows.append(row)

        if verbose:
            print(f"  processed race {race_row['id']} ({race_row['raceName']}) — {len(race_runners)} runners")

    dataset = pd.DataFrame(rows)
    return dataset


def feature_columns(dataset: pd.DataFrame) -> list[str]:
    """All engineered feature columns (excludes metadata + target columns)."""
    from racingedge_model.features.registry import all_feature_keys

    keys = set(all_feature_keys())
    return [c for c in dataset.columns if c in keys]


def metadata_columns(dataset: pd.DataFrame) -> list[str]:
    from racingedge_model.features.registry import all_feature_keys

    keys = set(all_feature_keys())
    target_cols = {WIN_TARGET_COL, *(place_target_col(d) for d in PLACE_DEPTHS)}
    return [c for c in dataset.columns if c not in keys and c not in target_cols]


def date_based_split(
    dataset: pd.DataFrame, train_frac: float = 0.6, val_frac: float = 0.2
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Splits by RACE (never by runner) in chronological order, so:
      - no race's runners are split across train/val/test
      - train dates are all <= val dates, which are all <= test dates

    This is what makes the resulting evaluation a genuine "trained on
    earlier dates, tested on later dates" backtest rather than a randomly
    shuffled (and therefore leakage-prone) split.
    """

    race_dates = dataset.groupby("race_id")["date"].first().sort_values()
    race_ids_sorted = race_dates.index.tolist()
    n = len(race_ids_sorted)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))

    train_ids = set(race_ids_sorted[:train_end])
    val_ids = set(race_ids_sorted[train_end:val_end])
    test_ids = set(race_ids_sorted[val_end:])

    train_df = dataset[dataset["race_id"].isin(train_ids)].copy()
    val_df = dataset[dataset["race_id"].isin(val_ids)].copy()
    test_df = dataset[dataset["race_id"].isin(test_ids)].copy()
    return train_df, val_df, test_df


if __name__ == "__main__":
    conn = db.get_connection()
    ds = build_training_dataset(conn, verbose=True)
    print(f"Dataset: {len(ds)} rows across {ds['race_id'].nunique()} races")
    print(f"Feature columns: {len(feature_columns(ds))}")
    tr, va, te = date_based_split(ds)
    print(f"Train: {len(tr)} rows / {tr['race_id'].nunique()} races ({tr['date'].min()} .. {tr['date'].max()})")
    print(f"Val:   {len(va)} rows / {va['race_id'].nunique()} races ({va['date'].min()} .. {va['date'].max()})")
    print(f"Test:  {len(te)} rows / {te['race_id'].nunique()} races ({te['date'].min()} .. {te['date'].max()})")

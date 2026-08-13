"""Shared prediction-generation pipeline, used by both predict.py (upcoming
races) and backtest.py (historical races, evaluated after the fact).

Every call to `generate_predictions` computes features for each target race
using ONLY information with raceDate < that race's own date (see
features/build.py), regardless of whether the race has already been run —
backtesting deliberately re-creates "what would have been predicted before
the race" using a model trained on data from BEFORE the backtest window.

PredictionSnapshot rows are ALWAYS inserted fresh (see db.py:
insert_prediction_snapshot) — this module never UPDATEs an existing
snapshot, preserving Phase 1's immutability guarantee.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pandas as pd

from racingedge_model import db
from racingedge_model.artifacts import ServingModelBundle
from racingedge_model.confidence import compute_model_confidence
from racingedge_model.config import PLACE_DEPTHS
from racingedge_model.features.build import build_features_for_race, build_global_prior_runs
from racingedge_model.models.place_models import enforce_monotonic_place_probabilities_df
from racingedge_model.value import assess_value


def generate_predictions(
    conn: sqlite3.Connection,
    race_ids: list[str],
    model_version_id: str,
    bundle: ServingModelBundle,
    *,
    persist: bool = True,
    update_evidence_profiles: bool = False,
) -> pd.DataFrame:
    races = db.load_races_df(conn)
    runners = db.load_runners_df(conn)
    results = db.load_results_df(conn)
    form = db.load_form_entries_df(conn)
    pace_profiles = db.load_pace_profiles_df(conn)
    global_prior_runs = build_global_prior_runs(runners, races, results)
    place_terms = db.load_race_place_terms_df(conn)

    target_races = races[races["id"].isin(race_ids)]
    all_rows: list[dict] = []

    for _, race_row in target_races.iterrows():
        race_runners = runners[runners["raceId"] == race_row["id"]]
        race_runners = race_runners[~race_runners["nonRunner"]]
        if len(race_runners) == 0:
            continue

        features_df = build_features_for_race(
            race_row=race_row,
            race_runners=race_runners,
            all_form=form,
            all_global_prior_runs=global_prior_runs,
            all_pace_profiles=pace_profiles,
        )
        if len(features_df) == 0:
            continue

        win_raw = bundle.predict_win_raw(features_df)
        win_calibrated = bundle.win_calibrator.transform(win_raw)
        race_id_series = pd.Series(race_row["id"], index=features_df.index)
        from racingedge_model.normalize import normalize_win_probabilities

        win_normalized = normalize_win_probabilities(pd.Series(win_calibrated, index=features_df.index), race_id_series)

        place_bands = bundle.predict_place_bands(features_df, race_id_series)
        calibrated_by_depth = {d: place_bands[d]["calibrated"] for d in PLACE_DEPTHS}
        monotonic_by_depth = enforce_monotonic_place_probabilities_df(calibrated_by_depth)

        secondary_raw = bundle.predict_secondary_win_raw(features_df)
        missing_fraction = bundle.preprocessor.missing_fraction(features_df)
        extreme_fraction = bundle.ood_detector.extreme_fraction(bundle.preprocessor.transform(features_df))

        top2_for_stability = monotonic_by_depth.get(2, win_normalized)
        confidence_df = compute_model_confidence(
            evidence_density_0_1=features_df["evidence_density_score"],
            missing_fraction=missing_fraction,
            win_prob_logistic=pd.Series(secondary_raw if secondary_raw is not None else win_raw, index=features_df.index),
            win_prob_gbm=pd.Series(win_raw, index=features_df.index),
            win_prob=win_normalized,
            top2_prob=top2_for_stability,
            race_ids=race_id_series,
            flat_jumps=pd.Series(race_row["flatJumps"], index=features_df.index),
            extreme_feature_fraction=extreme_fraction,
            brier_by_type=bundle.brier_by_type,
        )

        race_place_terms = place_terms[place_terms["raceId"] == race_row["id"]]
        default_places = int(race_row["bookmakerPlaces"]) if pd.notna(race_row["bookmakerPlaces"]) else 3
        default_places = min(max(default_places, min(PLACE_DEPTHS)), max(PLACE_DEPTHS))
        default_bookmaker_id = race_place_terms["bookmakerId"].iloc[0] if len(race_place_terms) > 0 else None

        odds = race_runners.set_index("id")["currentOddsDecimal"].reindex(features_df["runner_id"]).reset_index(drop=True)
        value = assess_value(win_normalized.reset_index(drop=True), odds)

        for i, runner_id in enumerate(features_df["runner_id"]):
            place_prob_default = float(monotonic_by_depth[default_places].iloc[i])
            snapshot_fields = {
                "runnerId": runner_id,
                "snapshotType": "PRE_RACE",
                "modelVersionId": model_version_id,
                "modelVersionLabel": bundle.win_algorithm,
                "winProbability": float(win_normalized.iloc[i]),
                "placeProbability": place_prob_default,
                "placeBasisPlaces": default_places,
                "placeBasisBookmakerId": default_bookmaker_id,
                "modelConfidence": float(confidence_df["model_confidence"].iloc[i]),
                "fairOddsDecimal": _none_if_nan(value["fair_odds_decimal"].iloc[i]),
                "marketImpliedProbability": _none_if_nan(value["market_implied_probability"].iloc[i]),
                "valueEdgeAbsolute": _none_if_nan(value["value_edge_absolute"].iloc[i]),
                "valueEdgeRelative": _none_if_nan(value["value_edge_relative"].iloc[i]),
                "referenceOddsDecimal": _none_if_nan(odds.iloc[i]),
                "isLocked": True,
            }

            row_summary = {
                "race_id": race_row["id"],
                "runner_id": runner_id,
                "win_probability": snapshot_fields["winProbability"],
                "place_probability_default": place_prob_default,
                "model_confidence": snapshot_fields["modelConfidence"],
                **{f"place_top{d}": float(monotonic_by_depth[d].iloc[i]) for d in PLACE_DEPTHS},
            }
            all_rows.append(row_summary)

            if persist:
                snapshot_id = db.insert_prediction_snapshot(conn, snapshot_fields)
                bands = {d: (float(place_bands[d]["raw"].iloc[i]), float(monotonic_by_depth[d].iloc[i])) for d in PLACE_DEPTHS}
                db.insert_place_probability_bands(conn, snapshot_id, bands)

        if persist and update_evidence_profiles:
            _update_evidence_profiles(conn, race_runners, features_df)

    return pd.DataFrame(all_rows)


def _none_if_nan(value) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    return float(value)


def _update_evidence_profiles(conn: sqlite3.Connection, race_runners: pd.DataFrame, features_df: pd.DataFrame) -> None:
    """Keeps Phase 1's EvidenceProfile cache (a "current state" table, see
    schema comment) fresh for horses in races we've just scored — used by
    the Phase 1 UI's evidence badges. Only called for upcoming races, never
    for historical backtests (which must not mutate "current" state)."""

    merged = features_df.merge(race_runners[["id", "horseId"]], left_on="runner_id", right_on="id")
    for _, row in merged.iterrows():
        existing = conn.execute('SELECT id FROM "EvidenceProfile" WHERE horseId = ?', (row["horseId"],)).fetchone()
        label = row["evidence_density_label"]
        score = row["evidence_density_score"]
        career_starts = int(row["career_runs_to_date"])
        starts_12mo = int(row["starts_last_12_months"])
        if existing:
            conn.execute(
                'UPDATE "EvidenceProfile" SET careerStarts=?, startsLast12Months=?, evidenceDensityScore=?, '
                "evidenceDensityLabel=?, updatedAt=? WHERE horseId=?",
                (career_starts, starts_12mo, round(score, 3), label, db.to_prisma_datetime(pd.Timestamp.utcnow()), row["horseId"]),
            )
        else:
            from racingedge_model.ids import new_id

            conn.execute(
                'INSERT INTO "EvidenceProfile" (id, horseId, careerStarts, startsLast12Months, startsAtCourse, '
                "startsAtDistance, startsOnGoing, evidenceDensityScore, evidenceDensityLabel, uncertaintyNote, updatedAt) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    new_id(),
                    row["horseId"],
                    career_starts,
                    starts_12mo,
                    0,
                    0,
                    0,
                    round(score, 3),
                    label,
                    None,
                    db.to_prisma_datetime(pd.Timestamp.utcnow()),
                ),
            )

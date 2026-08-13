"""Trains the Phase 2 baseline models end-to-end:

  1. Builds the training dataset from the database (leakage-safe features),
     restricted to REAL-source races UNLESS --include-synthetic is passed
     (Phase 3A's real/synthetic separation gate — see racingedge_data.
     dataset_version). Aborts with a clear message if the resulting dataset
     is empty rather than proceeding on zero rows.
  2. Runs the Phase 3A temporal leakage auditor against the whole database
     and aborts training if it reports FAILED — a leakage-positive database
     must never be trained on.
  3. Creates an immutable DatasetVersion row covering exactly the races
     used, and reports the Phase 3A minimum real-data production-readiness
     gate ("RESEARCH MODEL — INSUFFICIENT HISTORICAL DATA" below threshold).
  4. Splits by date (train / validation / test), never splitting a race
     across sets.
  5. Fits TWO baseline win models (logistic regression, LightGBM) on train.
  6. Calibrates each (Platt + isotonic compared) on validation only.
  7. Fits FIVE place-depth models (top2..top6) on train, calibrates each on
     validation, with monotonicity enforced at prediction time.
  8. Evaluates everything on the held-out test split (never touched until
     this point) and reports results — including if they're weak — plus the
     market-implied-probability baseline comparison (does the model add
     information beyond the market?).
  9. Saves two ModelVersion rows to the database, each referencing the
     DatasetVersion used to train it:
       - "baseline-logistic-win"  (comparison/interpretability only)
       - "baseline-lightgbm"      (the primary serving model: win + place)

Run: python -m racingedge_model.train [--primary logistic|gbm] [--include-synthetic]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

import pandas as pd

from racingedge_data.dataset_version import (
    classify_readiness,
    create_dataset_version,
    infer_providers_for_races,
)
from racingedge_data.leakage_audit import audit_training_data, save_audit_run
from racingedge_data.market_baseline import compare_market_vs_model, compute_market_probabilities
from racingedge_model import db
from racingedge_model.artifacts import ServingModelBundle, WinModelBundle, save_bundle
from racingedge_model.calibration import select_best_calibration
from racingedge_model.config import DATASET_SCHEMA_VERSION, FEATURE_SET_VERSION, PLACE_DEPTHS
from racingedge_model.dataset import (
    WIN_TARGET_COL,
    build_training_dataset,
    date_based_split,
    feature_columns,
    place_target_col,
)
from racingedge_model.evaluate import calibration_buckets, roi_flat_stake, top_ranked_strike_rate, win_metrics
from racingedge_model.models.place_models import (
    PlaceModelSet,
    enforce_monotonic_place_probabilities_df,
    rescale_place_probabilities_within_race,
)
from racingedge_model.models.preprocessing import FeaturePreprocessor, OutOfDistributionDetector
from racingedge_model.models.win_gbm import GbmWinModel
from racingedge_model.models.win_logistic import LogisticWinModel
from racingedge_model.normalize import assert_probabilities_sum_to_one, normalize_win_probabilities


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", choices=["gbm", "logistic"], default="gbm")
    parser.add_argument(
        "--include-synthetic",
        action="store_true",
        help=(
            "Include SYNTHETIC/SAMPLE races in training, in addition to REAL. "
            "Without this flag, training uses REAL races ONLY (Phase 3A default) "
            "and will abort if there are none yet."
        ),
    )
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    conn = db.get_connection()

    print("Running temporal leakage audit before touching training data...")
    audit_report = audit_training_data(conn)
    print(f"  {audit_report.summary_line()}")
    if audit_report.status == "FAILED":
        for violation in audit_report.violations[:20]:
            print(f"    VIOLATION: {violation.detail}")
        print("\nAborting: training must not proceed against a database that failed the leakage audit.")
        sys.exit(1)

    source_types = ["REAL"] if not args.include_synthetic else ["REAL", "SYNTHETIC", "SAMPLE"]
    print(f"\nBuilding training dataset (leakage-safe features, sourceType in {source_types})...")
    dataset = build_training_dataset(conn, verbose=False, source_types=source_types)

    if len(dataset) == 0:
        print(
            f"\nNo resulted races found with sourceType in {source_types}.\n"
            "Training aborted — this is the Phase 3A real/synthetic separation gate working as "
            "intended, not a bug. To train a research model on synthetic data, re-run with "
            "--include-synthetic. To train on real data, first import real historical races via "
            "racingedge_data.importers (see DATA_SOURCES.md)."
        )
        sys.exit(1)

    print(f"  {len(dataset)} rows across {dataset['race_id'].nunique()} races")

    race_ids = dataset["race_id"].unique().tolist()
    providers = infer_providers_for_races(conn, race_ids)
    dataset_version_id = create_dataset_version(
        conn,
        name=f"train-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
        race_ids=race_ids,
        providers=providers,
        schema_version=DATASET_SCHEMA_VERSION,
        notes=f"Built by racingedge_model.train (source_types={source_types}).",
    )
    conn.commit()
    readiness = classify_readiness(dataset["race_id"].nunique(), len(dataset))
    print(f"  DatasetVersion: {dataset_version_id}")
    print(
        f"  {readiness.label} (races={readiness.race_count}, runners={readiness.runner_count}, "
        f"required >= {readiness.min_races_required} races / {readiness.min_runners_required} runners)"
    )

    train_df, val_df, test_df = date_based_split(dataset)
    print(
        f"  train: {len(train_df)} rows / {train_df['race_id'].nunique()} races "
        f"({train_df['date'].min().date()} .. {train_df['date'].max().date()})"
    )
    print(
        f"  val:   {len(val_df)} rows / {val_df['race_id'].nunique()} races "
        f"({val_df['date'].min().date()} .. {val_df['date'].max().date()})"
    )
    print(
        f"  test:  {len(test_df)} rows / {test_df['race_id'].nunique()} races "
        f"({test_df['date'].min().date()} .. {test_df['date'].max().date()})"
    )

    is_synthetic = bool(dataset["is_synthetic"].any())
    if is_synthetic:
        print("\n*** Training data includes SYNTHETIC races. ***")
        print("*** Resulting models MUST be labelled: SYNTHETIC TEST MODEL — NOT FOR BETTING USE ***\n")

    feat_cols = feature_columns(dataset)
    preprocessor = FeaturePreprocessor(feat_cols).fit(train_df)
    ood_detector = OutOfDistributionDetector(feat_cols).fit(train_df)

    Xtr = preprocessor.transform(train_df)
    Xva = preprocessor.transform(val_df)
    Xte = preprocessor.transform(test_df)
    ytr, yva, yte = train_df[WIN_TARGET_COL], val_df[WIN_TARGET_COL], test_df[WIN_TARGET_COL]

    # --- Win models: Model A (logistic) and Model B (LightGBM) ---
    print("Fitting win Model A (logistic regression)...")
    win_logistic = LogisticWinModel().fit(Xtr, ytr)
    print("Fitting win Model B (LightGBM)...")
    win_gbm = GbmWinModel().fit(Xtr, ytr)

    raw_val_logistic = win_logistic.predict_proba_positive(Xva)
    raw_val_gbm = win_gbm.predict_proba_positive(Xva)
    calibrator_logistic, cmp_logistic = select_best_calibration(raw_val_logistic, yva)
    calibrator_gbm, cmp_gbm = select_best_calibration(raw_val_gbm, yva)
    print(f"  logistic calibration: {cmp_logistic.chosen_method} (val Brier {cmp_logistic.raw_brier:.4f} -> " f"{min(cmp_logistic.sigmoid_brier, cmp_logistic.isotonic_brier, cmp_logistic.raw_brier):.4f})")
    print(f"  gbm calibration:      {cmp_gbm.chosen_method} (val Brier {cmp_gbm.raw_brier:.4f} -> " f"{min(cmp_gbm.sigmoid_brier, cmp_gbm.isotonic_brier, cmp_gbm.raw_brier):.4f})")

    # --- Place models (top2..top6), all LightGBM ---
    print("Fitting place models (top2..top6)...")
    place_targets = {d: train_df[place_target_col(d)] for d in PLACE_DEPTHS}
    place_models = PlaceModelSet().fit(Xtr, place_targets)
    place_calibrators: dict[int, object] = {}
    for depth in PLACE_DEPTHS:
        raw_val = place_models.models[depth].predict_proba_positive(Xva)
        calibrator, cmp = select_best_calibration(raw_val, val_df[place_target_col(depth)])
        place_calibrators[depth] = calibrator
        print(f"  top{depth} calibration: {cmp.chosen_method} (val Brier {cmp.raw_brier:.4f} -> {min(cmp.sigmoid_brier, cmp.isotonic_brier, cmp.raw_brier):.4f})")

    # --- Historical calibration quality lookup (for ModelConfidence) ---
    primary_val_calibrated = (calibrator_gbm if args.primary == "gbm" else calibrator_logistic).transform(
        raw_val_gbm if args.primary == "gbm" else raw_val_logistic
    )
    val_eval = val_df.copy()
    val_eval["_calibrated"] = primary_val_calibrated
    brier_by_type = {}
    for t, grp in val_eval.groupby("flat_jumps"):
        m = win_metrics(grp[WIN_TARGET_COL], grp["_calibrated"])
        if m["brier_score"] is not None:
            brier_by_type[t] = m["brier_score"]

    # --- Held-out TEST evaluation (never touched until now) ---
    print("\nEvaluating on held-out TEST split...")

    def win_test_report(model, calibrator, raw_extractor) -> tuple[dict, pd.Series]:
        raw = raw_extractor(Xte)
        calibrated = calibrator.transform(raw)
        normalized = normalize_win_probabilities(pd.Series(calibrated, index=test_df.index), test_df["race_id"])
        assert_probabilities_sum_to_one(normalized, test_df["race_id"])
        metrics = win_metrics(yte, normalized)
        metrics["top_ranked_strike_rate"] = top_ranked_strike_rate(
            test_df.assign(_p=normalized.values), "_p", "race_id", WIN_TARGET_COL
        )
        metrics["roi_flat_win_stake"] = roi_flat_stake(yte, test_df["starting_price_decimal"])
        metrics["calibration_buckets"] = calibration_buckets(yte, normalized)
        return metrics, normalized

    logistic_test_metrics, logistic_normalized_test = win_test_report(
        win_logistic, calibrator_logistic, win_logistic.predict_proba_positive
    )
    gbm_test_metrics, gbm_normalized_test = win_test_report(win_gbm, calibrator_gbm, win_gbm.predict_proba_positive)

    print(f"  [logistic] test Brier={logistic_test_metrics['brier_score']:.4f} logloss={logistic_test_metrics['log_loss']:.4f} AUC={logistic_test_metrics['roc_auc']}")
    print(f"  [gbm]      test Brier={gbm_test_metrics['brier_score']:.4f} logloss={gbm_test_metrics['log_loss']:.4f} AUC={gbm_test_metrics['roc_auc']}")

    # --- Market baseline comparison: does the primary model add information
    #     beyond the market's own implied probabilities? ---
    primary_normalized_test = gbm_normalized_test if args.primary == "gbm" else logistic_normalized_test
    market_comparison_df = test_df.copy()
    market_comparison_df["_model_probability"] = primary_normalized_test.values
    market_comparison_df["_market_probability"] = compute_market_probabilities(
        market_comparison_df, odds_col="starting_price_decimal", race_id_col="race_id"
    )
    market_comparison = compare_market_vs_model(
        market_comparison_df,
        model_prob_col="_model_probability",
        target_col=WIN_TARGET_COL,
        market_prob_col="_market_probability",
    )
    print(
        f"  [market baseline] n={market_comparison['n_comparable_rows']} "
        f"market Brier={market_comparison['market']['brier_score']} "
        f"model Brier={market_comparison['model']['brier_score']} "
        f"model beats market on Brier={market_comparison['model_beats_market_on_brier']}"
    )

    place_test_metrics = {}
    place_raw_test = place_models.predict_proba(Xte)
    place_calibrated_test = {}
    for depth in PLACE_DEPTHS:
        calibrated = pd.Series(place_calibrators[depth].transform(place_raw_test[depth]), index=test_df.index)
        rescaled = rescale_place_probabilities_within_race(calibrated, test_df["race_id"], depth)
        place_calibrated_test[depth] = rescaled
    monotonic_test = enforce_monotonic_place_probabilities_df(place_calibrated_test)
    for depth in PLACE_DEPTHS:
        m = win_metrics(test_df[place_target_col(depth)], monotonic_test[depth])
        place_test_metrics[f"top{depth}"] = m
        print(f"  [place top{depth}] test Brier={m['brier_score']:.4f} AUC={m['roc_auc']}")

    monotonic_matrix = pd.DataFrame(monotonic_test)
    violations = int((monotonic_matrix.diff(axis=1).iloc[:, 1:] < -1e-9).any(axis=1).sum())
    print(f"  monotonicity violations on test (should be 0): {violations}")

    # --- Feature importance ---
    logistic_importance = win_logistic.feature_importance()
    gbm_importance = win_gbm.feature_importance()

    # --- Persist ModelVersion rows + artifacts ---
    now = datetime.now(timezone.utc)
    training_start = train_df["date"].min()
    training_end = train_df["date"].max()
    validation_start, validation_end = val_df["date"].min(), val_df["date"].max()
    test_start, test_end = test_df["date"].min(), test_df["date"].max()

    with db.transaction(conn):
        logistic_bundle = WinModelBundle(
            algorithm="logistic_regression",
            preprocessor=preprocessor,
            model=win_logistic,
            calibrator=calibrator_logistic,
        )
        logistic_version_id = db.insert_model_version(
            conn,
            {
                "name": "baseline-logistic-win",
                "version": now.strftime("%Y%m%d-%H%M%S"),
                "featureSetVersion": FEATURE_SET_VERSION,
                "algorithm": "logistic_regression",
                "hyperparameters": json.dumps(win_logistic.params),
                "calibrationMethod": cmp_logistic.chosen_method,
                "trainingStartDate": training_start,
                "trainingEndDate": training_end,
                "validationStartDate": validation_start,
                "validationEndDate": validation_end,
                "testStartDate": test_start,
                "testEndDate": test_end,
                "trainingRowCount": len(train_df),
                "trainingRaceCount": int(train_df["race_id"].nunique()),
                "isSynthetic": is_synthetic,
                "datasetVersionId": dataset_version_id,
                "metricsJson": json.dumps(
                    {
                        "win": logistic_test_metrics,
                        "calibration_comparison": vars(cmp_logistic),
                        "dataset_readiness_label": readiness.label,
                    }
                ),
                "featureImportanceJson": json.dumps(logistic_importance[:40]),
                "notes": "Comparison / interpretability baseline. Not used to generate live PredictionSnapshot rows — see baseline-lightgbm. "
                + args.notes,
            },
        )
        logistic_bundle_path = save_bundle(logistic_bundle, logistic_version_id)
        conn.execute('UPDATE "ModelVersion" SET artifactPath = ? WHERE id = ?', (logistic_bundle_path, logistic_version_id))

        primary_model = win_gbm if args.primary == "gbm" else win_logistic
        primary_calibrator = calibrator_gbm if args.primary == "gbm" else calibrator_logistic
        secondary_model = win_logistic if args.primary == "gbm" else win_gbm

        serving_bundle = ServingModelBundle(
            win_algorithm=primary_model.algorithm,
            preprocessor=preprocessor,
            ood_detector=ood_detector,
            win_model=primary_model,
            win_calibrator=primary_calibrator,
            place_models=place_models,
            place_calibrators=place_calibrators,
            brier_by_type=brier_by_type,
            secondary_win_model=secondary_model,
        )
        primary_metrics = gbm_test_metrics if args.primary == "gbm" else logistic_test_metrics
        serving_version_id = db.insert_model_version(
            conn,
            {
                "name": f"baseline-{primary_model.algorithm}",
                "version": now.strftime("%Y%m%d-%H%M%S"),
                "featureSetVersion": FEATURE_SET_VERSION,
                "algorithm": f"{primary_model.algorithm}+place_top2..6",
                "hyperparameters": json.dumps(
                    {"win": getattr(primary_model, "params", {}), "place": PlaceModelSet().models[2].params}
                ),
                "calibrationMethod": f"win={cmp_gbm.chosen_method if args.primary == 'gbm' else cmp_logistic.chosen_method}",
                "trainingStartDate": training_start,
                "trainingEndDate": training_end,
                "validationStartDate": validation_start,
                "validationEndDate": validation_end,
                "testStartDate": test_start,
                "testEndDate": test_end,
                "trainingRowCount": len(train_df),
                "trainingRaceCount": int(train_df["race_id"].nunique()),
                "isSynthetic": is_synthetic,
                "datasetVersionId": dataset_version_id,
                "metricsJson": json.dumps(
                    {
                        "win": primary_metrics,
                        "place": place_test_metrics,
                        "monotonicity_violations_test": violations,
                        "comparison_logistic_win_brier": logistic_test_metrics["brier_score"],
                        "comparison_gbm_win_brier": gbm_test_metrics["brier_score"],
                        "market_baseline_comparison": market_comparison,
                        "dataset_readiness_label": readiness.label,
                    }
                ),
                "featureImportanceJson": json.dumps(gbm_importance[:40] if args.primary == "gbm" else logistic_importance[:40]),
                "notes": f"Primary serving model — generates live PredictionSnapshot + PlaceProbabilityBand rows. {readiness.label}. "
                + args.notes,
            },
        )
        serving_bundle_path = save_bundle(serving_bundle, serving_version_id)
        conn.execute('UPDATE "ModelVersion" SET artifactPath = ? WHERE id = ?', (serving_bundle_path, serving_version_id))

        save_audit_run(conn, audit_report, dataset_version_id=dataset_version_id, model_version_id=serving_version_id)

    print(f"\nSaved ModelVersion {logistic_version_id} (baseline-logistic-win, comparison-only)")
    print(f"Saved ModelVersion {serving_version_id} (baseline-{primary_model.algorithm}, PRIMARY serving model)")
    print(f"DatasetVersion {dataset_version_id} — {readiness.label}")
    print(
        json.dumps(
            {
                "logistic_version_id": logistic_version_id,
                "serving_version_id": serving_version_id,
                "dataset_version_id": dataset_version_id,
            }
        )
    )


if __name__ == "__main__":
    main()

"""Date-based backtesting engine.

Re-creates exactly what a ModelVersion would have predicted BEFORE each
historical race in the requested window (using only information available
before that race's own date — see features/build.py), then compares those
predictions against the actual recorded outcome.

By default, backtests only the model's own held-out TEST window (the dates
never touched during training/calibration) — the only genuinely fair
out-of-sample check. Passing an explicit --start-date/--end-date that
overlaps the model's training or validation window is allowed for research
purposes but prints a loud warning, since that is no longer a fair test of
generalisation.

Predictions generated here ARE persisted as PredictionSnapshot rows (same
as predict.py) so the web "Backtest Mode" page can show exactly what was
predicted for any historical date — this is legitimate (the features still
only use prior information) and is what makes that page meaningful.

Run:
  python -m racingedge_model.backtest [--model-version-id ID]
                                       [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import pandas as pd

from racingedge_data.dataset_version import readiness_for_dataset_version
from racingedge_data.market_baseline import compare_market_vs_model, compute_market_probabilities
from racingedge_model import db
from racingedge_model.artifacts import load_bundle
from racingedge_model.config import PLACE_DEPTHS, REPORTS_DIR
from racingedge_model.evaluate import calibration_buckets, roi_flat_stake, top_ranked_strike_rate, win_metrics
from racingedge_model.pipeline import generate_predictions
from racingedge_model.predict import find_latest_serving_model_version


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-version-id", default=None)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--no-persist", action="store_true", help="evaluate without writing PredictionSnapshot rows")
    args = parser.parse_args()

    conn = db.get_connection()

    if args.model_version_id:
        row = conn.execute('SELECT * FROM "ModelVersion" WHERE id = ?', (args.model_version_id,)).fetchone()
        model_version = dict(row) if row else None
    else:
        model_version = find_latest_serving_model_version(conn)
    if model_version is None:
        raise SystemExit("No serving ModelVersion found. Run `python -m racingedge_model.train` first.")

    start_date = args.start_date or model_version["testStartDate"]
    end_date = args.end_date or model_version["testEndDate"]

    in_sample_warning = False
    if start_date and model_version["trainingEndDate"] and start_date < model_version["trainingEndDate"]:
        in_sample_warning = True

    print(f"Backtesting ModelVersion {model_version['id']} ({model_version['name']}, {model_version['version']})")
    print(f"Window: {start_date} .. {end_date}")
    if model_version["isSynthetic"]:
        print("*** SYNTHETIC TEST MODEL — NOT FOR BETTING USE ***")
    if model_version.get("datasetVersionId"):
        readiness = readiness_for_dataset_version(conn, model_version["datasetVersionId"])
        if not readiness.is_production_ready:
            print(f"*** {readiness.label} ***")
    if in_sample_warning:
        print(
            "*** WARNING: requested window overlaps the model's OWN TRAINING period "
            "(ends " + str(model_version["trainingEndDate"]) + "). This is NOT a fair "
            "out-of-sample test — results will look better than genuine generalisation. ***"
        )

    bundle = load_bundle(model_version["artifactPath"])

    race_ids = [
        r["id"]
        for r in conn.execute(
            'SELECT id FROM "Race" WHERE raceStatus = \'RESULTED\' AND date(date) >= date(?) AND date(date) <= date(?)',
            (start_date, end_date),
        ).fetchall()
    ]
    if not race_ids:
        raise SystemExit("No resulted races found in the requested window.")

    print(f"Generating as-of-date predictions for {len(race_ids)} historical race(s)...")
    with db.transaction(conn):
        predictions = generate_predictions(
            conn, race_ids, model_version["id"], bundle, persist=not args.no_persist, update_evidence_profiles=False
        )

    results = db.load_results_df(conn)
    merged = predictions.merge(results, left_on="runner_id", right_on="runnerId")
    merged["won"] = (merged["finishingPosition"] == 1).astype(int)
    for depth in PLACE_DEPTHS:
        merged[f"placed_top{depth}"] = (merged["finishingPosition"] <= depth).fillna(False).astype(int)

    win_report = win_metrics(merged["won"], merged["win_probability"])
    win_report["top_ranked_strike_rate"] = top_ranked_strike_rate(
        predictions.assign(won=merged["won"].values), "win_probability", "race_id", "won"
    )
    win_report["roi_flat_win_stake"] = roi_flat_stake(merged["won"], merged["startingPriceDecimal"])
    win_report["calibration_buckets"] = calibration_buckets(merged["won"], merged["win_probability"])

    place_report = {}
    for depth in PLACE_DEPTHS:
        place_report[f"top{depth}"] = win_metrics(merged[f"placed_top{depth}"], merged[f"place_top{depth}"])

    # Market baseline comparison over this same backtest window — does the
    # model add information beyond the market here too, not just at
    # original training-time evaluation?
    merged["_market_probability"] = compute_market_probabilities(
        merged, odds_col="startingPriceDecimal", race_id_col="race_id"
    )
    market_comparison = compare_market_vs_model(
        merged, model_prob_col="win_probability", target_col="won", market_prob_col="_market_probability"
    )

    # ROI breakdowns — evaluation-only, never a training objective.
    def band_roi(series: pd.Series, bins: list[float], labels: list[str]) -> dict:
        banded = pd.cut(series, bins=bins, labels=labels, include_lowest=True)
        out = {}
        for label in labels:
            mask = banded == label
            out[label] = roi_flat_stake(merged.loc[mask, "won"], merged.loc[mask, "startingPriceDecimal"])
        return out

    odds_bins = [0, 2, 4, 8, 16, 1000]
    odds_labels = ["<2", "2-4", "4-8", "8-16", "16+"]
    roi_by_odds_band = band_roi(merged["startingPriceDecimal"], odds_bins, odds_labels)

    confidence_bins = [0, 0.33, 0.5, 0.66, 1.0]
    confidence_labels = ["low(<0.33)", "mid(0.33-0.5)", "mid-high(0.5-0.66)", "high(0.66+)"]
    roi_by_confidence_band = band_roi(merged["model_confidence"], confidence_bins, confidence_labels)

    report = {
        "model_version_id": model_version["id"],
        "model_name": model_version["name"],
        "is_synthetic": bool(model_version["isSynthetic"]),
        "window": {"start": str(start_date), "end": str(end_date)},
        "in_sample_warning": in_sample_warning,
        "n_races": int(predictions["race_id"].nunique()),
        "n_runners": int(len(predictions)),
        "win": win_report,
        "place": place_report,
        "market_baseline_comparison": market_comparison,
        "roi_by_odds_band": roi_by_odds_band,
        "roi_by_confidence_band": roi_by_confidence_band,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    start_label = str(start_date)[:10]
    end_label = str(end_date)[:10]
    report_path = REPORTS_DIR / f"backtest_{model_version['id']}_{start_label}_{end_label}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))

    print(f"\nWin: Brier={win_report['brier_score']:.4f} logloss={win_report['log_loss']:.4f} AUC={win_report['roc_auc']}")
    print(f"Win: strike rate={win_report['win_strike_rate']:.3f} (expected {win_report['expected_wins']:.1f} vs actual {win_report['actual_wins']})")
    print(f"Win: flat £1 ROI={win_report['roi_flat_win_stake']['roi_percent']}")
    print(
        f"Market baseline: n={market_comparison['n_comparable_rows']} "
        f"market Brier={market_comparison['market']['brier_score']} "
        f"model Brier={market_comparison['model']['brier_score']} "
        f"model beats market on Brier={market_comparison['model_beats_market_on_brier']}"
    )
    for depth in PLACE_DEPTHS:
        pr = place_report[f"top{depth}"]
        print(f"Place top{depth}: Brier={pr['brier_score']:.4f} strike rate={pr['win_strike_rate']:.3f}")
    print(f"\nFull report written to {report_path}")


if __name__ == "__main__":
    main()

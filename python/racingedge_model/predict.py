"""Generates predictions for UPCOMING races (raceStatus SCHEDULED/DELAYED)
using a trained serving ModelVersion, and writes them as new (never
overwritten) PredictionSnapshot + PlaceProbabilityBand rows.

Run: python -m racingedge_model.predict [--model-version-id ID] [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json

from racingedge_model import db
from racingedge_model.artifacts import load_bundle
from racingedge_model.pipeline import generate_predictions


def find_latest_serving_model_version(conn) -> dict | None:
    row = conn.execute(
        'SELECT * FROM "ModelVersion" WHERE name LIKE \'baseline-%\' AND name != \'baseline-logistic-win\' '
        "ORDER BY createdAt DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-version-id", default=None)
    parser.add_argument("--date", default=None, help="YYYY-MM-DD; defaults to all upcoming races")
    args = parser.parse_args()

    conn = db.get_connection()

    if args.model_version_id:
        row = conn.execute('SELECT * FROM "ModelVersion" WHERE id = ?', (args.model_version_id,)).fetchone()
        model_version = dict(row) if row else None
    else:
        model_version = find_latest_serving_model_version(conn)

    if model_version is None:
        raise SystemExit("No serving ModelVersion found. Run `python -m racingedge_model.train` first.")

    print(f"Using ModelVersion {model_version['id']} ({model_version['name']}, {model_version['version']})")
    if model_version["isSynthetic"]:
        print("*** SYNTHETIC TEST MODEL — NOT FOR BETTING USE ***")

    bundle = load_bundle(model_version["artifactPath"])

    query = 'SELECT id FROM "Race" WHERE raceStatus IN (\'SCHEDULED\', \'DELAYED\')'
    params: list = []
    if args.date:
        query += " AND date(date) = date(?)"
        params.append(args.date)
    race_ids = [r["id"] for r in conn.execute(query, params).fetchall()]

    if not race_ids:
        print("No upcoming races found to predict.")
        return

    print(f"Generating predictions for {len(race_ids)} upcoming race(s)...")
    with db.transaction(conn):
        summary = generate_predictions(
            conn, race_ids, model_version["id"], bundle, persist=True, update_evidence_profiles=True
        )

    print(f"Wrote {len(summary)} PredictionSnapshot rows across {summary['race_id'].nunique()} race(s).")
    print(
        json.dumps(
            {
                "model_version_id": model_version["id"],
                "races": int(summary["race_id"].nunique()),
                "snapshots": int(len(summary)),
                "mean_win_probability": float(summary["win_probability"].mean()) if len(summary) else None,
                "mean_confidence": float(summary["model_confidence"].mean()) if len(summary) else None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

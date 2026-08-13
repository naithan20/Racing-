"""Dataset versioning and the minimum real-data production gate.

Every training run must reference an immutable `DatasetVersion` row so
results are reproducible: which providers, which date range, which exact
races (and therefore runners/results), a REAL/SYNTHETIC/SAMPLE/MIXED source
classification, and a frozen data-quality snapshot taken at creation time.
A `DatasetVersion` is never mutated after creation — a new import or data
change creates a NEW `DatasetVersion`, never an edit to an old one.

This module also implements the project's minimum real-data gate: a model
is not "production-ready" unless its training dataset has at least
`DEFAULT_MIN_REAL_RACES` completed historical REAL races (preferably
`DEFAULT_MIN_REAL_RUNNERS`+ runners). Below the threshold, the label is
`"RESEARCH MODEL — INSUFFICIENT HISTORICAL DATA"` — thresholds are
parameters, not hardcoded, so a deployment can tighten or (with eyes open)
loosen them.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pandas as pd

from racingedge_model.db import to_prisma_datetime
from racingedge_model.ids import new_id

DEFAULT_MIN_REAL_RACES = 10_000
DEFAULT_MIN_REAL_RUNNERS = 100_000

VALID_SOURCE_TYPES = ("REAL", "SYNTHETIC", "SAMPLE", "MIXED")


@dataclass(frozen=True)
class DatasetReadiness:
    is_production_ready: bool
    label: str
    race_count: int
    runner_count: int
    min_races_required: int
    min_runners_required: int


def classify_readiness(
    race_count: int,
    runner_count: int,
    min_races: int = DEFAULT_MIN_REAL_RACES,
    min_runners: int = DEFAULT_MIN_REAL_RUNNERS,
) -> DatasetReadiness:
    """A dataset is production-ready only if it clears BOTH thresholds —
    clearing one but not the other (e.g. many runners from very few races,
    or vice versa) still means the model hasn't seen enough genuinely
    distinct racing scenarios."""

    is_ready = race_count >= min_races and runner_count >= min_runners
    label = "PRODUCTION-READY" if is_ready else "RESEARCH MODEL — INSUFFICIENT HISTORICAL DATA"
    return DatasetReadiness(
        is_production_ready=is_ready,
        label=label,
        race_count=race_count,
        runner_count=runner_count,
        min_races_required=min_races,
        min_runners_required=min_runners,
    )


def determine_source_type(sources_present: set[str]) -> str:
    """REAL/SYNTHETIC/SAMPLE if every race in the dataset shares that one
    classification; MIXED otherwise. MIXED must never be silently treated
    as REAL by any consumer — see train.py's explicit --allow-synthetic
    gate, which checks this value."""

    if not sources_present:
        raise ValueError("sources_present must not be empty")
    if sources_present <= {"REAL"}:
        return "REAL"
    if sources_present <= {"SYNTHETIC"}:
        return "SYNTHETIC"
    if sources_present <= {"SAMPLE"}:
        return "SAMPLE"
    return "MIXED"


def _dt(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    return to_prisma_datetime(value)


def build_data_quality_snapshot(conn: sqlite3.Connection, race_ids: list[str]) -> dict:
    """A frozen data-quality snapshot scoped to exactly these races — the
    same kind of figures the Data Quality Dashboard shows live, captured
    once here so a DatasetVersion's quality claim never silently drifts as
    more data is imported later."""

    if not race_ids:
        return {"race_count": 0, "runner_count": 0}

    placeholders = ",".join("?" for _ in race_ids)

    runner_row = conn.execute(
        f'SELECT COUNT(*) as total, '
        f'SUM(CASE WHEN officialRating IS NULL THEN 1 ELSE 0 END) as missing_or, '
        f'SUM(CASE WHEN draw IS NULL THEN 1 ELSE 0 END) as missing_draw, '
        f'SUM(CASE WHEN startingPriceDecimal IS NULL THEN 1 ELSE 0 END) as missing_sp '
        f'FROM "Runner" WHERE raceId IN ({placeholders})',
        race_ids,
    ).fetchone()

    total_runners = runner_row["total"] or 0

    def pct(n: Optional[int]) -> Optional[float]:
        return round(100.0 * (n or 0) / total_runners, 2) if total_runners else None

    return {
        "race_count": len(race_ids),
        "runner_count": total_runners,
        "missing_official_rating_pct": pct(runner_row["missing_or"]),
        "missing_draw_pct": pct(runner_row["missing_draw"]),
        "missing_starting_price_pct": pct(runner_row["missing_sp"]),
    }


def infer_providers_for_races(conn: sqlite3.Connection, race_ids: list[str]) -> list[str]:
    """Distinct `DataProvenance.provider` values recorded for these races.
    Falls back to a placeholder label for races created before Phase 3A's
    provenance tracking existed (Phase 1 seed data, the Phase 2 synthetic
    generator) rather than raising — those races are real rows in the
    database and still deserve a DatasetVersion, just not source-provider
    traceability."""

    if not race_ids:
        return []
    placeholders = ",".join("?" for _ in race_ids)
    rows = conn.execute(
        f'SELECT DISTINCT provider FROM "DataProvenance" '
        f"WHERE entityType = 'Race' AND entityId IN ({placeholders})",
        race_ids,
    ).fetchall()
    providers = sorted({r["provider"] for r in rows})
    return providers if providers else ["legacy-seed-or-generator"]


def create_dataset_version(
    conn: sqlite3.Connection,
    name: str,
    race_ids: list[str],
    providers: list[str],
    schema_version: str,
    import_batch_ids: Optional[list[str]] = None,
    notes: Optional[str] = None,
) -> str:
    """Creates and persists an immutable `DatasetVersion` row describing
    exactly which races (and therefore runners/results) this version
    covers. Raises if any `race_ids` entry does not exist."""

    if not race_ids:
        raise ValueError("race_ids must not be empty")

    unique_race_ids = list(dict.fromkeys(race_ids))
    placeholders = ",".join("?" for _ in unique_race_ids)
    races = conn.execute(
        f'SELECT id, date, sourceType FROM "Race" WHERE id IN ({placeholders})', unique_race_ids
    ).fetchall()
    if len(races) != len(unique_race_ids):
        found_ids = {r["id"] for r in races}
        missing = [rid for rid in unique_race_ids if rid not in found_ids]
        raise ValueError(f"race_ids not found in database: {missing}")

    dates = [pd.Timestamp(r["date"]) for r in races]
    source_types = {r["sourceType"] for r in races}
    source_type = determine_source_type(source_types)

    runner_count = conn.execute(
        f'SELECT COUNT(*) as c FROM "Runner" WHERE raceId IN ({placeholders})', unique_race_ids
    ).fetchone()["c"]

    quality_snapshot = build_data_quality_snapshot(conn, unique_race_ids)

    dataset_version_id = new_id()
    now = to_prisma_datetime(datetime.now(timezone.utc))
    conn.execute(
        'INSERT INTO "DatasetVersion" '
        "(id, name, sourceType, providersJson, dateRangeStart, dateRangeEnd, raceCount, runnerCount, "
        "dataQualityMetricsJson, schemaVersion, importBatchIdsJson, notes, createdAt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            dataset_version_id,
            name,
            source_type,
            json.dumps(sorted(set(providers))),
            _dt(min(dates)),
            _dt(max(dates)),
            len(unique_race_ids),
            runner_count,
            json.dumps(quality_snapshot),
            schema_version,
            json.dumps(import_batch_ids or []),
            notes,
            now,
        ),
    )
    return dataset_version_id


def get_dataset_version(conn: sqlite3.Connection, dataset_version_id: str) -> Optional[dict]:
    row = conn.execute('SELECT * FROM "DatasetVersion" WHERE id = ?', (dataset_version_id,)).fetchone()
    return dict(row) if row is not None else None


def readiness_for_dataset_version(
    conn: sqlite3.Connection,
    dataset_version_id: str,
    min_races: int = DEFAULT_MIN_REAL_RACES,
    min_runners: int = DEFAULT_MIN_REAL_RUNNERS,
) -> DatasetReadiness:
    """Applies the production-readiness gate to an existing DatasetVersion.
    A non-REAL (SYNTHETIC/SAMPLE/MIXED) dataset is never production-ready
    regardless of size — the gate is about REAL data volume specifically."""

    version = get_dataset_version(conn, dataset_version_id)
    if version is None:
        raise ValueError(f"No DatasetVersion found with id {dataset_version_id!r}")

    if version["sourceType"] != "REAL":
        return DatasetReadiness(
            is_production_ready=False,
            label="RESEARCH MODEL — INSUFFICIENT HISTORICAL DATA",
            race_count=version["raceCount"],
            runner_count=version["runnerCount"],
            min_races_required=min_races,
            min_runners_required=min_runners,
        )

    return classify_readiness(version["raceCount"], version["runnerCount"], min_races, min_runners)

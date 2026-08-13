"""SQLite access layer.

Reads/writes the exact same SQLite file the Next.js app uses
(`DATABASE_URL` / `dev.db`), via Python's stdlib `sqlite3` — there is no
Prisma runtime dependency here, just careful adherence to the column names
and datetime string format Prisma's SQLite connector uses (ISO-8601 with
milliseconds and a UTC offset, e.g. "2026-08-13T00:00:00.000+00:00").

This module is intentionally the ONLY place that knows SQL/table shape.
Everything else (features, models, CLIs) works with pandas DataFrames or
plain Python values.
"""

from __future__ import annotations

import contextlib
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable

import pandas as pd

from racingedge_model.config import DB_PATH
from racingedge_model.ids import new_id

PRISMA_DATETIME_FMT = "%Y-%m-%dT%H:%M:%S.{ms}+00:00"


def to_prisma_datetime(dt: datetime) -> str:
    """Formats a datetime exactly as Prisma's SQLite connector does."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    ms = f"{dt.microsecond // 1000:03d}"
    return dt.strftime(f"%Y-%m-%dT%H:%M:%S.{ms}+00:00")


def from_prisma_datetime(value: str) -> pd.Timestamp:
    return pd.to_datetime(value, utc=True)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


@contextlib.contextmanager
def transaction(conn: sqlite3.Connection):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def read_df(conn: sqlite3.Connection, query: str, params: Iterable[Any] | None = None) -> pd.DataFrame:
    return pd.read_sql_query(query, conn, params=params)


# ---------------------------------------------------------------------------
# Loaders — return plain DataFrames, one row per DB row, columns matching
# the Prisma field names. Date columns are parsed to pandas Timestamps.
# ---------------------------------------------------------------------------


def load_races_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = read_df(conn, 'SELECT * FROM "Race"')
    for col in ("date", "createdAt", "updatedAt"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


def load_runners_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = read_df(conn, 'SELECT * FROM "Runner"')
    for col in ("createdAt", "updatedAt"):
        df[col] = pd.to_datetime(df[col], utc=True)
    for col in ("nonRunner", "firstTimeHeadgear"):
        df[col] = df[col].astype(bool)
    return df


def load_horses_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = read_df(conn, 'SELECT * FROM "Horse"')
    for col in ("createdAt", "updatedAt"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


def load_form_entries_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = read_df(conn, 'SELECT * FROM "FormEntry"')
    df["raceDate"] = pd.to_datetime(df["raceDate"], utc=True)
    df["createdAt"] = pd.to_datetime(df["createdAt"], utc=True)
    return df


def load_results_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = read_df(conn, 'SELECT * FROM "ResultEntry"')
    for col in ("createdAt", "updatedAt"):
        df[col] = pd.to_datetime(df[col], utc=True)
    if "placeOutcome" in df.columns:
        df["placeOutcome"] = df["placeOutcome"].astype("boolean")
    return df


def load_evidence_profiles_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = read_df(conn, 'SELECT * FROM "EvidenceProfile"')
    df["updatedAt"] = pd.to_datetime(df["updatedAt"], utc=True)
    return df


def load_pace_profiles_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = read_df(conn, 'SELECT * FROM "RunnerPaceProfile"')
    df["updatedAt"] = pd.to_datetime(df["updatedAt"], utc=True)
    return df


def load_race_place_terms_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = read_df(conn, 'SELECT * FROM "RacePlaceTerms"')
    df["createdAt"] = pd.to_datetime(df["createdAt"], utc=True)
    df["extraPlaces"] = df["extraPlaces"].astype(bool)
    return df


def load_bookmakers_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = read_df(conn, 'SELECT * FROM "Bookmaker"')
    df["createdAt"] = pd.to_datetime(df["createdAt"], utc=True)
    df["isExchange"] = df["isExchange"].astype(bool)
    return df


def load_market_prices_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = read_df(conn, 'SELECT * FROM "RunnerMarketPrice"')
    for col in ("timestamp", "createdAt"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


def load_prediction_snapshots_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = read_df(conn, 'SELECT * FROM "PredictionSnapshot"')
    df["createdAt"] = pd.to_datetime(df["createdAt"], utc=True)
    df["isLocked"] = df["isLocked"].astype(bool)
    return df


def load_model_versions_df(conn: sqlite3.Connection) -> pd.DataFrame:
    df = read_df(conn, 'SELECT * FROM "ModelVersion"')
    for col in (
        "trainingStartDate",
        "trainingEndDate",
        "validationStartDate",
        "validationEndDate",
        "testStartDate",
        "testEndDate",
        "createdAt",
    ):
        df[col] = pd.to_datetime(df[col], utc=True)
    df["isSynthetic"] = df["isSynthetic"].astype(bool)
    return df


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------


def insert_model_version(conn: sqlite3.Connection, fields: dict[str, Any]) -> str:
    model_version_id = fields.get("id") or new_id()
    now = to_prisma_datetime(datetime.now(timezone.utc))

    columns = [
        "id",
        "name",
        "version",
        "featureSetVersion",
        "algorithm",
        "hyperparameters",
        "calibrationMethod",
        "trainingStartDate",
        "trainingEndDate",
        "validationStartDate",
        "validationEndDate",
        "testStartDate",
        "testEndDate",
        "trainingRowCount",
        "trainingRaceCount",
        "isSynthetic",
        "metricsJson",
        "featureImportanceJson",
        "artifactPath",
        "notes",
        "createdAt",
    ]
    row = {
        "id": model_version_id,
        "name": fields["name"],
        "version": fields["version"],
        "featureSetVersion": fields["featureSetVersion"],
        "algorithm": fields["algorithm"],
        "hyperparameters": fields.get("hyperparameters", "{}"),
        "calibrationMethod": fields.get("calibrationMethod", "none"),
        "trainingStartDate": _dt(fields["trainingStartDate"]),
        "trainingEndDate": _dt(fields["trainingEndDate"]),
        "validationStartDate": _dt_opt(fields.get("validationStartDate")),
        "validationEndDate": _dt_opt(fields.get("validationEndDate")),
        "testStartDate": _dt_opt(fields.get("testStartDate")),
        "testEndDate": _dt_opt(fields.get("testEndDate")),
        "trainingRowCount": fields["trainingRowCount"],
        "trainingRaceCount": fields["trainingRaceCount"],
        "isSynthetic": int(bool(fields.get("isSynthetic", False))),
        "metricsJson": fields.get("metricsJson"),
        "featureImportanceJson": fields.get("featureImportanceJson"),
        "artifactPath": fields.get("artifactPath"),
        "notes": fields.get("notes"),
        "createdAt": now,
    }
    placeholders = ", ".join(["?"] * len(columns))
    conn.execute(
        f'INSERT INTO "ModelVersion" ({", ".join(columns)}) VALUES ({placeholders})',
        [row[c] for c in columns],
    )
    return model_version_id


def insert_prediction_snapshot(conn: sqlite3.Connection, fields: dict[str, Any]) -> str:
    """Always INSERTs a new row — PredictionSnapshot rows are immutable and
    are never UPDATEd by this module. `isLocked` defaults to 1 (True)."""

    snapshot_id = fields.get("id") or new_id()
    now = to_prisma_datetime(datetime.now(timezone.utc))

    columns = [
        "id",
        "runnerId",
        "snapshotType",
        "modelVersion",
        "modelVersionId",
        "winProbability",
        "placeProbability",
        "placeBasisPlaces",
        "placeBasisBookmakerId",
        "modelConfidence",
        "fairOddsDecimal",
        "marketImpliedProbability",
        "valueEdgeAbsolute",
        "valueEdgeRelative",
        "referenceOddsDecimal",
        "isLocked",
        "createdAt",
    ]
    row = {
        "id": snapshot_id,
        "runnerId": fields["runnerId"],
        "snapshotType": fields.get("snapshotType", "PRE_RACE"),
        "modelVersion": fields.get("modelVersionLabel", "unconfigured"),
        "modelVersionId": fields.get("modelVersionId"),
        "winProbability": fields.get("winProbability"),
        "placeProbability": fields.get("placeProbability"),
        "placeBasisPlaces": fields.get("placeBasisPlaces"),
        "placeBasisBookmakerId": fields.get("placeBasisBookmakerId"),
        "modelConfidence": fields.get("modelConfidence"),
        "fairOddsDecimal": fields.get("fairOddsDecimal"),
        "marketImpliedProbability": fields.get("marketImpliedProbability"),
        "valueEdgeAbsolute": fields.get("valueEdgeAbsolute"),
        "valueEdgeRelative": fields.get("valueEdgeRelative"),
        "referenceOddsDecimal": fields.get("referenceOddsDecimal"),
        "isLocked": int(fields.get("isLocked", True)),
        "createdAt": now,
    }
    placeholders = ", ".join(["?"] * len(columns))
    conn.execute(
        f'INSERT INTO "PredictionSnapshot" ({", ".join(columns)}) VALUES ({placeholders})',
        [row[c] for c in columns],
    )
    return snapshot_id


def insert_place_probability_bands(
    conn: sqlite3.Connection, prediction_snapshot_id: str, bands: dict[int, tuple[float, float]]
) -> None:
    """`bands`: {topN: (raw_probability, calibrated_probability)}."""

    for top_n, (raw, calibrated) in bands.items():
        conn.execute(
            'INSERT INTO "PlaceProbabilityBand" '
            '(id, predictionSnapshotId, topN, probabilityRaw, probabilityCalibrated) '
            "VALUES (?, ?, ?, ?, ?)",
            (new_id(), prediction_snapshot_id, int(top_n), float(raw), float(calibrated)),
        )


def _dt(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    return to_prisma_datetime(value)


def _dt_opt(value: Any) -> str | None:
    if value is None:
        return None
    return _dt(value)

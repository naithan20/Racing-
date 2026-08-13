"""As-of-timestamp reconstruction.

Answers the project's defining question: "what did RacingEdge know about
this race as of timestamp T" — reconstructing mutable Race/Runner/place-
terms field values from the point-in-time history logs (`RaceFieldHistory`,
`RunnerFieldHistory`, `RacePlaceTermsHistory`) plus `RunnerMarketPrice` rows
up to that timestamp, rather than ever reading the CURRENT (possibly
post-race) state of a mutable field.

The live `Race`/`Runner`/`RacePlaceTerms` rows hold the FINAL known state —
for a resulted race, that can include information (final going, confirmed
non-runner status, ...) that was not available before off-time. This module
never reads those mutable fields directly for reconstruction: only the
immutable fields (id, horseId/raceId, names, distance, ...) come from the
live row; every mutable field comes from its history log, and is reported
as UNKNOWN (`None`) rather than falling back to the live value if no
history row qualifies at or before `as_of` — a live value set AFTER `as_of`
must never leak through.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

import pandas as pd

from racingedge_model.db import to_prisma_datetime

# Mutable fields on Race / Runner that must be reconstructed from history
# rather than read live. Keep in sync with
# racingedge_data.importers.import_runner._RACE_HISTORY_FIELDS /
# _RUNNER_HISTORY_FIELDS — those are what populate the history in the first
# place.
RACE_MUTABLE_FIELDS = (
    "going",
    "goingDescription",
    "railPosition",
    "stallsPosition",
    "weatherSummary",
    "raceStatus",
    "resultStatus",
)
RUNNER_MUTABLE_FIELDS = (
    "draw",
    "jockeyName",
    "trainerName",
    "weightLbsTotal",
    "nonRunner",
    "headgear",
    "officialRating",
)


def _to_sql_datetime(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    return to_prisma_datetime(value)


def field_value_as_of(
    conn: sqlite3.Connection,
    history_table: str,
    entity_id_col: str,
    entity_id: str,
    field_name: str,
    as_of: Any,
) -> Optional[str]:
    """The most recent history value for one field with `effectiveAt <=
    as_of`, or `None` if nothing qualifies. `history_table` must be
    `"RaceFieldHistory"` or `"RunnerFieldHistory"` (validated, since this
    builds a SQL identifier)."""

    if history_table not in ("RaceFieldHistory", "RunnerFieldHistory"):
        raise ValueError(f"Unsupported history_table: {history_table!r}")

    cutoff = _to_sql_datetime(as_of)
    row = conn.execute(
        f'SELECT fieldValue FROM "{history_table}" '
        f"WHERE {entity_id_col} = ? AND fieldName = ? AND effectiveAt <= ? "
        "ORDER BY effectiveAt DESC LIMIT 1",
        (entity_id, field_name, cutoff),
    ).fetchone()
    return row["fieldValue"] if row else None


def reconstruct_race_as_of(conn: sqlite3.Connection, race_id: str, as_of: Any) -> dict[str, Any]:
    """Immutable fields come from the live `Race` row; every field in
    `RACE_MUTABLE_FIELDS` is reconstructed from `RaceFieldHistory` and set
    to `None` if no qualifying history row exists."""

    race = conn.execute('SELECT * FROM "Race" WHERE id = ?', (race_id,)).fetchone()
    if race is None:
        raise ValueError(f"No Race found with id {race_id!r}")

    reconstructed = {k: race[k] for k in race.keys() if k not in RACE_MUTABLE_FIELDS}
    reconstructed["as_of"] = _to_sql_datetime(as_of)
    for field_name in RACE_MUTABLE_FIELDS:
        reconstructed[field_name] = field_value_as_of(conn, "RaceFieldHistory", "raceId", race_id, field_name, as_of)
    return reconstructed


def reconstruct_runner_as_of(conn: sqlite3.Connection, runner_id: str, as_of: Any) -> dict[str, Any]:
    """Immutable fields come from the live `Runner` row; every field in
    `RUNNER_MUTABLE_FIELDS` is reconstructed from `RunnerFieldHistory` and
    set to `None` if no qualifying history row exists."""

    runner = conn.execute('SELECT * FROM "Runner" WHERE id = ?', (runner_id,)).fetchone()
    if runner is None:
        raise ValueError(f"No Runner found with id {runner_id!r}")

    reconstructed = {k: runner[k] for k in runner.keys() if k not in RUNNER_MUTABLE_FIELDS}
    reconstructed["as_of"] = _to_sql_datetime(as_of)
    for field_name in RUNNER_MUTABLE_FIELDS:
        reconstructed[field_name] = field_value_as_of(
            conn, "RunnerFieldHistory", "runnerId", runner_id, field_name, as_of
        )
    return reconstructed


def reconstruct_place_terms_as_of(
    conn: sqlite3.Connection, race_id: str, bookmaker_id: str, as_of: Any
) -> Optional[dict[str, Any]]:
    """The most recent `RacePlaceTermsHistory` row for this
    (race, bookmaker) with `effectiveAt <= as_of`, or `None` if this
    bookmaker had not yet published terms for this race by that time."""

    cutoff = _to_sql_datetime(as_of)
    row = conn.execute(
        'SELECT * FROM "RacePlaceTermsHistory" WHERE raceId = ? AND bookmakerId = ? AND effectiveAt <= ? '
        "ORDER BY effectiveAt DESC LIMIT 1",
        (race_id, bookmaker_id, cutoff),
    ).fetchone()
    return dict(row) if row is not None else None


def market_prices_as_of(
    conn: sqlite3.Connection, runner_id: str, as_of: Any, bookmaker_id: Optional[str] = None
) -> pd.DataFrame:
    """Every `RunnerMarketPrice` row for this runner timestamped `<=
    as_of` — the full point-in-time odds history available at that moment.
    Never includes a row timestamped after `as_of`. See
    `racingedge_data.odds_snapshots` for deriving named snapshots (opening,
    SP, ...) from this stream."""

    cutoff = _to_sql_datetime(as_of)
    query = 'SELECT * FROM "RunnerMarketPrice" WHERE runnerId = ? AND timestamp <= ?'
    params: list[Any] = [runner_id, cutoff]
    if bookmaker_id:
        query += " AND bookmakerId = ?"
        params.append(bookmaker_id)
    query += " ORDER BY timestamp ASC"

    df = pd.read_sql_query(query, conn, params=params)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        cutoff_ts = pd.to_datetime(cutoff, utc=True)
        if (df["timestamp"] > cutoff_ts).any():
            raise RuntimeError(
                "market_prices_as_of returned a row timestamped after as_of — this would leak "
                "future odds information."
            )
    return df

"""Chronological per-horse timeline queries — point-in-time safe by
construction.

Every function takes an explicit `before_date` cutoff and is guaranteed to
return only rows STRICTLY before it — never the target race, never a run
the horse hadn't yet had as of that date. This is the single choke point
ad-hoc research code (the Dataset Explorer, notebooks, one-off scripts)
should go through when it needs "this horse's history as of some date" —
the bulk training pipeline in `racingedge_model.features.build` enforces
the same invariant independently (operating on whole DataFrames at once,
for performance) and is unaffected by this module; the two are not meant to
be called together in a hot loop.

Corresponds to the project's required functions `getPreviousRuns`,
`getLastNRuns`, `getCourseHistoryBefore`, `getDistanceHistoryBefore`,
`getGoingHistoryBefore`, `getRatingHistoryBefore` — named here in Pythonic
snake_case.

Reads from `FormEntry`, the canonical store of a horse's historical
performance. Filtering happens in the SQL `WHERE` clause, then is verified
again in Python (`_assert_strictly_before`) as a defense-in-depth check —
belt and braces, since a leakage bug here would silently corrupt every
feature computed downstream.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pandas as pd

from racingedge_model.db import to_prisma_datetime


class TimelineLeakageError(RuntimeError):
    """Raised if a query result contains a row on/after the cutoff — should
    be unreachable given the SQL WHERE clause; catches a bug in that clause
    rather than trusting it blindly."""


def _to_sql_datetime(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    return to_prisma_datetime(value)


def _assert_strictly_before(df: pd.DataFrame, before_date: Any, date_col: str = "raceDate") -> None:
    if df.empty:
        return
    max_date = pd.to_datetime(df[date_col], utc=True).max()
    cutoff = pd.Timestamp(before_date)
    cutoff = cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")
    if max_date >= cutoff:
        raise TimelineLeakageError(
            f"Query returned a row with {date_col}={max_date}, which is not strictly before "
            f"before_date={cutoff} — this would leak future information."
        )


def get_previous_runs(conn: sqlite3.Connection, horse_id: str, before_date: Any) -> pd.DataFrame:
    """All of a horse's FormEntry rows with raceDate strictly before
    `before_date`, most recent first."""

    cutoff = _to_sql_datetime(before_date)
    df = pd.read_sql_query(
        'SELECT * FROM "FormEntry" WHERE horseId = ? AND raceDate < ? ORDER BY raceDate DESC',
        conn,
        params=(horse_id, cutoff),
    )
    df["raceDate"] = pd.to_datetime(df["raceDate"], utc=True)
    _assert_strictly_before(df, before_date)
    return df


def get_last_n_runs(conn: sqlite3.Connection, horse_id: str, before_date: Any, n: int) -> pd.DataFrame:
    """The `n` most recent runs strictly before `before_date`."""

    return get_previous_runs(conn, horse_id, before_date).head(n).reset_index(drop=True)


def get_course_history_before(conn: sqlite3.Connection, horse_id: str, course: str, before_date: Any) -> pd.DataFrame:
    df = get_previous_runs(conn, horse_id, before_date)
    return df[df["course"] == course].reset_index(drop=True)


def get_distance_history_before(
    conn: sqlite3.Connection,
    horse_id: str,
    distance_furlongs: float,
    before_date: Any,
    tolerance_furlongs: float = 0.0,
) -> pd.DataFrame:
    """Runs at (within `tolerance_furlongs` of) `distance_furlongs`."""

    df = get_previous_runs(conn, horse_id, before_date)
    if df.empty:
        return df
    if tolerance_furlongs > 0:
        mask = (df["distanceFurlongs"] - distance_furlongs).abs() <= tolerance_furlongs
    else:
        mask = df["distanceFurlongs"] == distance_furlongs
    return df[mask].reset_index(drop=True)


def get_going_history_before(conn: sqlite3.Connection, horse_id: str, going: str, before_date: Any) -> pd.DataFrame:
    df = get_previous_runs(conn, horse_id, before_date)
    return df[df["going"] == going].reset_index(drop=True)


def get_rating_history_before(conn: sqlite3.Connection, horse_id: str, before_date: Any) -> pd.DataFrame:
    """The (raceDate, officialRating) series, non-null ratings only, most
    recent first — the shape most rating-trend calculations want."""

    df = get_previous_runs(conn, horse_id, before_date)
    if df.empty:
        return df[["raceDate", "officialRating"]] if "officialRating" in df.columns else df
    df = df[df["officialRating"].notna()]
    return df[["raceDate", "officialRating"]].reset_index(drop=True)

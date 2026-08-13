"""Derives NAMED odds snapshots from the raw `RunnerMarketPrice` timestamp
stream, for one runner and one bookmaker at a time.

The project's required snapshots: opening, 24h pre-race, 6h pre-race, 1h
pre-race, 30m pre-race, 10m pre-race, 5m pre-race, off-time, and SP
(starting price) / BSP (Betfair Starting Price, exchange only).

**Never use a later price to stand in for an earlier one.** Each
"N before off-time" snapshot is the MOST RECENT price known at or before
that moment — found by filtering to `timestamp <= moment` and taking the
last one, never the price point numerically closest in time (which could
be a price observed slightly AFTER that moment and therefore leak future
market information into a supposedly-earlier snapshot).

This module only derives from a price series already loaded up to some
point-in-time-safe cutoff — see `racingedge_data.point_in_time.
market_prices_as_of`, which `get_named_snapshots_for_runner` uses to load
prices up to (and including) the race off-time, never beyond it.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Optional

import pandas as pd

from racingedge_data.point_in_time import market_prices_as_of

# Offsets before race off-time for the "N pre-race" named snapshots.
SNAPSHOT_OFFSETS: dict[str, timedelta] = {
    "24h": timedelta(hours=24),
    "6h": timedelta(hours=6),
    "1h": timedelta(hours=1),
    "30m": timedelta(minutes=30),
    "10m": timedelta(minutes=10),
    "5m": timedelta(minutes=5),
}

SNAPSHOT_LABELS: tuple[str, ...] = ("opening", *SNAPSHOT_OFFSETS.keys(), "off_time", "sp")


@dataclass(frozen=True)
class OddsSnapshot:
    label: str
    timestamp: Optional[pd.Timestamp]
    win_odds_decimal: Optional[float]
    # True if a genuine price point exists at exactly the target moment (or,
    # for "opening"/"sp", if the provider explicitly flagged it as such).
    # False means this snapshot was backfilled from the most recent EARLIER
    # price because none existed exactly then — still leakage-safe, just
    # not an exact match, and callers may want to treat it with less
    # confidence.
    is_exact: bool


def _last_price_at_or_before(prices: pd.DataFrame, moment: pd.Timestamp) -> Optional[pd.Series]:
    eligible = prices[prices["timestamp"] <= moment]
    if eligible.empty:
        return None
    return eligible.sort_values("timestamp").iloc[-1]


def derive_named_snapshots(prices: pd.DataFrame, race_off_time: Any) -> dict[str, OddsSnapshot]:
    """`prices` must be one runner's timestamped price history for a SINGLE
    bookmaker, with columns `timestamp` (tz-aware), `winOddsDecimal`,
    `isOpeningPrice`, `isStartingPrice`. Rows after `race_off_time` are
    ignored defensively (callers should not pass any, but this guards
    against a caller mistake rather than silently using future prices).
    """

    off_time = pd.Timestamp(race_off_time)
    off_time = off_time.tz_localize("UTC") if off_time.tzinfo is None else off_time.tz_convert("UTC")

    if not prices.empty:
        prices = prices[prices["timestamp"] <= off_time]

    results: dict[str, OddsSnapshot] = {}

    if prices.empty:
        for label in SNAPSHOT_LABELS:
            results[label] = OddsSnapshot(label, None, None, False)
        return results

    sorted_prices = prices.sort_values("timestamp")

    opening_flagged = sorted_prices[sorted_prices["isOpeningPrice"] == True]  # noqa: E712
    if not opening_flagged.empty:
        row = opening_flagged.iloc[0]
        results["opening"] = OddsSnapshot("opening", row["timestamp"], row["winOddsDecimal"], True)
    else:
        row = sorted_prices.iloc[0]
        results["opening"] = OddsSnapshot("opening", row["timestamp"], row["winOddsDecimal"], False)

    for label, offset in SNAPSHOT_OFFSETS.items():
        moment = off_time - offset
        row = _last_price_at_or_before(sorted_prices, moment)
        if row is not None:
            results[label] = OddsSnapshot(label, row["timestamp"], row["winOddsDecimal"], bool(row["timestamp"] == moment))
        else:
            results[label] = OddsSnapshot(label, None, None, False)

    off_time_row = _last_price_at_or_before(sorted_prices, off_time)
    results["off_time"] = OddsSnapshot(
        "off_time", off_time_row["timestamp"], off_time_row["winOddsDecimal"], True
    ) if off_time_row is not None else OddsSnapshot("off_time", None, None, False)

    sp_flagged = sorted_prices[sorted_prices["isStartingPrice"] == True]  # noqa: E712
    if not sp_flagged.empty:
        row = sp_flagged.iloc[-1]
        results["sp"] = OddsSnapshot("sp", row["timestamp"], row["winOddsDecimal"], True)
    else:
        results["sp"] = OddsSnapshot("sp", None, None, False)

    return results


def get_named_snapshots_for_runner(
    conn: sqlite3.Connection, runner_id: str, bookmaker_id: str, race_off_time: Any
) -> dict[str, OddsSnapshot]:
    """Loads this runner+bookmaker's price history up to (and including)
    `race_off_time` via `point_in_time.market_prices_as_of` — never a price
    observed after off-time — and derives every named snapshot from it."""

    prices = market_prices_as_of(conn, runner_id, race_off_time, bookmaker_id=bookmaker_id)
    return derive_named_snapshots(prices, race_off_time)


def get_bsp_for_runner(conn: sqlite3.Connection, runner_id: str) -> Optional[float]:
    """Betfair Starting Price: the SP-flagged `RunnerMarketPrice` row from
    an EXCHANGE bookmaker (`Bookmaker.isExchange = 1`), if one exists.
    `ResultEntry.bspDecimal` (set at settlement) remains the
    settlement-authoritative BSP value — this function derives the same
    figure independently from the raw price stream, useful for
    cross-checking or when settlement data isn't populated yet."""

    row = conn.execute(
        'SELECT mp.winOddsDecimal as odds FROM "RunnerMarketPrice" mp '
        'JOIN "Bookmaker" b ON b.id = mp.bookmakerId '
        "WHERE mp.runnerId = ? AND mp.isStartingPrice = 1 AND b.isExchange = 1 "
        "ORDER BY mp.timestamp DESC LIMIT 1",
        (runner_id,),
    ).fetchone()
    return float(row["odds"]) if row is not None else None

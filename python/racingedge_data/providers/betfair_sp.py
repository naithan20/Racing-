"""Free Betfair Starting Price (SP/BSP) historical data importer — Phase 3C.

Distinct from `betfair_historical.py` (the PAID Historical Data product's
tick-level Exchange Stream files): this parses the FREE per-sport/per-date
CSV files historically published at
`https://promo.betfair.com/betfairsp/SP_history.html`, covering starting
prices with no purchase required.

## Verification status

Direct access to `promo.betfair.com` was **blocked by this environment's
network egress policy** while building this adapter, so the exact current
CSV header could not be re-confirmed live. The column set implemented here
— `EVENT_ID`, `MENU_HINT`, `EVENT_NAME`, `EVENT_DT`, `SELECTION_ID`,
`SELECTION_NAME`, `WIN_LOSE`, `BSP`, `PPWAP`, `MORNINGWAP`, `PPMAX`,
`PPMIN`, `IPMAX`, `IPMIN`, `MORNINGTRADEDVOL`, `PPTRADEDVOL`,
`IPTRADEDVOL` — is the well-established, long-stable free Betfair
Historical SP CSV format used across numerous independent public datasets.
**A maintainer should confirm the actual header of a freshly-downloaded
file before relying on this without checking.** This parser reads columns
BY NAME (`csv.DictReader`, never by position), so extra or reordered
columns degrade gracefully; a genuinely renamed core column would still
need `COLUMN_NAMES` below updated.

## Label: CLOSING/SP MARKET BENCHMARK — NOT pre-race live odds

BSP/SP is set at the moment a race actually goes off, after the market has
absorbed every piece of information right up to that instant. Every price
this module writes is flagged `isStartingPrice=1` on a bookmaker literally
named `"Betfair SP (free historical)"`, and is intended ONLY for post-race
benchmarking, fair-market comparison, ROI analysis, and closing-price
comparison. **It must never be used as a feature representing what a
prediction made hours before the race could plausibly have known** — see
POINT_IN_TIME_ARCHITECTURE.md and `racingedge_data.market_baseline`.

## Entity matching

Per this project's no-fuzzy-matching rule, a row is matched to a
RacingEdge `Runner` via: (1) `resolve_horse` on `SELECTION_NAME` (provider
ID / exact-normalized-name only), then (2) an EXACT match on calendar date
(`EVENT_DT`) against `Race.date`. This free CSV format does not reliably
expose a separate, cleanly-structured course field (`EVENT_NAME` embeds
race time + course together in free text, e.g. `"14:30 Fixture Park"`), so
course is deliberately NOT used as a match criterion here — a horse
running more than once on the same calendar date is rare enough that
date + exact horse name is usually unambiguous; when it isn't (more than
one candidate `Runner` on that date), the row is reported unresolved
rather than guessed.

## Supported file formats

Plain CSV, gzip-compressed CSV (`.csv.gz`), and ZIP archives containing one
or more CSV files (Betfair's historical SP downloads are commonly
distributed as ZIP collections of per-day files).
"""

from __future__ import annotations

import csv
import gzip
import io
import logging
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import IO, Iterator, Optional

from racingedge_data.canonical import CanonicalOddsPoint
from racingedge_data.entity_resolution import resolve_horse
from racingedge_data.providers.csv_provider import parse_race_date

logger = logging.getLogger(__name__)

CLOSING_SP_BOOKMAKER_NAME = "Betfair SP (free historical)"


@dataclass(frozen=True)
class UnresolvedSpRow:
    event_id: str
    selection_name: str
    reason: str


def _open_text_files(path: str | Path) -> Iterator[tuple[str, IO[str]]]:
    """Yields `(filename, text_handle)` for every CSV in `path` — a single
    `.csv`, a `.csv.gz`, or a `.zip` containing one or more `.csv` files."""

    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if not name.lower().endswith(".csv"):
                    continue
                with zf.open(name) as raw:
                    yield name, io.TextIOWrapper(raw, encoding="utf-8")
        return

    if suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            yield path.stem, f
        return

    with open(path, "r", encoding="utf-8") as f:
        yield path.name, f


def _safe_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def extract_sp_points_from_file(
    path: str | Path,
) -> Iterator[tuple[CanonicalOddsPoint, str, str, str]]:
    """Yields `(CanonicalOddsPoint, event_id, event_name, selection_name)`
    tuples. A malformed row is skipped with a logged warning, not fatal to
    the rest of the file."""

    for filename, handle in _open_text_files(path):
        reader = csv.DictReader(handle)
        for row_number, row in enumerate(reader, start=1):
            event_dt_raw = (row.get("EVENT_DT") or "").strip()
            selection_name = (row.get("SELECTION_NAME") or "").strip()
            bsp_raw = (row.get("BSP") or "").strip()
            if not event_dt_raw or not selection_name or not bsp_raw:
                continue
            try:
                event_dt = parse_race_date(event_dt_raw)
                bsp = float(bsp_raw)
            except ValueError as exc:
                logger.warning("Skipping malformed row %d in %s: %s", row_number, filename, exc)
                continue

            event_id = (row.get("EVENT_ID") or "").strip()
            event_name = (row.get("EVENT_NAME") or "").strip()

            point = CanonicalOddsPoint(
                provider_runner_id=(row.get("SELECTION_ID") or "").strip() or selection_name,
                bookmaker_name=CLOSING_SP_BOOKMAKER_NAME,
                is_exchange=True,
                timestamp=event_dt,
                win_odds_decimal=bsp,
                is_starting_price=True,
                available_volume=_safe_float(row.get("PPTRADEDVOL")),
            )
            yield point, event_id, event_name, selection_name


def _get_or_create_closing_sp_bookmaker(conn: sqlite3.Connection) -> str:
    from racingedge_model.db import to_prisma_datetime
    from racingedge_model.ids import new_id

    row = conn.execute('SELECT id FROM "Bookmaker" WHERE name = ?', (CLOSING_SP_BOOKMAKER_NAME,)).fetchone()
    if row is not None:
        return row["id"]
    bookmaker_id = new_id()
    conn.execute(
        'INSERT INTO "Bookmaker" (id, name, isExchange, createdAt) VALUES (?, ?, 1, ?)',
        (bookmaker_id, CLOSING_SP_BOOKMAKER_NAME, to_prisma_datetime(datetime.now(timezone.utc))),
    )
    return bookmaker_id


def import_betfair_sp_file(
    conn: sqlite3.Connection,
    path: str | Path,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> tuple[int, list[UnresolvedSpRow]]:
    """Parses a free Betfair SP historical file and inserts
    `RunnerMarketPrice` rows (flagged `isStartingPrice=1`, bookmaker
    `"Betfair SP (free historical)"`) for every row that resolves to
    exactly one RacingEdge `Runner`. Does NOT create new races/runners —
    the race card must already be imported. Returns
    `(points_inserted, unresolved_rows)`."""

    from racingedge_model.db import to_prisma_datetime
    from racingedge_model.ids import new_id

    bookmaker_id = _get_or_create_closing_sp_bookmaker(conn)
    inserted = 0
    unresolved: list[UnresolvedSpRow] = []

    for point, event_id, event_name, selection_name in extract_sp_points_from_file(path):
        if start_date and point.timestamp.date() < start_date:
            continue
        if end_date and point.timestamp.date() > end_date:
            continue

        resolution = resolve_horse(conn, selection_name, provider_name="betfair-sp-free")
        candidate_runners = conn.execute(
            'SELECT r.id FROM "Runner" r JOIN "Race" ra ON ra.id = r.raceId '
            "WHERE r.horseId = ? AND date(ra.date) = date(?)",
            (resolution.canonical_id, to_prisma_datetime(point.timestamp)),
        ).fetchall()

        if len(candidate_runners) == 0:
            unresolved.append(
                UnresolvedSpRow(event_id, selection_name, "No Runner found for this horse on this date — import the race card first")
            )
            continue
        if len(candidate_runners) > 1:
            unresolved.append(
                UnresolvedSpRow(
                    event_id, selection_name, f"{len(candidate_runners)} ambiguous Runner matches on this date"
                )
            )
            continue

        runner_id = candidate_runners[0]["id"]
        conn.execute(
            'INSERT INTO "RunnerMarketPrice" '
            "(id, runnerId, bookmakerId, timestamp, winOddsDecimal, isStartingPrice, availableVolume, createdAt) "
            "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
            (
                new_id(),
                runner_id,
                bookmaker_id,
                to_prisma_datetime(point.timestamp),
                point.win_odds_decimal,
                point.available_volume,
                to_prisma_datetime(datetime.now(timezone.utc)),
            ),
        )
        inserted += 1

    return inserted, unresolved

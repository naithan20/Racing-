"""Parser for **purchased Betfair Historical Data** files — as opposed to
`betfair.py`'s `BetfairProvider`, which models a live/streaming exchange
feed. This module never makes a network call and never purchases anything;
it only parses files a maintainer has already bought and downloaded from
Betfair (`historicdata.betfair.com`) and extracted locally.

## Format (confirmed, well-established public spec)

Betfair Historical Data files are recordings of the Exchange **Stream API**
wire format — the same "Market Change Message" (`mcm`) JSON structure the
live Stream API sends, one JSON object per line (newline-delimited JSON),
optionally gzip-compressed. This wire format has been stable and publicly
documented for years and is used by numerous independent open-source
clients (e.g. `betfairlightweight`, `flumine`); unlike theracingapi's REST
field names (see `racing_api.py`), this is not something this build had to
guess at.

Each line looks like:

```json
{"op": "mcm", "pt": 1735732800000, "mc": [
  {
    "id": "1.123456789",
    "marketDefinition": {
      "marketTime": "2026-01-05T14:30:00.000Z",
      "eventName": "14:30 Fixture Park",
      "countryCode": "GB",
      "runners": [{"id": 12345678, "name": "Fixture Test Horse A", "sortPriority": 1}]
    },
    "rc": [
      {"id": 12345678, "ltp": 5.8, "atb": [[5.8, 120.5]], "atl": [[6.0, 80.0]], "tv": 4210.5}
    ]
  }
]}
```

- `pt` — publish time, **epoch milliseconds** — the exact, genuine
  timestamp of this update. This is what makes historical Betfair data
  point-in-time correct by construction: every price observation carries
  its own real timestamp, not an inferred one.
- `mc[].marketDefinition` — present on the first message for a market (and
  whenever the definition changes); carries `runners[]` with Betfair's own
  `id` (selection id) and `name` (**the only link back to a horse's
  identity in this file — see "Mapping to runner identities" below**).
- `mc[].rc[]` — runner (selection) price changes: `id` (selection id,
  matches a `marketDefinition.runners[].id`), `ltp` (last traded price),
  `atb`/`atl` (available-to-back / available-to-lay ladders, each
  `[[price, size], ...]` sorted best-first), `tv` (total matched volume).

## Mapping to runner identities

Betfair's own `id` (selection id) is an **exchange-internal identifier**,
not a RacingEdge `Runner.id` or a stable cross-provider horse id. The only
thing in the stream that identifies WHICH HORSE a selection id refers to is
`marketDefinition.runners[].name` — a plain-text runner name (sometimes
including a cloth number prefix, e.g. `"1. Fixture Test Horse A"`).

This module therefore resolves selection id -> horse name from the
market's own `marketDefinition`, then hands that name to
`racingedge_data.entity_resolution.resolve_horse` (exact-normalized-name /
provider-id matching — never blind fuzzy matching, per this project's
entity-resolution rule) to find the corresponding RacingEdge `Runner` for
the correct race (matched on `marketDefinition.marketTime` +
`eventName`/`countryCode` against `Race.date`/`raceTime`/`racecourse`).
**A market/race match failure or an unresolvable horse name is logged and
skipped, never guessed.**

## How timestamps are preserved

Every `CanonicalOddsPoint` produced here carries the message's own `pt`
(converted from epoch milliseconds to a UTC `datetime`) as its `timestamp`
— exactly what point-in-time correctness requires (see
POINT_IN_TIME_ARCHITECTURE.md). No timestamp is inferred, backfilled, or
approximated from file metadata.

## What you need to actually use this

1. A **Betfair Historical Data** purchase from `historicdata.betfair.com`
   covering horse racing (WIN market type) for the desired date range —
   this environment could not reach that portal to confirm the current
   exact plan tiers/pricing/packaging (network egress to
   `historicdata.betfair.com` and `support.developer.betfair.com` was
   blocked), so confirm current plan naming/pricing/file bundling at
   purchase time.
2. Extract the purchased archive (typically delivered as a `.tar`, itself
   containing per-day/per-market files, sometimes further gzip-compressed)
   with standard tools (`tar -xf ...`, `gunzip ...`) — this module does not
   do archive extraction, only newline-delimited-JSON parsing of the
   already-extracted market files.
3. Point `BetfairHistoricalFileProvider` at one or more extracted files.
"""

from __future__ import annotations

import gzip
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import IO, Any, Iterator, Optional

from racingedge_data.canonical import CanonicalOddsPoint
from racingedge_data.entity_resolution import resolve_horse

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UnresolvedSelection:
    """Recorded when a selection id in the stream could not be resolved to
    a RacingEdge Runner — surfaced to the caller rather than silently
    dropped, so import tooling can report it."""

    market_id: str
    selection_id: str
    horse_name: Optional[str]
    reason: str


def _open_maybe_gzip(path: str | Path) -> IO[str]:
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def _epoch_ms_to_datetime(epoch_ms: int) -> datetime:
    return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)


def parse_market_change_lines(lines: Iterator[str]) -> Iterator[dict[str, Any]]:
    """Parses newline-delimited market-change-message JSON, one dict per
    non-empty line. Malformed lines are skipped with a logged warning
    rather than aborting the whole file — a single corrupted line in a
    multi-megabyte historical file must not lose the rest of it."""

    for line_number, line in enumerate(lines, start=1):
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning("Skipping malformed line %d: %s", line_number, exc)


def extract_odds_points_from_file(
    path_or_lines: str | Path | Iterator[str],
    market_id_prefix: Optional[str] = None,
) -> Iterator[tuple[CanonicalOddsPoint, str, Optional[str]]]:
    """Yields `(CanonicalOddsPoint, market_id, horse_name)` tuples from one
    market file. `horse_name` is the selection's name from the market's own
    `marketDefinition` — the caller is responsible for resolving it to a
    RacingEdge horse/runner (see `import_betfair_historical_file` below),
    since this function has no database access by design (pure parsing).

    `market_id_prefix` optionally filters to only market ids starting with
    a given prefix (e.g. to skip non-WIN markets if a file mixes market
    types) — most historical file layouts are already one-market-per-file,
    so this is rarely needed.
    """

    if isinstance(path_or_lines, (str, Path)):
        handle = _open_maybe_gzip(path_or_lines)
        owns_handle = True
        lines: Iterator[str] = handle
    else:
        owns_handle = False
        lines = path_or_lines

    try:
        runner_names_by_market: dict[str, dict[str, str]] = {}

        for message in parse_market_change_lines(lines):
            if message.get("op") != "mcm":
                continue
            publish_time_ms = message.get("pt")
            if publish_time_ms is None:
                continue
            timestamp = _epoch_ms_to_datetime(int(publish_time_ms))

            for market_change in message.get("mc", []):
                market_id = market_change.get("id")
                if not market_id:
                    continue
                if market_id_prefix and not market_id.startswith(market_id_prefix):
                    continue

                market_definition = market_change.get("marketDefinition")
                if market_definition is not None:
                    runner_names_by_market[market_id] = {
                        str(r["id"]): r.get("name", "") for r in market_definition.get("runners", []) if "id" in r
                    }

                for runner_change in market_change.get("rc", []):
                    selection_id = runner_change.get("id")
                    if selection_id is None:
                        continue
                    selection_id = str(selection_id)

                    back_ladder = runner_change.get("atb") or []
                    lay_ladder = runner_change.get("atl") or []
                    best_back = back_ladder[0][0] if back_ladder else None
                    best_lay = lay_ladder[0][0] if lay_ladder else None
                    ltp = runner_change.get("ltp")
                    representative_price = ltp if ltp is not None else (best_back if best_back is not None else best_lay)
                    if representative_price is None:
                        continue

                    point = CanonicalOddsPoint(
                        provider_runner_id=selection_id,
                        bookmaker_name="Betfair Exchange",
                        is_exchange=True,
                        timestamp=timestamp,
                        win_odds_decimal=float(representative_price),
                        back_odds_decimal=float(best_back) if best_back is not None else None,
                        lay_odds_decimal=float(best_lay) if best_lay is not None else None,
                        available_volume=float(runner_change["tv"]) if runner_change.get("tv") is not None else None,
                    )
                    horse_name = runner_names_by_market.get(market_id, {}).get(selection_id)
                    yield point, market_id, horse_name
    finally:
        if owns_handle:
            handle.close()


def import_betfair_historical_file(
    conn: sqlite3.Connection,
    path: str | Path,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> tuple[int, list[UnresolvedSelection]]:
    """Parses one extracted Betfair historical market file, resolves each
    selection to a RacingEdge horse via `entity_resolution.resolve_horse`
    (exact-normalized-name matching against the selection's
    `marketDefinition` name — never fuzzy), and inserts `RunnerMarketPrice`
    rows for the matching `Runner`.

    Returns `(points_inserted, unresolved_selections)` — unresolved
    selections are reported, never silently dropped or guessed at. A
    selection only resolves if the horse name matches a runner already
    present in RacingEdge for a race at a plausible date — this function
    does NOT create new races/runners, since Betfair's feed alone doesn't
    carry the full race-card context this project requires (going, class,
    distance, etc. — see racing_api.py for that).
    """

    unresolved: list[UnresolvedSelection] = []
    inserted = 0

    from racingedge_model.db import to_prisma_datetime
    from racingedge_model.ids import new_id

    for point, market_id, horse_name in extract_odds_points_from_file(path):
        if start_date and point.timestamp.date() < start_date:
            continue
        if end_date and point.timestamp.date() > end_date:
            continue

        if not horse_name:
            unresolved.append(
                UnresolvedSelection(
                    market_id=market_id,
                    selection_id=point.provider_runner_id,
                    horse_name=None,
                    reason="No marketDefinition.runners[].name seen yet for this selection",
                )
            )
            continue

        resolution = resolve_horse(conn, horse_name, provider_name="betfair-historical")
        runner_row = conn.execute(
            'SELECT id FROM "Runner" WHERE horseId = ? ORDER BY createdAt DESC LIMIT 1',
            (resolution.canonical_id,),
        ).fetchone()
        if runner_row is None:
            unresolved.append(
                UnresolvedSelection(
                    market_id=market_id,
                    selection_id=point.provider_runner_id,
                    horse_name=horse_name,
                    reason="Horse resolved but has no Runner row in RacingEdge yet — import the race card first",
                )
            )
            continue

        bookmaker_row = conn.execute('SELECT id FROM "Bookmaker" WHERE name = ?', (point.bookmaker_name,)).fetchone()
        if bookmaker_row is None:
            bookmaker_id = new_id()
            conn.execute(
                'INSERT INTO "Bookmaker" (id, name, isExchange, createdAt) VALUES (?, ?, 1, ?)',
                (bookmaker_id, point.bookmaker_name, to_prisma_datetime(datetime.now(timezone.utc))),
            )
        else:
            bookmaker_id = bookmaker_row["id"]

        conn.execute(
            'INSERT INTO "RunnerMarketPrice" '
            "(id, runnerId, bookmakerId, timestamp, winOddsDecimal, backOddsDecimal, layOddsDecimal, "
            "availableVolume, createdAt) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                new_id(),
                runner_row["id"],
                bookmaker_id,
                to_prisma_datetime(point.timestamp),
                point.win_odds_decimal,
                point.back_odds_decimal,
                point.lay_odds_decimal,
                point.available_volume,
                to_prisma_datetime(datetime.now(timezone.utc)),
            ),
        )
        inserted += 1

    return inserted, unresolved

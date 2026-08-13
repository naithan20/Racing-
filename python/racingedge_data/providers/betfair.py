"""Stub adapter for a licensed Betfair Exchange (or similar betting
exchange) odds feed.

**This adapter does not make any network call.** No API credentials were
available when this was built. It exists to prove the adapter/field-mapping
pattern for `OddsDataProvider` — including exchange-specific fields
(back/lay/matched volume/market status) that fixed-odds bookmaker feeds
don't have — and to be fully testable via `FixtureBackedProvider`.

To connect this to a real account, a maintainer needs to:
1. Obtain a Betfair (or equivalent exchange) API subscription and app key —
   set via environment variables, e.g. `BETFAIR_APP_KEY` / `BETFAIR_SESSION_TOKEN`.
2. Implement an HTTP/streaming client inside `BetfairProvider.fetch_odds`
   that calls the exchange's documented market-data API (e.g. Betfair's
   Exchange Streaming API) and returns data shaped like
   `fixtures/betfair_sample.json` (or whatever the real response shape turns
   out to be — the field-mapping constants below would need updating to
   match the real API's actual field names, which this build has not
   verified against real documentation).
3. Respect the exchange's terms of service, rate limits, and licensing.

The fixture's field names below are an illustrative, plausible shape chosen
to demonstrate field translation — NOT verified against Betfair's actual
API contract.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterator

from racingedge_data.canonical import CanonicalOddsPoint
from racingedge_data.providers.base import FixtureBackedProvider, OddsDataProvider
from racingedge_data.providers.csv_provider import parse_race_date


def _map_price_point(obj: dict[str, Any]) -> CanonicalOddsPoint:
    back_price = obj.get("back")
    lay_price = obj.get("lay")
    representative_price = back_price if back_price is not None else lay_price
    return CanonicalOddsPoint(
        provider_runner_id=obj.get("selection_id", ""),
        bookmaker_name="Betfair Exchange",
        is_exchange=True,
        timestamp=parse_race_date(obj["market_time"]),
        win_odds_decimal=float(representative_price) if representative_price is not None else 0.0,
        back_odds_decimal=back_price,
        lay_odds_decimal=lay_price,
        available_volume=obj.get("total_matched"),
        market_status=obj.get("status"),
        is_starting_price=str(obj.get("status", "")).upper() == "CLOSED",
    )


class BetfairProvider(FixtureBackedProvider, OddsDataProvider):
    name = "betfair"
    required_credentials_note = (
        "a Betfair (or equivalent exchange) API app key and session token "
        "(BETFAIR_APP_KEY / BETFAIR_SESSION_TOKEN env vars) plus a streaming/HTTP "
        "client implementation in BetfairProvider.fetch_odds — neither exists in this build"
    )

    def fetch_odds(self, start_date: date, end_date: date) -> Iterator[CanonicalOddsPoint]:
        payload = self._load_fixture_json()
        records = payload.get("prices", []) if isinstance(payload, dict) else payload
        for obj in records:
            point = _map_price_point(obj)
            if start_date <= point.timestamp.date() <= end_date:
                yield point

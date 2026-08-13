"""Stub adapter for a licensed "Racing API"-style race-card provider (e.g.
theracingapi.com or a similar commercial racecards/results API).

**This adapter does not make any network call.** It has never been
integrated against a real Racing API account — no credentials were
available when this was built — and per the project's explicit "no
scraping" constraint, this file must not grow a scraper as a substitute.
It exists to prove the adapter/field-mapping pattern and to be fully
testable via `FixtureBackedProvider`.

To connect this to a real account, a maintainer needs to:
1. Obtain a licensed subscription and API credentials (commonly a username
   + password, or an API key, depending on the provider) — set them via
   environment variables, e.g. `RACING_API_USERNAME` / `RACING_API_PASSWORD`.
2. Implement an HTTP client (e.g. using `requests` or `httpx`) inside
   `RacingApiProvider.fetch_races` that calls the provider's documented
   racecards endpoint for the given date range and returns JSON shaped like
   `fixtures/racing_api_sample.json` (or whatever the real response shape
   turns out to be — the field-mapping constants below would need updating
   to match the real API's actual field names, which this build has not
   verified against real documentation).
3. Respect the provider's terms of service and rate limits.

The fixture's field names below (`meeting`, `off_dt`, `type`, `distance_f`,
...) are an illustrative, plausible racecards-API shape chosen to
demonstrate non-trivial field translation — they are NOT verified against
any real provider's actual API contract.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterator

from racingedge_data.canonical import CanonicalHorse, CanonicalRace, CanonicalRunner
from racingedge_data.providers.base import FixtureBackedProvider, RaceDataProvider
from racingedge_data.providers.csv_provider import parse_race_date

_FLAT_JUMPS_MAP = {"flat": "FLAT", "jumps": "JUMPS", "nh": "JUMPS"}
_SURFACE_MAP = {"turf": "TURF", "aw": "ALL_WEATHER", "all-weather": "ALL_WEATHER", "dirt": "DIRT"}


def _map_runner(obj: dict[str, Any]) -> CanonicalRunner:
    horse = CanonicalHorse(
        name=obj.get("horse", ""),
        provider_horse_id=obj.get("horse_id"),
        trainer_name=obj.get("trainer"),
    )
    return CanonicalRunner(
        horse=horse,
        provider_runner_id=obj.get("runner_id") or obj.get("horse_id"),
        cloth_number=obj.get("number"),
        draw=obj.get("draw"),
        official_rating=obj.get("or"),
        jockey_name=obj.get("jockey"),
        trainer_name=obj.get("trainer"),
        headgear=obj.get("headgear"),
        non_runner=bool(obj.get("non_runner", False)),
    )


def _map_race(obj: dict[str, Any]) -> CanonicalRace:
    off_dt = parse_race_date(obj["off_dt"])
    runners = tuple(_map_runner(r) for r in obj.get("runners", []))
    return CanonicalRace(
        provider_race_id=obj.get("race_id"),
        date=off_dt,
        race_time=off_dt.strftime("%H:%M"),
        racecourse=obj.get("meeting", ""),
        country=obj.get("country", ""),
        race_name=obj.get("race_name", ""),
        race_type=obj.get("race_type"),
        flat_jumps=_FLAT_JUMPS_MAP.get(str(obj.get("type", "")).lower(), "FLAT"),
        surface=_SURFACE_MAP.get(str(obj.get("surface", "")).lower(), "TURF"),
        distance_furlongs=float(obj.get("distance_f") or 0.0),
        race_class=obj.get("class"),
        handicap_type="HANDICAP" if obj.get("is_handicap") else "NON_HANDICAP",
        number_of_runners=int(obj.get("field_size") or len(runners)),
        going=obj.get("going"),
        runners=runners,
    )


class RacingApiProvider(FixtureBackedProvider, RaceDataProvider):
    name = "racing-api"
    required_credentials_note = (
        "a licensed racecards API subscription (credentials via "
        "RACING_API_USERNAME / RACING_API_PASSWORD env vars) plus an HTTP client "
        "implementation in RacingApiProvider.fetch_races — neither exists in this build"
    )

    def fetch_races(self, start_date: date, end_date: date) -> Iterator[CanonicalRace]:
        payload = self._load_fixture_json()
        records = payload.get("racecards", []) if isinstance(payload, dict) else payload
        for obj in records:
            race = _map_race(obj)
            if start_date <= race.date.date() <= end_date:
                yield race

"""Adapter for **The Racing API** (theracingapi.com) — a licensed UK & Irish
racecards/results API using HTTP Basic Authentication.

## Verification status (read before trusting this file)

Direct access to `https://api.theracingapi.com/documentation` and
`https://www.theracingapi.com/` was **blocked by this environment's network
egress policy** while building this adapter (both returned
`EGRESS_BLOCKED`). The following facts were instead verified from the
vendor's own publicly published example scripts and their OpenAPI listing
in the `APIs-guru/openapi-directory` GitHub repository — genuine primary
sources, just not the live docs site itself:

**Confirmed** (cite: `gist.github.com/theracingapi/ad930791391b398e0bf5b2d1b296ce05`,
`.../4d492dbdba58c2072fe4f98ee090126f`, `.../54c49327e961e6ff84ccf0c33ab5b2f1`,
and `raw.githubusercontent.com/APIs-guru/openapi-directory/.../theracingapi.com/1.0.0/openapi.yaml`):

- Base URL: `https://api.theracingapi.com/v1`
- Auth: HTTP Basic (username + password), i.e. `requests.auth.HTTPBasicAuth`
- Rate limit: **2 requests/second across all plans**
- Endpoints exist for: `GET /racecards` (query: `day=today|tomorrow`),
  `GET /results` (query: `start_date`, `end_date`, `limit`, `skip`),
  `GET /horses/{horse_id}/results`, `GET /horses/search`,
  `GET /jockeys/search`, `GET /jockeys/{jockey_id}/results` +
  `analysis/{courses,distances,owners,trainers}`, `GET /dams/search`,
  `GET /dams/{dam_id}/results` + `analysis/*`, `GET /damsires/*` (mirrors
  dams), `GET /courses`, `GET /courses/regions`.
- Pagination for `/results` (and the other list endpoints): `limit` /
  `skip` query params, response includes a `total` count; page by
  incrementing `skip` by `limit` until `skip >= total`.
- Confirmed top-level response keys: `racecards`, `results`, `runners`,
  `total`, `query`.
- Confirmed per-race fields: `region`, `course`, `off_time`.
- Confirmed per-runner fields: `horse`, `horse_id`, `jockey`, `jockey_id`,
  `trainer`, `trainer_id`, `sex_code` (racecards) / `sex` (results).

**NOT verified — best-effort candidate key names, not confirmed against a
live response.** Official rating, draw, weight, going, race class,
distance, pedigree (sire/dam/damsire), headgear, and starting price are
almost certainly present in a real `/results` or `/racecards` response
(this is a comprehensive commercial racing API), but this build could not
inspect one to confirm the exact key spellings. `_UNVERIFIED_RUNNER_FIELD_CANDIDATES`
below lists the key names this adapter will *try*, in order, for each
canonical field — informed guesses based on common UK-racing-data-feed
naming conventions, not confirmed facts. **A maintainer with real API
credentials MUST verify these against one real response and correct this
list before trusting the resulting data for training.** Until then, any
canonical field populated only from this best-effort list should be
treated as unverified — none of this build's own tests assert a specific
value for them, only that a missing key degrades to `None` rather than
raising.

## What's actually implemented here

- A real HTTP client (`_RacingApiHttpClient`) using `requests`, with retry +
  exponential backoff on transient failures (429/5xx/connection errors) and
  a rate limiter respecting the confirmed 2 req/s ceiling.
- `RacingApiProvider.fetch_races` pages through `/results` for a date range
  — the correct endpoint for HISTORICAL race+runner+result ingestion
  (`/racecards` is for today's/tomorrow's upcoming cards, not history).
- Falls back to `FixtureBackedProvider` behaviour (reading a local fixture
  file) when no live credentials are configured, so the adapter's parsing
  logic is fully testable without a subscription — see
  `providers/fixtures/racing_api_sample.json`.

## Credentials required to go live

Set `RACING_API_USERNAME` and `RACING_API_PASSWORD` environment variables
(a licensed theracingapi.com subscription). Neither is set in this
repository/environment — this adapter will raise `ProviderConfigurationError`
if asked to fetch live data without them and no fixture is supplied.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta
from typing import Any, Iterator, Optional

from racingedge_data.canonical import CanonicalHorse, CanonicalRace, CanonicalRunner
from racingedge_data.providers.base import FixtureBackedProvider, ProviderConfigurationError, RaceDataProvider
from racingedge_data.providers.csv_provider import parse_race_date

BASE_URL = "https://api.theracingapi.com/v1"
RATE_LIMIT_REQUESTS_PER_SECOND = 2  # confirmed vendor-wide limit, all plans
RESULTS_PAGE_SIZE = 50  # matches the vendor's own results_pull.py example

_FLAT_JUMPS_MAP = {"flat": "FLAT", "jumps": "JUMPS", "nh": "JUMPS", "national hunt": "JUMPS"}
_SURFACE_MAP = {"turf": "TURF", "aw": "ALL_WEATHER", "all-weather": "ALL_WEATHER", "dirt": "DIRT"}

# Unverified — see module docstring. Each canonical field maps to an
# ordered list of candidate JSON keys tried in turn; first present wins.
_UNVERIFIED_RUNNER_FIELD_CANDIDATES: dict[str, list[str]] = {
    "official_rating": ["ofr", "or", "official_rating", "rating"],
    "draw": ["draw", "stall_number", "stall"],
    "weight_lbs_total": ["lbs", "weight_lbs", "weight"],
    "headgear": ["headgear", "hg"],
    "sire_name": ["sire"],
    "dam_name": ["dam"],
    "damsire_name": ["damsire", "dams_sire"],
    "starting_price_decimal": ["sp_dec", "sp_decimal", "sp"],
    "cloth_number": ["number", "cloth_number"],
    "age_at_race": ["age"],
}
_UNVERIFIED_RACE_FIELD_CANDIDATES: dict[str, list[str]] = {
    "race_name": ["race_name", "name"],
    "race_type": ["type", "race_type"],
    "going": ["going"],
    "distance_furlongs": ["distance_f", "dist_f", "distance"],
    "race_class": ["race_class", "class"],
    "handicap_type": ["is_handicap"],
    "flat_jumps": ["type", "jumps_flat"],
}


def _first_present(obj: dict[str, Any], candidates: list[str]) -> Any:
    for key in candidates:
        if key in obj and obj[key] is not None:
            return obj[key]
    return None


class RacingApiHttpError(RuntimeError):
    """Raised after retries are exhausted for a live Racing API request."""


class _RacingApiHttpClient:
    """Thin wrapper: HTTP Basic Auth, rate limiting, retry with exponential
    backoff. No caching, no batching beyond what the API itself paginates."""

    def __init__(
        self,
        username: str,
        password: str,
        base_url: str = BASE_URL,
        max_retries: int = 5,
        backoff_base_seconds: float = 1.0,
    ):
        import requests  # local import: keep `requests` optional for fixture-only usage

        self._requests = requests
        self._auth = requests.auth.HTTPBasicAuth(username, password)
        self._base_url = base_url
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds
        self._min_interval = 1.0 / RATE_LIMIT_REQUESTS_PER_SECOND
        self._last_request_at: Optional[float] = None

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_at is None:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self._min_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def get(self, path: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        last_exception: Optional[BaseException] = None

        for attempt in range(self._max_retries):
            self._wait_for_rate_limit()
            self._last_request_at = time.monotonic()
            try:
                response = self._requests.get(url, auth=self._auth, params=params, timeout=30)
            except self._requests.RequestException as exc:  # connection errors, timeouts
                last_exception = exc
                time.sleep(self._backoff_base_seconds * (2**attempt))
                continue

            if response.status_code == 429 or response.status_code >= 500:
                last_exception = RacingApiHttpError(f"{response.status_code} from {url}")
                time.sleep(self._backoff_base_seconds * (2**attempt))
                continue

            if response.status_code == 401 or response.status_code == 403:
                raise ProviderConfigurationError(
                    f"Racing API returned {response.status_code} for {url} — check "
                    "RACING_API_USERNAME / RACING_API_PASSWORD are correct and the "
                    "subscription plan covers this endpoint."
                )

            response.raise_for_status()
            return response.json()

        raise RacingApiHttpError(
            f"Exhausted {self._max_retries} retries against {url}"
        ) from last_exception


def _map_runner(obj: dict[str, Any]) -> CanonicalRunner:
    horse = CanonicalHorse(
        name=obj.get("horse", ""),
        provider_horse_id=obj.get("horse_id"),
        sex=obj.get("sex") or obj.get("sex_code"),
        trainer_name=obj.get("trainer"),
        sire_name=_first_present(obj, _UNVERIFIED_RUNNER_FIELD_CANDIDATES["sire_name"]),
        dam_name=_first_present(obj, _UNVERIFIED_RUNNER_FIELD_CANDIDATES["dam_name"]),
        damsire_name=_first_present(obj, _UNVERIFIED_RUNNER_FIELD_CANDIDATES["damsire_name"]),
    )
    return CanonicalRunner(
        horse=horse,
        provider_runner_id=obj.get("horse_id"),
        cloth_number=_first_present(obj, _UNVERIFIED_RUNNER_FIELD_CANDIDATES["cloth_number"]),
        draw=_first_present(obj, _UNVERIFIED_RUNNER_FIELD_CANDIDATES["draw"]),
        age_at_race=_first_present(obj, _UNVERIFIED_RUNNER_FIELD_CANDIDATES["age_at_race"]),
        weight_lbs_total=_first_present(obj, _UNVERIFIED_RUNNER_FIELD_CANDIDATES["weight_lbs_total"]),
        official_rating=_first_present(obj, _UNVERIFIED_RUNNER_FIELD_CANDIDATES["official_rating"]),
        jockey_name=obj.get("jockey"),
        trainer_name=obj.get("trainer"),
        headgear=_first_present(obj, _UNVERIFIED_RUNNER_FIELD_CANDIDATES["headgear"]),
        non_runner=bool(obj.get("non_runner", False)),
    )


def _map_race(obj: dict[str, Any]) -> CanonicalRace:
    off_time_raw = obj.get("off_time") or obj.get("off_dt")
    if not off_time_raw:
        raise ValueError("Race object is missing 'off_time'")
    off_time = parse_race_date(str(off_time_raw))

    runners_raw = obj.get("runners", [])
    runners = tuple(_map_runner(r) for r in runners_raw)

    race_type_raw = str(_first_present(obj, _UNVERIFIED_RACE_FIELD_CANDIDATES["flat_jumps"]) or "").lower()
    is_handicap = _first_present(obj, _UNVERIFIED_RACE_FIELD_CANDIDATES["handicap_type"])

    return CanonicalRace(
        provider_race_id=obj.get("race_id") or obj.get("id"),
        date=off_time,
        race_time=off_time.strftime("%H:%M"),
        racecourse=obj.get("course", ""),
        country=obj.get("region", ""),
        race_name=_first_present(obj, _UNVERIFIED_RACE_FIELD_CANDIDATES["race_name"]) or "",
        race_type=_first_present(obj, _UNVERIFIED_RACE_FIELD_CANDIDATES["race_type"]),
        flat_jumps=_FLAT_JUMPS_MAP.get(race_type_raw, "FLAT"),
        surface="TURF",
        distance_furlongs=float(_first_present(obj, _UNVERIFIED_RACE_FIELD_CANDIDATES["distance_furlongs"]) or 0.0),
        race_class=_first_present(obj, _UNVERIFIED_RACE_FIELD_CANDIDATES["race_class"]),
        handicap_type="HANDICAP" if is_handicap else "NON_HANDICAP",
        number_of_runners=int(obj.get("field_size") or len(runners)),
        going=_first_present(obj, _UNVERIFIED_RACE_FIELD_CANDIDATES["going"]),
        race_status="RESULTED",
        runners=runners,
    )


class RacingApiProvider(FixtureBackedProvider, RaceDataProvider):
    name = "racing-api"
    required_credentials_note = (
        "a licensed theracingapi.com subscription — set RACING_API_USERNAME and "
        "RACING_API_PASSWORD environment variables. Neither is configured in this "
        "environment; see racing_api.py's module docstring for exactly what is and "
        "isn't verified about this API's field-level schema."
    )

    def __init__(
        self,
        fixture_path: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        super().__init__(fixture_path=fixture_path)
        self.username = username or os.environ.get("RACING_API_USERNAME")
        self.password = password or os.environ.get("RACING_API_PASSWORD")

    def _has_live_credentials(self) -> bool:
        return bool(self.username and self.password)

    def fetch_races(self, start_date: date, end_date: date) -> Iterator[CanonicalRace]:
        if self._has_live_credentials():
            yield from self._fetch_races_live(start_date, end_date)
            return

        payload = self._load_fixture_json()
        records = payload.get("results", payload.get("racecards", [])) if isinstance(payload, dict) else payload
        for obj in records:
            race = _map_race(obj)
            if start_date <= race.date.date() <= end_date:
                yield race

    def _fetch_races_live(self, start_date: date, end_date: date) -> Iterator[CanonicalRace]:
        client = _RacingApiHttpClient(self.username, self.password)  # type: ignore[arg-type]
        skip = 0
        total = None

        while total is None or skip < total:
            payload = client.get(
                "/results",
                params={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "limit": RESULTS_PAGE_SIZE,
                    "skip": skip,
                },
            )
            total = payload.get("total", 0)
            results = payload.get("results", [])
            if not results:
                break
            for obj in results:
                yield _map_race(obj)
            skip += RESULTS_PAGE_SIZE

"""Provider interfaces.

Five narrow, single-purpose interfaces — one per data domain — rather than a
single monolithic "RacingProvider". A real deployment might implement
several of these against one commercial API, or mix providers (e.g. race
cards from one source, exchange odds from Betfair, sectionals from a
specialist feed). Nothing in this codebase assumes one provider supplies
everything.

No implementation in this module or in any adapter under
`racingedge_data/providers/` performs website scraping or makes an
unauthenticated network call. Adapters either wrap a properly-credentialed
API client (not implemented here — see each adapter's docstring for exactly
what credentials/endpoint a real deployment must supply) or read
user-provided files (CSV/JSON/JSONL) or local fixtures used for testing the
interface.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import Iterator, Optional

from racingedge_data.canonical import (
    CanonicalFormEntry,
    CanonicalOddsPoint,
    CanonicalRace,
    CanonicalSectionalPoint,
    CanonicalWeatherReading,
)


class ProviderConfigurationError(RuntimeError):
    """Raised when a provider adapter is asked to fetch data it has not been
    given real credentials, a real endpoint, or a fixture for. Adapters must
    fail loudly here — never fall back to scraping, and never fabricate
    data to keep a caller happy.
    """


class RaceDataProvider(ABC):
    """Supplies race cards (race + runners + place terms) for a date range."""

    name: str

    @abstractmethod
    def fetch_races(self, start_date: date, end_date: date) -> Iterator[CanonicalRace]:
        """Yields one CanonicalRace per race, inclusive of start_date/end_date."""


class HistoricalResultsProvider(ABC):
    """Supplies historical per-horse form/results, independent of whether
    the underlying race is itself present in RacingEdge's own `Race` table."""

    name: str

    @abstractmethod
    def fetch_form_entries(self, start_date: date, end_date: date) -> Iterator[CanonicalFormEntry]:
        """Yields one CanonicalFormEntry per historical run."""


class OddsDataProvider(ABC):
    """Supplies a stream of timestamped odds observations. Historical odds
    infrastructure is built entirely from a sequence of these — see
    `racingedge_data.odds_snapshots` for how named snapshots (opening, SP,
    ...) are derived from the stream rather than reported directly."""

    name: str

    @abstractmethod
    def fetch_odds(self, start_date: date, end_date: date) -> Iterator[CanonicalOddsPoint]:
        """Yields one CanonicalOddsPoint per price observation."""


class SectionalDataProvider(ABC):
    """OPTIONAL: supplies granular in-running tracking data. Most providers
    do not supply this — nothing else in the schema assumes rows exist."""

    name: str

    @abstractmethod
    def fetch_sectionals(self, start_date: date, end_date: date) -> Iterator[CanonicalSectionalPoint]:
        """Yields one CanonicalSectionalPoint per tracked segment."""


class WeatherDataProvider(ABC):
    """Kept separate from official going — see POINT_IN_TIME_ARCHITECTURE.md."""

    name: str

    @abstractmethod
    def fetch_weather(self, start_date: date, end_date: date) -> Iterator[CanonicalWeatherReading]:
        """Yields one CanonicalWeatherReading per recorded observation."""


class FixtureBackedProvider:
    """Mixin for adapters that have no real API client wired up in this
    build. Operates ONLY against a local fixture file (JSON: either a single
    JSON document or JSON Lines) the caller supplies — this is how the
    interface gets exercised and tested without scraping or fabricating real
    racing data.

    Subclasses MUST set `required_credentials_note` to a short, specific
    description of what a real deployment would need to supply instead
    (env vars, endpoint, auth method) — surfaced verbatim in the error raised
    when no fixture is available, since that error is this project's
    documented mechanism for reporting "exactly what credentials/data files
    are required" per the no-scraping constraint.
    """

    required_credentials_note: str = "this provider's real API credentials and endpoint"

    def __init__(self, fixture_path: Optional[str | Path] = None, api_key: Optional[str] = None):
        self.fixture_path = Path(fixture_path) if fixture_path else None
        self.api_key = api_key

    def _require_fixture(self) -> Path:
        if self.fixture_path is None:
            raise ProviderConfigurationError(
                f"{type(self).__name__} has no fixture_path configured, and no live API "
                "client is implemented in this build (by design — no scraping, no "
                "fabricated data). To use real data, supply "
                f"{self.required_credentials_note}, and implement the live HTTP client "
                "in this class. To exercise/test the adapter's field-mapping logic "
                "without real credentials, pass a fixture_path instead."
            )
        if not self.fixture_path.exists():
            raise ProviderConfigurationError(f"Fixture file not found: {self.fixture_path}")
        return self.fixture_path

    def _load_fixture_json(self) -> dict | list:
        path = self._require_fixture()
        return json.loads(path.read_text(encoding="utf-8"))

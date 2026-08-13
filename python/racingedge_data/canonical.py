"""Canonical, provider-agnostic data shapes.

Every `RaceDataProvider` / `HistoricalResultsProvider` / `OddsDataProvider` /
`SectionalDataProvider` / `WeatherDataProvider` adapter maps its external
provider's fields into these dataclasses. Nothing downstream of this module
(importers, entity resolution, point-in-time reconstruction, feature
engineering) should ever need to know a specific provider's field names or
quirks — that translation lives entirely in `racingedge_data/providers/`.

These are plain, frozen dataclasses on purpose: no database access, no
validation side effects beyond basic shape, no provider-specific logic. They
are SOURCE DATA containers — a canonical race/runner/result/odds record is
exactly what a provider reported, not a derived feature.

String enum-like fields (flat_jumps, surface, sex, ...) intentionally reuse
the exact string values Prisma stores for the corresponding schema enum
(see prisma/schema.prisma), so importers can pass them straight through
without a translation table. They are typed as `str` rather than a Python
Enum to keep provider adapters free to pass through an unrecognized value for
validation to reject explicitly, rather than a KeyError deep in an adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# Matches Prisma's DataSourceType enum. Not attached to canonical records
# themselves — source classification is an explicit decision made by the
# caller of the importer (see racingedge_data.importers), not something a
# provider payload can be trusted to self-report.
DATA_SOURCE_TYPES = ("REAL", "SYNTHETIC", "SAMPLE")


@dataclass(frozen=True)
class CanonicalHorse:
    name: str
    country_bred: Optional[str] = None
    year_of_birth: Optional[int] = None
    sex: Optional[str] = None  # COLT | FILLY | GELDING | MARE | HORSE | RIG
    sire_name: Optional[str] = None
    dam_name: Optional[str] = None
    damsire_name: Optional[str] = None
    trainer_name: Optional[str] = None
    owner_name: Optional[str] = None

    # The provider's own identifier for this horse, if supplied. The
    # strongest signal entity resolution can use — see entity_resolution.py.
    provider_horse_id: Optional[str] = None


@dataclass(frozen=True)
class CanonicalRunner:
    horse: CanonicalHorse

    cloth_number: Optional[int] = None
    draw: Optional[int] = None

    age_at_race: Optional[int] = None
    weight_stone: Optional[int] = None
    weight_pounds: Optional[int] = None
    weight_lbs_total: Optional[int] = None

    official_rating: Optional[int] = None
    racing_post_rating: Optional[int] = None
    timeform_rating: Optional[int] = None
    topspeed_rating: Optional[int] = None

    jockey_name: Optional[str] = None
    jockey_claim_lbs: Optional[int] = None
    trainer_name: Optional[str] = None

    headgear: Optional[str] = None
    first_time_headgear: bool = False

    days_since_last_run: Optional[int] = None
    non_runner: bool = False

    # Provider's own identifier for this runner (horse-in-this-race), used to
    # join odds/result/sectional records back to the right runner within an
    # import batch without relying on name matching.
    provider_runner_id: Optional[str] = None


@dataclass(frozen=True)
class CanonicalPlaceTerms:
    bookmaker_name: str
    places: int
    each_way_fraction: float
    extra_places: bool = False
    terms: Optional[str] = None
    # When these terms became true. Required (not optional) because place
    # terms are exactly the kind of field the project requires point-in-time
    # correctness for — see POINT_IN_TIME_ARCHITECTURE.md.
    effective_at: Optional[datetime] = None


@dataclass(frozen=True)
class CanonicalRace:
    date: datetime
    race_time: str  # "14:35" local off-time
    racecourse: str
    country: str

    race_name: str
    flat_jumps: str  # FLAT | JUMPS
    surface: str  # TURF | ALL_WEATHER | DIRT
    distance_furlongs: float
    handicap_type: str  # HANDICAP | NON_HANDICAP
    number_of_runners: int

    race_type: Optional[str] = None
    distance_yards: Optional[int] = None
    race_class: Optional[int] = None
    grade_group: Optional[str] = None
    age_restriction: Optional[str] = None
    sex_restriction: Optional[str] = None

    going: Optional[str] = None
    going_description: Optional[str] = None
    rail_position: Optional[str] = None
    stalls_position: Optional[str] = None

    weather_summary: Optional[str] = None
    temperature_celsius: Optional[float] = None
    wind_summary: Optional[str] = None
    precipitation_mm: Optional[float] = None

    prize_money_total: Optional[float] = None
    currency: str = "GBP"

    each_way_fraction: Optional[float] = None
    bookmaker_places: Optional[int] = None
    extra_place_flag: bool = False

    race_status: str = "SCHEDULED"
    result_status: str = "PENDING"

    runners: tuple[CanonicalRunner, ...] = field(default_factory=tuple)
    place_terms: tuple[CanonicalPlaceTerms, ...] = field(default_factory=tuple)

    # Provider's own identifier for this race. Strongly recommended — used
    # both for idempotent re-import and as the join key odds/result/sectional
    # records reference.
    provider_race_id: Optional[str] = None


@dataclass(frozen=True)
class CanonicalOddsPoint:
    """One timestamped price observation for one runner from one bookmaker.

    Historical odds infrastructure is built entirely from a stream of these
    — never a single "current price" field. Named snapshots (opening, 24h,
    6h, ..., SP/BSP) are DERIVED views over a sequence of these points, not
    separately-reported values (see racingedge_data/odds_snapshots.py).
    """

    provider_runner_id: str
    bookmaker_name: str
    is_exchange: bool
    timestamp: datetime
    win_odds_decimal: float

    each_way_fraction: Optional[float] = None
    number_of_places: Optional[int] = None
    extra_places: bool = False

    back_odds_decimal: Optional[float] = None
    lay_odds_decimal: Optional[float] = None
    available_volume: Optional[float] = None
    market_status: Optional[str] = None

    is_opening_price: bool = False
    is_starting_price: bool = False
    is_closing_price: bool = False


@dataclass(frozen=True)
class CanonicalResult:
    provider_runner_id: str

    finishing_position: Optional[int] = None
    finish_status: Optional[str] = None  # "WON","PLACED","RAN","PU","UR","F","BD","DSQ", etc.
    beaten_distance_lengths: Optional[float] = None
    dead_heat: bool = False

    starting_price_decimal: Optional[float] = None
    closing_odds_decimal: Optional[float] = None
    bsp_decimal: Optional[float] = None

    result_status: str = "PENDING"  # PENDING | PROVISIONAL | CONFIRMED | VOID


@dataclass(frozen=True)
class CanonicalFormEntry:
    """A single historical run for a horse, sourced independently of
    whether the underlying race is itself present in RacingEdge's own
    `Race` table (`linked_race_provider_id` is best-effort)."""

    horse: CanonicalHorse
    race_date: datetime
    course: str

    country: Optional[str] = None
    distance_furlongs: Optional[float] = None
    going: Optional[str] = None
    race_class: Optional[int] = None
    flat_jumps: Optional[str] = None
    field_size: Optional[int] = None

    finishing_position: Optional[int] = None
    finish_status: Optional[str] = None
    beaten_distance_lengths: Optional[float] = None
    starting_price_decimal: Optional[float] = None
    official_rating: Optional[int] = None
    weight_pounds: Optional[int] = None
    draw: Optional[int] = None

    jockey_name: Optional[str] = None
    headgear: Optional[str] = None

    race_comment: Optional[str] = None
    in_running_comment: Optional[str] = None

    early_position: Optional[int] = None
    halfway_position: Optional[int] = None
    position_3f_out: Optional[int] = None
    position_2f_out: Optional[int] = None
    position_1f_out: Optional[int] = None

    sectional_times: Optional[str] = None  # JSON-encoded array of furlong splits
    finishing_speed_percentage: Optional[float] = None
    pace_classification: Optional[str] = None
    race_strength_index: Optional[float] = None

    linked_race_provider_id: Optional[str] = None

    @property
    def has_positional_data(self) -> bool:
        return any(
            value is not None
            for value in (
                self.early_position,
                self.halfway_position,
                self.position_3f_out,
                self.position_2f_out,
                self.position_1f_out,
            )
        )

    @property
    def has_sectional_data(self) -> bool:
        return self.sectional_times is not None


@dataclass(frozen=True)
class CanonicalSectionalPoint:
    """Optional granular in-running tracking data for one runner. Providers
    supplying this are rare — nothing else in the schema assumes it exists.
    """

    provider_runner_id: str
    segment_index: int

    segment_distance_furlongs: Optional[float] = None
    segment_time_seconds: Optional[float] = None
    speed_mps: Optional[float] = None
    position_in_race: Optional[int] = None
    stride_length: Optional[float] = None
    stride_frequency: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@dataclass(frozen=True)
class CanonicalWeatherReading:
    """Kept separate from the official going — see POINT_IN_TIME_ARCHITECTURE.md
    for why weather and going must never be conflated."""

    provider_race_id: str
    recorded_at: datetime

    temperature_celsius: Optional[float] = None
    rainfall_mm: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_direction: Optional[str] = None

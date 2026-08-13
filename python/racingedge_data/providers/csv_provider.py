"""CSV race-card provider — the primary supported way to bring a purchased
or user-supplied historical dataset into RacingEdge.

Expected format: a "wide" CSV, one row per runner, with race-level fields
repeated on every row for that race (a standard export shape for racing
data). Rows for the same race MUST be contiguous (the file is assumed
pre-sorted by race) — this provider does a single streaming pass and never
buffers the whole file, which is what makes it safe to point at a
100,000+ row file (see `racingedge_data.importers.streaming_csv` for the
chunked-read layer that sits above this).

Column names match the `Canonical*` dataclass field names in
`racingedge_data.canonical` (snake_case). Unknown columns are ignored;
missing/blank values become `None`. See `RACE_FIELDS` / `RUNNER_FIELDS`
below for the exact recognized column names.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import IO, Any, Iterator, Optional

from racingedge_data.canonical import CanonicalHorse, CanonicalRace, CanonicalRunner
from racingedge_data.providers.base import RaceDataProvider

# Columns read off the FIRST row of each race group (repeated per-runner in
# the file, but only needs to be correct once per race).
RACE_FIELDS = [
    "provider_race_id",
    "date",
    "race_time",
    "racecourse",
    "country",
    "race_name",
    "race_type",
    "flat_jumps",
    "surface",
    "distance_furlongs",
    "distance_yards",
    "race_class",
    "grade_group",
    "handicap_type",
    "age_restriction",
    "sex_restriction",
    "number_of_runners",
    "going",
    "going_description",
    "rail_position",
    "stalls_position",
    "weather_summary",
    "temperature_celsius",
    "wind_summary",
    "precipitation_mm",
    "prize_money_total",
    "currency",
    "each_way_fraction",
    "bookmaker_places",
    "extra_place_flag",
    "race_status",
    "result_status",
]

# Columns read off EVERY row (one runner per row).
RUNNER_FIELDS = [
    "runner_provider_id",
    "horse_name",
    "horse_provider_id",
    "country_bred",
    "year_of_birth",
    "sex",
    "sire_name",
    "dam_name",
    "damsire_name",
    "trainer_name",
    "owner_name",
    "cloth_number",
    "draw",
    "age_at_race",
    "weight_stone",
    "weight_pounds",
    "weight_lbs_total",
    "official_rating",
    "racing_post_rating",
    "timeform_rating",
    "topspeed_rating",
    "jockey_name",
    "jockey_claim_lbs",
    "headgear",
    "first_time_headgear",
    "days_since_last_run",
    "non_runner",
]

_INT_FIELDS = {
    "distance_yards",
    "race_class",
    "number_of_runners",
    "bookmaker_places",
    "year_of_birth",
    "cloth_number",
    "draw",
    "age_at_race",
    "weight_stone",
    "weight_pounds",
    "weight_lbs_total",
    "official_rating",
    "racing_post_rating",
    "timeform_rating",
    "topspeed_rating",
    "jockey_claim_lbs",
    "days_since_last_run",
}
_FLOAT_FIELDS = {
    "distance_furlongs",
    "temperature_celsius",
    "precipitation_mm",
    "prize_money_total",
    "each_way_fraction",
}
_BOOL_FIELDS = {"extra_place_flag", "first_time_headgear", "non_runner"}


def _blank_to_none(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return value


def _coerce(field_name: str, raw: Any) -> Any:
    value = _blank_to_none(raw)
    if value is None:
        return None
    if field_name in _INT_FIELDS:
        return int(float(value))
    if field_name in _FLOAT_FIELDS:
        return float(value)
    if field_name in _BOOL_FIELDS:
        return str(value).strip().lower() in {"1", "true", "yes", "y"}
    return value


def parse_race_date(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Unparseable race date: {value!r} (expected ISO 8601)") from exc


def _extract(row: dict[str, str], fields: list[str]) -> dict[str, Any]:
    return {name: _coerce(name, row.get(name)) for name in fields if name in row}


def _build_runner(row: dict[str, str]) -> CanonicalRunner:
    fields = _extract(row, RUNNER_FIELDS)
    horse = CanonicalHorse(
        name=fields.get("horse_name") or "",
        provider_horse_id=fields.get("horse_provider_id"),
        country_bred=fields.get("country_bred"),
        year_of_birth=fields.get("year_of_birth"),
        sex=fields.get("sex"),
        sire_name=fields.get("sire_name"),
        dam_name=fields.get("dam_name"),
        damsire_name=fields.get("damsire_name"),
        trainer_name=fields.get("trainer_name"),
        owner_name=fields.get("owner_name"),
    )
    return CanonicalRunner(
        horse=horse,
        provider_runner_id=fields.get("runner_provider_id"),
        cloth_number=fields.get("cloth_number"),
        draw=fields.get("draw"),
        age_at_race=fields.get("age_at_race"),
        weight_stone=fields.get("weight_stone"),
        weight_pounds=fields.get("weight_pounds"),
        weight_lbs_total=fields.get("weight_lbs_total"),
        official_rating=fields.get("official_rating"),
        racing_post_rating=fields.get("racing_post_rating"),
        timeform_rating=fields.get("timeform_rating"),
        topspeed_rating=fields.get("topspeed_rating"),
        jockey_name=fields.get("jockey_name"),
        jockey_claim_lbs=fields.get("jockey_claim_lbs"),
        trainer_name=fields.get("trainer_name"),
        headgear=fields.get("headgear"),
        first_time_headgear=bool(fields.get("first_time_headgear") or False),
        days_since_last_run=fields.get("days_since_last_run"),
        non_runner=bool(fields.get("non_runner") or False),
    )


def _build_race(row: dict[str, str], runners: list[CanonicalRunner]) -> CanonicalRace:
    fields = _extract(row, RACE_FIELDS)
    if not fields.get("date"):
        raise ValueError("CSV row is missing required 'date' column")
    return CanonicalRace(
        provider_race_id=fields.get("provider_race_id"),
        date=parse_race_date(fields["date"]),
        race_time=fields.get("race_time") or "",
        racecourse=fields.get("racecourse") or "",
        country=fields.get("country") or "",
        race_name=fields.get("race_name") or "",
        race_type=fields.get("race_type"),
        flat_jumps=fields.get("flat_jumps") or "FLAT",
        surface=fields.get("surface") or "TURF",
        distance_furlongs=float(fields.get("distance_furlongs") or 0.0),
        distance_yards=fields.get("distance_yards"),
        race_class=fields.get("race_class"),
        grade_group=fields.get("grade_group"),
        handicap_type=fields.get("handicap_type") or "NON_HANDICAP",
        age_restriction=fields.get("age_restriction"),
        sex_restriction=fields.get("sex_restriction"),
        number_of_runners=int(fields.get("number_of_runners") or len(runners)),
        going=fields.get("going"),
        going_description=fields.get("going_description"),
        rail_position=fields.get("rail_position"),
        stalls_position=fields.get("stalls_position"),
        weather_summary=fields.get("weather_summary"),
        temperature_celsius=fields.get("temperature_celsius"),
        wind_summary=fields.get("wind_summary"),
        precipitation_mm=fields.get("precipitation_mm"),
        prize_money_total=fields.get("prize_money_total"),
        currency=fields.get("currency") or "GBP",
        each_way_fraction=fields.get("each_way_fraction"),
        bookmaker_places=fields.get("bookmaker_places"),
        extra_place_flag=bool(fields.get("extra_place_flag") or False),
        race_status=fields.get("race_status") or "RESULTED",
        result_status=fields.get("result_status") or "PENDING",
        runners=tuple(runners),
    )


class CsvRaceDataProvider(RaceDataProvider):
    """Streams `CanonicalRace` objects from a wide-format, race-card CSV
    file (or any file-like object opened in text mode)."""

    name = "csv"

    def __init__(self, path_or_file: str | Path | IO[str]):
        self._path_or_file = path_or_file

    def fetch_races(self, start_date: date, end_date: date) -> Iterator[CanonicalRace]:
        handle, owns_handle = self._open()
        try:
            reader = csv.DictReader(handle)
            current_key: Optional[tuple] = None
            current_race_row: Optional[dict[str, str]] = None
            current_runners: list[CanonicalRunner] = []

            for row in reader:
                raw_date = row.get("date")
                if not raw_date:
                    continue
                race_date = parse_race_date(raw_date).date()

                key = (
                    row.get("provider_race_id")
                    or (row.get("date"), row.get("race_time"), row.get("racecourse"))
                )
                if key != current_key:
                    if current_race_row is not None:
                        race_date_prev = parse_race_date(current_race_row["date"]).date()
                        if start_date <= race_date_prev <= end_date:
                            yield _build_race(current_race_row, current_runners)
                    current_key = key
                    current_race_row = row
                    current_runners = []

                if start_date <= race_date <= end_date:
                    current_runners.append(_build_runner(row))

            if current_race_row is not None:
                race_date_prev = parse_race_date(current_race_row["date"]).date()
                if start_date <= race_date_prev <= end_date:
                    yield _build_race(current_race_row, current_runners)
        finally:
            if owns_handle:
                handle.close()

    def _open(self) -> tuple[IO[str], bool]:
        if hasattr(self._path_or_file, "read"):
            return self._path_or_file, False  # type: ignore[return-value]
        return open(self._path_or_file, newline="", encoding="utf-8"), True

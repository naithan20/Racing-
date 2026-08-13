"""Generic JSON / JSON Lines race-card provider.

Expected format: either a single JSON document containing a top-level array
of race objects, or a JSON Lines file (one race object per line) — the
latter is preferred for large files since it can be streamed without
loading the whole file into memory. Each race object's keys match the
`CanonicalRace` field names (snake_case) with a nested `"runners"` array
whose objects' keys match `CanonicalRunner` (and nested `"horse"`) field
names. Unknown keys are ignored; this keeps the adapter forward-compatible
with providers that include extra fields RacingEdge doesn't use yet.

This is the adapter to reach for when a provider's native export is JSON
and doesn't cleanly flatten into the CSV provider's wide-row format (e.g.
nested odds ladders or sectional arrays per runner).
"""

from __future__ import annotations

import json
from dataclasses import fields as dataclass_fields
from datetime import date
from itertools import chain as itertools_chain
from pathlib import Path
from typing import IO, Any, Iterator

from racingedge_data.canonical import CanonicalHorse, CanonicalRace, CanonicalRunner
from racingedge_data.providers.base import RaceDataProvider
from racingedge_data.providers.csv_provider import parse_race_date

_RACE_FIELD_NAMES = {f.name for f in dataclass_fields(CanonicalRace)} - {"runners", "place_terms"}
_RUNNER_FIELD_NAMES = {f.name for f in dataclass_fields(CanonicalRunner)} - {"horse"}
_HORSE_FIELD_NAMES = {f.name for f in dataclass_fields(CanonicalHorse)}


def _filter_known(obj: dict[str, Any], known: set[str]) -> dict[str, Any]:
    return {k: v for k, v in obj.items() if k in known and v is not None}


def _build_runner(obj: dict[str, Any]) -> CanonicalRunner:
    horse_obj = obj.get("horse") or {"name": obj.get("horse_name", "")}
    horse = CanonicalHorse(**{"name": horse_obj.get("name", ""), **_filter_known(horse_obj, _HORSE_FIELD_NAMES - {"name"})})
    runner_kwargs = _filter_known(obj, _RUNNER_FIELD_NAMES)
    return CanonicalRunner(horse=horse, **runner_kwargs)


def _build_race(obj: dict[str, Any]) -> CanonicalRace:
    if "date" not in obj:
        raise ValueError("JSON race object is missing required 'date' field")
    race_kwargs = _filter_known(obj, _RACE_FIELD_NAMES)
    race_kwargs["date"] = parse_race_date(str(obj["date"]))
    runners = tuple(_build_runner(r) for r in obj.get("runners", []))
    return CanonicalRace(runners=runners, **race_kwargs)


class GenericJsonRaceDataProvider(RaceDataProvider):
    """Streams `CanonicalRace` objects from a JSON array or JSON Lines file
    (or file-like object) of race objects."""

    name = "generic-json"

    def __init__(self, path_or_file: str | Path | IO[str], jsonl: bool | None = None):
        self._path_or_file = path_or_file
        self._jsonl = jsonl

    def fetch_races(self, start_date: date, end_date: date) -> Iterator[CanonicalRace]:
        handle, owns_handle = self._open()
        try:
            first_line = handle.readline()
            jsonl = self._jsonl
            if jsonl is None:
                jsonl = self._detect_jsonl(first_line)

            if jsonl:
                remaining_lines = itertools_chain([first_line], handle)
                for line in remaining_lines:
                    line = line.strip()
                    if not line:
                        continue
                    race = _build_race(json.loads(line))
                    if start_date <= race.date.date() <= end_date:
                        yield race
            else:
                payload = json.loads(first_line + handle.read())
                records = payload if isinstance(payload, list) else payload.get("races", [])
                for obj in records:
                    race = _build_race(obj)
                    if start_date <= race.date.date() <= end_date:
                        yield race
        finally:
            if owns_handle:
                handle.close()

    @staticmethod
    def _detect_jsonl(first_line: str) -> bool:
        """A JSON Lines file has one complete, self-contained JSON object
        per line — so if the first line parses on its own, it's JSONL. A
        single JSON document (array or object) spanning many lines won't
        parse from its first line alone (unless the whole thing is on one
        line, in which case treating it as "JSONL with one line" still
        produces the correct single race)."""

        stripped = first_line.strip()
        if not stripped or stripped.startswith("["):
            return False
        try:
            json.loads(stripped)
            return True
        except json.JSONDecodeError:
            return False

    def _open(self) -> tuple[IO[str], bool]:
        if hasattr(self._path_or_file, "read"):
            return self._path_or_file, False  # type: ignore[return-value]
        return open(self._path_or_file, "r", encoding="utf-8"), True

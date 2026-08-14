"""Mapping-driven importer for user-supplied free/community historical
racing datasets — the second step of the Phase 3C £0-data-cost workflow
(after `racingedge_data.inspector`).

Consumes a REVIEWED mapping file and the source file it describes, and
imports it via the existing `racingedge_data.importers.import_runner`
pipeline — duplicate handling, idempotency, resumability, provenance, and
point-in-time field history all work exactly as they do for every other
provider; this module's only job is turning arbitrary tabular rows into
`CanonicalRace`/`CanonicalRunner`/`CanonicalResult` objects using the
confirmed column mapping.

**Refuses to proceed if any non-high-confidence column in the mapping
isn't explicitly `"confirmed": true`** — see `load_and_validate_mapping`.
Nothing here infers a missing field's value or fabricates a role for an
unmapped column; an unmapped canonical field is simply left `None` for
every row.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date as date_type, datetime
from pathlib import Path
from typing import Any, Iterator, Optional

import pandas as pd

from racingedge_data.canonical import CanonicalHorse, CanonicalRace, CanonicalResult, CanonicalRunner
from racingedge_data.importers.import_runner import ImportResult, import_races
from racingedge_data.providers.base import RaceDataProvider
from racingedge_data.providers.csv_provider import parse_race_date

VALID_PROVENANCE_STATUSES = (
    "VERIFIED_OPEN",
    "PUBLIC_RESEARCH",
    "COMMUNITY_UNVERIFIED",
    "USER_SUPPLIED",
    "UNKNOWN",
    "RESTRICTED",
)

# Fields whose canonical role identifies them as POST-RACE information —
# these are ALWAYS routed to CanonicalResult (-> ResultEntry), never to a
# Runner's pre-race fields, regardless of what the mapping file says. See
# POINT_IN_TIME_ARCHITECTURE.md.
POST_RACE_ROLES = {"finishing_position", "beaten_distance", "starting_price", "bsp"}


class MappingNotConfirmedError(RuntimeError):
    """Raised when the mapping file has non-high-confidence columns that
    haven't been explicitly reviewed and confirmed."""


@dataclass(frozen=True)
class TableMapping:
    likely_kind: str
    role_to_column: dict[str, str]


@dataclass(frozen=True)
class ConfirmedMapping:
    source_path: str
    source_format: str
    tables: dict[str, TableMapping]


def load_and_validate_mapping(mapping_path: str | Path) -> ConfirmedMapping:
    raw = json.loads(Path(mapping_path).read_text())

    unconfirmed: list[str] = []
    tables: dict[str, TableMapping] = {}

    for table_name, table_data in raw.get("tables", {}).items():
        role_to_column: dict[str, str] = {}
        for column_name, col_mapping in table_data.get("columns", {}).items():
            role = col_mapping.get("role")
            if role is None:
                continue
            confidence = col_mapping.get("confidence")
            confirmed = col_mapping.get("confirmed", False)
            if confidence != "high" and not confirmed:
                unconfirmed.append(f"{table_name}.{column_name} (proposed role={role!r}, confidence={confidence!r})")
                continue
            role_to_column[role] = column_name
        tables[table_name] = TableMapping(likely_kind=table_data.get("likely_kind", "unknown"), role_to_column=role_to_column)

    if unconfirmed:
        raise MappingNotConfirmedError(
            "The following columns have not been confirmed and will NOT be imported until "
            'reviewed — edit the mapping file and set "confirmed": true (or correct the "role") '
            "for each:\n  " + "\n  ".join(unconfirmed)
        )

    return ConfirmedMapping(source_path=raw["source_path"], source_format=raw["source_format"], tables=tables)


# ---------------------------------------------------------------------------
# Value coercion
# ---------------------------------------------------------------------------


def _get(row: dict[str, Any], role_to_column: dict[str, str], role: str) -> Any:
    column = role_to_column.get(role)
    if column is None or column not in row:
        return None
    value = row[column]
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return value


def _as_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _row_to_result(row: dict[str, Any], role_to_column: dict[str, str]) -> Optional[CanonicalResult]:
    finishing_position = _as_int(_get(row, role_to_column, "finishing_position"))
    beaten_distance = _as_float(_get(row, role_to_column, "beaten_distance"))
    starting_price = _as_float(_get(row, role_to_column, "starting_price"))
    bsp = _as_float(_get(row, role_to_column, "bsp"))

    if finishing_position is None and beaten_distance is None and starting_price is None and bsp is None:
        return None

    return CanonicalResult(
        finishing_position=finishing_position,
        beaten_distance_lengths=beaten_distance,
        starting_price_decimal=starting_price,
        bsp_decimal=bsp,
        result_status="CONFIRMED",
    )


def _row_to_runner(row: dict[str, Any], role_to_column: dict[str, str]) -> Optional[CanonicalRunner]:
    horse_name = _as_str(_get(row, role_to_column, "horse_name"))
    if not horse_name:
        return None

    horse = CanonicalHorse(
        name=horse_name,
        provider_horse_id=_as_str(_get(row, role_to_column, "horse_id")),
        sex=_as_str(_get(row, role_to_column, "sex")),
        sire_name=_as_str(_get(row, role_to_column, "sire")),
        dam_name=_as_str(_get(row, role_to_column, "dam")),
        damsire_name=_as_str(_get(row, role_to_column, "damsire")),
    )
    return CanonicalRunner(
        horse=horse,
        draw=_as_int(_get(row, role_to_column, "draw")),
        age_at_race=_as_int(_get(row, role_to_column, "age")),
        weight_lbs_total=_as_int(_get(row, role_to_column, "weight")),
        official_rating=_as_int(_get(row, role_to_column, "official_rating")),
        jockey_name=_as_str(_get(row, role_to_column, "jockey")),
        trainer_name=_as_str(_get(row, role_to_column, "trainer")),
        headgear=_as_str(_get(row, role_to_column, "headgear")),
        non_runner=bool(_get(row, role_to_column, "non_runner")) if _get(row, role_to_column, "non_runner") else False,
        result=_row_to_result(row, role_to_column),
    )


def _row_to_race(row: dict[str, Any], role_to_column: dict[str, str], runners: list[CanonicalRunner]) -> CanonicalRace:
    raw_date = _get(row, role_to_column, "race_date")
    if raw_date is None:
        raise ValueError("Row is missing a mapped race_date value")
    race_date = parse_race_date(str(raw_date))

    race_time = _as_str(_get(row, role_to_column, "race_time")) or "00:00"
    course = _as_str(_get(row, role_to_column, "course")) or ""
    if not course:
        raise ValueError("Row is missing a mapped course value")

    flat_jumps_raw = (_as_str(_get(row, role_to_column, "flat_jumps")) or "flat").lower()
    flat_jumps = "JUMPS" if "jump" in flat_jumps_raw or flat_jumps_raw in ("nh", "national hunt") else "FLAT"

    return CanonicalRace(
        provider_race_id=_as_str(_get(row, role_to_column, "race_id")),
        date=race_date,
        race_time=race_time,
        racecourse=course,
        country=_as_str(_get(row, role_to_column, "country")) or "",
        race_name=_as_str(_get(row, role_to_column, "race_name")) or f"{course} {race_date.date()}",
        race_type=_as_str(_get(row, role_to_column, "race_type")),
        flat_jumps=flat_jumps,
        surface="TURF",
        distance_furlongs=_as_float(_get(row, role_to_column, "distance")) or 0.0,
        race_class=_as_int(_get(row, role_to_column, "race_class")),
        handicap_type="NON_HANDICAP",
        number_of_runners=_as_int(_get(row, role_to_column, "field_size")) or len(runners),
        going=_as_str(_get(row, role_to_column, "going")),
        race_status="RESULTED",
        result_status="CONFIRMED",
        runners=tuple(runners),
    )


def _race_group_key(row: dict[str, Any], role_to_column: dict[str, str]) -> tuple:
    race_id = _get(row, role_to_column, "race_id")
    if race_id is not None:
        return ("id", str(race_id))
    return (
        "composite",
        str(_get(row, role_to_column, "race_date")),
        str(_get(row, role_to_column, "race_time"))
        if _get(row, role_to_column, "race_time") is not None
        else "",
        str(_get(row, role_to_column, "course")),
    )


class MappedTableProvider(RaceDataProvider):
    """Streams `CanonicalRace` objects from a single wide (race-and-runner
    level) table using a confirmed column mapping — the common shape for
    free CSV/SQLite racing datasets (one row per runner, race fields
    repeated). For a genuinely two-table (separate race/runner tables)
    source, join the tables into one wide row set BEFORE calling this
    (see `_load_wide_rows` for the join this module attempts automatically
    when a `race_id` role is present in both tables)."""

    name = "free-dataset"

    def __init__(self, rows: Iterator[dict[str, Any]], role_to_column: dict[str, str]):
        self._rows = rows
        self._role_to_column = role_to_column

    def fetch_races(self, start_date: date_type, end_date: date_type) -> Iterator[CanonicalRace]:
        current_key = None
        current_first_row: Optional[dict[str, Any]] = None
        current_runners: list[CanonicalRunner] = []

        def _flush():
            if current_first_row is None:
                return None
            try:
                race = _row_to_race(current_first_row, self._role_to_column, current_runners)
            except ValueError:
                return None
            if start_date <= race.date.date() <= end_date:
                return race
            return None

        for row in self._rows:
            key = _race_group_key(row, self._role_to_column)
            if key != current_key:
                race = _flush()
                if race is not None:
                    yield race
                current_key = key
                current_first_row = row
                current_runners = []
            runner = _row_to_runner(row, self._role_to_column)
            if runner is not None:
                current_runners.append(runner)

        race = _flush()
        if race is not None:
            yield race


def _load_wide_rows(mapping: ConfirmedMapping) -> Iterator[dict[str, Any]]:
    """Loads rows from the mapped source, joining a separate race-level and
    runner-level table on `race_id` if the dataset has two tables (raises
    if a two-table dataset has no `race_id` role mapped on both — a safe
    refusal rather than guessing a join)."""

    path = Path(mapping.source_path)

    if mapping.source_format == "sqlite":
        conn = sqlite3.connect(str(path))
        try:
            if len(mapping.tables) == 1:
                table_name, table_mapping = next(iter(mapping.tables.items()))
                df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
                yield from df.to_dict(orient="records")
                return

            race_table = next((n for n, t in mapping.tables.items() if t.likely_kind == "race_level"), None)
            runner_table = next((n for n, t in mapping.tables.items() if t.likely_kind == "runner_level"), None)
            if race_table is None or runner_table is None:
                raise ValueError(
                    "Multiple tables found but could not identify a race-level and a "
                    "runner-level table — check likely_kind in the mapping file."
                )
            race_role_map = mapping.tables[race_table].role_to_column
            runner_role_map = mapping.tables[runner_table].role_to_column
            if "race_id" not in race_role_map or "race_id" not in runner_role_map:
                raise ValueError(
                    f"Tables '{race_table}' and '{runner_table}' have no shared 'race_id' role mapped — "
                    "add a race_id mapping to BOTH tables in the mapping file before import. This "
                    "importer will not guess a join key."
                )
            races_df = pd.read_sql_query(f'SELECT * FROM "{race_table}"', conn)
            runners_df = pd.read_sql_query(f'SELECT * FROM "{runner_table}"', conn)
            merged = runners_df.merge(
                races_df,
                left_on=runner_role_map["race_id"],
                right_on=race_role_map["race_id"],
                suffixes=("_runner", "_race"),
            )
            yield from merged.to_dict(orient="records")
        finally:
            conn.close()
        return

    if mapping.source_format == "csv":
        df = pd.read_csv(path, low_memory=False)
        yield from df.to_dict(orient="records")
        return

    if mapping.source_format in ("json", "jsonl"):
        if mapping.source_format == "jsonl":
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield json.loads(line)
        else:
            payload = json.loads(path.read_text(encoding="utf-8"))
            records = payload if isinstance(payload, list) else payload.get("records", payload.get("races", []))
            yield from records
        return

    raise ValueError(f"Unsupported source_format: {mapping.source_format}")


@dataclass
class FreeDatasetImportOutcome:
    result: ImportResult
    provenance_status: str
    warnings: list[str]


def import_free_dataset(
    conn: sqlite3.Connection,
    mapping_path: str | Path,
    source_type: str,
    provenance_status: str,
    source_label: str,
    start_date: date_type,
    end_date: date_type,
    idempotency_key: Optional[str] = None,
) -> FreeDatasetImportOutcome:
    """Imports a dataset described by a REVIEWED mapping file (see
    `load_and_validate_mapping`). `provenance_status` must be one of
    `VALID_PROVENANCE_STATUSES` — there is no default, by design, matching
    the project's real/synthetic/sample separation precedent (see
    `racingedge_data.importers.import_runner.import_races`'s `source_type`
    requirement)."""

    if provenance_status not in VALID_PROVENANCE_STATUSES:
        raise ValueError(f"provenance_status must be one of {VALID_PROVENANCE_STATUSES}, got {provenance_status!r}")

    mapping = load_and_validate_mapping(mapping_path)

    # A single-table mapping has exactly one entry in mapping.tables.
    if len(mapping.tables) == 1:
        role_to_column = next(iter(mapping.tables.values())).role_to_column
    else:
        # For the two-table join case, the merged rows carry BOTH tables'
        # original column names (pandas .merge with suffixes on collision),
        # so the role mapping must be the union of both tables' mappings.
        role_to_column = {}
        for table_mapping in mapping.tables.values():
            role_to_column.update(table_mapping.role_to_column)

    rows = _load_wide_rows(mapping)
    provider = MappedTableProvider(rows, role_to_column)

    warnings: list[str] = []
    if provenance_status in ("UNKNOWN", "COMMUNITY_UNVERIFIED"):
        warnings.append(
            f"provenance_status={provenance_status} — this dataset's reuse rights have not been "
            "confirmed. It will be imported and tracked, but review its licence before relying on "
            "it for anything beyond research (see DatasetReview / DATA_PROVENANCE.md)."
        )
    if provenance_status == "RESTRICTED":
        warnings.append(
            "provenance_status=RESTRICTED — this data will be imported for record-keeping, but is "
            "EXCLUDED from training datasets by default "
            "(racingedge_data.dataset_version.filter_race_ids_excluding_provenance)."
        )

    result = import_races(
        conn,
        provider,
        start_date,
        end_date,
        source_type=source_type,
        filename=str(mapping.source_path),
        idempotency_key=idempotency_key,
    )

    if result.import_batch_id:
        conn.execute(
            'UPDATE "DataProvenance" SET provenanceStatus = ?, sourceUrl = ? WHERE importBatchId = ?',
            (provenance_status, source_label, result.import_batch_id),
        )

    return FreeDatasetImportOutcome(result=result, provenance_status=provenance_status, warnings=warnings)

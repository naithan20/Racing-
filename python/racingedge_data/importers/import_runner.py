"""Streaming import orchestration.

`import_races` drives a `RaceDataProvider` one race at a time — since every
provider's `fetch_races` is a generator, a multi-million-row source file is
never materialized in memory here, only the current race's runners.

Everything the project requires of a large-scale importer lives in this one
function:
- **Progress**: `ImportBatch.processedRows` is updated after every race, so
  a caller (or the Data Quality Dashboard) polling the row mid-run sees live
  progress. `on_progress(processed, errors)` is called for the same reason.
- **Validation / failed-row reporting**: a race that fails to import is
  caught, its DB writes are rolled back, and it's logged to
  `ImportBatch.errorLog` (a JSON array of `{index, provider_race_id,
  message}`) — the batch continues rather than aborting.
- **Duplicate handling**: a race already recorded in `DataProvenance` for
  this `(provider, RACE_CARD, providerRecordId)` triple is skipped and
  counted, never re-inserted. Races without a `provider_race_id` fall back
  to a content hash of (date, time, course, name) as their dedup key.
- **Idempotency**: pass the same `idempotency_key` on a re-run and, if a
  prior run with that key already reached SUCCESS, the whole run short-
  circuits and returns that batch's summary unchanged.
- **Resume/retry**: pass `resume_from_batch_id` (an earlier, interrupted
  batch's id) to pick up from `ImportBatch.resumeCursor` instead of
  re-processing races already written.

Every explicit call site MUST pass `source_type` — there is no default, by
design (see the project's real/synthetic/sample separation requirement).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date as date_type, datetime, timezone
from typing import Callable, Optional

from racingedge_data.canonical import CanonicalRace
from racingedge_data.entity_resolution import resolve_horse
from racingedge_data.provenance import (
    ProvenanceRecord,
    hash_payload,
    record_place_terms_change,
    record_provenance,
    record_race_field_change,
    record_runner_field_change,
)
from racingedge_data.providers.base import RaceDataProvider
from racingedge_model.db import to_prisma_datetime
from racingedge_model.ids import new_id

# Mutable fields point-in-time reconstruction cares about — see
# racingedge_data.point_in_time. An initial history row is logged for each
# at import time so "what was known as of T" queries have something to find
# even for a horse's/race's very first recorded state.
_RACE_HISTORY_FIELDS = (
    "going",
    "goingDescription",
    "railPosition",
    "stallsPosition",
    "weatherSummary",
    "raceStatus",
    "resultStatus",
)
_RUNNER_HISTORY_FIELDS = (
    "draw",
    "jockeyName",
    "trainerName",
    "weightLbsTotal",
    "nonRunner",
    "headgear",
    "officialRating",
)

VALID_SOURCE_TYPES = ("REAL", "SYNTHETIC", "SAMPLE")


@dataclass
class RowError:
    index: int
    provider_race_id: Optional[str]
    message: str


@dataclass
class ImportResult:
    import_batch_id: str
    status: str  # SUCCESS | PARTIAL | FAILED
    total_rows: int
    processed_rows: int
    success_count: int
    duplicate_rows: int
    error_count: int
    errors: list[RowError] = field(default_factory=list)


def _now() -> str:
    return to_prisma_datetime(datetime.now(timezone.utc))


def _dt(value: datetime) -> str:
    return to_prisma_datetime(value)


def import_races(
    conn: sqlite3.Connection,
    provider: RaceDataProvider,
    start_date: date_type,
    end_date: date_type,
    source_type: str,
    filename: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    resume_from_batch_id: Optional[str] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> ImportResult:
    if source_type not in VALID_SOURCE_TYPES:
        raise ValueError(f"source_type must be one of {VALID_SOURCE_TYPES}, got {source_type!r}")

    if idempotency_key:
        existing = conn.execute(
            'SELECT * FROM "ImportBatch" WHERE idempotencyKey = ?', (idempotency_key,)
        ).fetchone()
        if existing is not None and existing["status"] == "SUCCESS":
            return ImportResult(
                import_batch_id=existing["id"],
                status="SUCCESS",
                total_rows=existing["totalRows"] or 0,
                processed_rows=existing["processedRows"] or 0,
                success_count=existing["successCount"] or 0,
                duplicate_rows=existing["duplicateRows"] or 0,
                error_count=existing["errorCount"] or 0,
                errors=[],
            )

    resume_cursor = 0
    if resume_from_batch_id:
        row = conn.execute('SELECT * FROM "ImportBatch" WHERE id = ?', (resume_from_batch_id,)).fetchone()
        if row is None:
            raise ValueError(f"No ImportBatch found with id {resume_from_batch_id!r} to resume")
        import_batch_id = resume_from_batch_id
        resume_cursor = int(row["resumeCursor"]) if row["resumeCursor"] else 0
        success_count = row["successCount"] or 0
        duplicate_count = row["duplicateRows"] or 0
        error_count = row["errorCount"] or 0
        errors: list[RowError] = (
            [RowError(**e) for e in json.loads(row["errorLog"])] if row["errorLog"] else []
        )
        conn.execute('UPDATE "ImportBatch" SET status = ? WHERE id = ?', ("IN_PROGRESS", import_batch_id))
    else:
        import_batch_id = new_id()
        success_count = 0
        duplicate_count = 0
        error_count = 0
        errors = []
        conn.execute(
            'INSERT INTO "ImportBatch" '
            "(id, sourceType, filename, status, rowCount, successCount, errorCount, "
            "totalRows, processedRows, duplicateRows, idempotencyKey, providerName, importedAt) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                import_batch_id,
                _map_import_source_type(provider.name),
                filename,
                "IN_PROGRESS",
                0,
                0,
                0,
                None,
                0,
                0,
                idempotency_key,
                provider.name,
                _now(),
            ),
        )
    conn.commit()

    processed = resume_cursor
    for index, race in enumerate(provider.fetch_races(start_date, end_date)):
        if index < resume_cursor:
            continue
        try:
            was_duplicate = _import_one_race(conn, race, source_type, provider.name, import_batch_id)
            if was_duplicate:
                duplicate_count += 1
            else:
                success_count += 1
            conn.commit()
        except Exception as exc:  # noqa: BLE001 - one bad race must not abort the batch
            conn.rollback()
            error_count += 1
            errors.append(RowError(index=index, provider_race_id=race.provider_race_id, message=str(exc)))

        processed = index + 1
        conn.execute(
            'UPDATE "ImportBatch" SET processedRows = ?, successCount = ?, duplicateRows = ?, '
            "errorCount = ?, resumeCursor = ?, errorLog = ? WHERE id = ?",
            (
                processed,
                success_count,
                duplicate_count,
                error_count,
                str(processed),
                json.dumps([e.__dict__ for e in errors]),
                import_batch_id,
            ),
        )
        conn.commit()
        if on_progress:
            on_progress(processed, error_count)

    if error_count == 0:
        final_status = "SUCCESS"
    elif success_count == 0 and duplicate_count == 0:
        final_status = "FAILED"
    else:
        final_status = "PARTIAL"

    conn.execute(
        'UPDATE "ImportBatch" SET status = ?, rowCount = ?, totalRows = ? WHERE id = ?',
        (final_status, processed, processed, import_batch_id),
    )
    conn.commit()

    return ImportResult(
        import_batch_id=import_batch_id,
        status=final_status,
        total_rows=processed,
        processed_rows=processed,
        success_count=success_count,
        duplicate_rows=duplicate_count,
        error_count=error_count,
        errors=errors,
    )


def _map_import_source_type(provider_name: str) -> str:
    if provider_name == "csv":
        return "CSV"
    if "json" in provider_name:
        return "JSON"
    return "API"


def _dedup_key(race: CanonicalRace) -> str:
    if race.provider_race_id:
        return race.provider_race_id
    return hash_payload(f"{race.date.isoformat()}|{race.race_time}|{race.racecourse}|{race.race_name}")


def _import_one_race(
    conn: sqlite3.Connection,
    race: CanonicalRace,
    source_type: str,
    provider_name: str,
    import_batch_id: str,
) -> bool:
    """Returns True if this race was a duplicate (skipped), False if it was
    newly imported."""

    dedup_key = _dedup_key(race)
    existing = conn.execute(
        'SELECT entityId FROM "DataProvenance" '
        "WHERE provider = ? AND dataDomain = ? AND providerRecordId = ? LIMIT 1",
        (provider_name, "RACE_CARD", dedup_key),
    ).fetchone()
    if existing is not None:
        return True

    if not race.racecourse or not race.race_name:
        raise ValueError("Race is missing required racecourse/race_name")

    race_id = new_id()
    now = _now()
    conn.execute(
        'INSERT INTO "Race" '
        "(id, isSampleData, sourceType, date, raceTime, racecourse, country, raceName, raceType, "
        "flatJumps, surface, distanceYards, distanceFurlongs, raceClass, gradeGroup, handicapType, "
        "ageRestriction, sexRestriction, numberOfRunners, going, goingDescription, railPosition, "
        "stallsPosition, weatherSummary, temperatureCelsius, windSummary, precipitationMm, "
        "prizeMoneyTotal, currency, eachWayFraction, bookmakerPlaces, extraPlaceFlag, raceStatus, "
        "resultStatus, createdAt, updatedAt, importBatchId) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?, ?, ?, ?)",
        (
            race_id,
            0,
            source_type,
            _dt(race.date),
            race.race_time,
            race.racecourse,
            race.country,
            race.race_name,
            race.race_type,
            race.flat_jumps,
            race.surface,
            race.distance_yards,
            race.distance_furlongs,
            race.race_class,
            race.grade_group,
            race.handicap_type,
            race.age_restriction,
            race.sex_restriction,
            race.number_of_runners,
            race.going,
            race.going_description,
            race.rail_position,
            race.stalls_position,
            race.weather_summary,
            race.temperature_celsius,
            race.wind_summary,
            race.precipitation_mm,
            race.prize_money_total,
            race.currency,
            race.each_way_fraction,
            race.bookmaker_places,
            int(race.extra_place_flag),
            race.race_status,
            race.result_status,
            now,
            now,
            import_batch_id,
        ),
    )

    record_provenance(
        conn,
        ProvenanceRecord(
            entity_type="Race",
            entity_id=race_id,
            data_domain="RACE_CARD",
            provider=provider_name,
            provider_record_id=dedup_key,
            effective_at=race.date,
            import_batch_id=import_batch_id,
            raw_payload_hash=hash_payload(_race_field_snapshot(race)),
        ),
    )

    race_field_values = {
        "going": race.going,
        "goingDescription": race.going_description,
        "railPosition": race.rail_position,
        "stallsPosition": race.stalls_position,
        "weatherSummary": race.weather_summary,
        "raceStatus": race.race_status,
        "resultStatus": race.result_status,
    }
    for field_name in _RACE_HISTORY_FIELDS:
        value = race_field_values[field_name]
        if value is None:
            continue
        record_race_field_change(
            conn,
            race_id=race_id,
            field_name=field_name,
            field_value=str(value),
            effective_at=race.date,
            source=provider_name,
            import_batch_id=import_batch_id,
        )

    for runner in race.runners:
        resolution = resolve_horse(
            conn,
            runner.horse.name,
            provider_name=provider_name,
            provider_horse_id=runner.horse.provider_horse_id,
            country_bred=runner.horse.country_bred,
            year_of_birth=runner.horse.year_of_birth,
            sex=runner.horse.sex,
            trainer_name=runner.horse.trainer_name or runner.trainer_name,
            source_type=source_type,
        )
        horse_id = resolution.canonical_id

        runner_id = new_id()
        conn.execute(
            'INSERT INTO "Runner" '
            "(id, isSampleData, raceId, horseId, clothNumber, draw, ageAtRace, weightStone, "
            "weightPounds, weightLbsTotal, officialRating, racingPostRating, timeformRating, "
            "topspeedRating, jockeyName, jockeyClaimLbs, trainerName, headgear, firstTimeHeadgear, "
            "daysSinceLastRun, nonRunner, createdAt, updatedAt) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                runner_id,
                0,
                race_id,
                horse_id,
                runner.cloth_number,
                runner.draw,
                runner.age_at_race,
                runner.weight_stone,
                runner.weight_pounds,
                runner.weight_lbs_total,
                runner.official_rating,
                runner.racing_post_rating,
                runner.timeform_rating,
                runner.topspeed_rating,
                runner.jockey_name,
                runner.jockey_claim_lbs,
                runner.trainer_name,
                runner.headgear,
                int(runner.first_time_headgear),
                runner.days_since_last_run,
                int(runner.non_runner),
                now,
                now,
            ),
        )
        record_provenance(
            conn,
            ProvenanceRecord(
                entity_type="Runner",
                entity_id=runner_id,
                data_domain="RACE_CARD",
                provider=provider_name,
                provider_record_id=runner.provider_runner_id,
                effective_at=race.date,
                import_batch_id=import_batch_id,
            ),
        )

        runner_field_values = {
            "draw": runner.draw,
            "jockeyName": runner.jockey_name,
            "trainerName": runner.trainer_name,
            "weightLbsTotal": runner.weight_lbs_total,
            "nonRunner": runner.non_runner,
            "headgear": runner.headgear,
            "officialRating": runner.official_rating,
        }
        for field_name in _RUNNER_HISTORY_FIELDS:
            value = runner_field_values[field_name]
            if value is None:
                continue
            record_runner_field_change(
                conn,
                runner_id=runner_id,
                field_name=field_name,
                field_value=str(value),
                effective_at=race.date,
                source=provider_name,
                import_batch_id=import_batch_id,
            )

    for terms in race.place_terms:
        bookmaker_id = _get_or_create_bookmaker(conn, terms.bookmaker_name)
        terms_id = new_id()
        effective_at = terms.effective_at or race.date
        conn.execute(
            'INSERT INTO "RacePlaceTerms" '
            "(id, raceId, bookmakerId, places, eachWayFraction, extraPlaces, terms, effectiveAt, createdAt) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                terms_id,
                race_id,
                bookmaker_id,
                terms.places,
                terms.each_way_fraction,
                int(terms.extra_places),
                terms.terms,
                _dt(effective_at),
                now,
            ),
        )
        record_provenance(
            conn,
            ProvenanceRecord(
                entity_type="RacePlaceTerms",
                entity_id=terms_id,
                data_domain="PLACE_TERMS",
                provider=provider_name,
                effective_at=effective_at,
                import_batch_id=import_batch_id,
            ),
        )
        record_place_terms_change(
            conn,
            race_place_terms_id=terms_id,
            race_id=race_id,
            bookmaker_id=bookmaker_id,
            places=terms.places,
            each_way_fraction=terms.each_way_fraction,
            extra_places=terms.extra_places,
            terms=terms.terms,
            effective_at=effective_at,
            source=provider_name,
            import_batch_id=import_batch_id,
        )

    return False


def _get_or_create_bookmaker(conn: sqlite3.Connection, name: str) -> str:
    row = conn.execute('SELECT id FROM "Bookmaker" WHERE name = ?', (name,)).fetchone()
    if row is not None:
        return row["id"]
    bookmaker_id = new_id()
    conn.execute(
        'INSERT INTO "Bookmaker" (id, name, isExchange, createdAt) VALUES (?, ?, ?, ?)',
        (bookmaker_id, name, 0, _now()),
    )
    return bookmaker_id


def _race_field_snapshot(race: CanonicalRace) -> dict:
    """A compact dict used only to compute rawPayloadHash — not stored."""

    return {
        "provider_race_id": race.provider_race_id,
        "date": race.date.isoformat(),
        "racecourse": race.racecourse,
        "race_name": race.race_name,
        "runner_count": len(race.runners),
        "going": race.going,
    }

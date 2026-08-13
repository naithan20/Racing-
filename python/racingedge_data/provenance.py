"""Provenance and point-in-time field history.

Two related but distinct concerns live here, both required so a historical
prediction can be defended:

1. **Provenance** (`DataProvenance` table): for an imported record, exactly
   which provider produced it, the provider's own record id/timestamp, when
   RacingEdge retrieved it, when it became effective, and a hash of the raw
   payload (never the payload itself, to avoid unbounded duplication — the
   goal is traceability and dedup, not a raw-data warehouse).

2. **Point-in-time field history** (`RaceFieldHistory` / `RunnerFieldHistory`
   / `RacePlaceTermsHistory` tables): a generic append-only log of every
   prior value of a mutable field (going, draw, jockey, non-runner status,
   place terms, ...). The live `Race`/`Runner`/`RacePlaceTerms` rows always
   hold the CURRENT value; these history tables are what
   `racingedge_data.point_in_time` reconstruction queries read from to
   answer "what was known as of timestamp T".

Both write through `racingedge_model.db`'s connection/datetime helpers so
there is exactly one place in the codebase that knows the Prisma-compatible
SQLite datetime string format.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from racingedge_model.db import to_prisma_datetime
from racingedge_model.ids import new_id


def hash_payload(payload: Any) -> str:
    """Stable SHA-256 hex digest of a JSON-serializable payload, or of a
    raw str/bytes payload directly. Used for `rawPayloadHash` (dedup/audit)
    and for import-idempotency checks — never for anything security-sensitive.
    """

    if isinstance(payload, (bytes, bytearray)):
        data = bytes(payload)
    elif isinstance(payload, str):
        data = payload.encode("utf-8")
    else:
        data = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _dt_opt(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return to_prisma_datetime(value)


def _now() -> str:
    return to_prisma_datetime(datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProvenanceRecord:
    entity_type: str  # e.g. "Race", "Runner", "Horse", "FormEntry", "RunnerMarketPrice", "ResultEntry"
    entity_id: str
    data_domain: str  # e.g. "RACE_CARD", "ODDS", "RESULT", "SECTIONAL", "WEATHER", "PLACE_TERMS"
    provider: str

    provider_record_id: Optional[str] = None
    provider_timestamp: Optional[datetime] = None
    effective_at: Optional[datetime] = None
    source_version: Optional[str] = None
    raw_payload_hash: Optional[str] = None
    import_batch_id: Optional[str] = None


def record_provenance(conn: sqlite3.Connection, record: ProvenanceRecord) -> str:
    provenance_id = new_id()
    now = _now()
    columns = [
        "id",
        "entityType",
        "entityId",
        "dataDomain",
        "provider",
        "providerRecordId",
        "providerTimestamp",
        "retrievedAt",
        "effectiveAt",
        "sourceVersion",
        "rawPayloadHash",
        "importBatchId",
        "createdAt",
    ]
    row = {
        "id": provenance_id,
        "entityType": record.entity_type,
        "entityId": record.entity_id,
        "dataDomain": record.data_domain,
        "provider": record.provider,
        "providerRecordId": record.provider_record_id,
        "providerTimestamp": _dt_opt(record.provider_timestamp),
        "retrievedAt": now,
        "effectiveAt": _dt_opt(record.effective_at),
        "sourceVersion": record.source_version,
        "rawPayloadHash": record.raw_payload_hash,
        "importBatchId": record.import_batch_id,
        "createdAt": now,
    }
    placeholders = ", ".join(["?"] * len(columns))
    conn.execute(
        f'INSERT INTO "DataProvenance" ({", ".join(columns)}) VALUES ({placeholders})',
        [row[c] for c in columns],
    )
    return provenance_id


# ---------------------------------------------------------------------------
# Point-in-time field history
# ---------------------------------------------------------------------------


def record_race_field_change(
    conn: sqlite3.Connection,
    race_id: str,
    field_name: str,
    field_value: Optional[str],
    effective_at: datetime,
    source: Optional[str] = None,
    import_batch_id: Optional[str] = None,
) -> str:
    history_id = new_id()
    conn.execute(
        'INSERT INTO "RaceFieldHistory" '
        "(id, raceId, fieldName, fieldValue, effectiveAt, source, importBatchId, createdAt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            history_id,
            race_id,
            field_name,
            field_value,
            _dt_opt(effective_at),
            source,
            import_batch_id,
            _now(),
        ),
    )
    return history_id


def record_runner_field_change(
    conn: sqlite3.Connection,
    runner_id: str,
    field_name: str,
    field_value: Optional[str],
    effective_at: datetime,
    source: Optional[str] = None,
    import_batch_id: Optional[str] = None,
) -> str:
    history_id = new_id()
    conn.execute(
        'INSERT INTO "RunnerFieldHistory" '
        "(id, runnerId, fieldName, fieldValue, effectiveAt, source, importBatchId, createdAt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            history_id,
            runner_id,
            field_name,
            field_value,
            _dt_opt(effective_at),
            source,
            import_batch_id,
            _now(),
        ),
    )
    return history_id


def record_place_terms_change(
    conn: sqlite3.Connection,
    race_place_terms_id: str,
    race_id: str,
    bookmaker_id: str,
    places: int,
    each_way_fraction: float,
    extra_places: bool,
    terms: Optional[str],
    effective_at: datetime,
    superseded_at: Optional[datetime] = None,
    source: Optional[str] = None,
    import_batch_id: Optional[str] = None,
) -> str:
    """Logs one prior (or current) state of a RacePlaceTerms row. Call this
    BEFORE overwriting the live RacePlaceTerms row with new terms, passing
    the OLD values and `superseded_at=<the new terms' effective_at>` — the
    live row is left holding only the current state, this table accumulates
    every state that preceded it.
    """

    history_id = new_id()
    conn.execute(
        'INSERT INTO "RacePlaceTermsHistory" '
        "(id, racePlaceTermsId, raceId, bookmakerId, places, eachWayFraction, extraPlaces, "
        "terms, effectiveAt, supersededAt, source, importBatchId, createdAt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            history_id,
            race_place_terms_id,
            race_id,
            bookmaker_id,
            int(places),
            float(each_way_fraction),
            int(bool(extra_places)),
            terms,
            _dt_opt(effective_at),
            _dt_opt(superseded_at),
            source,
            import_batch_id,
            _now(),
        ),
    )
    return history_id


def record_sectional_point(
    conn: sqlite3.Connection,
    runner_id: str,
    segment_index: int,
    segment_distance_furlongs: Optional[float] = None,
    segment_time_seconds: Optional[float] = None,
    speed_mps: Optional[float] = None,
    position_in_race: Optional[int] = None,
    stride_length: Optional[float] = None,
    stride_frequency: Optional[float] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    source: Optional[str] = None,
    import_batch_id: Optional[str] = None,
) -> str:
    point_id = new_id()
    conn.execute(
        'INSERT INTO "RunnerSectionalPoint" '
        "(id, runnerId, segmentIndex, segmentDistanceFurlongs, segmentTimeSeconds, speedMps, "
        "positionInRace, strideLength, strideFrequency, latitude, longitude, source, "
        "importBatchId, createdAt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            point_id,
            runner_id,
            int(segment_index),
            segment_distance_furlongs,
            segment_time_seconds,
            speed_mps,
            position_in_race,
            stride_length,
            stride_frequency,
            latitude,
            longitude,
            source,
            import_batch_id,
            _now(),
        ),
    )
    return point_id

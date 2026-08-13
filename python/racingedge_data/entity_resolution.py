"""Entity resolution for horses, trainers, jockeys, and courses.

The project's explicit instruction: **do not blindly fuzzy-match.**
Resolution proceeds through strictly-ordered, auditable strategies, from
strongest to weakest signal:

1. **Provider ID match** — if we've already seen this exact
   `(providerName, providerId)` pair before (via `EntityAlias`), reuse the
   canonical entity it resolved to. This is the only fully-reliable signal;
   used whenever a provider supplies its own entity id.
2. **Exact normalized-name match** — lowercase, strip diacritics/
   punctuation, collapse whitespace, and match against existing
   `EntityAlias.normalizedName` rows for the same entity type. No fuzzy
   distance, no similarity scoring — an exact match on the normalized form
   only (this is what correctly unifies "O'Brien" / "OBrien" / "O Brien"
   without ever risking merging two genuinely different names).
3. **Ambiguous or unseen** — for `HORSE` (the one entity type with a real
   canonical table), an unseen name creates a new `Horse` row; a name that
   matches MORE THAN ONE existing canonical horse is never auto-merged —
   a new `Horse` row is still created (under-merging is the safe default:
   a duplicate horse record is a data-quality nuisance, but wrongly merging
   two different horses silently corrupts every feature computed from their
   combined history) and the ambiguity is queued to
   `EntityResolutionQueueItem` for a human to resolve later. `TRAINER`,
   `JOCKEY`, and `COURSE` have no dedicated table in this schema (they are
   free-text fields on `Runner`/`Race`) — their "canonical id" is simply
   their normalized name, so ambiguity in the HORSE sense cannot occur for
   them; only the raw-name -> normalized-name mapping is recorded, for
   audit purposes.

Every resolution — successful, newly-created, or queued — is recorded in
`EntityAlias` / `EntityResolutionQueueItem`, so any merge decision can be
traced and, if wrong, reviewed and reversed.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from racingedge_model.db import to_prisma_datetime
from racingedge_model.ids import new_id

ENTITY_TYPES = ("HORSE", "TRAINER", "JOCKEY", "COURSE")


def normalize_name(raw_name: str) -> str:
    """Lowercase, strip diacritics/punctuation, collapse whitespace.

    Deliberately conservative: this is a normalization, not a similarity
    function. "Kingman" and "King's Man" normalize to different strings
    ("kingman" vs "kings man") and are NOT considered a match — only
    genuinely identical-after-normalization names match here.
    """

    text = unicodedata.normalize("NFKD", raw_name)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[''`.,]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass(frozen=True)
class ResolutionResult:
    canonical_id: str
    match_method: str  # "PROVIDER_ID" | "EXACT_NORMALIZED_NAME"
    created_new: bool
    ambiguous: bool = False


def _now() -> str:
    return to_prisma_datetime(datetime.now(timezone.utc))


def _insert_alias(
    conn: sqlite3.Connection,
    entity_type: str,
    canonical_id: str,
    raw_name: str,
    normalized_name: str,
    provider_name: Optional[str],
    provider_id: Optional[str],
    match_method: str,
    confidence: Optional[float] = None,
) -> None:
    conn.execute(
        'INSERT INTO "EntityAlias" '
        "(id, entityType, canonicalId, rawName, normalizedName, providerName, providerId, "
        "matchMethod, confidence, createdAt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            new_id(),
            entity_type,
            canonical_id,
            raw_name,
            normalized_name,
            provider_name,
            provider_id,
            match_method,
            confidence,
            _now(),
        ),
    )


def _find_by_provider_id(
    conn: sqlite3.Connection, entity_type: str, provider_name: str, provider_id: str
) -> Optional[str]:
    row = conn.execute(
        'SELECT canonicalId FROM "EntityAlias" '
        "WHERE entityType = ? AND providerName = ? AND providerId = ? LIMIT 1",
        (entity_type, provider_name, provider_id),
    ).fetchone()
    return row["canonicalId"] if row else None


def _find_by_normalized_name(
    conn: sqlite3.Connection, entity_type: str, normalized_name: str
) -> list[str]:
    rows = conn.execute(
        'SELECT DISTINCT canonicalId FROM "EntityAlias" '
        "WHERE entityType = ? AND normalizedName = ?",
        (entity_type, normalized_name),
    ).fetchall()
    return [r["canonicalId"] for r in rows]


def _queue_for_review(
    conn: sqlite3.Connection,
    entity_type: str,
    raw_name: str,
    normalized_name: str,
    provider_name: Optional[str],
    candidate_canonical_ids: list[str],
) -> str:
    import json

    queue_id = new_id()
    conn.execute(
        'INSERT INTO "EntityResolutionQueueItem" '
        "(id, entityType, rawName, normalizedName, providerName, candidateCanonicalIdsJson, "
        "status, createdAt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            queue_id,
            entity_type,
            raw_name,
            normalized_name,
            provider_name,
            json.dumps(candidate_canonical_ids),
            "PENDING",
            _now(),
        ),
    )
    return queue_id


def resolve_horse(
    conn: sqlite3.Connection,
    name: str,
    provider_name: Optional[str] = None,
    provider_horse_id: Optional[str] = None,
    country_bred: Optional[str] = None,
    year_of_birth: Optional[int] = None,
    sex: Optional[str] = None,
    trainer_name: Optional[str] = None,
    source_type: str = "SAMPLE",
) -> ResolutionResult:
    """Resolves a horse name to a canonical `Horse.id`, creating a new
    `Horse` row only when no confident match exists. See module docstring
    for the exact strategy ordering."""

    normalized = normalize_name(name)

    if provider_name and provider_horse_id:
        existing = _find_by_provider_id(conn, "HORSE", provider_name, provider_horse_id)
        if existing is not None:
            return ResolutionResult(canonical_id=existing, match_method="PROVIDER_ID", created_new=False)

    candidates = _find_by_normalized_name(conn, "HORSE", normalized)

    if len(candidates) == 1:
        canonical_id = candidates[0]
        if provider_name and provider_horse_id:
            _insert_alias(
                conn,
                "HORSE",
                canonical_id,
                name,
                normalized,
                provider_name,
                provider_horse_id,
                "PROVIDER_ID",
            )
        return ResolutionResult(canonical_id=canonical_id, match_method="EXACT_NORMALIZED_NAME", created_new=False)

    if len(candidates) > 1:
        _queue_for_review(conn, "HORSE", name, normalized, provider_name, candidates)
        canonical_id = _create_horse(conn, name, country_bred, year_of_birth, sex, trainer_name, source_type)
        _insert_alias(
            conn,
            "HORSE",
            canonical_id,
            name,
            normalized,
            provider_name,
            provider_horse_id,
            "MANUAL_REVIEW",
        )
        return ResolutionResult(
            canonical_id=canonical_id, match_method="MANUAL_REVIEW", created_new=True, ambiguous=True
        )

    canonical_id = _create_horse(conn, name, country_bred, year_of_birth, sex, trainer_name, source_type)
    _insert_alias(
        conn,
        "HORSE",
        canonical_id,
        name,
        normalized,
        provider_name,
        provider_horse_id,
        "PROVIDER_ID" if provider_horse_id else "EXACT_NORMALIZED_NAME",
    )
    return ResolutionResult(canonical_id=canonical_id, match_method="EXACT_NORMALIZED_NAME", created_new=True)


def _create_horse(
    conn: sqlite3.Connection,
    name: str,
    country_bred: Optional[str],
    year_of_birth: Optional[int],
    sex: Optional[str],
    trainer_name: Optional[str],
    source_type: str,
) -> str:
    horse_id = new_id()
    now = _now()
    conn.execute(
        'INSERT INTO "Horse" '
        "(id, isSampleData, sourceType, name, countryBred, yearOfBirth, sex, trainerName, "
        "createdAt, updatedAt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            horse_id,
            0,
            source_type,
            name,
            country_bred,
            year_of_birth,
            sex,
            trainer_name,
            now,
            now,
        ),
    )
    return horse_id


def resolve_free_text_entity(
    conn: sqlite3.Connection,
    entity_type: str,
    name: str,
    provider_name: Optional[str] = None,
) -> ResolutionResult:
    """Resolves a TRAINER/JOCKEY/COURSE name. These have no dedicated
    canonical table in this schema, so the canonical id IS the normalized
    name — this function's only real job is recording the raw-name ->
    normalized-name mapping in `EntityAlias` for audit/traceability, and
    reporting whether this exact raw spelling has been seen before.
    """

    if entity_type not in ("TRAINER", "JOCKEY", "COURSE"):
        raise ValueError(f"resolve_free_text_entity does not support entityType={entity_type!r}")

    normalized = normalize_name(name)
    existing = conn.execute(
        'SELECT 1 FROM "EntityAlias" WHERE entityType = ? AND rawName = ? AND normalizedName = ? LIMIT 1',
        (entity_type, name, normalized),
    ).fetchone()

    if existing is None:
        _insert_alias(conn, entity_type, normalized, name, normalized, provider_name, None, "EXACT_NORMALIZED_NAME")
        return ResolutionResult(canonical_id=normalized, match_method="EXACT_NORMALIZED_NAME", created_new=True)

    return ResolutionResult(canonical_id=normalized, match_method="EXACT_NORMALIZED_NAME", created_new=False)

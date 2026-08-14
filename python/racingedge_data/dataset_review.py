"""Dataset licence/provenance review — Phase 3C.

A `DatasetReview` is a human-legible record of what's known and NOT known
about a dataset's reuse rights, created BEFORE import so licence
uncertainty is visible rather than discovered after the fact. This module
deliberately does not attempt to give legal advice or make a licence
determination on the user's behalf — it only structures what's been
observed (a stated licence, a URL, a reviewer's notes) and a
`provenanceConfidence` classification, which is the same `ProvenanceStatus`
used to gate individual imported records (see
`racingedge_data.importers.free_dataset_importer` and
`racingedge_data.dataset_version.filter_race_ids_excluding_provenance`).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from racingedge_model.db import to_prisma_datetime
from racingedge_model.ids import new_id

VALID_PROVENANCE_STATUSES = (
    "VERIFIED_OPEN",
    "PUBLIC_RESEARCH",
    "COMMUNITY_UNVERIFIED",
    "USER_SUPPLIED",
    "UNKNOWN",
    "RESTRICTED",
)


@dataclass(frozen=True)
class DatasetReviewInput:
    dataset_name: str
    source: str

    licence_stated: Optional[str] = None
    licence_url: Optional[str] = None
    original_provider: Optional[str] = None

    redistribution_permitted: Optional[bool] = None
    research_use_permitted: Optional[bool] = None
    commercial_use_permitted: Optional[bool] = None

    provenance_confidence: str = "UNKNOWN"
    reviewer_notes: Optional[str] = None


def create_dataset_review(conn: sqlite3.Connection, review: DatasetReviewInput) -> str:
    if review.provenance_confidence not in VALID_PROVENANCE_STATUSES:
        raise ValueError(
            f"provenance_confidence must be one of {VALID_PROVENANCE_STATUSES}, "
            f"got {review.provenance_confidence!r}"
        )

    review_id = new_id()
    now = to_prisma_datetime(datetime.now(timezone.utc))
    conn.execute(
        'INSERT INTO "DatasetReview" '
        "(id, datasetName, source, licenceStated, licenceUrl, originalProvider, "
        "redistributionPermitted, researchUsePermitted, commercialUsePermitted, "
        "provenanceConfidence, reviewerNotes, createdAt, updatedAt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            review_id,
            review.dataset_name,
            review.source,
            review.licence_stated,
            review.licence_url,
            review.original_provider,
            _bool_or_none(review.redistribution_permitted),
            _bool_or_none(review.research_use_permitted),
            _bool_or_none(review.commercial_use_permitted),
            review.provenance_confidence,
            review.reviewer_notes,
            now,
            now,
        ),
    )
    return review_id


def get_dataset_review(conn: sqlite3.Connection, review_id: str) -> Optional[dict]:
    row = conn.execute('SELECT * FROM "DatasetReview" WHERE id = ?', (review_id,)).fetchone()
    return dict(row) if row is not None else None


def list_dataset_reviews(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute('SELECT * FROM "DatasetReview" ORDER BY createdAt DESC').fetchall()
    return [dict(r) for r in rows]


def _bool_or_none(value: Optional[bool]) -> Optional[int]:
    return None if value is None else int(value)

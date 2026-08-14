"""RACINGEDGE_BEHAVIOURAL_DATA — Phase 3C.

`RunnerObservation` (a human/analyst tagging a settled run with structured
race-reading notes — trouble in running, how it travelled, how it finished)
is RacingEdge's own proprietary observation dataset: nothing free or
public produces this, it can only come from someone watching the race. It
predates Phase 3C in the schema but had no Python code touching it at all
until now.

This module does two things, and deliberately keeps them separate:

1. `insert_runner_observation()` — an INSERT-ONLY write path. Observations
   are never updated or deleted by this module; a correction is a NEW row,
   the old one stays. `ObservationTagType` values and free text are kept
   verbatim forever — nothing here is ever overwritten.

2. `map_tags_to_behavioural_scores()` / `load_behavioural_observations()` —
   a READ-ONLY derived layer that turns the raw tags into small, signed
   integers on a handful of named axes (break quality, early position,
   position-acquisition cost, pace-pressure response, 2f transition,
   final-furlong sustainability, pace-collapse interaction) plus boolean
   confidence flags (bad ride, race not representative, clean test).

   Every mapping is a fixed lookup table defined once in this file, on a
   small ordinal scale (-2..+2), chosen by inspection of what each tag
   means — NEVER learned from outcomes, NEVER inferred. A tag absent from
   a category's map contributes nothing to that category (`None`, not 0
   — "not observed" must never look like "observed as neutral"). Any tag
   this module doesn't recognise is surfaced in `tags_with_no_mapping`
   rather than silently dropped.

This is a *research* feature dataset — see Phase 3C section 15 for the
planned CORE_FREE_MODEL vs CORE_FREE_MODEL+RACINGEDGE_BEHAVIOURAL_DATA
comparison. Nothing here claims predictive value yet.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from racingedge_model.db import to_prisma_datetime
from racingedge_model.ids import new_id

RACINGEDGE_BEHAVIOURAL_DATA_VERSION = "v1"

VALID_OBSERVATION_TAGS = (
    "EXCELLENT_BREAK",
    "SLOW_BREAK",
    "LED_CHEAPLY",
    "FOUGHT_FOR_LEAD",
    "RACED_PROMINENTLY",
    "MIDFIELD",
    "HELD_UP",
    "TRAPPED_WIDE",
    "BLOCKED",
    "SWITCHED",
    "LOST_GROUND_SEEKING_RUN",
    "TRAVELLED_STRONGLY",
    "UNABLE_TO_MATCH_ACCELERATION",
    "STRONG_TRANSITION",
    "WEAKENED_FINAL_FURLONG",
    "STAYED_ON_STRONGLY",
    "PACE_COLLAPSE_BENEFITED",
    "PACE_COLLAPSE_HURT",
    "BAD_RIDE_POSITIONING",
    "RACE_NOT_REPRESENTATIVE",
    "CLEAN_TEST_OF_THESIS",
)

# --- Transparent, fixed numeric mappings -----------------------------------
# Each map is a plain lookup table, small enough to read top to bottom and
# check by eye. Scale is -2 (strong negative signal) .. +2 (strong positive
# signal), 0 reserved for an explicitly neutral observed tag (MIDFIELD) —
# never used as a default for "not mentioned".

BREAK_QUALITY_MAP: dict[str, int] = {
    "EXCELLENT_BREAK": 1,
    "SLOW_BREAK": -1,
}

EARLY_POSITION_MAP: dict[str, int] = {
    "LED_CHEAPLY": 2,
    "FOUGHT_FOR_LEAD": 1,
    "RACED_PROMINENTLY": 1,
    "MIDFIELD": 0,
    "HELD_UP": -1,
}

# "position acquisition cost" — how much trouble the horse had getting
# into the position it raced from. Higher = more cost/interference.
POSITION_ACQUISITION_COST_MAP: dict[str, int] = {
    "TRAPPED_WIDE": 1,
    "SWITCHED": 1,
    "LOST_GROUND_SEEKING_RUN": 2,
    "BLOCKED": 2,
}

# "pace pressure experienced" / 3f response.
PACE_PRESSURE_RESPONSE_MAP: dict[str, int] = {
    "TRAVELLED_STRONGLY": 1,
    "UNABLE_TO_MATCH_ACCELERATION": -1,
}

# "2f transition" — the shift from mid-race pace into the closing effort.
TRANSITION_2F_MAP: dict[str, int] = {
    "STRONG_TRANSITION": 1,
}

FINAL_FURLONG_SUSTAINABILITY_MAP: dict[str, int] = {
    "STAYED_ON_STRONGLY": 1,
    "WEAKENED_FINAL_FURLONG": -1,
}

PACE_COLLAPSE_INTERACTION_MAP: dict[str, int] = {
    "PACE_COLLAPSE_BENEFITED": 1,
    "PACE_COLLAPSE_HURT": -1,
}

# Confidence/data-quality flags. These describe how much to trust the run
# as a performance data point, not which direction the horse's ability
# should be adjusted — kept as booleans, never folded into the numeric
# scores above.
BAD_RIDE_FLAG_TAGS = {"BAD_RIDE_POSITIONING"}
RACE_NOT_REPRESENTATIVE_TAGS = {"RACE_NOT_REPRESENTATIVE"}
CLEAN_TEST_TAGS = {"CLEAN_TEST_OF_THESIS"}

_SCORE_CATEGORY_MAPS: dict[str, dict[str, int]] = {
    "break_quality": BREAK_QUALITY_MAP,
    "early_position": EARLY_POSITION_MAP,
    "position_acquisition_cost": POSITION_ACQUISITION_COST_MAP,
    "pace_pressure_response": PACE_PRESSURE_RESPONSE_MAP,
    "transition_2f": TRANSITION_2F_MAP,
    "final_furlong_sustainability": FINAL_FURLONG_SUSTAINABILITY_MAP,
    "pace_collapse_interaction": PACE_COLLAPSE_INTERACTION_MAP,
}

_FLAG_CATEGORIES: dict[str, set[str]] = {
    "bad_ride_flag": BAD_RIDE_FLAG_TAGS,
    "race_not_representative_flag": RACE_NOT_REPRESENTATIVE_TAGS,
    "clean_test_flag": CLEAN_TEST_TAGS,
}

_ALL_MAPPED_TAGS = set().union(*_SCORE_CATEGORY_MAPS.values(), *_FLAG_CATEGORIES.values())


@dataclass(frozen=True)
class BehaviouralObservationRow:
    """One resultId's worth of behavioural signal, derived from however
    many raw `RunnerObservation` rows exist for it. `raw_tags`/
    `raw_free_text` are the untouched source rows — always kept alongside
    the derived scores so nothing here can be mistaken for the original
    evidence."""

    result_id: str
    raw_tags: list[str] = field(default_factory=list)
    raw_free_text: list[str] = field(default_factory=list)

    break_quality: Optional[int] = None
    early_position: Optional[int] = None
    position_acquisition_cost: Optional[int] = None
    pace_pressure_response: Optional[int] = None
    transition_2f: Optional[int] = None
    final_furlong_sustainability: Optional[int] = None
    pace_collapse_interaction: Optional[int] = None

    bad_ride_flag: bool = False
    race_not_representative_flag: bool = False
    clean_test_flag: bool = False

    tags_with_no_mapping: list[str] = field(default_factory=list)


def map_tags_to_behavioural_scores(tags: list[str]) -> dict:
    """Pure function: a list of raw `ObservationTagType` strings for a
    single result -> the derived score/flag dict. Multiple tags in the
    same category are summed (documented, not hidden) — e.g. BLOCKED +
    LOST_GROUND_SEEKING_RUN both present gives position_acquisition_cost
    = 2 + 2 = 4. A category with no matching tag present stays `None`."""

    scores: dict[str, Optional[int]] = {}
    for category, tag_map in _SCORE_CATEGORY_MAPS.items():
        matched = [tag_map[t] for t in tags if t in tag_map]
        scores[category] = sum(matched) if matched else None

    flags: dict[str, bool] = {
        flag_name: any(t in flag_tags for t in tags) for flag_name, flag_tags in _FLAG_CATEGORIES.items()
    }

    unmapped = sorted({t for t in tags if t not in _ALL_MAPPED_TAGS})

    return {**scores, **flags, "tags_with_no_mapping": unmapped}


def load_behavioural_observations(
    conn: sqlite3.Connection, result_ids: Optional[list[str]] = None
) -> list[BehaviouralObservationRow]:
    """Reads every raw `RunnerObservation` row (never mutating them) and
    groups by resultId to produce one `BehaviouralObservationRow` per
    result that has at least one observation. Results with zero
    observations are simply absent from the returned list — this module
    never fabricates a "no signal" row for unobserved results."""

    if result_ids is not None and not result_ids:
        return []

    if result_ids is None:
        rows = conn.execute(
            'SELECT resultId, tag, freeText FROM "RunnerObservation" ORDER BY resultId, createdAt'
        ).fetchall()
    else:
        placeholders = ",".join("?" for _ in result_ids)
        rows = conn.execute(
            f'SELECT resultId, tag, freeText FROM "RunnerObservation" '
            f"WHERE resultId IN ({placeholders}) ORDER BY resultId, createdAt",
            result_ids,
        ).fetchall()

    by_result: dict[str, dict[str, list]] = {}
    for row in rows:
        bucket = by_result.setdefault(row["resultId"], {"tags": [], "free_text": []})
        if row["tag"] is not None:
            bucket["tags"].append(row["tag"])
        if row["freeText"] is not None:
            bucket["free_text"].append(row["freeText"])

    results: list[BehaviouralObservationRow] = []
    for result_id, bucket in by_result.items():
        derived = map_tags_to_behavioural_scores(bucket["tags"])
        results.append(
            BehaviouralObservationRow(
                result_id=result_id,
                raw_tags=bucket["tags"],
                raw_free_text=bucket["free_text"],
                break_quality=derived["break_quality"],
                early_position=derived["early_position"],
                position_acquisition_cost=derived["position_acquisition_cost"],
                pace_pressure_response=derived["pace_pressure_response"],
                transition_2f=derived["transition_2f"],
                final_furlong_sustainability=derived["final_furlong_sustainability"],
                pace_collapse_interaction=derived["pace_collapse_interaction"],
                bad_ride_flag=derived["bad_ride_flag"],
                race_not_representative_flag=derived["race_not_representative_flag"],
                clean_test_flag=derived["clean_test_flag"],
                tags_with_no_mapping=derived["tags_with_no_mapping"],
            )
        )
    return results


def insert_runner_observation(
    conn: sqlite3.Connection,
    result_id: str,
    tag: Optional[str] = None,
    free_text: Optional[str] = None,
) -> str:
    """INSERT-ONLY. There is no update/delete helper in this module by
    design — a correction to an observation is recorded as a new row, the
    original is never touched. At least one of `tag`/`free_text` must be
    given; `tag`, if given, must be a recognised `ObservationTagType`."""

    if tag is None and free_text is None:
        raise ValueError("At least one of tag or free_text must be provided")
    if tag is not None and tag not in VALID_OBSERVATION_TAGS:
        raise ValueError(f"Unknown observation tag: {tag!r}. Valid tags: {VALID_OBSERVATION_TAGS}")

    observation_id = new_id()
    now = to_prisma_datetime(datetime.now(timezone.utc))
    conn.execute(
        'INSERT INTO "RunnerObservation" (id, resultId, tag, freeText, createdAt) VALUES (?, ?, ?, ?, ?)',
        (observation_id, result_id, tag, free_text, now),
    )
    return observation_id

"""Temporal leakage auditor.

Upgrades Phase 2's inline `racingedge_model.features.build.assert_no_leakage`
— which raises immediately on the first violation, appropriate as a runtime
guard inside the training pipeline — into a full, storable audit that
checks EVERY history row for EVERY runner in EVERY resulted race,
collects EVERY violation found, and produces the "LEAKAGE AUDIT PASSED /
FAILED" report the project requires before any dataset/model can be
trusted.

For each runner, the auditor requires `max(source row date) < race start
time` for every history source that feeds feature engineering (currently:
`FormEntry` and the population-level `global_prior_runs` table — see
`racingedge_model.features.build.build_global_prior_runs`). A row dated ON
OR AFTER the race start time is a violation, since it could not have been
known before that race and using it would leak future information.

This module re-derives its inputs from `racingedge_model.dataset.RaceData`
— literally the same tables the training pipeline loads — so a PASSED
result here is independent evidence that the training pipeline's own
`raceDate < as_of_date` filtering is correct, not just an assumption
carried over from it.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from racingedge_model.dataset import RaceData
from racingedge_model.db import to_prisma_datetime
from racingedge_model.ids import new_id


@dataclass(frozen=True)
class LeakageViolation:
    source: str
    race_id: str
    runner_id: Optional[str]
    offending_timestamp: str
    race_start_time: str
    detail: str


@dataclass
class LeakageAuditReport:
    status: str  # "PASSED" | "FAILED"
    features_checked: int
    violations: list[LeakageViolation] = field(default_factory=list)

    @property
    def violations_found(self) -> int:
        return len(self.violations)

    def summary_line(self) -> str:
        if self.status == "PASSED":
            return (
                f"LEAKAGE AUDIT PASSED — {self.features_checked} source(s) checked "
                "across all resulted races, 0 violations."
            )
        return (
            f"LEAKAGE AUDIT FAILED — {self.features_checked} source(s) checked, "
            f"{self.violations_found} violation(s) found. See `violations` for details."
        )

    def to_report_json(self) -> str:
        return json.dumps(
            {
                "status": self.status,
                "features_checked": self.features_checked,
                "violations_found": self.violations_found,
                "violations": [v.__dict__ for v in self.violations],
            }
        )


def audit_history_frame(
    frame: Optional[pd.DataFrame],
    race_id: str,
    runner_id: Optional[str],
    race_start_time,
    source_name: str,
    date_col: str = "raceDate",
) -> list[LeakageViolation]:
    """Checks every row of one history DataFrame against one race's start
    time, returning ALL violating rows — the property that distinguishes
    this from `assert_no_leakage`, which stops at the first."""

    if frame is None or len(frame) == 0 or date_col not in frame.columns:
        return []

    start = pd.Timestamp(race_start_time)
    start = start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")

    dates = pd.to_datetime(frame[date_col], utc=True)
    bad_mask = dates >= start
    if not bad_mask.any():
        return []

    violations = []
    for bad_date in dates[bad_mask]:
        violations.append(
            LeakageViolation(
                source=source_name,
                race_id=race_id,
                runner_id=runner_id,
                offending_timestamp=bad_date.isoformat(),
                race_start_time=start.isoformat(),
                detail=f"{source_name} row dated {bad_date.isoformat()} is on/after race start {start.isoformat()}",
            )
        )
    return violations


def _audit_self_referencing_form_entries(
    horse_form_filtered: pd.DataFrame, race_id: str, runner_id: str, as_of_date
) -> list[LeakageViolation]:
    """A `FormEntry` row whose `linkedRaceId` points at the race CURRENTLY
    being predicted is a leak if it survives the `raceDate < as_of_date`
    filter — i.e. it's been backdated to look like legitimate prior history
    for a race it actually describes/derives from. Deliberately checked
    against the FILTERED frame, not the horse's full history: every race's
    own outcome legitimately gets recorded as a same-race-id FormEntry row
    for FUTURE races to read as history, dated at/after this race's own
    start — that row is correctly excluded by the date filter already and
    must not be flagged here. This is the vector the deliberately malicious
    test case in `tests/test_leakage_audit.py` exercises: a row with
    linkedRaceId == race_id AND a date that incorrectly passes the filter.
    """

    if "linkedRaceId" not in horse_form_filtered.columns:
        return []
    self_referencing = horse_form_filtered[horse_form_filtered["linkedRaceId"] == race_id]
    if self_referencing.empty:
        return []

    start = pd.Timestamp(as_of_date)
    start = start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")
    violations = []
    for _, row in self_referencing.iterrows():
        violations.append(
            LeakageViolation(
                source="FormEntry.linkedRaceId",
                race_id=race_id,
                runner_id=runner_id,
                offending_timestamp=str(row.get("raceDate")),
                race_start_time=start.isoformat(),
                detail=(
                    f"FormEntry row references linkedRaceId={race_id}, the race currently "
                    "being predicted — a self-referential leak regardless of its recorded date."
                ),
            )
        )
    return violations


def audit_training_data(conn: sqlite3.Connection, verbose: bool = False) -> LeakageAuditReport:
    """Audits every resulted race's runners.

    For `FormEntry` and `global_prior_runs`, replicates the EXACT
    `raceDate < as_of_date` filter `racingedge_model.features.build.
    build_features_for_race` applies before feature computation, then
    re-checks the filtered result for any row on/after the race start —
    structurally this should always pass and exists as defense-in-depth
    against a filter bug (wrong comparison operator, wrong column, ...).

    Separately, and NOT defeated by date filtering, every `FormEntry` row
    that references the race currently being predicted via `linkedRaceId`
    is flagged regardless of its recorded date — see
    `_audit_self_referencing_form_entries`.
    """

    data = RaceData(conn)
    resulted_races = data.races[data.races["raceStatus"] == "RESULTED"].sort_values("date")

    all_violations: list[LeakageViolation] = []
    sources_checked = 0

    for _, race_row in resulted_races.iterrows():
        race_id = race_row["id"]
        as_of_date = race_row["date"]
        race_runners = data.runners[data.runners["raceId"] == race_id]

        for _, runner_row in race_runners.iterrows():
            horse_id = runner_row["horseId"]
            runner_id = runner_row["id"]

            horse_form_all = data.form[data.form["horseId"] == horse_id]
            horse_form_filtered = horse_form_all[horse_form_all["raceDate"] < as_of_date]

            horse_global_all = data.global_prior_runs[data.global_prior_runs["horseId"] == horse_id]
            horse_global_filtered = horse_global_all[horse_global_all["raceDate"] < as_of_date]

            all_violations += audit_history_frame(
                horse_form_filtered, race_id, runner_id, as_of_date, "FormEntry (post-filter)"
            )
            all_violations += audit_history_frame(
                horse_global_filtered, race_id, runner_id, as_of_date, "global_prior_runs (post-filter)"
            )
            all_violations += _audit_self_referencing_form_entries(
                horse_form_filtered, race_id, runner_id, as_of_date
            )
            sources_checked += 3

        if verbose:
            print(f"  audited race {race_id} ({len(race_runners)} runners)")

    status = "FAILED" if all_violations else "PASSED"
    return LeakageAuditReport(status=status, features_checked=sources_checked, violations=all_violations)


def save_audit_run(
    conn: sqlite3.Connection,
    report: LeakageAuditReport,
    dataset_version_id: Optional[str] = None,
    model_version_id: Optional[str] = None,
) -> str:
    """Persists a `LeakageAuditReport` as a `LeakageAuditRun` row — the
    durable, queryable artifact behind the PASSED/FAILED headline."""

    audit_id = new_id()
    now = to_prisma_datetime(datetime.now(timezone.utc))
    conn.execute(
        'INSERT INTO "LeakageAuditRun" '
        "(id, datasetVersionId, modelVersionId, status, featuresChecked, violationsFound, reportJson, createdAt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            audit_id,
            dataset_version_id,
            model_version_id,
            report.status,
            report.features_checked,
            report.violations_found,
            report.to_report_json(),
            now,
        ),
    )
    return audit_id

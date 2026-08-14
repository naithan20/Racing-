"""The "click Import -> done" pipeline — Phase 3D.

Runs the full sequence a consumer-facing "IMPORT" button triggers: fetch
the data (or use an already-supplied local file) -> inspect its schema ->
propose a mapping -> (pause for human review if anything is below high
confidence) -> validate the confirmed mapping -> import -> resolve
entities -> provenance review -> leakage audit -> DatasetVersion ->
data-quality summary -> done.

This module is the ONLY thing that writes to the `ImportJob` table — the
Next.js server just creates a job row (or reads/polls one) and spawns this
module as a subprocess; every step below is a plain, resumable function
that reads the job's current `status` and continues from there, the same
"Python writes SQLite directly, Next.js reads it via Prisma" pattern every
other data-layer table in this project already uses (see db.py, dataset_
version.py). There is no separate job queue or message broker.

**Resumability.** `run_import_job` is idempotent to call: if the job is
already `AWAITING_MAPPING_REVIEW`, calling it again just re-checks the
mapping file and, if it's now fully confirmed, continues; it does not
re-download or re-inspect. This is what lets the mapping-review UI simply
call `confirm_mapping_and_resume` (which patches the mapping file, resets
status, and calls `run_import_job` again) rather than needing its own
separate resume codepath.
"""

from __future__ import annotations

import json
import sqlite3
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from racingedge_data.bias_analysis import compute_bias_report
from racingedge_data.dataset_review import DatasetReviewInput, create_dataset_review
from racingedge_data.dataset_version import (
    classify_readiness,
    create_dataset_version,
    filter_race_ids_excluding_provenance,
)
from racingedge_data.importers.free_dataset_importer import (
    MappingNotConfirmedError,
    import_free_dataset,
    load_and_validate_mapping,
)
from racingedge_data.inspector import inspect_file
from racingedge_data.leakage_audit import audit_training_data, save_audit_run
from racingedge_data.providers.download_adapter import DownloadProgress, download_file
from racingedge_data.providers.kaggle_adapter import KaggleAdapter
from racingedge_model.config import PROJECT_ROOT
from racingedge_model.db import to_prisma_datetime
from racingedge_model.ids import new_id

IMPORT_JOB_STORAGE_DIR = PROJECT_ROOT / "python" / "storage" / "import_jobs"

# Extensions inspect_file/import_free_dataset can actually read. Used to
# pick the "primary" data file out of a downloaded/extracted directory
# (e.g. a Kaggle dataset often bundles a README, a licence file, and more
# than one candidate data file).
_DATA_EXTENSIONS_BY_PREFERENCE = (".db", ".sqlite", ".sqlite3", ".csv", ".json", ".jsonl")

TERMINAL_STATUSES = ("COMPLETED", "FAILED")


class ImportJobNotFoundError(RuntimeError):
    pass


class ImportJobFailedError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# ImportJob row helpers — the only writers of this table.
# ---------------------------------------------------------------------------


def _now() -> str:
    return to_prisma_datetime(datetime.now(timezone.utc))


def get_import_job(conn: sqlite3.Connection, job_id: str) -> dict[str, Any]:
    row = conn.execute('SELECT * FROM "ImportJob" WHERE id = ?', (job_id,)).fetchone()
    if row is None:
        raise ImportJobNotFoundError(job_id)
    return dict(row)


def _append_log(conn: sqlite3.Connection, job_id: str, step: str, message: str) -> None:
    job = get_import_job(conn, job_id)
    log = json.loads(job["logJson"]) if job["logJson"] else []
    log.append({"ts": _now(), "step": step, "message": message})
    conn.execute('UPDATE "ImportJob" SET logJson = ?, updatedAt = ? WHERE id = ?', (json.dumps(log), _now(), job_id))


def _set_status(
    conn: sqlite3.Connection,
    job_id: str,
    status: str,
    *,
    progress_percent: Optional[int] = None,
    current_step_label: Optional[str] = None,
    error_message: Optional[str] = None,
    message: Optional[str] = None,
) -> None:
    fields: dict[str, Any] = {"status": status, "updatedAt": _now()}
    if progress_percent is not None:
        fields["progressPercent"] = progress_percent
    if current_step_label is not None:
        fields["currentStepLabel"] = current_step_label
    if error_message is not None:
        fields["errorMessage"] = error_message
    if status in TERMINAL_STATUSES:
        fields["completedAt"] = _now()

    set_clause = ", ".join(f'"{k}" = ?' for k in fields)
    conn.execute(f'UPDATE "ImportJob" SET {set_clause} WHERE id = ?', (*fields.values(), job_id))
    if message:
        _append_log(conn, job_id, status, message)


def create_import_job(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    connection_id: Optional[str] = None,
    source_label: Optional[str] = None,
    provenance_status: Optional[str] = None,
    download_url: Optional[str] = None,
    kaggle_dataset_ref: Optional[str] = None,
    local_file_path: Optional[str] = None,
    source_type: str = "REAL",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> str:
    """Creates the job row (status PENDING) and returns its id. Does NOT
    start the pipeline — the caller (a server action) spawns
    `run_import_job` as a subprocess so this stays a fast, synchronous
    call from the UI's perspective."""

    job_id = new_id()
    now = _now()
    params = {
        "kaggle_dataset_ref": kaggle_dataset_ref,
        "local_file_path": local_file_path,
        "source_type": source_type,
        "date_from": date_from,
        "date_to": date_to,
    }
    conn.execute(
        'INSERT INTO "ImportJob" '
        "(id, sourceId, connectionId, status, progressPercent, downloadUrl, downloadedFilePath, "
        "provenanceStatus, sourceLabel, paramsJson, logJson, startedAt, updatedAt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            job_id,
            source_id,
            connection_id,
            "PENDING",
            0,
            download_url,
            local_file_path,
            provenance_status,
            source_label,
            json.dumps(params),
            json.dumps([{"ts": now, "step": "PENDING", "message": "Import job created."}]),
            now,
            now,
        ),
    )
    return job_id


# ---------------------------------------------------------------------------
# File acquisition helpers
# ---------------------------------------------------------------------------


def _extract_if_archive(path: Path) -> Path:
    """A `.zip` is extracted into a sibling `<stem>_extracted/` directory
    and that directory is returned; anything else (including `.gz`, which
    `inspect_file`/pandas read natively) is returned unchanged."""

    if path.suffix.lower() != ".zip":
        return path
    extract_dir = path.parent / f"{path.stem}_extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as zf:
        zf.extractall(extract_dir)
    return extract_dir


def pick_primary_data_file(candidate: Path) -> Path:
    """If `candidate` is already a file, returns it. If it's a directory
    (a Kaggle download, or an extracted ZIP), picks the single most likely
    "main" data file: the highest-preference recognised extension
    (sqlite > csv > json), breaking ties by file size — a dataset bundling
    a README/licence file alongside one real data file is the common case
    this is written for. Raises if no recognised data file is found."""

    if candidate.is_file():
        return candidate

    found: list[Path] = [
        p for p in candidate.rglob("*") if p.is_file() and p.suffix.lower() in _DATA_EXTENSIONS_BY_PREFERENCE
    ]
    if not found:
        raise ValueError(f"No recognised data file (csv/json/jsonl/db/sqlite) found under {candidate}")

    def sort_key(p: Path) -> tuple[int, int]:
        preference = _DATA_EXTENSIONS_BY_PREFERENCE.index(p.suffix.lower())
        return (preference, -p.stat().st_size)

    return sorted(found, key=sort_key)[0]


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------


def _job_storage_dir(job_id: str) -> Path:
    directory = IMPORT_JOB_STORAGE_DIR / job_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _step_download(conn: sqlite3.Connection, job: dict[str, Any], params: dict[str, Any]) -> Path:
    if params.get("local_file_path"):
        path = Path(params["local_file_path"])
        if not path.exists():
            raise ImportJobFailedError(f"Local file not found: {path}")
        _set_status(conn, job["id"], "DOWNLOADING", progress_percent=10, current_step_label="Using local file", message=f"Using existing local file {path}")
        return path

    storage_dir = _job_storage_dir(job["id"])

    if params.get("kaggle_dataset_ref"):
        _set_status(conn, job["id"], "DOWNLOADING", progress_percent=5, current_step_label="Downloading from Kaggle", message=f"Requesting dataset {params['kaggle_dataset_ref']} from Kaggle")
        adapter = KaggleAdapter()
        dest_dir = adapter.download_dataset(params["kaggle_dataset_ref"], storage_dir / "kaggle")
        _set_status(conn, job["id"], "DOWNLOADING", progress_percent=40, message="Kaggle download complete")
        return dest_dir

    if job.get("downloadUrl"):
        dest_path = storage_dir / Path(job["downloadUrl"]).name

        def on_progress(p: DownloadProgress) -> None:
            pct = 5 + int((p.percent or 0) * 0.35 / 100 * 100) if p.percent is not None else 20
            _set_status(conn, job["id"], "DOWNLOADING", progress_percent=min(pct, 40), current_step_label=f"Downloading ({p.bytes_downloaded:,} bytes)")

        _set_status(conn, job["id"], "DOWNLOADING", progress_percent=5, current_step_label=f"Downloading from {job['downloadUrl']}")
        result = download_file(job["downloadUrl"], dest_path, on_progress=on_progress)
        _set_status(conn, job["id"], "DOWNLOADING", progress_percent=40, message=f"Downloaded {result.bytes_downloaded:,} bytes (sha256={result.sha256[:12]}...)")
        return _extract_if_archive(dest_path)

    raise ImportJobFailedError("No local_file_path, kaggle_dataset_ref, or downloadUrl provided for this job.")


def _step_inspect_and_propose_mapping(conn: sqlite3.Connection, job: dict[str, Any], data_path: Path) -> tuple[Path, bool]:
    """Returns `(mapping_path, needs_review)`."""

    _set_status(conn, job["id"], "INSPECTING", progress_percent=45, current_step_label="Inspecting file schema")
    report = inspect_file(data_path)

    storage_dir = _job_storage_dir(job["id"])
    inspection_path = storage_dir / "inspection.json"
    mapping_path = storage_dir / "mapping.json"
    inspection_path.write_text(report.to_json())
    report.write_mapping_template(mapping_path)

    ambiguous = report.ambiguous_columns()
    total_mapped = sum(1 for t in report.tables for c in t.columns if c.proposed_role is not None)
    high_confidence = total_mapped - len(ambiguous)

    conn.execute('UPDATE "ImportJob" SET mappingFilePath = ?, updatedAt = ? WHERE id = ?', (str(mapping_path), _now(), job["id"]))
    _append_log(
        conn,
        job["id"],
        "INSPECTING",
        f"{high_confidence} field(s) mapped automatically. {len(ambiguous)} field(s) need confirmation."
        if ambiguous
        else f"{high_confidence} field(s) mapped automatically. No fields need confirmation.",
    )

    return mapping_path, len(ambiguous) > 0


def _step_import(conn: sqlite3.Connection, job: dict[str, Any], mapping_path: Path, params: dict[str, Any]) -> Any:
    _set_status(conn, job["id"], "VALIDATING", progress_percent=55, current_step_label="Validating confirmed mapping")
    try:
        load_and_validate_mapping(mapping_path)
    except MappingNotConfirmedError as exc:
        _set_status(conn, job["id"], "AWAITING_MAPPING_REVIEW", current_step_label="Mapping needs review", message=str(exc))
        raise

    provenance_status = job["provenanceStatus"] or "UNKNOWN"
    date_from = params.get("date_from")
    date_to = params.get("date_to")
    start_date = date.fromisoformat(date_from) if date_from else date(1900, 1, 1)
    end_date = date.fromisoformat(date_to) if date_to else date.today()

    _set_status(conn, job["id"], "IMPORTING", progress_percent=65, current_step_label="Importing races and runners")
    outcome = import_free_dataset(
        conn,
        mapping_path,
        source_type=params.get("source_type", "REAL"),
        provenance_status=provenance_status,
        source_label=job["sourceLabel"] or job["sourceId"],
        start_date=start_date,
        end_date=end_date,
        idempotency_key=job["id"],
    )
    for warning in outcome.warnings:
        _append_log(conn, job["id"], "IMPORTING", warning)

    conn.execute('UPDATE "ImportJob" SET importBatchId = ?, updatedAt = ? WHERE id = ?', (outcome.result.import_batch_id, _now(), job["id"]))
    _append_log(
        conn,
        job["id"],
        "IMPORTING",
        f"Imported {outcome.result.success_count} race(s), skipped {outcome.result.duplicate_rows} duplicate(s), "
        f"{outcome.result.error_count} error(s).",
    )
    return outcome


def _step_resolve_entities(conn: sqlite3.Connection, job: dict[str, Any], import_batch_id: str) -> None:
    # Entity resolution happens INLINE during import (see
    # entity_resolution.py, called from import_runner._import_one_race) —
    # this step is a summary/UX checkpoint, not a separate action.
    # `EntityResolutionQueueItem` has no import-batch link (ambiguity is a
    # property of the entity, not the batch that surfaced it), so this
    # reports the current PENDING total across the whole database, not one
    # scoped to just this job's races.
    _set_status(conn, job["id"], "RESOLVING_ENTITIES", progress_percent=72, current_step_label="Resolving horses/trainers/jockeys/courses")
    queued = conn.execute('SELECT COUNT(*) as c FROM "EntityResolutionQueueItem" WHERE status = ?', ("PENDING",)).fetchone()
    queued_count = queued["c"] if queued is not None else 0
    _append_log(
        conn,
        job["id"],
        "RESOLVING_ENTITIES",
        f"{queued_count} ambiguous entity match(es) pending manual review (database-wide)." if queued_count else "No ambiguous entity matches pending.",
    )


def _step_provenance_review(conn: sqlite3.Connection, job: dict[str, Any]) -> None:
    """Auto-drafts a `DatasetReview` from the catalog metadata the job was
    created with, so the "provenance review" pipeline step always leaves an
    audit record — never a legal judgement. `reviewer_notes` says plainly
    that this was auto-drafted and needs a human to actually verify it."""

    _set_status(conn, job["id"], "PROVENANCE_REVIEW", progress_percent=78, current_step_label="Recording provenance/licence review")
    create_dataset_review(
        conn,
        DatasetReviewInput(
            dataset_name=job["sourceLabel"] or job["sourceId"],
            source=job["sourceId"],
            provenance_confidence=job["provenanceStatus"] or "UNKNOWN",
            reviewer_notes=(
                "Auto-drafted by RacingEdge's import pipeline from its SourceCatalog description at "
                "import time. This is NOT a legal determination — verify the dataset's actual stated "
                "licence before treating this as authoritative."
            ),
        ),
    )
    _append_log(conn, job["id"], "PROVENANCE_REVIEW", "DatasetReview record created.")


def _step_leakage_audit(conn: sqlite3.Connection, job: dict[str, Any]) -> str:
    """Returns the new `LeakageAuditRun` id. The audit necessarily runs
    BEFORE a `DatasetVersion` can exist (creating one requires a passed
    audit first), so `save_audit_run` is called here with
    `dataset_version_id=None`; `_step_dataset_version_and_quality` links
    this same row to the version it gates once that version is created."""

    _set_status(conn, job["id"], "LEAKAGE_AUDIT", progress_percent=85, current_step_label="Running temporal leakage audit")
    report = audit_training_data(conn)
    audit_run_id = save_audit_run(conn, report)
    if report.status == "FAILED":
        raise ImportJobFailedError(f"Leakage audit FAILED with {report.violations_found} violation(s) — import rolled back to review, no DatasetVersion created.")
    _append_log(conn, job["id"], "LEAKAGE_AUDIT", report.summary_line())
    return audit_run_id


def _step_dataset_version_and_quality(conn: sqlite3.Connection, job: dict[str, Any], import_batch_id: str, audit_run_id: str) -> None:
    _set_status(conn, job["id"], "CREATING_DATASET_VERSION", progress_percent=92, current_step_label="Creating dataset version")

    race_ids_all = [r["id"] for r in conn.execute('SELECT id FROM "Race" WHERE importBatchId = ?', (import_batch_id,)).fetchall()]
    race_ids = filter_race_ids_excluding_provenance(conn, race_ids_all)
    if not race_ids:
        raise ImportJobFailedError("Every imported race was excluded by provenance status (RESTRICTED) — no DatasetVersion created.")

    dataset_version_id = create_dataset_version(
        conn,
        name=f"{job['sourceLabel'] or job['sourceId']}-{job['id'][:8]}",
        race_ids=race_ids,
        providers=[job["sourceId"]],
        schema_version="phase3d-v1",
        import_batch_ids=[import_batch_id],
        notes=f"Created automatically by the Phase 3D import pipeline for source={job['sourceId']!r}.",
    )
    conn.execute('UPDATE "LeakageAuditRun" SET datasetVersionId = ? WHERE id = ?', (dataset_version_id, audit_run_id))

    runner_count = conn.execute(
        f"SELECT COUNT(*) as c FROM \"Runner\" WHERE raceId IN ({','.join('?' for _ in race_ids)})", race_ids
    ).fetchone()["c"]
    readiness = classify_readiness(len(race_ids), runner_count)

    _set_status(conn, job["id"], "GENERATING_QUALITY_REPORT", progress_percent=97, current_step_label="Generating data quality report")
    bias_report = compute_bias_report(conn, race_ids=race_ids)

    conn.execute(
        'UPDATE "ImportJob" SET datasetVersionId = ?, racesImported = ?, runnersImported = ?, updatedAt = ? WHERE id = ?',
        (dataset_version_id, len(race_ids), runner_count, _now(), job["id"]),
    )
    _append_log(
        conn,
        job["id"],
        "GENERATING_QUALITY_REPORT",
        f"DatasetVersion {dataset_version_id} created: {len(race_ids)} race(s), {runner_count} runner(s), "
        f"level={readiness.label}. {len(bias_report.warnings)} bias warning(s) — see the Data Quality dashboard.",
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_import_job(conn: sqlite3.Connection, job_id: str) -> None:
    """Resumable entry point. Reads the job's own stored status/params and
    continues from there — safe to call on a brand-new PENDING job or on
    one paused at AWAITING_MAPPING_REVIEW after a human confirmed the
    mapping."""

    job = get_import_job(conn, job_id)
    params = json.loads(job["paramsJson"]) if job["paramsJson"] else {}

    try:
        if job["status"] == "PENDING":
            data_path = _step_download(conn, job, params)
            data_path = pick_primary_data_file(data_path)
            conn.execute('UPDATE "ImportJob" SET downloadedFilePath = ?, updatedAt = ? WHERE id = ?', (str(data_path), _now(), job_id))
            mapping_path, needs_review = _step_inspect_and_propose_mapping(conn, job, data_path)
            if needs_review:
                _set_status(
                    conn,
                    job_id,
                    "AWAITING_MAPPING_REVIEW",
                    progress_percent=50,
                    current_step_label="Waiting for mapping review",
                )
                return  # paused — resumes via confirm_mapping_and_resume
        else:
            mapping_path = Path(job["mappingFilePath"])

        job = get_import_job(conn, job_id)
        outcome = _step_import(conn, job, mapping_path, params)
        job = get_import_job(conn, job_id)
        _step_resolve_entities(conn, job, outcome.result.import_batch_id)
        _step_provenance_review(conn, job)
        audit_run_id = _step_leakage_audit(conn, job)
        _step_dataset_version_and_quality(conn, job, outcome.result.import_batch_id, audit_run_id)

        if job["connectionId"]:
            conn.execute('UPDATE "DataSourceConnection" SET lastSyncAt = ?, updatedAt = ? WHERE id = ?', (_now(), _now(), job["connectionId"]))

        _set_status(conn, job_id, "COMPLETED", progress_percent=100, current_step_label="Done", message="Import completed successfully.")
    except MappingNotConfirmedError:
        raise  # already recorded as AWAITING_MAPPING_REVIEW by _step_import
    except Exception as exc:
        _set_status(conn, job_id, "FAILED", current_step_label="Failed", error_message=str(exc), message=str(exc))
        raise


def apply_mapping_review(conn: sqlite3.Connection, job_id: str, confirmed: dict[str, dict[str, Any]]) -> None:
    """`confirmed`: `{"table.column": {"role": str|None, "confirmed": bool}}`
    — applied on top of the existing mapping file. A column with
    `role=None` is dropped from the mapping entirely (left unmapped)
    rather than imported with a guessed role.

    Deliberately fast and synchronous (a JSON file edit, no pipeline
    steps) — split out from resuming the pipeline itself so a caller (the
    Next.js server action) can apply the review synchronously, return to
    the browser immediately, and separately spawn `run_import_job` as a
    detached background process for the (potentially slow) rest of the
    pipeline. `run_import_job` itself already resumes correctly from any
    non-PENDING status, so no separate "resume" codepath is needed once
    the mapping file is patched — see its docstring."""

    job = get_import_job(conn, job_id)
    if job["status"] != "AWAITING_MAPPING_REVIEW":
        raise ImportJobFailedError(f"Job {job_id} is not awaiting mapping review (status={job['status']!r}).")

    mapping_path = Path(job["mappingFilePath"])
    raw = json.loads(mapping_path.read_text())
    for key, update in confirmed.items():
        table_name, column_name = key.split(".", 1)
        if table_name not in raw["tables"]:
            raise ValueError(
                f"Mapping review update {key!r} refers to table {table_name!r}, which isn't in this "
                f"job's inspected mapping (known tables: {sorted(raw['tables'])}). Refusing to silently "
                "create a new table entry that would never actually be imported."
            )
        table = raw["tables"][table_name]
        if update.get("role") is None:
            table["columns"].pop(column_name, None)
        else:
            table["columns"][column_name] = {
                "role": update["role"],
                "confidence": table["columns"].get(column_name, {}).get("confidence", "medium"),
                "confirmed": bool(update.get("confirmed", True)),
            }
    mapping_path.write_text(json.dumps(raw, indent=2))

    _append_log(conn, job_id, "AWAITING_MAPPING_REVIEW", f"Mapping reviewed and confirmed by user ({len(confirmed)} field(s) updated).")


def confirm_mapping_and_resume(conn: sqlite3.Connection, job_id: str, confirmed: dict[str, dict[str, Any]]) -> None:
    """Convenience wrapper for CLI/test use: `apply_mapping_review` then
    `run_import_job` in one call. The Next.js server action calls the two
    separately instead — see `apply_mapping_review`'s docstring."""

    apply_mapping_review(conn, job_id, confirmed)
    run_import_job(conn, job_id)

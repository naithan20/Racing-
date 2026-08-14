import csv

import pytest

from racingedge_data import import_pipeline
from racingedge_data.import_pipeline import (
    ImportJobFailedError,
    ImportJobNotFoundError,
    confirm_mapping_and_resume,
    create_import_job,
    get_import_job,
    pick_primary_data_file,
    run_import_job,
)

# All columns below are exact, HIGH-confidence matches in
# racingedge_data.inspector.ROLE_RULES, so a CSV built from this header
# needs no mapping review — the pipeline should run PENDING -> COMPLETED
# in one call.
HIGH_CONFIDENCE_HEADER = [
    "race_date", "race_time", "course", "country", "flat_jumps", "distance", "going",
    "field_size", "horse_name", "draw", "weight", "age", "official_rating", "jockey",
    "trainer", "finishing_position", "starting_price",
]


def _write_csv(path, rows):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HIGH_CONFIDENCE_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _sample_rows():
    return [
        {
            "race_date": "2020-06-01", "race_time": "14:00", "course": "Ascot", "country": "GB",
            "flat_jumps": "FLAT", "distance": "8", "going": "Good", "field_size": "2",
            "horse_name": "Pipeline Horse A", "draw": "1", "weight": "140", "age": "5",
            "official_rating": "80", "jockey": "J Smith", "trainer": "T Trainer",
            "finishing_position": "1", "starting_price": "3.5",
        },
        {
            "race_date": "2020-06-01", "race_time": "14:00", "course": "Ascot", "country": "GB",
            "flat_jumps": "FLAT", "distance": "8", "going": "Good", "field_size": "2",
            "horse_name": "Pipeline Horse B", "draw": "2", "weight": "138", "age": "4",
            "official_rating": "75", "jockey": "J Doe", "trainer": "T Trainer",
            "finishing_position": "2", "starting_price": "2.1",
        },
    ]


@pytest.fixture(autouse=True)
def _isolated_job_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(import_pipeline, "IMPORT_JOB_STORAGE_DIR", tmp_path / "job_storage")


class TestPickPrimaryDataFile:
    def test_returns_file_directly(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b\n1,2\n")
        assert pick_primary_data_file(f) == f

    def test_prefers_sqlite_over_csv_in_a_directory(self, tmp_path):
        (tmp_path / "readme.txt").write_text("not data")
        (tmp_path / "data.csv").write_text("a,b\n1,2\n")
        (tmp_path / "data.db").write_bytes(b"fake sqlite bytes")
        assert pick_primary_data_file(tmp_path).name == "data.db"

    def test_raises_when_no_recognised_data_file(self, tmp_path):
        (tmp_path / "readme.txt").write_text("not data")
        with pytest.raises(ValueError, match="No recognised data file"):
            pick_primary_data_file(tmp_path)


class TestGetImportJob:
    def test_raises_for_unknown_job(self, tmp_db_conn):
        with pytest.raises(ImportJobNotFoundError):
            get_import_job(tmp_db_conn, "does-not-exist")


class TestRunImportJobHappyPath:
    def test_local_csv_with_all_high_confidence_columns_completes_without_review(self, tmp_db_conn, tmp_path):
        csv_path = tmp_path / "races.csv"
        _write_csv(csv_path, _sample_rows())

        job_id = create_import_job(
            tmp_db_conn,
            source_id="local-file",
            source_label="Pipeline test dataset",
            provenance_status="USER_SUPPLIED",
            local_file_path=str(csv_path),
        )
        tmp_db_conn.commit()

        run_import_job(tmp_db_conn, job_id)
        tmp_db_conn.commit()

        job = get_import_job(tmp_db_conn, job_id)
        assert job["status"] == "COMPLETED"
        assert job["progressPercent"] == 100
        assert job["racesImported"] == 1
        assert job["runnersImported"] == 2
        assert job["datasetVersionId"] is not None
        assert job["importBatchId"] is not None

        log = job["logJson"]
        assert log is not None and "LEAKAGE AUDIT PASSED" in log

        review = tmp_db_conn.execute(
            'SELECT * FROM "DatasetReview" WHERE datasetName = ?', ("Pipeline test dataset",)
        ).fetchone()
        assert review is not None
        assert review["provenanceConfidence"] == "USER_SUPPLIED"

    def test_leakage_audit_run_is_linked_to_the_dataset_version(self, tmp_db_conn, tmp_path):
        csv_path = tmp_path / "races.csv"
        _write_csv(csv_path, _sample_rows())
        job_id = create_import_job(
            tmp_db_conn, source_id="local-file", provenance_status="USER_SUPPLIED", local_file_path=str(csv_path)
        )
        tmp_db_conn.commit()
        run_import_job(tmp_db_conn, job_id)
        tmp_db_conn.commit()

        job = get_import_job(tmp_db_conn, job_id)
        audit_run = tmp_db_conn.execute(
            'SELECT * FROM "LeakageAuditRun" WHERE datasetVersionId = ?', (job["datasetVersionId"],)
        ).fetchone()
        assert audit_run is not None
        assert audit_run["status"] == "PASSED"

    def test_missing_source_fails_cleanly(self, tmp_db_conn):
        job_id = create_import_job(tmp_db_conn, source_id="local-file")
        tmp_db_conn.commit()

        with pytest.raises(ImportJobFailedError):
            run_import_job(tmp_db_conn, job_id)

        job = get_import_job(tmp_db_conn, job_id)
        assert job["status"] == "FAILED"
        assert job["errorMessage"]


class TestMappingReviewPause:
    def _write_ambiguous_csv(self, path):
        # Same shape as the happy-path fixture, but "official_rating" is
        # renamed to the abbreviation "or" — a LOW-confidence match, so the
        # pipeline must pause rather than guess.
        header = [h if h != "official_rating" else "or" for h in HIGH_CONFIDENCE_HEADER]
        rows = []
        for row in _sample_rows():
            new_row = dict(row)
            new_row["or"] = new_row.pop("official_rating")
            rows.append(new_row)
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def test_ambiguous_column_pauses_for_review(self, tmp_db_conn, tmp_path):
        csv_path = tmp_path / "races.csv"
        self._write_ambiguous_csv(csv_path)

        job_id = create_import_job(
            tmp_db_conn, source_id="local-file", provenance_status="USER_SUPPLIED", local_file_path=str(csv_path)
        )
        tmp_db_conn.commit()

        run_import_job(tmp_db_conn, job_id)
        tmp_db_conn.commit()

        job = get_import_job(tmp_db_conn, job_id)
        assert job["status"] == "AWAITING_MAPPING_REVIEW"
        assert job["mappingFilePath"] is not None
        assert job["datasetVersionId"] is None

    def test_confirming_mapping_resumes_to_completion(self, tmp_db_conn, tmp_path):
        csv_path = tmp_path / "races.csv"
        self._write_ambiguous_csv(csv_path)

        job_id = create_import_job(
            tmp_db_conn, source_id="local-file", provenance_status="USER_SUPPLIED", local_file_path=str(csv_path)
        )
        tmp_db_conn.commit()
        run_import_job(tmp_db_conn, job_id)
        tmp_db_conn.commit()

        confirm_mapping_and_resume(
            tmp_db_conn, job_id, {"races.or": {"role": "official_rating", "confirmed": True}}
        )
        tmp_db_conn.commit()

        job = get_import_job(tmp_db_conn, job_id)
        assert job["status"] == "COMPLETED"
        assert job["racesImported"] == 1
        assert job["runnersImported"] == 2

    def test_confirm_mapping_requires_awaiting_status(self, tmp_db_conn, tmp_path):
        csv_path = tmp_path / "races.csv"
        _write_csv(csv_path, _sample_rows())
        job_id = create_import_job(tmp_db_conn, source_id="local-file", local_file_path=str(csv_path))
        tmp_db_conn.commit()

        with pytest.raises(ImportJobFailedError, match="not awaiting mapping review"):
            confirm_mapping_and_resume(tmp_db_conn, job_id, {})

    def test_mismatched_table_name_raises_rather_than_silently_creating_a_phantom_table(self, tmp_db_conn, tmp_path):
        csv_path = tmp_path / "races.csv"
        self._write_ambiguous_csv(csv_path)
        job_id = create_import_job(
            tmp_db_conn, source_id="local-file", provenance_status="USER_SUPPLIED", local_file_path=str(csv_path)
        )
        tmp_db_conn.commit()
        run_import_job(tmp_db_conn, job_id)
        tmp_db_conn.commit()

        with pytest.raises(ValueError, match="isn't in this job's inspected mapping"):
            confirm_mapping_and_resume(
                tmp_db_conn, job_id, {"not_a_real_table.or": {"role": "official_rating", "confirmed": True}}
            )

        # The job must still be resumable with the CORRECT key after the
        # bad one was rejected — the failed attempt shouldn't have
        # corrupted the mapping file.
        job = get_import_job(tmp_db_conn, job_id)
        assert job["status"] == "AWAITING_MAPPING_REVIEW"
        confirm_mapping_and_resume(tmp_db_conn, job_id, {"races.or": {"role": "official_rating", "confirmed": True}})
        tmp_db_conn.commit()
        assert get_import_job(tmp_db_conn, job_id)["status"] == "COMPLETED"

    def test_dropping_a_column_via_role_none_leaves_it_unmapped(self, tmp_db_conn, tmp_path):
        csv_path = tmp_path / "races.csv"
        self._write_ambiguous_csv(csv_path)
        job_id = create_import_job(
            tmp_db_conn, source_id="local-file", provenance_status="USER_SUPPLIED", local_file_path=str(csv_path)
        )
        tmp_db_conn.commit()
        run_import_job(tmp_db_conn, job_id)
        tmp_db_conn.commit()

        confirm_mapping_and_resume(tmp_db_conn, job_id, {"races.or": {"role": None}})
        tmp_db_conn.commit()

        job = get_import_job(tmp_db_conn, job_id)
        assert job["status"] == "COMPLETED"
        # official_rating was dropped, not guessed — the imported runners
        # simply have no officialRating value.
        runners = tmp_db_conn.execute(
            'SELECT officialRating FROM "Runner" ru JOIN "Race" r ON r.id = ru.raceId WHERE r.importBatchId = ?',
            (get_import_job(tmp_db_conn, job_id)["importBatchId"],),
        ).fetchall()
        assert all(r["officialRating"] is None for r in runners)

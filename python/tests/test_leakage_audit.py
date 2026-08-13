import json

import pandas as pd

from racingedge_data.leakage_audit import audit_history_frame, audit_training_data, save_audit_run
from racingedge_model.db import to_prisma_datetime
from racingedge_model.ids import new_id


class TestAuditHistoryFrameBoundary:
    def test_row_dated_exactly_at_race_start_is_a_violation(self):
        race_start = pd.Timestamp("2026-01-01T14:00:00", tz="UTC")
        frame = pd.DataFrame({"raceDate": [race_start]})
        violations = audit_history_frame(frame, "race-1", "runner-1", race_start, "FormEntry")
        assert len(violations) == 1

    def test_row_strictly_before_race_start_is_not_a_violation(self):
        race_start = pd.Timestamp("2026-01-01T14:00:00", tz="UTC")
        frame = pd.DataFrame({"raceDate": [race_start - pd.Timedelta(seconds=1)]})
        violations = audit_history_frame(frame, "race-1", "runner-1", race_start, "FormEntry")
        assert violations == []

    def test_collects_every_violating_row_not_just_the_first(self):
        race_start = pd.Timestamp("2026-01-01T14:00:00", tz="UTC")
        frame = pd.DataFrame(
            {
                "raceDate": [
                    race_start - pd.Timedelta(days=1),  # fine
                    race_start,  # violation
                    race_start + pd.Timedelta(days=1),  # violation
                ]
            }
        )
        violations = audit_history_frame(frame, "race-1", "runner-1", race_start, "FormEntry")
        assert len(violations) == 2


class TestAuditTrainingDataOnCleanDatabase:
    def test_unmodified_database_passes(self, tmp_db_conn):
        report = audit_training_data(tmp_db_conn)
        assert report.status == "PASSED"
        assert report.violations_found == 0
        assert report.features_checked > 0
        assert "PASSED" in report.summary_line()


class TestAuditDetectsInjectedFutureData:
    def test_future_dated_form_entry_is_correctly_excluded_by_the_pipelines_own_filter(self, tmp_db_conn):
        # A FormEntry row dated AFTER a race is exactly what the training
        # pipeline's own `raceDate < as_of_date` filter is supposed to
        # exclude before that race's features are ever computed — so this
        # should NOT show up as a violation (it never reaches feature
        # computation for THIS race in the first place). This confirms the
        # auditor replicates the pipeline's real filtering behaviour rather
        # than flagging every future row a horse ever accumulates, which
        # would make every multi-race horse "fail" trivially.
        race_row = tmp_db_conn.execute(
            'SELECT * FROM "Race" WHERE raceStatus = \'RESULTED\' ORDER BY date ASC LIMIT 1'
        ).fetchone()
        runner_row = tmp_db_conn.execute(
            'SELECT * FROM "Runner" WHERE raceId = ? LIMIT 1', (race_row["id"],)
        ).fetchone()

        future_date = pd.Timestamp(race_row["date"]) + pd.Timedelta(days=30)
        tmp_db_conn.execute(
            'INSERT INTO "FormEntry" '
            "(id, isSampleData, horseId, raceDate, course, finishingPosition, fieldSize, createdAt) "
            "VALUES (?, 0, ?, ?, 'Fixture Future Course', 1, 8, ?)",
            (
                new_id(),
                runner_row["horseId"],
                to_prisma_datetime(future_date.to_pydatetime()),
                to_prisma_datetime(future_date.to_pydatetime()),
            ),
        )
        tmp_db_conn.commit()

        report = audit_training_data(tmp_db_conn)
        assert report.status == "PASSED"

    def test_self_referencing_form_entry_is_flagged_regardless_of_its_date(self, tmp_db_conn):
        # The genuinely dangerous malicious case: a FormEntry row that is
        # BACKDATED to look like legitimate prior history (so a date-only
        # filter would let it through) but actually references the SAME
        # race currently being predicted via linkedRaceId — i.e. the
        # target race's own outcome, disguised as "history". This is the
        # kind of leak a naive date check cannot catch.
        race_row = tmp_db_conn.execute(
            'SELECT * FROM "Race" WHERE raceStatus = \'RESULTED\' ORDER BY date ASC LIMIT 1'
        ).fetchone()
        assert race_row is not None
        runner_row = tmp_db_conn.execute(
            'SELECT * FROM "Runner" WHERE raceId = ? LIMIT 1', (race_row["id"],)
        ).fetchone()
        assert runner_row is not None

        backdated = pd.Timestamp(race_row["date"]) - pd.Timedelta(days=1)
        tmp_db_conn.execute(
            'INSERT INTO "FormEntry" '
            "(id, isSampleData, horseId, linkedRaceId, raceDate, course, finishingPosition, fieldSize, createdAt) "
            "VALUES (?, 0, ?, ?, ?, 'Fixture Self-Reference Course', 1, 8, ?)",
            (
                new_id(),
                runner_row["horseId"],
                race_row["id"],
                to_prisma_datetime(backdated.to_pydatetime()),
                to_prisma_datetime(backdated.to_pydatetime()),
            ),
        )
        tmp_db_conn.commit()

        report = audit_training_data(tmp_db_conn)

        assert report.status == "FAILED"
        assert report.violations_found > 0
        assert any(
            v.race_id == race_row["id"] and v.source == "FormEntry.linkedRaceId" for v in report.violations
        )
        assert "FAILED" in report.summary_line()


class TestSaveAuditRun:
    def test_persists_report_and_is_readable(self, tmp_db_conn):
        report = audit_training_data(tmp_db_conn)
        audit_id = save_audit_run(tmp_db_conn, report)
        tmp_db_conn.commit()

        row = tmp_db_conn.execute('SELECT * FROM "LeakageAuditRun" WHERE id = ?', (audit_id,)).fetchone()
        assert row is not None
        assert row["status"] == report.status
        assert row["violationsFound"] == report.violations_found
        parsed = json.loads(row["reportJson"])
        assert parsed["status"] == report.status

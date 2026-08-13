import io

from racingedge_data.importers.import_runner import import_races
from racingedge_data.providers.csv_provider import CsvRaceDataProvider

CSV_HEADER = (
    "provider_race_id,date,race_time,racecourse,country,race_name,flat_jumps,surface,"
    "distance_furlongs,handicap_type,number_of_runners,going,runner_provider_id,horse_name,"
    "horse_provider_id,draw,official_rating,jockey_name,trainer_name,non_runner\n"
)


def _csv(rows: list[str]) -> io.StringIO:
    return io.StringIO(CSV_HEADER + "".join(rows))


def _row(race_id, date, course, race_name, runner_id, horse_name, horse_provider_id="h1"):
    return (
        f"{race_id},{date},14:00,{course},GB,{race_name},FLAT,TURF,8.0,NON_HANDICAP,1,Good,"
        f"{runner_id},{horse_name},{horse_provider_id},3,80,Jockey One,Trainer One,false\n"
    )


class TestImportRacesBasics:
    def test_imports_races_runners_and_horses(self, tmp_db_conn):
        csv_data = _csv(
            [
                _row("imp-race-1", "2026-04-01T14:00:00", "Fixture Course", "Fixture Stakes", "r1", "Fixture Horse A"),
            ]
        )
        provider = CsvRaceDataProvider(csv_data)

        from datetime import date

        result = import_races(
            tmp_db_conn,
            provider,
            date(2026, 1, 1),
            date(2026, 12, 31),
            source_type="REAL",
        )

        assert result.status == "SUCCESS"
        assert result.success_count == 1
        assert result.duplicate_rows == 0
        assert result.error_count == 0

        race_row = tmp_db_conn.execute(
            'SELECT * FROM "Race" WHERE raceName = ?', ("Fixture Stakes",)
        ).fetchone()
        assert race_row is not None
        assert race_row["sourceType"] == "REAL"

        runner_row = tmp_db_conn.execute(
            'SELECT * FROM "Runner" WHERE raceId = ?', (race_row["id"],)
        ).fetchone()
        assert runner_row is not None

        horse_row = tmp_db_conn.execute(
            'SELECT * FROM "Horse" WHERE id = ?', (runner_row["horseId"],)
        ).fetchone()
        assert horse_row["name"] == "Fixture Horse A"
        assert horse_row["sourceType"] == "REAL"

        provenance_row = tmp_db_conn.execute(
            'SELECT * FROM "DataProvenance" WHERE entityId = ? AND entityType = ?',
            (race_row["id"], "Race"),
        ).fetchone()
        assert provenance_row is not None
        assert provenance_row["providerRecordId"] == "imp-race-1"

    def test_rejects_invalid_source_type(self, tmp_db_conn):
        import pytest
        from datetime import date

        provider = CsvRaceDataProvider(_csv([]))
        with pytest.raises(ValueError):
            import_races(tmp_db_conn, provider, date(2026, 1, 1), date(2026, 12, 31), source_type="BOGUS")


class TestDuplicateHandling:
    def test_reimporting_same_provider_race_id_is_marked_duplicate(self, tmp_db_conn):
        from datetime import date

        row = _row("imp-race-dup", "2026-04-02T14:00:00", "Fixture Course", "Fixture Dup Race", "r1", "Fixture Horse B")

        first = import_races(
            tmp_db_conn, CsvRaceDataProvider(_csv([row])), date(2026, 1, 1), date(2026, 12, 31), source_type="REAL"
        )
        assert first.success_count == 1

        second = import_races(
            tmp_db_conn, CsvRaceDataProvider(_csv([row])), date(2026, 1, 1), date(2026, 12, 31), source_type="REAL"
        )
        assert second.success_count == 0
        assert second.duplicate_rows == 1

        race_count = tmp_db_conn.execute(
            'SELECT COUNT(*) as c FROM "Race" WHERE raceName = ?', ("Fixture Dup Race",)
        ).fetchone()["c"]
        assert race_count == 1


class TestIdempotency:
    def test_same_idempotency_key_short_circuits_second_run(self, tmp_db_conn):
        from datetime import date

        row = _row("imp-race-idem", "2026-04-03T14:00:00", "Fixture Course", "Fixture Idem Race", "r1", "Fixture Horse C")

        first = import_races(
            tmp_db_conn,
            CsvRaceDataProvider(_csv([row])),
            date(2026, 1, 1),
            date(2026, 12, 31),
            source_type="REAL",
            idempotency_key="idem-key-1",
        )
        assert first.status == "SUCCESS"

        batch_count_before = tmp_db_conn.execute('SELECT COUNT(*) as c FROM "ImportBatch"').fetchone()["c"]

        second = import_races(
            tmp_db_conn,
            CsvRaceDataProvider(_csv([row])),
            date(2026, 1, 1),
            date(2026, 12, 31),
            source_type="REAL",
            idempotency_key="idem-key-1",
        )
        assert second.import_batch_id == first.import_batch_id

        batch_count_after = tmp_db_conn.execute('SELECT COUNT(*) as c FROM "ImportBatch"').fetchone()["c"]
        assert batch_count_after == batch_count_before  # no new batch created


class TestFailedRowReporting:
    def test_a_bad_race_is_logged_and_does_not_abort_the_batch(self, tmp_db_conn):
        from datetime import date

        good_row = _row(
            "imp-race-good", "2026-04-04T14:00:00", "Fixture Course", "Fixture Good Race", "r1", "Fixture Horse D"
        )
        # Missing racecourse -> _import_one_race raises ValueError.
        bad_row = (
            "imp-race-bad,2026-04-05T14:00:00,14:00,,GB,Fixture Bad Race,FLAT,TURF,8.0,NON_HANDICAP,1,"
            "Good,r2,Fixture Horse E,h2,3,80,Jockey One,Trainer One,false\n"
        )

        result = import_races(
            tmp_db_conn,
            CsvRaceDataProvider(_csv([good_row, bad_row])),
            date(2026, 1, 1),
            date(2026, 12, 31),
            source_type="REAL",
        )

        assert result.status == "PARTIAL"
        assert result.success_count == 1
        assert result.error_count == 1
        assert len(result.errors) == 1
        assert result.errors[0].provider_race_id == "imp-race-bad"

        good_race = tmp_db_conn.execute(
            'SELECT * FROM "Race" WHERE raceName = ?', ("Fixture Good Race",)
        ).fetchone()
        assert good_race is not None

        bad_race = tmp_db_conn.execute(
            'SELECT * FROM "Race" WHERE raceName = ?', ("Fixture Bad Race",)
        ).fetchone()
        assert bad_race is None


class TestResume:
    def test_resume_from_batch_id_skips_already_processed_races(self, tmp_db_conn):
        from datetime import date

        row_a = _row(
            "imp-race-resume-a", "2026-04-06T14:00:00", "Fixture Course", "Fixture Resume A", "r1", "Fixture Horse F"
        )
        row_b = _row(
            "imp-race-resume-b", "2026-04-07T14:00:00", "Fixture Course", "Fixture Resume B", "r2", "Fixture Horse G"
        )

        # Simulate a batch that was interrupted after processing race index 0.
        from racingedge_data.importers.import_runner import _now
        from racingedge_model.ids import new_id

        batch_id = new_id()
        tmp_db_conn.execute(
            'INSERT INTO "ImportBatch" '
            "(id, sourceType, status, rowCount, successCount, errorCount, totalRows, processedRows, "
            "duplicateRows, providerName, resumeCursor, importedAt) "
            "VALUES (?, 'CSV', 'IN_PROGRESS', 0, 1, 0, NULL, 1, 0, 'csv', '1', ?)",
            (batch_id, _now()),
        )
        tmp_db_conn.commit()

        result = import_races(
            tmp_db_conn,
            CsvRaceDataProvider(_csv([row_a, row_b])),
            date(2026, 1, 1),
            date(2026, 12, 31),
            source_type="REAL",
            resume_from_batch_id=batch_id,
        )

        assert result.import_batch_id == batch_id
        # success_count carries forward the pre-resume count (1, from the
        # simulated interrupted run) plus this run's newly-processed race_b.
        assert result.success_count == 2
        assert result.processed_rows == 2

        race_a = tmp_db_conn.execute('SELECT * FROM "Race" WHERE raceName = ?', ("Fixture Resume A",)).fetchone()
        race_b = tmp_db_conn.execute('SELECT * FROM "Race" WHERE raceName = ?', ("Fixture Resume B",)).fetchone()
        assert race_a is None  # was skipped, since resumeCursor said it was already done
        assert race_b is not None

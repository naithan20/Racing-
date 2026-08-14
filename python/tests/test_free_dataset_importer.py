import io
import json
import sqlite3
from datetime import date

import pytest

from racingedge_data.dataset_version import filter_race_ids_excluding_provenance
from racingedge_data.importers.free_dataset_importer import (
    MappingNotConfirmedError,
    import_free_dataset,
    load_and_validate_mapping,
)
from racingedge_data.inspector import inspect_file


def _build_wide_sqlite(path):
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE races (race_id TEXT, race_date TEXT, course TEXT, race_name TEXT, "
        "distance_f REAL, going TEXT, horse_name TEXT, jockey TEXT, trainer TEXT, draw INTEGER, "
        "or_rating INTEGER, finish_pos INTEGER, sp REAL)"
    )
    conn.executemany(
        "INSERT INTO races VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("r1", "2021-04-01", "Fixture Park", "Fixture Maiden Stakes", 8.0, "Good",
             "Fixture Horse A", "Fixture Jockey A", "Fixture Trainer A", 3, 80, 1, 4.5),
            ("r1", "2021-04-01", "Fixture Park", "Fixture Maiden Stakes", 8.0, "Good",
             "Fixture Horse B", "Fixture Jockey B", "Fixture Trainer B", 5, 75, 2, 6.0),
            ("r2", "2021-04-15", "Fixture Downs", "Fixture Handicap", 10.0, "Soft",
             "Fixture Horse C", "Fixture Jockey C", "Fixture Trainer C", 1, 90, 1, 2.5),
        ],
    )
    conn.commit()
    conn.close()


def _confirm_all(mapping_path):
    mapping = json.loads(mapping_path.read_text())
    for table in mapping["tables"].values():
        for col in table["columns"].values():
            col["confirmed"] = True
    mapping_path.write_text(json.dumps(mapping))


class TestLoadAndValidateMapping:
    def test_raises_on_unconfirmed_ambiguous_columns(self, tmp_path):
        db_path = tmp_path / "fixture.db"
        _build_wide_sqlite(db_path)
        report = inspect_file(db_path)
        mapping_path = tmp_path / "mapping.json"
        report.write_mapping_template(mapping_path)

        with pytest.raises(MappingNotConfirmedError, match="sp"):
            load_and_validate_mapping(mapping_path)

    def test_succeeds_once_confirmed(self, tmp_path):
        db_path = tmp_path / "fixture.db"
        _build_wide_sqlite(db_path)
        report = inspect_file(db_path)
        mapping_path = tmp_path / "mapping.json"
        report.write_mapping_template(mapping_path)
        _confirm_all(mapping_path)

        mapping = load_and_validate_mapping(mapping_path)
        assert mapping.source_format == "sqlite"
        assert "races" in mapping.tables
        assert mapping.tables["races"].role_to_column["horse_name"] == "horse_name"


class TestImportFreeDatasetWideTable(object):
    def test_imports_races_runners_and_results(self, tmp_path, tmp_db_conn):
        db_path = tmp_path / "fixture.db"
        _build_wide_sqlite(db_path)
        report = inspect_file(db_path)
        mapping_path = tmp_path / "mapping.json"
        report.write_mapping_template(mapping_path)
        _confirm_all(mapping_path)

        outcome = import_free_dataset(
            tmp_db_conn,
            mapping_path,
            source_type="REAL",
            provenance_status="COMMUNITY_UNVERIFIED",
            source_label="Fixture Test Dataset",
            start_date=date(2000, 1, 1),
            end_date=date(2030, 1, 1),
        )
        tmp_db_conn.commit()

        assert outcome.result.success_count == 2  # 2 distinct races
        assert any("COMMUNITY_UNVERIFIED" in w for w in outcome.warnings)

        race_row = tmp_db_conn.execute('SELECT * FROM "Race" WHERE raceName = ?', ("Fixture Maiden Stakes",)).fetchone()
        assert race_row is not None
        assert race_row["sourceType"] == "REAL"

        runner_rows = tmp_db_conn.execute('SELECT * FROM "Runner" WHERE raceId = ?', (race_row["id"],)).fetchall()
        assert len(runner_rows) == 2

        result_rows = tmp_db_conn.execute(
            'SELECT * FROM "ResultEntry" WHERE runnerId IN (SELECT id FROM "Runner" WHERE raceId = ?)',
            (race_row["id"],),
        ).fetchall()
        assert len(result_rows) == 2
        positions = sorted(r["finishingPosition"] for r in result_rows)
        assert positions == [1, 2]

        provenance_row = tmp_db_conn.execute(
            'SELECT * FROM "DataProvenance" WHERE entityId = ? AND entityType = ?', (race_row["id"], "Race")
        ).fetchone()
        assert provenance_row["provenanceStatus"] == "COMMUNITY_UNVERIFIED"
        assert provenance_row["sourceUrl"] == "Fixture Test Dataset"

    def test_rejects_invalid_provenance_status(self, tmp_path, tmp_db_conn):
        db_path = tmp_path / "fixture.db"
        _build_wide_sqlite(db_path)
        report = inspect_file(db_path)
        mapping_path = tmp_path / "mapping.json"
        report.write_mapping_template(mapping_path)
        _confirm_all(mapping_path)

        with pytest.raises(ValueError, match="provenance_status"):
            import_free_dataset(
                tmp_db_conn,
                mapping_path,
                source_type="REAL",
                provenance_status="TOTALLY_MADE_UP",
                source_label="Fixture Test Dataset",
                start_date=date(2000, 1, 1),
                end_date=date(2030, 1, 1),
            )

    def test_restricted_provenance_is_excluded_from_training_by_default(self, tmp_path, tmp_db_conn):
        db_path = tmp_path / "fixture.db"
        _build_wide_sqlite(db_path)
        report = inspect_file(db_path)
        mapping_path = tmp_path / "mapping.json"
        report.write_mapping_template(mapping_path)
        _confirm_all(mapping_path)

        outcome = import_free_dataset(
            tmp_db_conn,
            mapping_path,
            source_type="REAL",
            provenance_status="RESTRICTED",
            source_label="Fixture Restricted Dataset",
            start_date=date(2000, 1, 1),
            end_date=date(2030, 1, 1),
        )
        tmp_db_conn.commit()
        assert any("RESTRICTED" in w for w in outcome.warnings)

        race_rows = tmp_db_conn.execute(
            'SELECT id FROM "Race" WHERE raceName IN (?, ?)', ("Fixture Maiden Stakes", "Fixture Handicap")
        ).fetchall()
        race_ids = [r["id"] for r in race_rows]
        assert len(race_ids) == 2

        filtered = filter_race_ids_excluding_provenance(tmp_db_conn, race_ids)
        assert filtered == []


class TestImportFreeDatasetCsv:
    def test_imports_from_csv(self, tmp_path, tmp_db_conn):
        csv_path = tmp_path / "fixture.csv"
        csv_path.write_text(
            "race_date,course,race_name,distance_f,going,horse_name,jockey,trainer,draw,or,finish_pos,sp\n"
            "2022-02-01,Fixture Park,Fixture Novice Stakes,7.0,Good to Firm,Fixture Horse D,"
            "Fixture Jockey D,Fixture Trainer D,2,70,1,3.0\n"
        )
        report = inspect_file(csv_path)
        mapping_path = tmp_path / "mapping.json"
        report.write_mapping_template(mapping_path)
        _confirm_all(mapping_path)

        outcome = import_free_dataset(
            tmp_db_conn,
            mapping_path,
            source_type="REAL",
            provenance_status="VERIFIED_OPEN",
            source_label="Fixture CSV Dataset",
            start_date=date(2000, 1, 1),
            end_date=date(2030, 1, 1),
        )
        assert outcome.result.success_count == 1
        assert outcome.warnings == []


class TestImportFreeDatasetTwoTable:
    def test_joins_race_and_runner_tables_on_race_id(self, tmp_path, tmp_db_conn):
        db_path = tmp_path / "fixture_two_table.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE races (race_id TEXT, race_date TEXT, course TEXT, race_name TEXT)")
        conn.execute("CREATE TABLE runners (race_id TEXT, horse_name TEXT, jockey TEXT, finish_pos INTEGER)")
        conn.execute("INSERT INTO races VALUES ('r1', '2023-05-01', 'Fixture Course', 'Fixture Race')")
        conn.execute("INSERT INTO runners VALUES ('r1', 'Fixture Horse E', 'Fixture Jockey E', 1)")
        conn.commit()
        conn.close()

        report = inspect_file(db_path)
        mapping_path = tmp_path / "mapping.json"
        report.write_mapping_template(mapping_path)
        _confirm_all(mapping_path)

        outcome = import_free_dataset(
            tmp_db_conn,
            mapping_path,
            source_type="REAL",
            provenance_status="USER_SUPPLIED",
            source_label="Fixture Two-Table Dataset",
            start_date=date(2000, 1, 1),
            end_date=date(2030, 1, 1),
        )
        assert outcome.result.success_count == 1

        race_row = tmp_db_conn.execute('SELECT * FROM "Race" WHERE raceName = ?', ("Fixture Race",)).fetchone()
        assert race_row is not None
        runner_row = tmp_db_conn.execute('SELECT * FROM "Runner" WHERE raceId = ?', (race_row["id"],)).fetchone()
        assert runner_row is not None

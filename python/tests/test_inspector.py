import json
import sqlite3
from datetime import date

import pytest

from racingedge_data.inspector import inspect_file, normalize_column_name, propose_role


class TestNormalizeColumnName:
    def test_lowercases_and_replaces_punctuation(self):
        assert normalize_column_name("Race Date") == "race_date"
        assert normalize_column_name("Horse-Name") == "horse_name"
        assert normalize_column_name("OR") == "or"


class TestProposeRole:
    def test_exact_match_is_high_confidence(self):
        role, confidence = propose_role("horse_name")
        assert role == "horse_name"
        assert confidence == "high"

    def test_partial_match_is_medium_confidence(self):
        role, confidence = propose_role("horse_id_number")
        assert role == "horse_id"
        assert confidence == "medium"

    def test_ambiguous_abbreviation_is_low_confidence(self):
        role, confidence = propose_role("or")
        assert role == "official_rating"
        assert confidence == "low"

    def test_unrecognized_column_is_unmapped(self):
        role, confidence = propose_role("some_totally_unrelated_column_xyz")
        assert role is None
        assert confidence == "unmapped"


class TestInspectFileMissing:
    def test_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            inspect_file(tmp_path / "does_not_exist.db")

    def test_raises_on_unrecognized_extension(self, tmp_path):
        path = tmp_path / "data.txt"
        path.write_text("not a real format")
        with pytest.raises(ValueError, match="Unrecognized file type"):
            inspect_file(path)


class TestInspectSqlite:
    def _build_fixture_db(self, path):
        conn = sqlite3.connect(str(path))
        conn.execute(
            "CREATE TABLE races (race_id TEXT, race_date TEXT, course TEXT, race_name TEXT, "
            "distance_f REAL, going TEXT, race_class INTEGER)"
        )
        conn.execute(
            "CREATE TABLE runners (race_id TEXT, horse_name TEXT, jockey TEXT, trainer TEXT, "
            "draw INTEGER, or_rating INTEGER, finish_pos INTEGER, sp REAL)"
        )
        conn.executemany(
            "INSERT INTO races VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("r1", "2020-01-01", "Fixture Park", "Fixture Maiden Stakes", 8.0, "Good", 4),
                ("r2", "2020-06-15", "Fixture Downs", "Fixture Handicap", 10.0, "Soft", 3),
            ],
        )
        conn.executemany(
            "INSERT INTO runners VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("r1", "Fixture Horse A", "Fixture Jockey A", "Fixture Trainer A", 3, 80, 1, 4.5),
                ("r1", "Fixture Horse B", "Fixture Jockey B", "Fixture Trainer B", 5, 75, 2, 6.0),
                ("r2", "Fixture Horse C", "Fixture Jockey C", "Fixture Trainer C", 1, 90, 1, 2.5),
            ],
        )
        conn.commit()
        conn.close()

    def test_detects_tables_and_row_counts(self, tmp_path):
        db_path = tmp_path / "fixture_raceform.db"
        self._build_fixture_db(db_path)

        report = inspect_file(db_path)
        assert report.source_format == "sqlite"
        table_names = {t.name for t in report.tables}
        assert table_names == {"races", "runners"}

        races_table = next(t for t in report.tables if t.name == "races")
        runners_table = next(t for t in report.tables if t.name == "runners")
        assert races_table.row_count == 2
        assert runners_table.row_count == 3

    def test_classifies_race_and_runner_level_tables(self, tmp_path):
        db_path = tmp_path / "fixture_raceform.db"
        self._build_fixture_db(db_path)
        report = inspect_file(db_path)

        races_table = next(t for t in report.tables if t.name == "races")
        runners_table = next(t for t in report.tables if t.name == "runners")
        assert races_table.likely_kind == "race_level"
        assert runners_table.likely_kind == "runner_level"

    def test_proposes_high_confidence_roles_for_clear_columns(self, tmp_path):
        db_path = tmp_path / "fixture_raceform.db"
        self._build_fixture_db(db_path)
        report = inspect_file(db_path)

        races_table = next(t for t in report.tables if t.name == "races")
        course_col = next(c for c in races_table.columns if c.name == "course")
        assert course_col.proposed_role == "course"
        assert course_col.confidence == "high"

        runners_table = next(t for t in report.tables if t.name == "runners")
        horse_col = next(c for c in runners_table.columns if c.name == "horse_name")
        assert horse_col.proposed_role == "horse_name"
        assert horse_col.confidence == "high"

    def test_flags_ambiguous_columns_for_review(self, tmp_path):
        db_path = tmp_path / "fixture_raceform.db"
        self._build_fixture_db(db_path)
        report = inspect_file(db_path)

        ambiguous = report.ambiguous_columns()
        ambiguous_names = {col for _, col in ambiguous}
        # "sp" and "finish_pos" are low/medium confidence abbreviations by design.
        assert "sp" in ambiguous_names

    def test_detects_date_coverage(self, tmp_path):
        db_path = tmp_path / "fixture_raceform.db"
        self._build_fixture_db(db_path)
        report = inspect_file(db_path)

        races_table = next(t for t in report.tables if t.name == "races")
        assert races_table.date_range == ("2020-01-01", "2020-06-15")

    def test_write_mapping_template_marks_low_confidence_unconfirmed(self, tmp_path):
        db_path = tmp_path / "fixture_raceform.db"
        self._build_fixture_db(db_path)
        report = inspect_file(db_path)

        mapping_path = tmp_path / "mapping.json"
        report.write_mapping_template(mapping_path)
        mapping = json.loads(mapping_path.read_text())

        runners_mapping = mapping["tables"]["runners"]["columns"]
        assert runners_mapping["horse_name"]["confirmed"] is True
        assert runners_mapping["sp"]["confirmed"] is False


class TestInspectCsv:
    def test_detects_columns_and_row_count(self, tmp_path):
        csv_path = tmp_path / "fixture_races.csv"
        csv_path.write_text(
            "race_date,course,horse_name,jockey,trainer,draw,or,finish_pos,sp\n"
            "2021-03-01,Fixture Park,Fixture Horse A,Fixture Jockey A,Fixture Trainer A,3,80,1,4.5\n"
            "2021-03-01,Fixture Park,Fixture Horse B,Fixture Jockey B,Fixture Trainer B,5,75,2,6.0\n"
        )

        report = inspect_file(csv_path)
        assert report.source_format == "csv"
        assert len(report.tables) == 1
        table = report.tables[0]
        assert table.row_count == 2
        assert table.likely_kind == "race_and_runner_level"


class TestInspectJsonl:
    def test_detects_records_and_row_count(self, tmp_path):
        jsonl_path = tmp_path / "fixture_races.jsonl"
        jsonl_path.write_text(
            '{"race_date": "2022-01-01", "course": "Fixture Park", "horse_name": "Fixture Horse A"}\n'
            '{"race_date": "2022-01-02", "course": "Fixture Park", "horse_name": "Fixture Horse B"}\n'
        )

        report = inspect_file(jsonl_path)
        assert report.source_format == "jsonl"
        table = report.tables[0]
        assert table.row_count == 2

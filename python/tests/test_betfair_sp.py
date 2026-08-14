"""Tests for racingedge_data.providers.betfair_sp.

Fixture note: `providers/fixtures/betfair_sp_sample.csv` is an illustrative
test fixture only, NOT real market data, hand-constructed to match the
well-known free Betfair Historical SP CSV column format (see
betfair_sp.py's module docstring). Selection/event ids and names are
fictitious.
"""

import gzip
import io
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

from racingedge_data.entity_resolution import resolve_horse
from racingedge_data.providers import betfair_sp
from racingedge_data.providers.betfair_sp import (
    CLOSING_SP_BOOKMAKER_NAME,
    extract_sp_points_from_file,
    import_betfair_sp_file,
)
from racingedge_model.db import to_prisma_datetime
from racingedge_model.ids import new_id

FIXTURES_DIR = Path(betfair_sp.__file__).resolve().parent / "fixtures"
FIXTURE_PATH = FIXTURES_DIR / "betfair_sp_sample.csv"


class TestExtractSpPointsFromFile:
    def test_yields_points_with_correct_values(self):
        points = list(extract_sp_points_from_file(FIXTURE_PATH))
        assert len(points) == 2  # the malformed third line is skipped

        point, event_id, event_name, selection_name = points[0]
        assert event_id == "29900001"
        assert selection_name == "Fixture SP Horse A"
        assert point.win_odds_decimal == 5.2
        assert point.is_starting_price is True
        assert point.is_exchange is True
        assert point.bookmaker_name == CLOSING_SP_BOOKMAKER_NAME
        assert point.timestamp == datetime(2026, 1, 5, 14, 30, 0)
        assert point.available_volume == 3400.5

    def test_malformed_line_is_skipped_not_fatal(self):
        points = list(extract_sp_points_from_file(FIXTURE_PATH))
        assert len(points) == 2

    def test_handles_gzip_files(self, tmp_path):
        gz_path = tmp_path / "sp.csv.gz"
        content = FIXTURE_PATH.read_text()
        with gzip.open(gz_path, "wt", encoding="utf-8") as f:
            f.write(content)
        points = list(extract_sp_points_from_file(gz_path))
        assert len(points) == 2

    def test_handles_zip_files(self, tmp_path):
        zip_path = tmp_path / "sp.zip"
        content = FIXTURE_PATH.read_text()
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("2026-01-05.csv", content)
        points = list(extract_sp_points_from_file(zip_path))
        assert len(points) == 2


class TestImportBetfairSpFile:
    def _seed_runner(self, conn, horse_name: str, race_date: datetime):
        now = to_prisma_datetime(datetime.now(timezone.utc))
        race_id = new_id()
        conn.execute(
            'INSERT INTO "Race" '
            "(id, isSampleData, sourceType, date, raceTime, racecourse, country, raceName, flatJumps, "
            "surface, distanceFurlongs, handicapType, numberOfRunners, raceStatus, resultStatus, "
            "createdAt, updatedAt) "
            "VALUES (?, 0, 'REAL', ?, '14:30', 'Fixture Park', 'GB', 'Fixture SP Race', 'FLAT', "
            "'TURF', 8.0, 'NON_HANDICAP', 1, 'RESULTED', 'CONFIRMED', ?, ?)",
            (race_id, to_prisma_datetime(race_date), now, now),
        )
        resolution = resolve_horse(conn, horse_name, provider_name="csv", source_type="REAL")
        runner_id = new_id()
        conn.execute(
            'INSERT INTO "Runner" (id, isSampleData, raceId, horseId, createdAt, updatedAt) '
            "VALUES (?, 0, ?, ?, ?, ?)",
            (runner_id, race_id, resolution.canonical_id, now, now),
        )
        conn.commit()
        return runner_id

    def test_inserts_sp_price_for_matching_runner(self, tmp_db_conn):
        runner_id = self._seed_runner(
            tmp_db_conn, "Fixture SP Horse A", datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
        )

        inserted, unresolved = import_betfair_sp_file(tmp_db_conn, FIXTURE_PATH)
        tmp_db_conn.commit()

        assert inserted == 1
        assert len(unresolved) == 1  # "Fixture SP Horse B" has no seeded runner

        rows = tmp_db_conn.execute('SELECT * FROM "RunnerMarketPrice" WHERE runnerId = ?', (runner_id,)).fetchall()
        assert len(rows) == 1
        assert rows[0]["winOddsDecimal"] == 5.2
        assert rows[0]["isStartingPrice"] == 1

        bookmaker_row = tmp_db_conn.execute(
            'SELECT * FROM "Bookmaker" WHERE id = ?', (rows[0]["bookmakerId"],)
        ).fetchone()
        assert bookmaker_row["name"] == CLOSING_SP_BOOKMAKER_NAME
        assert bookmaker_row["isExchange"] == 1

    def test_reports_unresolved_rows_without_a_matching_runner(self, tmp_db_conn):
        inserted, unresolved = import_betfair_sp_file(tmp_db_conn, FIXTURE_PATH)
        assert inserted == 0
        assert len(unresolved) == 2
        assert all("Runner" in u.reason for u in unresolved)

    def test_ambiguous_match_is_reported_not_guessed(self, tmp_db_conn):
        race_date = datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
        self._seed_runner(tmp_db_conn, "Fixture SP Horse A", race_date)
        self._seed_runner(tmp_db_conn, "Fixture SP Horse A", race_date)  # same horse, same date -> ambiguous

        inserted, unresolved = import_betfair_sp_file(tmp_db_conn, FIXTURE_PATH)
        matching_unresolved = [u for u in unresolved if u.selection_name == "Fixture SP Horse A"]
        assert len(matching_unresolved) == 1
        assert "ambiguous" in matching_unresolved[0].reason

    def test_date_range_filtering(self, tmp_db_conn):
        runner_id = self._seed_runner(
            tmp_db_conn, "Fixture SP Horse A", datetime(2026, 1, 5, 14, 30, tzinfo=timezone.utc)
        )
        inserted_out_of_range, _ = import_betfair_sp_file(
            tmp_db_conn, FIXTURE_PATH, start_date=date(2026, 2, 1), end_date=date(2026, 2, 28)
        )
        assert inserted_out_of_range == 0

        inserted_in_range, _ = import_betfair_sp_file(
            tmp_db_conn, FIXTURE_PATH, start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)
        )
        assert inserted_in_range == 1

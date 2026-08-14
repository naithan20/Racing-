"""Tests for racingedge_data.providers.betfair_historical.

Fixture note: `providers/fixtures/betfair_historical_sample.jsonl` is an
illustrative test fixture only, NOT real market data, hand-constructed to
match the publicly-documented Betfair Exchange Stream "market change
message" wire format (see betfair_historical.py's module docstring for
citations). Course/horse/market ids are fictitious.
"""

from datetime import date, datetime, timezone
from pathlib import Path

from racingedge_data.entity_resolution import resolve_horse
from racingedge_data.providers import betfair_historical
from racingedge_data.providers.betfair_historical import (
    extract_odds_points_from_file,
    import_betfair_historical_file,
)
from racingedge_model.db import to_prisma_datetime
from racingedge_model.ids import new_id

FIXTURES_DIR = Path(betfair_historical.__file__).resolve().parent / "fixtures"
FIXTURE_PATH = FIXTURES_DIR / "betfair_historical_sample.jsonl"


class TestExtractOddsPointsFromFile:
    def test_yields_points_with_correct_timestamps_from_epoch_millis(self):
        points = list(extract_odds_points_from_file(FIXTURE_PATH))
        assert len(points) == 4  # 2 selections x 2 messages

        first_point, market_id, horse_name = points[0]
        assert market_id == "1.999000001"
        assert horse_name == "Fixture Test Horse A"
        assert first_point.timestamp == datetime(2026, 1, 5, 13, 0, 0, tzinfo=timezone.utc)

    def test_maps_back_lay_ltp_and_volume(self):
        points = list(extract_odds_points_from_file(FIXTURE_PATH))
        first_point, _, _ = points[0]
        assert first_point.win_odds_decimal == 6.4  # ltp
        assert first_point.back_odds_decimal == 6.4
        assert first_point.lay_odds_decimal == 6.6
        assert first_point.available_volume == 4210.5
        assert first_point.is_exchange is True

    def test_second_message_carries_a_later_timestamp(self):
        points = list(extract_odds_points_from_file(FIXTURE_PATH))
        later_point, _, horse_name = points[2]
        assert horse_name == "Fixture Test Horse A"
        assert later_point.timestamp == datetime(2026, 1, 5, 14, 29, 0, tzinfo=timezone.utc)
        assert later_point.win_odds_decimal == 5.8

    def test_malformed_line_is_skipped_not_fatal(self):
        # The fixture's last line is deliberately malformed JSON — parsing
        # must not raise, and must still yield the valid points before it.
        points = list(extract_odds_points_from_file(FIXTURE_PATH))
        assert len(points) == 4

    def test_handles_gzip_compressed_files(self, tmp_path):
        import gzip
        import shutil

        gz_path = tmp_path / "market.jsonl.gz"
        with open(FIXTURE_PATH, "rb") as src, gzip.open(gz_path, "wb") as dst:
            shutil.copyfileobj(src, dst)

        points = list(extract_odds_points_from_file(gz_path))
        assert len(points) == 4


class TestImportBetfairHistoricalFile:
    def _seed_race_with_runner(self, conn, horse_name: str):
        now = to_prisma_datetime(datetime.now(timezone.utc))
        race_id = new_id()
        conn.execute(
            'INSERT INTO "Race" '
            "(id, isSampleData, sourceType, date, raceTime, racecourse, country, raceName, flatJumps, "
            "surface, distanceFurlongs, handicapType, numberOfRunners, raceStatus, resultStatus, "
            "createdAt, updatedAt) "
            "VALUES (?, 0, 'REAL', ?, '14:30', 'Fixture Park', 'GB', 'Fixture Betfair Race', 'FLAT', "
            "'TURF', 8.0, 'NON_HANDICAP', 1, 'RESULTED', 'PENDING', ?, ?)",
            (race_id, now, now, now),
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

    def test_inserts_market_prices_for_a_matching_runner(self, tmp_db_conn):
        runner_id = self._seed_race_with_runner(tmp_db_conn, "Fixture Test Horse A")

        inserted, unresolved = import_betfair_historical_file(tmp_db_conn, FIXTURE_PATH)
        tmp_db_conn.commit()

        assert inserted == 2  # 2 messages for "Fixture Test Horse A"
        rows = tmp_db_conn.execute(
            'SELECT * FROM "RunnerMarketPrice" WHERE runnerId = ? ORDER BY timestamp', (runner_id,)
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]["winOddsDecimal"] == 6.4
        assert rows[1]["winOddsDecimal"] == 5.8
        assert rows[0]["backOddsDecimal"] == 6.4
        assert rows[0]["layOddsDecimal"] == 6.6

        bookmaker_row = tmp_db_conn.execute(
            'SELECT * FROM "Bookmaker" WHERE id = ?', (rows[0]["bookmakerId"],)
        ).fetchone()
        assert bookmaker_row["name"] == "Betfair Exchange"
        assert bookmaker_row["isExchange"] == 1

    def test_reports_unresolved_selections_without_a_matching_runner(self, tmp_db_conn):
        # No Race/Runner seeded at all -> every selection is unresolved.
        inserted, unresolved = import_betfair_historical_file(tmp_db_conn, FIXTURE_PATH)
        tmp_db_conn.commit()

        assert inserted == 0
        assert len(unresolved) == 4
        assert all(u.horse_name in ("Fixture Test Horse A", "Fixture Test Horse B") for u in unresolved)
        assert all("Runner row" in u.reason for u in unresolved)

    def test_date_range_filtering(self, tmp_db_conn):
        self._seed_race_with_runner(tmp_db_conn, "Fixture Test Horse A")

        # Only the SECOND message's date should be included.
        inserted, _ = import_betfair_historical_file(
            tmp_db_conn, FIXTURE_PATH, start_date=date(2026, 1, 5), end_date=date(2026, 1, 5)
        )
        assert inserted == 2  # both messages are on the same calendar date in this fixture

        inserted_none, _ = import_betfair_historical_file(
            tmp_db_conn, FIXTURE_PATH, start_date=date(2026, 1, 6), end_date=date(2026, 1, 10)
        )
        assert inserted_none == 0

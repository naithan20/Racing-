import io
from datetime import date, datetime, timezone

import pandas as pd
import pytest

from racingedge_data.importers.import_runner import import_races
from racingedge_data.point_in_time import (
    market_prices_as_of,
    reconstruct_race_as_of,
    reconstruct_runner_as_of,
)
from racingedge_data.provenance import record_race_field_change, record_runner_field_change
from racingedge_data.providers.csv_provider import CsvRaceDataProvider
from racingedge_model.db import to_prisma_datetime
from racingedge_model.ids import new_id

CSV_HEADER = (
    "provider_race_id,date,race_time,racecourse,country,race_name,flat_jumps,surface,"
    "distance_furlongs,handicap_type,number_of_runners,going,runner_provider_id,horse_name,"
    "horse_provider_id,draw,official_rating,jockey_name,trainer_name,non_runner\n"
)


def _import_one_fixture_race(conn):
    row = (
        "pit-race-1,2026-06-01T14:00:00,14:00,Fixture Course,GB,Fixture PIT Race,FLAT,TURF,"
        "8.0,NON_HANDICAP,1,Good,r1,Fixture PIT Horse,h1,3,80,Jockey One,Trainer One,false\n"
    )
    provider = CsvRaceDataProvider(io.StringIO(CSV_HEADER + row))
    result = import_races(conn, provider, date(2026, 1, 1), date(2026, 12, 31), source_type="REAL")
    conn.commit()
    race_row = conn.execute('SELECT * FROM "Race" WHERE raceName = ?', ("Fixture PIT Race",)).fetchone()
    runner_row = conn.execute('SELECT * FROM "Runner" WHERE raceId = ?', (race_row["id"],)).fetchone()
    return result, race_row, runner_row


class TestReconstructRaceAsOf:
    def test_reconstructs_initial_import_time_state(self, tmp_db_conn):
        _, race_row, _ = _import_one_fixture_race(tmp_db_conn)
        as_of = race_row["date"]

        reconstructed = reconstruct_race_as_of(tmp_db_conn, race_row["id"], as_of)
        assert reconstructed["going"] == "Good"
        assert reconstructed["racecourse"] == "Fixture Course"  # immutable field, from live row

    def test_field_with_no_history_before_cutoff_is_none(self, tmp_db_conn):
        _, race_row, _ = _import_one_fixture_race(tmp_db_conn)
        earlier = pd.Timestamp(race_row["date"]) - pd.Timedelta(days=1)

        reconstructed = reconstruct_race_as_of(tmp_db_conn, race_row["id"], earlier)
        assert reconstructed["going"] is None

    def test_later_field_change_is_picked_up_only_after_its_effective_time(self, tmp_db_conn):
        _, race_row, _ = _import_one_fixture_race(tmp_db_conn)

        change_time = pd.Timestamp(race_row["date"]) + pd.Timedelta(hours=2)
        record_race_field_change(
            tmp_db_conn,
            race_id=race_row["id"],
            field_name="going",
            field_value="Soft",
            effective_at=change_time.to_pydatetime(),
            source="manual",
        )
        tmp_db_conn.commit()

        before_change = pd.Timestamp(race_row["date"]) + pd.Timedelta(hours=1)
        after_change = pd.Timestamp(race_row["date"]) + pd.Timedelta(hours=3)

        assert reconstruct_race_as_of(tmp_db_conn, race_row["id"], before_change)["going"] == "Good"
        assert reconstruct_race_as_of(tmp_db_conn, race_row["id"], after_change)["going"] == "Soft"

    def test_unknown_race_raises(self, tmp_db_conn):
        with pytest.raises(ValueError):
            reconstruct_race_as_of(tmp_db_conn, "nonexistent-race-id", datetime.now(timezone.utc))


class TestReconstructRunnerAsOf:
    def test_reconstructs_initial_draw(self, tmp_db_conn):
        _, race_row, runner_row = _import_one_fixture_race(tmp_db_conn)
        reconstructed = reconstruct_runner_as_of(tmp_db_conn, runner_row["id"], race_row["date"])
        assert reconstructed["draw"] == "3"

    def test_draw_change_is_point_in_time_correct(self, tmp_db_conn):
        _, race_row, runner_row = _import_one_fixture_race(tmp_db_conn)

        change_time = pd.Timestamp(race_row["date"]) + pd.Timedelta(hours=1)
        record_runner_field_change(
            tmp_db_conn,
            runner_id=runner_row["id"],
            field_name="draw",
            field_value="7",
            effective_at=change_time.to_pydatetime(),
            source="manual",
        )
        tmp_db_conn.commit()

        before = race_row["date"]
        after = (pd.Timestamp(race_row["date"]) + pd.Timedelta(hours=2)).to_pydatetime()

        assert reconstruct_runner_as_of(tmp_db_conn, runner_row["id"], before)["draw"] == "3"
        assert reconstruct_runner_as_of(tmp_db_conn, runner_row["id"], after)["draw"] == "7"


class TestMarketPricesAsOf:
    def test_only_returns_prices_at_or_before_as_of(self, tmp_db_conn):
        _, race_row, runner_row = _import_one_fixture_race(tmp_db_conn)
        bookmaker_id = tmp_db_conn.execute('SELECT id FROM "Bookmaker" LIMIT 1').fetchone()["id"]

        t1 = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 6, 1, 13, 0, tzinfo=timezone.utc)
        for ts, odds in ((t1, 5.0), (t2, 4.0)):
            tmp_db_conn.execute(
                'INSERT INTO "RunnerMarketPrice" '
                "(id, runnerId, bookmakerId, timestamp, winOddsDecimal, createdAt) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (new_id(), runner_row["id"], bookmaker_id, to_prisma_datetime(ts), odds, to_prisma_datetime(ts)),
            )
        tmp_db_conn.commit()

        as_of_between = datetime(2026, 6, 1, 11, 0, tzinfo=timezone.utc)
        df = market_prices_as_of(tmp_db_conn, runner_row["id"], as_of_between)
        assert len(df) == 1
        assert df["winOddsDecimal"].iloc[0] == 5.0

        as_of_after_both = datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
        df_all = market_prices_as_of(tmp_db_conn, runner_row["id"], as_of_after_both)
        assert len(df_all) == 2

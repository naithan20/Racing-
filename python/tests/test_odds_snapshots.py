from datetime import datetime, timedelta, timezone

import pandas as pd

from racingedge_data.odds_snapshots import (
    SNAPSHOT_LABELS,
    derive_named_snapshots,
    get_bsp_for_runner,
    get_named_snapshots_for_runner,
)
from racingedge_model.db import to_prisma_datetime
from racingedge_model.ids import new_id

OFF_TIME = datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)


def _price_row(hours_before_off, odds, is_opening=False, is_sp=False):
    ts = pd.Timestamp(OFF_TIME - timedelta(hours=hours_before_off))
    return {
        "timestamp": ts,
        "winOddsDecimal": odds,
        "isOpeningPrice": is_opening,
        "isStartingPrice": is_sp,
    }


class TestDeriveNamedSnapshots:
    def test_empty_price_series_gives_all_none_snapshots(self):
        prices = pd.DataFrame(columns=["timestamp", "winOddsDecimal", "isOpeningPrice", "isStartingPrice"])
        results = derive_named_snapshots(prices, OFF_TIME)
        for label in SNAPSHOT_LABELS:
            assert results[label].timestamp is None
            assert results[label].win_odds_decimal is None

    def test_picks_most_recent_price_at_or_before_each_offset(self):
        prices = pd.DataFrame(
            [
                _price_row(30, 10.0, is_opening=True),  # 30h before off -> opening
                _price_row(7, 8.0),  # 7h before -> should serve as "6h" snapshot's fallback (last price <=6h before is this one, since nothing closer)
                _price_row(0.5, 5.0),  # 30 min before off -> serves 1h/30m
                _price_row(0.02, 4.5, is_sp=True),  # ~1min before off -> SP
            ]
        )
        results = derive_named_snapshots(prices, OFF_TIME)

        assert results["opening"].win_odds_decimal == 10.0
        assert results["opening"].is_exact is True

        # "6h" snapshot moment = off_time - 6h. Only the 30h and 7h rows are
        # at or before that moment; the 7h one (more recent) should win.
        assert results["6h"].win_odds_decimal == 8.0

        # "1h" and "30m" snapshot moments are both >= the 0.5h-before row's
        # timestamp only for "30m" (moment = off - 30m = exactly the row);
        # "1h" moment (off - 1h) is BEFORE the 0.5h-before row, so "1h"
        # should still resolve to the 7h-before row (last price <= that moment).
        assert results["1h"].win_odds_decimal == 8.0
        assert results["30m"].win_odds_decimal == 5.0

        assert results["sp"].win_odds_decimal == 4.5
        assert results["sp"].is_exact is True

        assert results["off_time"].win_odds_decimal == 4.5  # last known price by off-time

    def test_never_uses_a_price_after_the_offset_moment(self):
        # A price recorded AFTER the "24h" moment must never be used for it.
        prices = pd.DataFrame(
            [
                _price_row(1, 3.0),  # only 1h before off-time — after the 24h-before moment
            ]
        )
        results = derive_named_snapshots(prices, OFF_TIME)
        assert results["24h"].win_odds_decimal is None

    def test_ignores_prices_recorded_after_race_off_time(self):
        prices = pd.DataFrame(
            [
                _price_row(1, 5.0),
                {
                    "timestamp": pd.Timestamp(OFF_TIME + timedelta(minutes=5)),
                    "winOddsDecimal": 100.0,  # a post-off-time price that must never leak in
                    "isOpeningPrice": False,
                    "isStartingPrice": True,
                },
            ]
        )
        results = derive_named_snapshots(prices, OFF_TIME)
        assert results["off_time"].win_odds_decimal == 5.0
        assert results["sp"].win_odds_decimal is None  # the only SP-flagged row was post-off-time, so excluded


class TestGetNamedSnapshotsForRunnerAndBsp(object):
    def _seed_runner(self, conn):
        now = to_prisma_datetime(datetime.now(timezone.utc))
        race_id = new_id()
        horse_id = new_id()
        runner_id = new_id()
        conn.execute(
            'INSERT INTO "Race" '
            "(id, isSampleData, sourceType, date, raceTime, racecourse, country, raceName, flatJumps, "
            "surface, distanceFurlongs, handicapType, numberOfRunners, raceStatus, resultStatus, "
            "createdAt, updatedAt) "
            "VALUES (?, 0, 'SAMPLE', ?, '15:00', 'Fixture Odds Course', 'GB', 'Fixture Odds Race', "
            "'FLAT', 'TURF', 8.0, 'NON_HANDICAP', 1, 'RESULTED', 'PENDING', ?, ?)",
            (race_id, now, now, now),
        )
        conn.execute(
            'INSERT INTO "Horse" (id, isSampleData, sourceType, name, createdAt, updatedAt) '
            "VALUES (?, 0, 'SAMPLE', 'Fixture Odds Horse', ?, ?)",
            (horse_id, now, now),
        )
        conn.execute(
            'INSERT INTO "Runner" (id, isSampleData, raceId, horseId, createdAt, updatedAt) '
            "VALUES (?, 0, ?, ?, ?, ?)",
            (runner_id, race_id, horse_id, now, now),
        )
        return runner_id

    def test_db_backed_snapshots_and_bsp(self, tmp_db_conn):
        runner_id = self._seed_runner(tmp_db_conn)

        fixed_odds_bookmaker_id = new_id()
        exchange_bookmaker_id = new_id()
        tmp_db_conn.execute(
            'INSERT INTO "Bookmaker" (id, name, isExchange, createdAt) VALUES (?, ?, 0, ?)',
            (fixed_odds_bookmaker_id, "Fixture Bookmaker", to_prisma_datetime(datetime.now(timezone.utc))),
        )
        tmp_db_conn.execute(
            'INSERT INTO "Bookmaker" (id, name, isExchange, createdAt) VALUES (?, ?, 1, ?)',
            (exchange_bookmaker_id, "Fixture Exchange", to_prisma_datetime(datetime.now(timezone.utc))),
        )

        def insert_price(bookmaker_id, ts, odds, is_sp=False):
            tmp_db_conn.execute(
                'INSERT INTO "RunnerMarketPrice" '
                "(id, runnerId, bookmakerId, timestamp, winOddsDecimal, isOpeningPrice, isStartingPrice, createdAt) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    new_id(),
                    runner_id,
                    bookmaker_id,
                    to_prisma_datetime(ts),
                    odds,
                    0,
                    int(is_sp),
                    to_prisma_datetime(ts),
                ),
            )

        insert_price(fixed_odds_bookmaker_id, OFF_TIME - timedelta(hours=2), 6.0)
        insert_price(fixed_odds_bookmaker_id, OFF_TIME - timedelta(minutes=1), 5.0, is_sp=True)
        insert_price(exchange_bookmaker_id, OFF_TIME - timedelta(minutes=1), 5.5, is_sp=True)
        tmp_db_conn.commit()

        results = get_named_snapshots_for_runner(tmp_db_conn, runner_id, fixed_odds_bookmaker_id, OFF_TIME)
        assert results["sp"].win_odds_decimal == 5.0

        bsp = get_bsp_for_runner(tmp_db_conn, runner_id)
        assert bsp == 5.5

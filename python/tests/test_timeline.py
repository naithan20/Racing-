import pandas as pd
import pytest

from racingedge_data.timeline import (
    TimelineLeakageError,
    get_course_history_before,
    get_distance_history_before,
    get_going_history_before,
    get_last_n_runs,
    get_previous_runs,
    get_rating_history_before,
)


def _horse_with_form(conn, min_runs=3):
    row = conn.execute(
        'SELECT horseId, COUNT(*) as n FROM "FormEntry" GROUP BY horseId HAVING n >= ? ORDER BY n DESC LIMIT 1',
        (min_runs,),
    ).fetchone()
    if row is None:
        pytest.skip("No horse in the database has enough FormEntry rows for this test")
    return row["horseId"]


class TestGetPreviousRuns:
    def test_returns_only_rows_strictly_before_cutoff(self, tmp_db_conn):
        horse_id = _horse_with_form(tmp_db_conn)
        all_rows = pd.read_sql_query(
            'SELECT raceDate FROM "FormEntry" WHERE horseId = ? ORDER BY raceDate', tmp_db_conn, params=(horse_id,)
        )
        all_rows["raceDate"] = pd.to_datetime(all_rows["raceDate"], utc=True)
        midpoint = all_rows["raceDate"].iloc[len(all_rows) // 2]

        df = get_previous_runs(tmp_db_conn, horse_id, midpoint)
        assert (df["raceDate"] < midpoint).all()

    def test_ordered_most_recent_first(self, tmp_db_conn):
        horse_id = _horse_with_form(tmp_db_conn)
        far_future = pd.Timestamp("2099-01-01", tz="UTC")
        df = get_previous_runs(tmp_db_conn, horse_id, far_future)
        dates = df["raceDate"].tolist()
        assert dates == sorted(dates, reverse=True)

    def test_unknown_horse_returns_empty(self, tmp_db_conn):
        df = get_previous_runs(tmp_db_conn, "nonexistent-horse-id", pd.Timestamp("2099-01-01", tz="UTC"))
        assert df.empty


class TestGetLastNRuns:
    def test_limits_to_n_rows(self, tmp_db_conn):
        horse_id = _horse_with_form(tmp_db_conn, min_runs=3)
        far_future = pd.Timestamp("2099-01-01", tz="UTC")
        df = get_last_n_runs(tmp_db_conn, horse_id, far_future, 2)
        assert len(df) <= 2


class TestCourseDistanceGoingHistory:
    def test_course_history_filters_correctly(self, tmp_db_conn):
        horse_id = _horse_with_form(tmp_db_conn)
        far_future = pd.Timestamp("2099-01-01", tz="UTC")
        all_runs = get_previous_runs(tmp_db_conn, horse_id, far_future)
        if all_runs.empty:
            pytest.skip("no runs")
        course = all_runs["course"].iloc[0]
        filtered = get_course_history_before(tmp_db_conn, horse_id, course, far_future)
        assert (filtered["course"] == course).all()
        assert len(filtered) <= len(all_runs)

    def test_distance_history_with_tolerance(self, tmp_db_conn):
        horse_id = _horse_with_form(tmp_db_conn)
        far_future = pd.Timestamp("2099-01-01", tz="UTC")
        all_runs = get_previous_runs(tmp_db_conn, horse_id, far_future)
        if all_runs.empty or all_runs["distanceFurlongs"].isna().all():
            pytest.skip("no distance data")
        target_distance = all_runs["distanceFurlongs"].dropna().iloc[0]
        filtered = get_distance_history_before(tmp_db_conn, horse_id, target_distance, far_future, tolerance_furlongs=0.0)
        assert (filtered["distanceFurlongs"] == target_distance).all()

    def test_going_history_filters_correctly(self, tmp_db_conn):
        horse_id = _horse_with_form(tmp_db_conn)
        far_future = pd.Timestamp("2099-01-01", tz="UTC")
        all_runs = get_previous_runs(tmp_db_conn, horse_id, far_future)
        if all_runs.empty or all_runs["going"].isna().all():
            pytest.skip("no going data")
        going = all_runs["going"].dropna().iloc[0]
        filtered = get_going_history_before(tmp_db_conn, horse_id, going, far_future)
        assert (filtered["going"] == going).all()


class TestGetRatingHistoryBefore:
    def test_drops_null_ratings_and_keeps_shape(self, tmp_db_conn):
        horse_id = _horse_with_form(tmp_db_conn)
        far_future = pd.Timestamp("2099-01-01", tz="UTC")
        df = get_rating_history_before(tmp_db_conn, horse_id, far_future)
        assert list(df.columns) == ["raceDate", "officialRating"]
        assert df["officialRating"].notna().all()

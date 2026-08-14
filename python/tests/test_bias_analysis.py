from datetime import datetime, timezone

import pytest

from racingedge_data.bias_analysis import compute_bias_report
from racingedge_model.db import to_prisma_datetime
from racingedge_model.ids import new_id


def _insert_horse(conn, name="Bias Test Horse"):
    horse_id = new_id()
    now = to_prisma_datetime(datetime.now(timezone.utc))
    conn.execute(
        'INSERT INTO "Horse" (id, isSampleData, sourceType, name, createdAt, updatedAt) '
        "VALUES (?, ?, ?, ?, ?, ?)",
        (horse_id, 0, "REAL", name, now, now),
    )
    return horse_id


def _insert_race(conn, date_str, racecourse="Testbury", flat_jumps="FLAT", race_class=3,
                  going="Good", number_of_runners=2, source_type="REAL"):
    race_id = new_id()
    now = to_prisma_datetime(datetime.now(timezone.utc))
    conn.execute(
        'INSERT INTO "Race" '
        "(id, isSampleData, sourceType, date, raceTime, racecourse, country, raceName, raceType, "
        "flatJumps, surface, distanceYards, distanceFurlongs, raceClass, gradeGroup, handicapType, "
        "ageRestriction, sexRestriction, numberOfRunners, going, goingDescription, railPosition, "
        "stallsPosition, weatherSummary, temperatureCelsius, windSummary, precipitationMm, "
        "prizeMoneyTotal, currency, eachWayFraction, bookmakerPlaces, extraPlaceFlag, raceStatus, "
        "resultStatus, createdAt, updatedAt, importBatchId) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?, ?, ?, ?)",
        (
            race_id, 0, source_type, f"{date_str}T14:00:00.000+00:00", "14:00", racecourse, "GB",
            "Bias Test Stakes", "Handicap", flat_jumps, "TURF", None, 8.0, race_class, None,
            "HANDICAP", None, None, number_of_runners, going, None, None, None, None, None, None,
            None, None, "GBP", None, None, 0, "RESULTED", "CONFIRMED", now, now, None,
        ),
    )
    return race_id


def _insert_runner(conn, race_id, horse_id, favourite_rank=None, sp=None, non_runner=False):
    runner_id = new_id()
    now = to_prisma_datetime(datetime.now(timezone.utc))
    conn.execute(
        'INSERT INTO "Runner" '
        "(id, isSampleData, raceId, horseId, clothNumber, draw, ageAtRace, weightStone, "
        "weightPounds, weightLbsTotal, officialRating, racingPostRating, timeformRating, "
        "topspeedRating, jockeyName, jockeyClaimLbs, trainerName, headgear, firstTimeHeadgear, "
        "daysSinceLastRun, startingPriceDecimal, nonRunner, favouriteRank, createdAt, updatedAt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            runner_id, 0, race_id, horse_id, 1, 1, 5, None, None, 140, None, None, None, None,
            "T Jockey", None, "T Trainer", None, 0, None, sp, int(non_runner), favourite_rank, now, now,
        ),
    )
    return runner_id


def _insert_result(conn, runner_id, finishing_position, finish_status="RAN"):
    result_id = new_id()
    now = to_prisma_datetime(datetime.now(timezone.utc))
    conn.execute(
        'INSERT INTO "ResultEntry" '
        "(id, runnerId, finishingPosition, finishStatus, beatenDistanceLengths, deadHeat, "
        "startingPriceDecimal, closingOddsDecimal, bspDecimal, resultStatus, createdAt, updatedAt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (result_id, runner_id, finishing_position, finish_status, None, 0, None, None, None, "CONFIRMED", now, now),
    )
    return result_id


class TestComputeBiasReportOnRealDatabase:
    """Smoke/invariant tests against the real (synthetic) project database —
    checks the report doesn't crash and every percentage/count is internally
    consistent, without asserting exact values that would drift as the
    dataset grows."""

    def test_returns_nonzero_counts(self, tmp_db_conn):
        report = compute_bias_report(tmp_db_conn)
        assert report.race_count > 0
        assert report.runner_count > 0

    def test_years_present_matches_race_dates(self, tmp_db_conn):
        report = compute_bias_report(tmp_db_conn)
        assert len(report.years_present) > 0
        assert report.years_present == sorted(report.years_present)

    def test_odds_bucket_counts_do_not_exceed_runner_count(self, tmp_db_conn):
        report = compute_bias_report(tmp_db_conn)
        assert sum(report.odds_distribution_buckets.values()) <= report.runner_count

    def test_percentages_are_within_0_100(self, tmp_db_conn):
        report = compute_bias_report(tmp_db_conn)
        for pct in (report.missing_class_pct, report.non_runner_pct, report.dnf_pct, report.missing_sp_pct):
            if pct is not None:
                assert 0.0 <= pct <= 100.0

    def test_scoping_to_explicit_race_ids_matches_that_subset(self, tmp_db_conn):
        race_ids = [r["id"] for r in tmp_db_conn.execute('SELECT id FROM "Race" LIMIT 5').fetchall()]
        report = compute_bias_report(tmp_db_conn, race_ids=race_ids)
        assert report.race_count == len(race_ids)

    def test_empty_race_ids_returns_empty_report_with_warning(self, tmp_db_conn):
        report = compute_bias_report(tmp_db_conn, race_ids=[])
        assert report.race_count == 0
        assert report.runner_count == 0
        assert report.warnings == ["No races in scope — nothing to analyse."]


class TestComputeBiasReportOnControlledFixture:
    """Exact-value tests against a small, fully controlled set of races
    inserted directly — isolates each metric from the shape of whatever
    happens to be in the shared synthetic database."""

    @pytest.fixture
    def fixture_race_ids(self, tmp_db_conn):
        horse_a = _insert_horse(tmp_db_conn, "Fixture Horse A")
        horse_b = _insert_horse(tmp_db_conn, "Fixture Horse B")

        race_2020 = _insert_race(tmp_db_conn, "2020-06-01", racecourse="Ascot", going="Good")
        r1 = _insert_runner(tmp_db_conn, race_2020, horse_a, favourite_rank=1, sp=1.5)
        r2 = _insert_runner(tmp_db_conn, race_2020, horse_b, favourite_rank=2, sp=10.0, non_runner=True)
        _insert_result(tmp_db_conn, r1, finishing_position=1, finish_status="WON")
        _insert_result(tmp_db_conn, r2, finishing_position=None, finish_status=None)

        race_2022 = _insert_race(tmp_db_conn, "2022-06-01", racecourse="Ascot", flat_jumps="JUMPS", going="Soft")
        r3 = _insert_runner(tmp_db_conn, race_2022, horse_a, favourite_rank=1, sp=3.0)
        r4 = _insert_runner(tmp_db_conn, race_2022, horse_b, favourite_rank=2, sp=25.0)
        _insert_result(tmp_db_conn, r3, finishing_position=4, finish_status="PU")
        _insert_result(tmp_db_conn, r4, finishing_position=1, finish_status="WON")

        tmp_db_conn.commit()
        return [race_2020, race_2022]

    def test_missing_year_2021_is_reported(self, tmp_db_conn, fixture_race_ids):
        report = compute_bias_report(tmp_db_conn, race_ids=fixture_race_ids)
        assert report.years_present == [2020, 2022]
        assert report.missing_years_in_range == [2021]

    def test_flat_jumps_split_matches_fixture(self, tmp_db_conn, fixture_race_ids):
        report = compute_bias_report(tmp_db_conn, race_ids=fixture_race_ids)
        assert report.flat_jumps_counts == {"FLAT": 1, "JUMPS": 1}

    def test_favourite_win_rate_matches_fixture(self, tmp_db_conn, fixture_race_ids):
        # Two favourites (rank 1): one won (race 2020), one was pulled up (race 2022) -> 50%.
        report = compute_bias_report(tmp_db_conn, race_ids=fixture_race_ids)
        fav_bucket = report.favourite_outsider_buckets["Favourite (rank 1)"]
        assert fav_bucket["runner_count"] == 2
        assert fav_bucket["win_rate_pct"] == 50.0

    def test_non_runner_count_matches_fixture(self, tmp_db_conn, fixture_race_ids):
        report = compute_bias_report(tmp_db_conn, race_ids=fixture_race_ids)
        assert report.non_runner_count == 1
        assert report.non_runner_pct == pytest.approx(25.0)

    def test_dnf_status_counts_include_pulled_up(self, tmp_db_conn, fixture_race_ids):
        report = compute_bias_report(tmp_db_conn, race_ids=fixture_race_ids)
        assert report.dnf_status_counts.get("PU") == 1
        assert report.dnf_pct == pytest.approx(25.0)

    def test_odds_distribution_buckets_fixture_values(self, tmp_db_conn, fixture_race_ids):
        report = compute_bias_report(tmp_db_conn, race_ids=fixture_race_ids)
        # SPs: 1.5 (<=2.0), 10.0 (8.01-16.0), 3.0 (2.01-4.0), 25.0 (16.01-33.0)
        assert report.odds_distribution_buckets["<=2.0 (odds-on)"] == 1
        assert report.odds_distribution_buckets["8.01-16.0"] == 1
        assert report.odds_distribution_buckets["2.01-4.0"] == 1
        assert report.odds_distribution_buckets["16.01-33.0"] == 1

    def test_by_year_breakdown_has_one_entry_per_year(self, tmp_db_conn, fixture_race_ids):
        report = compute_bias_report(tmp_db_conn, race_ids=fixture_race_ids)
        years = {y.year: y for y in report.by_year}
        assert set(years.keys()) == {2020, 2022}
        assert years[2020].race_count == 1
        assert years[2022].flat_pct == 0.0

    def test_no_non_runner_warning_when_non_runners_present(self, tmp_db_conn, fixture_race_ids):
        report = compute_bias_report(tmp_db_conn, race_ids=fixture_race_ids)
        assert not any("Zero non-runners" in w for w in report.warnings)

    def test_report_serializes_to_json(self, tmp_db_conn, fixture_race_ids):
        report = compute_bias_report(tmp_db_conn, race_ids=fixture_race_ids)
        json_str = report.to_json()
        assert "years_present" in json_str
        assert "by_year" in json_str


class TestZeroNonRunnerWarning:
    def test_flags_zero_non_runners_as_suspicious(self, tmp_db_conn):
        horse = _insert_horse(tmp_db_conn, "Zero NR Horse")
        race_id = _insert_race(tmp_db_conn, "2023-01-01")
        runner_id = _insert_runner(tmp_db_conn, race_id, horse, favourite_rank=1, sp=2.0, non_runner=False)
        _insert_result(tmp_db_conn, runner_id, finishing_position=1, finish_status="WON")
        tmp_db_conn.commit()

        report = compute_bias_report(tmp_db_conn, race_ids=[race_id])
        assert any("Zero non-runners" in w for w in report.warnings)

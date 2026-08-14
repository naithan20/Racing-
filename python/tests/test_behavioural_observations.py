from datetime import datetime, timezone

import pytest

from racingedge_data.behavioural_observations import (
    VALID_OBSERVATION_TAGS,
    BehaviouralObservationRow,
    insert_runner_observation,
    load_behavioural_observations,
    map_tags_to_behavioural_scores,
)
from racingedge_model.db import to_prisma_datetime
from racingedge_model.ids import new_id


def _insert_horse(conn):
    horse_id = new_id()
    now = to_prisma_datetime(datetime.now(timezone.utc))
    conn.execute(
        'INSERT INTO "Horse" (id, isSampleData, sourceType, name, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?, ?)',
        (horse_id, 0, "REAL", "Observation Test Horse", now, now),
    )
    return horse_id


def _insert_race(conn):
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
            race_id, 0, "REAL", "2024-05-01T14:00:00.000+00:00", "14:00", "Testbury", "GB",
            "Observation Test Stakes", "Handicap", "FLAT", "TURF", None, 8.0, 3, None,
            "HANDICAP", None, None, 6, "Good", None, None, None, None, None, None,
            None, None, "GBP", None, None, 0, "RESULTED", "CONFIRMED", now, now, None,
        ),
    )
    return race_id


def _insert_runner(conn, race_id, horse_id):
    runner_id = new_id()
    now = to_prisma_datetime(datetime.now(timezone.utc))
    conn.execute(
        'INSERT INTO "Runner" '
        "(id, isSampleData, raceId, horseId, clothNumber, draw, weightLbsTotal, nonRunner, createdAt, updatedAt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (runner_id, 0, race_id, horse_id, 1, 1, 140, 0, now, now),
    )
    return runner_id


def _insert_result(conn, runner_id):
    result_id = new_id()
    now = to_prisma_datetime(datetime.now(timezone.utc))
    conn.execute(
        'INSERT INTO "ResultEntry" (id, runnerId, finishingPosition, finishStatus, resultStatus, createdAt, updatedAt) '
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (result_id, runner_id, 1, "WON", "CONFIRMED", now, now),
    )
    return result_id


@pytest.fixture
def result_id(tmp_db_conn):
    horse_id = _insert_horse(tmp_db_conn)
    race_id = _insert_race(tmp_db_conn)
    runner_id = _insert_runner(tmp_db_conn, race_id, horse_id)
    rid = _insert_result(tmp_db_conn, runner_id)
    tmp_db_conn.commit()
    return rid


class TestMapTagsToBehaviouralScores:
    def test_every_valid_tag_is_mapped_to_something(self):
        for tag in VALID_OBSERVATION_TAGS:
            derived = map_tags_to_behavioural_scores([tag])
            # Use `is not` rather than `!=`/`in` — 0 (MIDFIELD's explicit
            # neutral score) is a real signal, but `0 == False` in Python,
            # so an equality-based filter would wrongly discard it too.
            score_hits = [
                v
                for k, v in derived.items()
                if k != "tags_with_no_mapping" and v is not None and v is not False
            ]
            assert score_hits, f"tag {tag} produced no signal at all"
            assert derived["tags_with_no_mapping"] == []

    def test_empty_tags_gives_all_none_and_no_unmapped(self):
        derived = map_tags_to_behavioural_scores([])
        assert derived["break_quality"] is None
        assert derived["bad_ride_flag"] is False
        assert derived["tags_with_no_mapping"] == []

    def test_unrecognised_tag_is_surfaced_not_dropped(self):
        derived = map_tags_to_behavioural_scores(["NOT_A_REAL_TAG"])
        assert derived["tags_with_no_mapping"] == ["NOT_A_REAL_TAG"]
        assert derived["break_quality"] is None

    def test_multiple_tags_in_same_category_are_summed(self):
        derived = map_tags_to_behavioural_scores(["BLOCKED", "LOST_GROUND_SEEKING_RUN"])
        assert derived["position_acquisition_cost"] == 4

    def test_midfield_is_explicit_zero_not_none(self):
        derived = map_tags_to_behavioural_scores(["MIDFIELD"])
        assert derived["early_position"] == 0

    def test_flags_are_independent_of_score_categories(self):
        derived = map_tags_to_behavioural_scores(["RACE_NOT_REPRESENTATIVE", "CLEAN_TEST_OF_THESIS"])
        assert derived["race_not_representative_flag"] is True
        assert derived["clean_test_flag"] is True
        assert derived["bad_ride_flag"] is False
        assert derived["break_quality"] is None

    def test_opposing_tags_do_not_appear_in_same_race_but_map_independently(self):
        excellent = map_tags_to_behavioural_scores(["EXCELLENT_BREAK"])
        slow = map_tags_to_behavioural_scores(["SLOW_BREAK"])
        assert excellent["break_quality"] > 0
        assert slow["break_quality"] < 0


class TestInsertRunnerObservation:
    def test_inserts_and_is_readable(self, tmp_db_conn, result_id):
        insert_runner_observation(tmp_db_conn, result_id, tag="EXCELLENT_BREAK")
        tmp_db_conn.commit()
        row = tmp_db_conn.execute('SELECT * FROM "RunnerObservation" WHERE resultId = ?', (result_id,)).fetchone()
        assert row["tag"] == "EXCELLENT_BREAK"

    def test_free_text_only_is_allowed(self, tmp_db_conn, result_id):
        obs_id = insert_runner_observation(tmp_db_conn, result_id, free_text="Hampered leaving the stalls.")
        tmp_db_conn.commit()
        row = tmp_db_conn.execute('SELECT * FROM "RunnerObservation" WHERE id = ?', (obs_id,)).fetchone()
        assert row["tag"] is None
        assert row["freeText"] == "Hampered leaving the stalls."

    def test_rejects_unknown_tag(self, tmp_db_conn, result_id):
        with pytest.raises(ValueError, match="Unknown observation tag"):
            insert_runner_observation(tmp_db_conn, result_id, tag="NOT_A_REAL_TAG")

    def test_rejects_neither_tag_nor_free_text(self, tmp_db_conn, result_id):
        with pytest.raises(ValueError, match="At least one"):
            insert_runner_observation(tmp_db_conn, result_id)

    def test_multiple_observations_on_same_result_never_overwrite(self, tmp_db_conn, result_id):
        insert_runner_observation(tmp_db_conn, result_id, tag="EXCELLENT_BREAK")
        insert_runner_observation(tmp_db_conn, result_id, tag="BLOCKED")
        tmp_db_conn.commit()
        rows = tmp_db_conn.execute('SELECT tag FROM "RunnerObservation" WHERE resultId = ? ORDER BY createdAt', (result_id,)).fetchall()
        assert [r["tag"] for r in rows] == ["EXCELLENT_BREAK", "BLOCKED"]


class TestLoadBehaviouralObservations:
    def test_result_with_no_observations_is_absent(self, tmp_db_conn, result_id):
        results = load_behavioural_observations(tmp_db_conn, result_ids=[result_id])
        assert results == []

    def test_loads_and_derives_scores_for_one_result(self, tmp_db_conn, result_id):
        insert_runner_observation(tmp_db_conn, result_id, tag="EXCELLENT_BREAK")
        insert_runner_observation(tmp_db_conn, result_id, tag="STAYED_ON_STRONGLY", free_text="Kept finding more.")
        tmp_db_conn.commit()

        results = load_behavioural_observations(tmp_db_conn, result_ids=[result_id])
        assert len(results) == 1
        row = results[0]
        assert isinstance(row, BehaviouralObservationRow)
        assert row.result_id == result_id
        assert set(row.raw_tags) == {"EXCELLENT_BREAK", "STAYED_ON_STRONGLY"}
        assert row.raw_free_text == ["Kept finding more."]
        assert row.break_quality == 1
        assert row.final_furlong_sustainability == 1
        assert row.position_acquisition_cost is None

    def test_empty_result_ids_list_returns_empty(self, tmp_db_conn):
        assert load_behavioural_observations(tmp_db_conn, result_ids=[]) == []

    def test_none_result_ids_scans_whole_table(self, tmp_db_conn, result_id):
        insert_runner_observation(tmp_db_conn, result_id, tag="MIDFIELD")
        tmp_db_conn.commit()
        results = load_behavioural_observations(tmp_db_conn, result_ids=None)
        assert any(r.result_id == result_id for r in results)

    def test_raw_observations_are_never_mutated_by_loading(self, tmp_db_conn, result_id):
        insert_runner_observation(tmp_db_conn, result_id, tag="SLOW_BREAK")
        tmp_db_conn.commit()
        before = tmp_db_conn.execute('SELECT * FROM "RunnerObservation" WHERE resultId = ?', (result_id,)).fetchall()
        load_behavioural_observations(tmp_db_conn, result_ids=[result_id])
        after = tmp_db_conn.execute('SELECT * FROM "RunnerObservation" WHERE resultId = ?', (result_id,)).fetchall()
        assert [dict(r) for r in before] == [dict(r) for r in after]

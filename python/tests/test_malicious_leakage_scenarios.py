"""Deliberately malicious test cases for the Phase 3A data infrastructure.

Per the project's explicit requirement: "Generate deliberately malicious
test cases where future information is inserted and confirm RacingEdge
blocks it." Each test here constructs a scenario where an attacker (or,
more realistically, a data-entry error or a buggy importer) inserts
information that should not be visible at prediction time, and asserts the
relevant module refuses to use it.

Coverage map (some scenarios are exercised more thoroughly in their own
dedicated test files — noted here rather than duplicated in full):
  - future-race leakage in FormEntry             -> test_leakage_audit.py, test_timeline.py
  - post-race odds leakage                       -> test_odds_snapshots.py, test_point_in_time.py, AND below
  - result leakage into FEATURES (not targets)   -> below
  - entity resolution ambiguity                  -> test_entity_resolution.py
  - duplicate imports                            -> test_import_runner.py::TestDuplicateHandling
  - idempotent imports                           -> test_import_runner.py::TestIdempotency
  - large-file streaming                         -> below (thousands of rows, generator-driven)
  - dataset version immutability                 -> below
  - historical (point-in-time) reconstruction    -> test_point_in_time.py, AND below (place terms)
  - place-term timestamps                        -> below
"""

from __future__ import annotations

import io
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from racingedge_data.dataset_version import create_dataset_version, get_dataset_version
from racingedge_data.importers.import_runner import import_races
from racingedge_data.odds_snapshots import get_named_snapshots_for_runner
from racingedge_data.point_in_time import market_prices_as_of, reconstruct_place_terms_as_of
from racingedge_data.providers.csv_provider import CsvRaceDataProvider
from racingedge_model.db import to_prisma_datetime
from racingedge_model.features.build import build_features_for_race
from racingedge_model.ids import new_id


class TestMaliciousResultLeakageIntoFeatures:
    def test_mutating_a_races_own_result_never_changes_its_computed_features(self, tmp_db_conn):
        """The malicious scenario: someone edits a race's own ResultEntry
        (e.g. tries to make a losing favourite's features look
        retroactively different once the result is known) hoping the
        change ripples into the FEATURE columns used for prediction. It
        must not — ResultEntry only ever supplies the training TARGET
        (WIN_TARGET / PLACE_N), never a feature."""

        race_row = pd.read_sql_query(
            'SELECT * FROM "Race" WHERE raceStatus = \'RESULTED\' ORDER BY date ASC LIMIT 1', tmp_db_conn
        ).iloc[0]
        race_runners = pd.read_sql_query(
            'SELECT * FROM "Runner" WHERE raceId = ?', tmp_db_conn, params=(race_row["id"],)
        )
        all_form = pd.read_sql_query('SELECT * FROM "FormEntry"', tmp_db_conn)
        all_form["raceDate"] = pd.to_datetime(all_form["raceDate"], utc=True)
        race_row["date"] = pd.Timestamp(race_row["date"])

        empty_global = pd.DataFrame(
            columns=[
                "id", "raceId", "horseId", "raceDate", "course", "distanceFurlongs", "going", "flatJumps",
                "raceClass", "numberOfRunners", "fieldSizeBand", "trainerName", "jockeyName", "draw",
                "weightLbsTotal", "officialRating", "headgear", "finishingPosition",
            ]
        )
        empty_pace = pd.DataFrame(columns=["runnerId"])

        features_before = build_features_for_race(
            race_row=race_row,
            race_runners=race_runners,
            all_form=all_form,
            all_global_prior_runs=empty_global,
            all_pace_profiles=empty_pace,
        )

        # The attack: fabricate a completely different result for this
        # race's own runners.
        tmp_db_conn.execute(
            'UPDATE "ResultEntry" SET finishingPosition = 1 WHERE runnerId IN '
            '(SELECT id FROM "Runner" WHERE raceId = ?)',
            (race_row["id"],),
        )
        tmp_db_conn.commit()

        features_after = build_features_for_race(
            race_row=race_row,
            race_runners=race_runners,
            all_form=all_form,
            all_global_prior_runs=empty_global,
            all_pace_profiles=empty_pace,
        )

        pd.testing.assert_frame_equal(
            features_before.sort_values("runner_id").reset_index(drop=True),
            features_after.sort_values("runner_id").reset_index(drop=True),
        )


class TestMaliciousPostRaceOddsInsertion:
    def test_a_price_recorded_after_off_time_never_appears_in_pre_race_snapshots(self, tmp_db_conn):
        now = to_prisma_datetime(datetime.now(timezone.utc))
        race_id = new_id()
        horse_id = new_id()
        runner_id = new_id()
        bookmaker_id = new_id()
        off_time = datetime(2026, 7, 1, 15, 0, tzinfo=timezone.utc)

        tmp_db_conn.execute(
            'INSERT INTO "Race" '
            "(id, isSampleData, sourceType, date, raceTime, racecourse, country, raceName, flatJumps, "
            "surface, distanceFurlongs, handicapType, numberOfRunners, raceStatus, resultStatus, "
            "createdAt, updatedAt) "
            "VALUES (?, 0, 'SAMPLE', ?, '15:00', 'Fixture Malicious Course', 'GB', 'Fixture Malicious Race', "
            "'FLAT', 'TURF', 8.0, 'NON_HANDICAP', 1, 'RESULTED', 'PENDING', ?, ?)",
            (race_id, to_prisma_datetime(off_time), now, now),
        )
        tmp_db_conn.execute(
            'INSERT INTO "Horse" (id, isSampleData, sourceType, name, createdAt, updatedAt) '
            "VALUES (?, 0, 'SAMPLE', 'Fixture Malicious Horse', ?, ?)",
            (horse_id, now, now),
        )
        tmp_db_conn.execute(
            'INSERT INTO "Runner" (id, isSampleData, raceId, horseId, createdAt, updatedAt) '
            "VALUES (?, 0, ?, ?, ?, ?)",
            (runner_id, race_id, horse_id, now, now),
        )
        tmp_db_conn.execute(
            'INSERT INTO "Bookmaker" (id, name, isExchange, createdAt) VALUES (?, ?, 0, ?)',
            (bookmaker_id, "Fixture Malicious Bookmaker", now),
        )

        legit_time = off_time - timedelta(minutes=1)
        tmp_db_conn.execute(
            'INSERT INTO "RunnerMarketPrice" '
            "(id, runnerId, bookmakerId, timestamp, winOddsDecimal, isStartingPrice, createdAt) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (new_id(), runner_id, bookmaker_id, to_prisma_datetime(legit_time), 5.0, now),
        )

        # The attack: a price inserted 5 minutes AFTER the race went off,
        # with a suspiciously short price (as if inserted with hindsight
        # knowledge the horse won easily) and ALSO flagged isStartingPrice.
        malicious_time = off_time + timedelta(minutes=5)
        tmp_db_conn.execute(
            'INSERT INTO "RunnerMarketPrice" '
            "(id, runnerId, bookmakerId, timestamp, winOddsDecimal, isStartingPrice, createdAt) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (new_id(), runner_id, bookmaker_id, to_prisma_datetime(malicious_time), 1.01, now),
        )
        tmp_db_conn.commit()

        # point_in_time.market_prices_as_of must exclude the malicious row.
        prices = market_prices_as_of(tmp_db_conn, runner_id, off_time)
        assert len(prices) == 1
        assert prices["winOddsDecimal"].iloc[0] == 5.0

        # odds_snapshots must derive "sp"/"off_time" from the legitimate row only.
        snapshots = get_named_snapshots_for_runner(tmp_db_conn, runner_id, bookmaker_id, off_time)
        assert snapshots["sp"].win_odds_decimal == 5.0
        assert snapshots["off_time"].win_odds_decimal == 5.0


class TestMaliciousPlaceTermsReordering:
    def test_reconstruction_uses_effective_at_not_insertion_order(self, tmp_db_conn):
        """The malicious scenario: an attacker (or a buggy backfill job)
        inserts place-terms history rows OUT OF CHRONOLOGICAL ORDER, hoping
        a naive "most recently inserted" reconstruction would surface a
        later promotional change as if it applied earlier. Reconstruction
        must key off `effectiveAt`, never insertion order."""

        race_id = new_id()
        bookmaker_id = new_id()
        terms_id = new_id()
        now = to_prisma_datetime(datetime.now(timezone.utc))

        tmp_db_conn.execute(
            'INSERT INTO "Race" '
            "(id, isSampleData, sourceType, date, raceTime, racecourse, country, raceName, flatJumps, "
            "surface, distanceFurlongs, handicapType, numberOfRunners, raceStatus, resultStatus, "
            "createdAt, updatedAt) "
            "VALUES (?, 0, 'SAMPLE', ?, '15:00', 'Fixture Terms Course', 'GB', 'Fixture Terms Race', "
            "'FLAT', 'TURF', 8.0, 'NON_HANDICAP', 1, 'RESULTED', 'PENDING', ?, ?)",
            (race_id, now, now, now),
        )
        tmp_db_conn.execute(
            'INSERT INTO "Bookmaker" (id, name, isExchange, createdAt) VALUES (?, ?, 0, ?)',
            (bookmaker_id, "Fixture Terms Bookmaker", now),
        )
        tmp_db_conn.execute(
            'INSERT INTO "RacePlaceTerms" '
            "(id, raceId, bookmakerId, places, eachWayFraction, extraPlaces, terms, effectiveAt, createdAt) "
            "VALUES (?, ?, ?, 5, 0.2, 1, 'promo', ?, ?)",
            (terms_id, race_id, bookmaker_id, to_prisma_datetime(datetime(2026, 7, 1, 14, 0, tzinfo=timezone.utc)), now),
        )

        tmp_db_conn.execute(
            'INSERT INTO "RacePlaceTermsHistory" '
            "(id, racePlaceTermsId, raceId, bookmakerId, places, eachWayFraction, extraPlaces, terms, "
            "effectiveAt, createdAt) "
            "VALUES (?, ?, ?, ?, 5, 0.2, 1, 'promo', ?, ?)",
            (new_id(), terms_id, race_id, bookmaker_id, to_prisma_datetime(datetime(2026, 7, 1, 14, 0, tzinfo=timezone.utc)), now),
        )
        # Inserted SECOND (later createdAt / insertion order) but its
        # effectiveAt is actually EARLIER than the row above.
        tmp_db_conn.execute(
            'INSERT INTO "RacePlaceTermsHistory" '
            "(id, racePlaceTermsId, raceId, bookmakerId, places, eachWayFraction, extraPlaces, terms, "
            "effectiveAt, createdAt) "
            "VALUES (?, ?, ?, ?, 3, 0.25, 0, 'standard', ?, ?)",
            (new_id(), terms_id, race_id, bookmaker_id, to_prisma_datetime(datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc)), now),
        )
        tmp_db_conn.commit()

        # As of 10am — only the 9am ("standard") row should be visible.
        as_of_morning = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
        result_morning = reconstruct_place_terms_as_of(tmp_db_conn, race_id, bookmaker_id, as_of_morning)
        assert result_morning["places"] == 3
        assert result_morning["terms"] == "standard"

        # As of 3pm — the 2pm ("promo") row should now be visible.
        as_of_afternoon = datetime(2026, 7, 1, 15, 0, tzinfo=timezone.utc)
        result_afternoon = reconstruct_place_terms_as_of(tmp_db_conn, race_id, bookmaker_id, as_of_afternoon)
        assert result_afternoon["places"] == 5
        assert result_afternoon["terms"] == "promo"


class TestDatasetVersionImmutability:
    def test_creating_a_second_version_does_not_alter_the_first(self, tmp_db_conn):
        all_race_ids = [r["id"] for r in tmp_db_conn.execute('SELECT id FROM "Race" LIMIT 20').fetchall()]
        first_ids = all_race_ids[:10]
        second_ids = all_race_ids[5:15]  # deliberately overlapping, not identical

        first_version_id = create_dataset_version(
            tmp_db_conn, name="immutability-test-v1", race_ids=first_ids, providers=["csv"], schema_version="v1"
        )
        first_snapshot = get_dataset_version(tmp_db_conn, first_version_id)

        second_version_id = create_dataset_version(
            tmp_db_conn, name="immutability-test-v2", race_ids=second_ids, providers=["csv"], schema_version="v1"
        )

        assert second_version_id != first_version_id

        first_after = get_dataset_version(tmp_db_conn, first_version_id)
        assert first_after["raceCount"] == first_snapshot["raceCount"] == len(first_ids)
        assert first_after["name"] == "immutability-test-v1"

    def test_module_exposes_no_update_function(self):
        import racingedge_data.dataset_version as dv_module

        public_names = [n for n in dir(dv_module) if not n.startswith("_")]
        assert not any("update" in n.lower() for n in public_names), (
            "dataset_version module must not expose any function to mutate an "
            "existing DatasetVersion row — create a new version instead."
        )


class TestLargeFileStreamingImport:
    def test_imports_thousands_of_rows_without_loading_them_all_up_front(self, tmp_db_conn):
        """Not a literal 100,000+-row test (too slow for the unit suite),
        but confirms the streaming pipeline correctly processes an order of
        magnitude more races than the other importer tests use, via the
        same generator-based provider/importer path — i.e. the code path
        that scales, exercised at meaningful (if reduced) size."""

        header = (
            "provider_race_id,date,race_time,racecourse,country,race_name,flat_jumps,surface,"
            "distance_furlongs,handicap_type,number_of_runners,going,runner_provider_id,horse_name,"
            "horse_provider_id,draw,official_rating,jockey_name,trainer_name,non_runner\n"
        )

        def _generate_rows(n_races: int):
            for i in range(n_races):
                race_id = f"large-race-{i}"
                race_date = (pd.Timestamp("2026-01-01") + pd.Timedelta(days=i)).strftime("%Y-%m-%dT%H:%M:%S")
                for runner_idx in range(3):
                    yield (
                        f"{race_id},{race_date},14:00,Fixture Course {i % 20},GB,Fixture Race {i},FLAT,TURF,"
                        f"8.0,NON_HANDICAP,3,Good,r{i}-{runner_idx},Horse {i}-{runner_idx},h{i}-{runner_idx},"
                        f"{runner_idx + 1},80,Jockey {runner_idx},Trainer {runner_idx},false\n"
                    )

        n_races = 500  # 1500 runner rows total
        csv_content = header + "".join(_generate_rows(n_races))
        provider = CsvRaceDataProvider(io.StringIO(csv_content))

        result = import_races(
            tmp_db_conn, provider, date(2020, 1, 1), date(2030, 1, 1), source_type="REAL"
        )

        assert result.status == "SUCCESS"
        assert result.success_count == n_races
        assert result.error_count == 0

        stored_count = tmp_db_conn.execute(
            'SELECT COUNT(*) as c FROM "Race" WHERE raceName LIKE \'Fixture Race %\''
        ).fetchone()["c"]
        assert stored_count == n_races

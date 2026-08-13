"""The explicit anti-leakage test: mutating a FUTURE race's result must
NEVER change the features computed for an EARLIER race. This is checked
end-to-end against a real (isolated, disposable) copy of the project
database rather than synthetic fixtures, so it exercises the actual
date-filtering logic in features/build.py and dataset.py.
"""

import pandas as pd

from racingedge_model import db
from racingedge_model.features.build import assert_no_leakage, build_features_for_race, build_global_prior_runs, LeakageError


def _snapshot_features(conn, target_race_row, target_runner_id):
    runners = db.load_runners_df(conn)
    races_df = db.load_races_df(conn)
    results = db.load_results_df(conn)
    form = db.load_form_entries_df(conn)
    pace = db.load_pace_profiles_df(conn)
    global_prior = build_global_prior_runs(runners, races_df, results)

    race_runners = runners[runners["raceId"] == target_race_row["id"]]
    feats = build_features_for_race(
        race_row=target_race_row,
        race_runners=race_runners,
        all_form=form,
        all_global_prior_runs=global_prior,
        all_pace_profiles=pace,
    )
    return feats.set_index("runner_id").loc[target_runner_id]


def test_mutating_a_future_race_result_does_not_change_earlier_race_features(tmp_db_conn):
    races = db.load_races_df(tmp_db_conn)
    resulted = races[races["raceStatus"] == "RESULTED"].sort_values("date").reset_index(drop=True)
    assert len(resulted) >= 5, "need enough resulted races for a meaningful leakage test"

    target_race = resulted.iloc[len(resulted) // 3]
    future_races = resulted[resulted["date"] > target_race["date"]]
    assert len(future_races) > 0, "need at least one race after the target race"
    future_race = future_races.iloc[-1]  # the LATEST race in the whole dataset

    runners_all = db.load_runners_df(tmp_db_conn)
    target_runner_id = runners_all[runners_all["raceId"] == target_race["id"]].iloc[0]["id"]

    before = _snapshot_features(tmp_db_conn, target_race, target_runner_id)

    # Aggressively mutate every runner in the FUTURE race: flip finishing
    # positions to an impossible value and inflate ratings, in both the
    # relational history (Runner/Race/ResultEntry) and the denormalised
    # FormEntry record.
    future_runner_ids = [
        r["id"] for r in tmp_db_conn.execute('SELECT id FROM "Runner" WHERE raceId = ?', (future_race["id"],)).fetchall()
    ]
    for runner_id in future_runner_ids:
        tmp_db_conn.execute('UPDATE "ResultEntry" SET finishingPosition = 999 WHERE runnerId = ?', (runner_id,))
        tmp_db_conn.execute('UPDATE "Runner" SET officialRating = 250 WHERE id = ?', (runner_id,))
    tmp_db_conn.execute(
        'UPDATE "FormEntry" SET finishingPosition = 999, officialRating = 250 WHERE linkedRaceId = ?',
        (future_race["id"],),
    )
    tmp_db_conn.commit()

    after = _snapshot_features(tmp_db_conn, target_race, target_runner_id)

    pd.testing.assert_series_equal(before, after, check_names=False)


def test_assert_no_leakage_raises_when_history_is_not_strictly_before_as_of_date():
    as_of = pd.Timestamp("2026-01-10", tz="UTC")
    bad_history = pd.DataFrame({"raceDate": [pd.Timestamp("2026-01-10", tz="UTC")]})  # equal, not before
    try:
        assert_no_leakage(as_of, bad_history)
        assert False, "expected LeakageError"
    except LeakageError:
        pass


def test_assert_no_leakage_passes_for_strictly_prior_history():
    as_of = pd.Timestamp("2026-01-10", tz="UTC")
    good_history = pd.DataFrame({"raceDate": [pd.Timestamp("2026-01-09", tz="UTC")]})
    assert_no_leakage(as_of, good_history)  # should not raise

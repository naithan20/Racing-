from racingedge_model import db


def _sample_model_version_fields(name="test-model", version="v1"):
    return {
        "name": name,
        "version": version,
        "featureSetVersion": "test-1",
        "algorithm": "logistic_regression",
        "hyperparameters": "{}",
        "calibrationMethod": "none",
        "trainingStartDate": "2026-01-01T00:00:00.000+00:00",
        "trainingEndDate": "2026-02-01T00:00:00.000+00:00",
        "trainingRowCount": 100,
        "trainingRaceCount": 10,
    }


def test_retraining_creates_a_new_model_version_row_not_an_update(tmp_db_conn):
    with db.transaction(tmp_db_conn):
        id_v1 = db.insert_model_version(tmp_db_conn, _sample_model_version_fields(version="v1"))
        id_v2 = db.insert_model_version(tmp_db_conn, _sample_model_version_fields(version="v2"))

    assert id_v1 != id_v2
    rows = tmp_db_conn.execute('SELECT id, version FROM "ModelVersion" WHERE name = ?', ("test-model",)).fetchall()
    versions = {r["version"] for r in rows}
    assert versions == {"v1", "v2"}


def test_model_version_row_is_never_mutated_by_a_later_training_run(tmp_db_conn):
    with db.transaction(tmp_db_conn):
        id_v1 = db.insert_model_version(tmp_db_conn, _sample_model_version_fields(version="v1"))
    before = dict(tmp_db_conn.execute('SELECT * FROM "ModelVersion" WHERE id = ?', (id_v1,)).fetchone())

    with db.transaction(tmp_db_conn):
        db.insert_model_version(tmp_db_conn, _sample_model_version_fields(version="v2"))

    after = dict(tmp_db_conn.execute('SELECT * FROM "ModelVersion" WHERE id = ?', (id_v1,)).fetchone())
    assert before == after


def test_generating_a_new_prediction_snapshot_never_updates_an_existing_one(tmp_db_conn):
    runner_id = tmp_db_conn.execute('SELECT id FROM "Runner" LIMIT 1').fetchone()["id"]

    with db.transaction(tmp_db_conn):
        snapshot_1_id = db.insert_prediction_snapshot(tmp_db_conn, {"runnerId": runner_id, "winProbability": 0.1})
    before = dict(tmp_db_conn.execute('SELECT * FROM "PredictionSnapshot" WHERE id = ?', (snapshot_1_id,)).fetchone())

    with db.transaction(tmp_db_conn):
        snapshot_2_id = db.insert_prediction_snapshot(tmp_db_conn, {"runnerId": runner_id, "winProbability": 0.9})

    after = dict(tmp_db_conn.execute('SELECT * FROM "PredictionSnapshot" WHERE id = ?', (snapshot_1_id,)).fetchone())
    assert before == after  # the first snapshot is byte-for-byte unchanged
    assert snapshot_1_id != snapshot_2_id

    count = tmp_db_conn.execute(
        'SELECT COUNT(*) as c FROM "PredictionSnapshot" WHERE runnerId = ?', (runner_id,)
    ).fetchone()["c"]
    assert count >= 2


def test_prediction_snapshots_default_to_locked(tmp_db_conn):
    runner_id = tmp_db_conn.execute('SELECT id FROM "Runner" LIMIT 1').fetchone()["id"]
    with db.transaction(tmp_db_conn):
        snapshot_id = db.insert_prediction_snapshot(tmp_db_conn, {"runnerId": runner_id, "winProbability": 0.2})
    row = tmp_db_conn.execute('SELECT isLocked FROM "PredictionSnapshot" WHERE id = ?', (snapshot_id,)).fetchone()
    assert row["isLocked"] == 1

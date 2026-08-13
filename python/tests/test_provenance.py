from datetime import datetime, timezone

from racingedge_data.provenance import (
    ProvenanceRecord,
    hash_payload,
    record_place_terms_change,
    record_provenance,
    record_race_field_change,
    record_runner_field_change,
    record_sectional_point,
)


def test_hash_payload_is_stable_and_order_independent():
    a = hash_payload({"b": 2, "a": 1})
    b = hash_payload({"a": 1, "b": 2})
    assert a == b
    assert len(a) == 64  # sha256 hex digest


def test_hash_payload_distinguishes_different_content():
    assert hash_payload({"a": 1}) != hash_payload({"a": 2})
    assert hash_payload("raw text") != hash_payload("other text")


def test_record_provenance_inserts_and_is_readable(tmp_db_conn):
    race_id = tmp_db_conn.execute('SELECT id FROM "Race" LIMIT 1').fetchone()["id"]

    provenance_id = record_provenance(
        tmp_db_conn,
        ProvenanceRecord(
            entity_type="Race",
            entity_id=race_id,
            data_domain="RACE_CARD",
            provider="csv",
            provider_record_id="ext-race-123",
            provider_timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            effective_at=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
            source_version="v1",
            raw_payload_hash=hash_payload({"foo": "bar"}),
        ),
    )
    tmp_db_conn.commit()

    row = tmp_db_conn.execute(
        'SELECT * FROM "DataProvenance" WHERE id = ?', (provenance_id,)
    ).fetchone()
    assert row is not None
    assert row["entityType"] == "Race"
    assert row["entityId"] == race_id
    assert row["dataDomain"] == "RACE_CARD"
    assert row["provider"] == "csv"
    assert row["providerRecordId"] == "ext-race-123"
    assert row["retrievedAt"] is not None


def test_record_race_field_change_logs_a_row(tmp_db_conn):
    race_id = tmp_db_conn.execute('SELECT id FROM "Race" LIMIT 1').fetchone()["id"]

    history_id = record_race_field_change(
        tmp_db_conn,
        race_id=race_id,
        field_name="going",
        field_value="Good to Soft",
        effective_at=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc),
        source="csv",
    )
    tmp_db_conn.commit()

    row = tmp_db_conn.execute(
        'SELECT * FROM "RaceFieldHistory" WHERE id = ?', (history_id,)
    ).fetchone()
    assert row["raceId"] == race_id
    assert row["fieldName"] == "going"
    assert row["fieldValue"] == "Good to Soft"


def test_record_runner_field_change_logs_a_row(tmp_db_conn):
    runner_id = tmp_db_conn.execute('SELECT id FROM "Runner" LIMIT 1').fetchone()["id"]

    history_id = record_runner_field_change(
        tmp_db_conn,
        runner_id=runner_id,
        field_name="draw",
        field_value="4",
        effective_at=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc),
    )
    tmp_db_conn.commit()

    row = tmp_db_conn.execute(
        'SELECT * FROM "RunnerFieldHistory" WHERE id = ?', (history_id,)
    ).fetchone()
    assert row["runnerId"] == runner_id
    assert row["fieldName"] == "draw"
    assert row["fieldValue"] == "4"


def test_record_place_terms_change_logs_superseded_state(tmp_db_conn):
    terms_row = tmp_db_conn.execute('SELECT * FROM "RacePlaceTerms" LIMIT 1').fetchone()
    assert terms_row is not None

    history_id = record_place_terms_change(
        tmp_db_conn,
        race_place_terms_id=terms_row["id"],
        race_id=terms_row["raceId"],
        bookmaker_id=terms_row["bookmakerId"],
        places=3,
        each_way_fraction=0.25,
        extra_places=False,
        terms="1-2-3",
        effective_at=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc),
        superseded_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        source="manual",
    )
    tmp_db_conn.commit()

    row = tmp_db_conn.execute(
        'SELECT * FROM "RacePlaceTermsHistory" WHERE id = ?', (history_id,)
    ).fetchone()
    assert row["racePlaceTermsId"] == terms_row["id"]
    assert row["places"] == 3
    assert row["supersededAt"] is not None


def test_record_sectional_point_logs_a_row(tmp_db_conn):
    runner_id = tmp_db_conn.execute('SELECT id FROM "Runner" LIMIT 1').fetchone()["id"]

    point_id = record_sectional_point(
        tmp_db_conn,
        runner_id=runner_id,
        segment_index=0,
        segment_distance_furlongs=1.0,
        segment_time_seconds=12.3,
        speed_mps=16.4,
        source="sectional-feed",
    )
    tmp_db_conn.commit()

    row = tmp_db_conn.execute(
        'SELECT * FROM "RunnerSectionalPoint" WHERE id = ?', (point_id,)
    ).fetchone()
    assert row["runnerId"] == runner_id
    assert row["segmentIndex"] == 0
    assert row["segmentDistanceFurlongs"] == 1.0

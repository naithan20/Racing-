import json

import pytest

from racingedge_data.dataset_version import (
    DEFAULT_MIN_REAL_RACES,
    DEFAULT_MIN_REAL_RUNNERS,
    build_data_quality_snapshot,
    classify_readiness,
    create_dataset_version,
    determine_source_type,
    get_dataset_version,
    infer_providers_for_races,
    readiness_for_dataset_version,
)


class TestClassifyReadiness:
    def test_below_threshold_is_research_model(self):
        result = classify_readiness(race_count=500, runner_count=5000)
        assert result.is_production_ready is False
        assert result.label == "RESEARCH MODEL — INSUFFICIENT HISTORICAL DATA"

    def test_at_or_above_threshold_is_production_ready(self):
        result = classify_readiness(
            race_count=DEFAULT_MIN_REAL_RACES, runner_count=DEFAULT_MIN_REAL_RUNNERS
        )
        assert result.is_production_ready is True
        assert result.label == "PRODUCTION-READY"

    def test_races_ok_but_runners_short_is_not_ready(self):
        result = classify_readiness(race_count=20_000, runner_count=1000)
        assert result.is_production_ready is False

    def test_thresholds_are_configurable(self):
        result = classify_readiness(race_count=100, runner_count=1000, min_races=50, min_runners=500)
        assert result.is_production_ready is True


class TestDetermineSourceType:
    def test_pure_real(self):
        assert determine_source_type({"REAL"}) == "REAL"

    def test_pure_synthetic(self):
        assert determine_source_type({"SYNTHETIC"}) == "SYNTHETIC"

    def test_mixed_sources_is_mixed(self):
        assert determine_source_type({"REAL", "SYNTHETIC"}) == "MIXED"
        assert determine_source_type({"SAMPLE", "SYNTHETIC"}) == "MIXED"

    def test_empty_set_raises(self):
        with pytest.raises(ValueError):
            determine_source_type(set())


class TestBuildDataQualitySnapshot:
    def test_empty_race_ids_returns_zero_counts(self, tmp_db_conn):
        snapshot = build_data_quality_snapshot(tmp_db_conn, [])
        assert snapshot["race_count"] == 0
        assert snapshot["runner_count"] == 0

    def test_computes_missingness_percentages(self, tmp_db_conn):
        race_ids = [r["id"] for r in tmp_db_conn.execute('SELECT id FROM "Race" LIMIT 5').fetchall()]
        snapshot = build_data_quality_snapshot(tmp_db_conn, race_ids)
        assert snapshot["race_count"] == len(race_ids)
        assert snapshot["runner_count"] >= 0
        if snapshot["runner_count"] > 0:
            assert 0 <= snapshot["missing_official_rating_pct"] <= 100


class TestCreateDatasetVersion:
    def test_creates_and_persists_a_version(self, tmp_db_conn):
        race_rows = tmp_db_conn.execute('SELECT id FROM "Race" LIMIT 10').fetchall()
        race_ids = [r["id"] for r in race_rows]

        version_id = create_dataset_version(
            tmp_db_conn,
            name="test-version-1",
            race_ids=race_ids,
            providers=["csv", "synthetic-generator"],
            schema_version="test-schema-v1",
            notes="unit test",
        )
        tmp_db_conn.commit()

        version = get_dataset_version(tmp_db_conn, version_id)
        assert version is not None
        assert version["name"] == "test-version-1"
        assert version["raceCount"] == len(race_ids)
        assert json.loads(version["providersJson"]) == ["csv", "synthetic-generator"]
        assert version["sourceType"] in ("REAL", "SYNTHETIC", "SAMPLE", "MIXED")

    def test_raises_on_unknown_race_id(self, tmp_db_conn):
        with pytest.raises(ValueError, match="not found"):
            create_dataset_version(
                tmp_db_conn,
                name="bad-version",
                race_ids=["does-not-exist"],
                providers=["csv"],
                schema_version="v1",
            )

    def test_raises_on_empty_race_ids(self, tmp_db_conn):
        with pytest.raises(ValueError):
            create_dataset_version(
                tmp_db_conn, name="empty-version", race_ids=[], providers=["csv"], schema_version="v1"
            )

    def test_deduplicates_race_ids(self, tmp_db_conn):
        race_id = tmp_db_conn.execute('SELECT id FROM "Race" LIMIT 1').fetchone()["id"]
        version_id = create_dataset_version(
            tmp_db_conn,
            name="dedup-version",
            race_ids=[race_id, race_id, race_id],
            providers=["csv"],
            schema_version="v1",
        )
        version = get_dataset_version(tmp_db_conn, version_id)
        assert version["raceCount"] == 1


class TestInferProvidersForRaces:
    def test_empty_returns_empty(self, tmp_db_conn):
        assert infer_providers_for_races(tmp_db_conn, []) == []

    def test_falls_back_when_no_provenance_recorded(self, tmp_db_conn):
        race_id = tmp_db_conn.execute('SELECT id FROM "Race" LIMIT 1').fetchone()["id"]
        providers = infer_providers_for_races(tmp_db_conn, [race_id])
        assert providers == ["legacy-seed-or-generator"]

    def test_returns_recorded_provider(self, tmp_db_conn):
        from racingedge_data.provenance import ProvenanceRecord, record_provenance

        race_id = tmp_db_conn.execute('SELECT id FROM "Race" LIMIT 1').fetchone()["id"]
        record_provenance(
            tmp_db_conn,
            ProvenanceRecord(entity_type="Race", entity_id=race_id, data_domain="RACE_CARD", provider="csv"),
        )
        tmp_db_conn.commit()
        assert infer_providers_for_races(tmp_db_conn, [race_id]) == ["csv"]


class TestReadinessForDatasetVersion:
    def test_non_real_dataset_is_never_production_ready(self, tmp_db_conn):
        race_ids = [
            r["id"]
            for r in tmp_db_conn.execute(
                'SELECT id FROM "Race" WHERE sourceType = \'SYNTHETIC\' LIMIT 50'
            ).fetchall()
        ]
        if not race_ids:
            pytest.skip("no synthetic races in database")

        version_id = create_dataset_version(
            tmp_db_conn, name="synthetic-version", race_ids=race_ids, providers=["synthetic-generator"], schema_version="v1"
        )
        readiness = readiness_for_dataset_version(tmp_db_conn, version_id, min_races=1, min_runners=1)
        assert readiness.is_production_ready is False
        assert readiness.label == "RESEARCH MODEL — INSUFFICIENT HISTORICAL DATA"

    def test_unknown_dataset_version_raises(self, tmp_db_conn):
        with pytest.raises(ValueError):
            readiness_for_dataset_version(tmp_db_conn, "does-not-exist")

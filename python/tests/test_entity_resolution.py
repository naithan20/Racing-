import json

from racingedge_data.entity_resolution import (
    normalize_name,
    resolve_free_text_entity,
    resolve_horse,
)


class TestNormalizeName:
    def test_lowercases_and_strips_punctuation(self):
        assert normalize_name("O'Brien") == "obrien"
        assert normalize_name("O'Brien.") == "obrien"

    def test_collapses_whitespace(self):
        assert normalize_name("  Kingman   Stakes  ") == "kingman stakes"

    def test_does_not_merge_genuinely_different_names(self):
        assert normalize_name("Kingman") != normalize_name("King's Man")

    def test_strips_diacritics(self):
        assert normalize_name("Séamus") == "seamus"


class TestResolveHorse:
    def test_creates_new_horse_on_first_sighting(self, tmp_db_conn):
        result = resolve_horse(tmp_db_conn, "Brand New Horse", provider_name="csv", source_type="REAL")
        tmp_db_conn.commit()

        assert result.created_new is True
        row = tmp_db_conn.execute('SELECT * FROM "Horse" WHERE id = ?', (result.canonical_id,)).fetchone()
        assert row["name"] == "Brand New Horse"
        assert row["sourceType"] == "REAL"

    def test_provider_id_match_reuses_canonical_horse(self, tmp_db_conn):
        first = resolve_horse(
            tmp_db_conn, "Repeat Horse", provider_name="csv", provider_horse_id="prov-123", source_type="REAL"
        )
        tmp_db_conn.commit()

        second = resolve_horse(
            tmp_db_conn, "Repeat Horse", provider_name="csv", provider_horse_id="prov-123", source_type="REAL"
        )
        tmp_db_conn.commit()

        assert second.canonical_id == first.canonical_id
        assert second.created_new is False
        assert second.match_method == "PROVIDER_ID"

    def test_exact_normalized_name_match_reuses_canonical_horse_without_provider_id(self, tmp_db_conn):
        first = resolve_horse(tmp_db_conn, "Named Horse", provider_name="csv-a", source_type="REAL")
        tmp_db_conn.commit()

        # A second provider reports the exact same name (differently punctuated)
        # with no provider id at all — should resolve to the same horse via
        # exact normalized-name match, not create a duplicate.
        second = resolve_horse(tmp_db_conn, "Named  Horse", provider_name="csv-b", source_type="REAL")
        tmp_db_conn.commit()

        assert second.canonical_id == first.canonical_id
        assert second.created_new is False
        assert second.match_method == "EXACT_NORMALIZED_NAME"

    def test_different_provider_ids_with_same_normalized_name_still_resolve_together(self, tmp_db_conn):
        first = resolve_horse(
            tmp_db_conn, "Cross Provider Horse", provider_name="csv-a", provider_horse_id="a-1", source_type="REAL"
        )
        tmp_db_conn.commit()

        second = resolve_horse(
            tmp_db_conn, "Cross Provider Horse", provider_name="csv-b", provider_horse_id="b-9", source_type="REAL"
        )
        tmp_db_conn.commit()

        assert second.canonical_id == first.canonical_id

        # And a THIRD sighting from provider csv-b with the same provider id
        # should now be a direct PROVIDER_ID hit.
        third = resolve_horse(
            tmp_db_conn, "Cross Provider Horse", provider_name="csv-b", provider_horse_id="b-9", source_type="REAL"
        )
        assert third.match_method == "PROVIDER_ID"
        assert third.canonical_id == first.canonical_id

    def test_ambiguous_normalized_name_creates_new_horse_and_queues_review(self, tmp_db_conn):
        # Simulate two genuinely different existing horses that happen to
        # share a normalized name (deliberately constructed for the test —
        # this should never be produced by normal resolution, since exact
        # matches always reuse the existing canonical id).
        first = resolve_horse(tmp_db_conn, "Ambiguous Horse", provider_name="csv-a", provider_horse_id="a-1")
        tmp_db_conn.commit()

        # Force a second, genuinely distinct Horse row that happens to
        # share the same normalized name (as could occur with two real,
        # different horses that coincidentally share a name).
        from racingedge_data.entity_resolution import _create_horse, _insert_alias, normalize_name

        second_horse_id = _create_horse(tmp_db_conn, "Ambiguous Horse", None, None, None, None, "REAL")
        _insert_alias(
            tmp_db_conn,
            "HORSE",
            second_horse_id,
            "Ambiguous Horse",
            normalize_name("Ambiguous Horse"),
            "csv-b",
            "b-1",
            "PROVIDER_ID",
        )
        tmp_db_conn.commit()

        assert first.canonical_id != second_horse_id

        # Now a THIRD sighting, from a new provider with no provider id,
        # should find TWO candidates and refuse to guess.
        third = resolve_horse(tmp_db_conn, "Ambiguous Horse", provider_name="csv-c")
        tmp_db_conn.commit()

        assert third.ambiguous is True
        assert third.created_new is True
        assert third.canonical_id not in (first.canonical_id, second_horse_id)

        queue_row = tmp_db_conn.execute(
            'SELECT * FROM "EntityResolutionQueueItem" WHERE rawName = ? ORDER BY createdAt DESC LIMIT 1',
            ("Ambiguous Horse",),
        ).fetchone()
        assert queue_row is not None
        assert queue_row["status"] == "PENDING"
        candidate_ids = json.loads(queue_row["candidateCanonicalIdsJson"])
        assert set(candidate_ids) == {first.canonical_id, second_horse_id}


class TestResolveFreeTextEntity:
    def test_first_sighting_is_created_new(self, tmp_db_conn):
        result = resolve_free_text_entity(tmp_db_conn, "TRAINER", "A. P. O'Brien")
        tmp_db_conn.commit()
        assert result.created_new is True
        assert result.canonical_id == normalize_name("A. P. O'Brien")

    def test_repeat_raw_spelling_is_not_recreated(self, tmp_db_conn):
        first = resolve_free_text_entity(tmp_db_conn, "JOCKEY", "R. Moore")
        tmp_db_conn.commit()
        second = resolve_free_text_entity(tmp_db_conn, "JOCKEY", "R. Moore")
        tmp_db_conn.commit()
        assert first.canonical_id == second.canonical_id
        assert second.created_new is False

    def test_different_raw_spellings_of_same_normalized_name_share_canonical_id(self, tmp_db_conn):
        first = resolve_free_text_entity(tmp_db_conn, "COURSE", "Newmarket (July)")
        second = resolve_free_text_entity(tmp_db_conn, "COURSE", "Newmarket  (July)")
        assert first.canonical_id == second.canonical_id

    def test_rejects_unsupported_entity_type(self, tmp_db_conn):
        import pytest

        with pytest.raises(ValueError):
            resolve_free_text_entity(tmp_db_conn, "HORSE", "Some Horse")

import pytest

from racingedge_model.features.registry import (
    FEATURE_GROUPS,
    FEATURE_PROFILES,
    all_feature_keys,
    feature_keys_for_profile,
)


def test_registry_has_no_duplicate_keys_across_groups():
    keys = all_feature_keys()
    assert len(keys) == len(set(keys)), "a feature key is documented in more than one group"


def test_every_group_has_required_metadata_fields():
    required = {"group", "category", "calculation_method", "source_fields", "missing_behaviour", "feature_keys"}
    for group in FEATURE_GROUPS:
        missing = required - set(group.keys())
        assert not missing, f"group {group.get('group')} is missing metadata fields: {missing}"
        assert len(group["feature_keys"]) > 0
        assert len(group["calculation_method"]) > 20  # a real sentence, not a stub
        assert len(group["missing_behaviour"]) > 20


def test_registry_matches_actual_computed_features_on_a_real_race(full_dataset):
    from racingedge_model.dataset import feature_columns

    computed = set(feature_columns(full_dataset))
    registered = set(all_feature_keys())
    assert computed == registered


class TestFeatureProfiles:
    def test_full_model_includes_every_feature_key(self):
        assert set(feature_keys_for_profile("FULL_MODEL")) == set(all_feature_keys())

    def test_core_free_model_excludes_pace_group(self):
        pace_group = next(g for g in FEATURE_GROUPS if g["group"] == "pace")
        core_keys = set(feature_keys_for_profile("CORE_FREE_MODEL"))
        assert not (set(pace_group["feature_keys"]) & core_keys)

    def test_core_free_model_excludes_headgear_group(self):
        headgear_group = next(g for g in FEATURE_GROUPS if g["group"] == "headgear_changes")
        core_keys = set(feature_keys_for_profile("CORE_FREE_MODEL"))
        assert not (set(headgear_group["feature_keys"]) & core_keys)

    def test_enriched_free_model_includes_headgear_but_not_pace(self):
        headgear_group = next(g for g in FEATURE_GROUPS if g["group"] == "headgear_changes")
        pace_group = next(g for g in FEATURE_GROUPS if g["group"] == "pace")
        enriched_keys = set(feature_keys_for_profile("ENRICHED_FREE_MODEL"))
        assert set(headgear_group["feature_keys"]) <= enriched_keys
        assert not (set(pace_group["feature_keys"]) & enriched_keys)

    def test_core_is_a_subset_of_enriched_is_a_subset_of_full(self):
        core = set(feature_keys_for_profile("CORE_FREE_MODEL"))
        enriched = set(feature_keys_for_profile("ENRICHED_FREE_MODEL"))
        full = set(feature_keys_for_profile("FULL_MODEL"))
        assert core <= enriched <= full

    def test_unknown_profile_raises(self):
        with pytest.raises(ValueError):
            feature_keys_for_profile("NOT_A_REAL_PROFILE")

    def test_every_profile_group_exists_in_registry(self):
        group_names = {g["group"] for g in FEATURE_GROUPS}
        for groups in FEATURE_PROFILES.values():
            assert set(groups) <= group_names

from racingedge_model.features.registry import FEATURE_GROUPS, all_feature_keys


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

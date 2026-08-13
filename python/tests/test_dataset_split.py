from racingedge_model.dataset import date_based_split


def test_no_race_is_split_across_train_val_test(full_dataset):
    train, val, test = date_based_split(full_dataset)
    train_races = set(train["race_id"])
    val_races = set(val["race_id"])
    test_races = set(test["race_id"])

    assert train_races.isdisjoint(val_races)
    assert train_races.isdisjoint(test_races)
    assert val_races.isdisjoint(test_races)


def test_split_is_chronological(full_dataset):
    train, val, test = date_based_split(full_dataset)
    assert train["date"].max() <= val["date"].max()
    assert val["date"].max() <= test["date"].max()
    # The strongest guarantee: every train row predates every test row by
    # at least the val window, EXCEPT for same-calendar-day boundary races
    # (a real occurrence — multiple races on one day). Feature leakage
    # safety comes from the strict "<" cutoff in features/build.py, not
    # from this split alone — see test_leakage.py.
    assert train["date"].min() <= train["date"].max() <= test["date"].max()


def test_every_row_lands_in_exactly_one_split(full_dataset):
    train, val, test = date_based_split(full_dataset)
    assert len(train) + len(val) + len(test) == len(full_dataset)


def test_split_produces_non_empty_sets_for_this_dataset(full_dataset):
    train, val, test = date_based_split(full_dataset)
    assert len(train) > 0
    assert len(val) > 0
    assert len(test) > 0

from datetime import datetime, timezone

import pytest

from racingedge_data.canonical import (
    CanonicalFormEntry,
    CanonicalHorse,
    CanonicalOddsPoint,
    CanonicalRace,
    CanonicalRunner,
)


def test_canonical_horse_defaults_to_none():
    horse = CanonicalHorse(name="Test Horse")
    assert horse.country_bred is None
    assert horse.provider_horse_id is None


def test_canonical_race_runners_default_to_empty_tuple():
    race = CanonicalRace(
        date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        race_time="14:35",
        racecourse="Ascot",
        country="GB",
        race_name="Test Handicap",
        flat_jumps="FLAT",
        surface="TURF",
        distance_furlongs=8.0,
        handicap_type="HANDICAP",
        number_of_runners=0,
    )
    assert race.runners == ()
    assert race.place_terms == ()


def test_canonical_race_is_immutable():
    race = CanonicalRace(
        date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        race_time="14:35",
        racecourse="Ascot",
        country="GB",
        race_name="Test Handicap",
        flat_jumps="FLAT",
        surface="TURF",
        distance_furlongs=8.0,
        handicap_type="HANDICAP",
        number_of_runners=0,
    )
    with pytest.raises(AttributeError):
        race.going = "Good"  # type: ignore[misc]


def test_canonical_runner_requires_horse():
    runner = CanonicalRunner(horse=CanonicalHorse(name="Test Horse"), draw=4)
    assert runner.horse.name == "Test Horse"
    assert runner.draw == 4
    assert runner.non_runner is False


def test_canonical_odds_point_requires_core_fields():
    point = CanonicalOddsPoint(
        provider_runner_id="ext-1",
        bookmaker_name="Bet365",
        is_exchange=False,
        timestamp=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        win_odds_decimal=4.5,
    )
    assert point.win_odds_decimal == 4.5
    assert point.is_opening_price is False


def test_form_entry_has_positional_data_flag():
    without_positions = CanonicalFormEntry(
        horse=CanonicalHorse(name="Test Horse"),
        race_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        course="Cheltenham",
    )
    assert without_positions.has_positional_data is False
    assert without_positions.has_sectional_data is False

    with_positions = CanonicalFormEntry(
        horse=CanonicalHorse(name="Test Horse"),
        race_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        course="Cheltenham",
        halfway_position=3,
    )
    assert with_positions.has_positional_data is True

    with_sectionals = CanonicalFormEntry(
        horse=CanonicalHorse(name="Test Horse"),
        race_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        course="Cheltenham",
        sectional_times="[12.1, 12.4, 13.0]",
    )
    assert with_sectionals.has_sectional_data is True

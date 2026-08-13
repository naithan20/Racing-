import io
import json
from datetime import date
from pathlib import Path

import pytest

from racingedge_data.canonical import CanonicalRace
from racingedge_data.providers import betfair, racing_api, timeform
from racingedge_data.providers.base import ProviderConfigurationError
from racingedge_data.providers.betfair import BetfairProvider
from racingedge_data.providers.csv_provider import CsvRaceDataProvider
from racingedge_data.providers.generic_json_provider import GenericJsonRaceDataProvider
from racingedge_data.providers.racing_api import RacingApiProvider
from racingedge_data.providers.timeform import TimeformProvider

FIXTURES_DIR = Path(racing_api.__file__).resolve().parent / "fixtures"

CSV_SAMPLE = """provider_race_id,date,race_time,racecourse,country,race_name,flat_jumps,surface,distance_furlongs,handicap_type,number_of_runners,going,runner_provider_id,horse_name,horse_provider_id,draw,official_rating,jockey_name,trainer_name,non_runner
race-1,2026-02-01T14:00:00,14:00,Fixture Course,GB,Fixture Maiden Stakes,FLAT,TURF,8.0,NON_HANDICAP,2,Good,r1,Horse One,h1,3,80,Jockey One,Trainer One,false
race-1,2026-02-01T14:00:00,14:00,Fixture Course,GB,Fixture Maiden Stakes,FLAT,TURF,8.0,NON_HANDICAP,2,Good,r2,Horse Two,h2,5,75,Jockey Two,Trainer Two,false
race-2,2026-02-01T15:00:00,15:00,Fixture Course,GB,Fixture Handicap,FLAT,TURF,10.0,HANDICAP,1,Good to Soft,r3,Horse Three,h3,1,90,Jockey Three,Trainer Three,false
"""


class TestCsvRaceDataProvider:
    def test_groups_rows_into_races_by_provider_race_id(self):
        provider = CsvRaceDataProvider(io.StringIO(CSV_SAMPLE))
        races = list(provider.fetch_races(date(2026, 1, 1), date(2026, 12, 31)))
        assert len(races) == 2
        assert races[0].provider_race_id == "race-1"
        assert len(races[0].runners) == 2
        assert races[1].provider_race_id == "race-2"
        assert len(races[1].runners) == 1

    def test_maps_runner_fields_correctly(self):
        provider = CsvRaceDataProvider(io.StringIO(CSV_SAMPLE))
        races = list(provider.fetch_races(date(2026, 1, 1), date(2026, 12, 31)))
        first_runner = races[0].runners[0]
        assert first_runner.horse.name == "Horse One"
        assert first_runner.horse.provider_horse_id == "h1"
        assert first_runner.draw == 3
        assert first_runner.official_rating == 80
        assert first_runner.non_runner is False

    def test_filters_by_date_range(self):
        provider = CsvRaceDataProvider(io.StringIO(CSV_SAMPLE))
        races = list(provider.fetch_races(date(2026, 2, 1), date(2026, 2, 1)))
        assert len(races) == 2  # both races are on 2026-02-01

        races_out_of_range = list(provider.fetch_races(date(2026, 3, 1), date(2026, 3, 31)))
        assert races_out_of_range == []

    def test_blank_values_become_none(self):
        csv_with_blank = (
            "provider_race_id,date,race_time,racecourse,country,race_name,flat_jumps,"
            "surface,distance_furlongs,handicap_type,number_of_runners,going,"
            "runner_provider_id,horse_name,draw\n"
            "race-1,2026-02-01T14:00:00,14:00,Fixture Course,GB,Fixture Race,FLAT,TURF,"
            "8.0,NON_HANDICAP,1,,r1,Horse One,\n"
        )
        provider = CsvRaceDataProvider(io.StringIO(csv_with_blank))
        races = list(provider.fetch_races(date(2026, 1, 1), date(2026, 12, 31)))
        assert races[0].going is None
        assert races[0].runners[0].draw is None


GENERIC_JSON_ARRAY = json.dumps(
    [
        {
            "provider_race_id": "race-1",
            "date": "2026-03-01T13:00:00",
            "race_time": "13:00",
            "racecourse": "Fixture Course",
            "country": "GB",
            "race_name": "Fixture Novice Hurdle",
            "flat_jumps": "JUMPS",
            "surface": "TURF",
            "distance_furlongs": 16.0,
            "handicap_type": "NON_HANDICAP",
            "number_of_runners": 1,
            "runners": [
                {"provider_runner_id": "r1", "draw": None, "horse": {"name": "Horse One"}}
            ],
        }
    ]
)

GENERIC_JSONL = "\n".join(
    [
        json.dumps(
            {
                "provider_race_id": "race-1",
                "date": "2026-03-01T13:00:00",
                "race_time": "13:00",
                "racecourse": "Fixture Course",
                "country": "GB",
                "race_name": "Fixture Novice Hurdle",
                "flat_jumps": "JUMPS",
                "surface": "TURF",
                "distance_furlongs": 16.0,
                "handicap_type": "NON_HANDICAP",
                "number_of_runners": 1,
                "runners": [{"provider_runner_id": "r1", "horse": {"name": "Horse One"}}],
            }
        ),
        json.dumps(
            {
                "provider_race_id": "race-2",
                "date": "2026-03-02T13:00:00",
                "race_time": "13:00",
                "racecourse": "Fixture Course",
                "country": "GB",
                "race_name": "Fixture Handicap",
                "flat_jumps": "FLAT",
                "surface": "TURF",
                "distance_furlongs": 10.0,
                "handicap_type": "HANDICAP",
                "number_of_runners": 1,
                "runners": [{"provider_runner_id": "r2", "horse": {"name": "Horse Two"}}],
            }
        ),
    ]
)


class TestGenericJsonRaceDataProvider:
    def test_parses_json_array(self):
        provider = GenericJsonRaceDataProvider(io.StringIO(GENERIC_JSON_ARRAY))
        races = list(provider.fetch_races(date(2026, 1, 1), date(2026, 12, 31)))
        assert len(races) == 1
        assert isinstance(races[0], CanonicalRace)
        assert races[0].runners[0].horse.name == "Horse One"

    def test_parses_jsonl(self):
        provider = GenericJsonRaceDataProvider(io.StringIO(GENERIC_JSONL))
        races = list(provider.fetch_races(date(2026, 1, 1), date(2026, 12, 31)))
        assert len(races) == 2
        assert races[0].provider_race_id == "race-1"
        assert races[1].provider_race_id == "race-2"

    def test_unknown_keys_are_ignored(self):
        payload = json.loads(GENERIC_JSON_ARRAY)
        payload[0]["some_unrecognized_field"] = "ignored"
        provider = GenericJsonRaceDataProvider(io.StringIO(json.dumps(payload)))
        races = list(provider.fetch_races(date(2026, 1, 1), date(2026, 12, 31)))
        assert len(races) == 1


class TestFixtureBackedStubAdapters:
    def test_racing_api_without_fixture_raises_configuration_error(self):
        provider = RacingApiProvider()
        with pytest.raises(ProviderConfigurationError, match="RACING_API"):
            list(provider.fetch_races(date(2020, 1, 1), date(2030, 1, 1)))

    def test_racing_api_with_fixture_maps_canonical_fields(self):
        provider = RacingApiProvider(fixture_path=FIXTURES_DIR / "racing_api_sample.json")
        races = list(provider.fetch_races(date(2020, 1, 1), date(2030, 1, 1)))
        assert len(races) == 1
        race = races[0]
        assert race.racecourse == "Fixture Park"
        assert race.flat_jumps == "JUMPS"
        assert race.handicap_type == "HANDICAP"
        assert len(race.runners) == 2
        assert race.runners[0].horse.name == "Fixture Test Horse A"
        assert race.runners[0].official_rating == 128

    def test_timeform_without_fixture_raises_configuration_error(self):
        provider = TimeformProvider()
        with pytest.raises(ProviderConfigurationError, match="TIMEFORM"):
            list(provider.fetch_form_entries(date(2020, 1, 1), date(2030, 1, 1)))

    def test_timeform_with_fixture_maps_canonical_fields(self):
        provider = TimeformProvider(fixture_path=FIXTURES_DIR / "timeform_sample.json")
        entries = list(provider.fetch_form_entries(date(2020, 1, 1), date(2030, 1, 1)))
        assert len(entries) == 1
        entry = entries[0]
        assert entry.horse.name == "Fixture Test Horse A"
        assert entry.course == "Fixture Downs"
        assert entry.finishing_position == 2
        assert entry.has_positional_data is True

    def test_betfair_without_fixture_raises_configuration_error(self):
        provider = BetfairProvider()
        with pytest.raises(ProviderConfigurationError, match="BETFAIR"):
            list(provider.fetch_odds(date(2020, 1, 1), date(2030, 1, 1)))

    def test_betfair_with_fixture_maps_exchange_specific_fields(self):
        provider = BetfairProvider(fixture_path=FIXTURES_DIR / "betfair_sample.json")
        points = list(provider.fetch_odds(date(2020, 1, 1), date(2030, 1, 1)))
        assert len(points) == 2
        assert points[0].is_exchange is True
        assert points[0].back_odds_decimal == 6.4
        assert points[0].lay_odds_decimal == 6.6
        assert points[0].available_volume == 15230.5
        assert points[1].is_starting_price is True

    def test_missing_fixture_file_raises_configuration_error(self, tmp_path):
        provider = RacingApiProvider(fixture_path=tmp_path / "does_not_exist.json")
        with pytest.raises(ProviderConfigurationError, match="not found"):
            list(provider.fetch_races(date(2020, 1, 1), date(2030, 1, 1)))

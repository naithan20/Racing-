import gzip

from racingedge_data.importers.file_io import build_race_provider_from_path
from racingedge_data.providers.csv_provider import CsvRaceDataProvider
from racingedge_data.providers.generic_json_provider import GenericJsonRaceDataProvider

CSV_CONTENT = (
    "provider_race_id,date,race_time,racecourse,country,race_name,flat_jumps,surface,"
    "distance_furlongs,handicap_type,number_of_runners\n"
    "race-1,2026-05-01T14:00:00,14:00,Fixture Course,GB,Fixture Race,FLAT,TURF,8.0,NON_HANDICAP,0\n"
)

JSONL_CONTENT = (
    '{"provider_race_id": "race-1", "date": "2026-05-01T14:00:00", "race_time": "14:00", '
    '"racecourse": "Fixture Course", "country": "GB", "race_name": "Fixture Race", '
    '"flat_jumps": "FLAT", "surface": "TURF", "distance_furlongs": 8.0, '
    '"handicap_type": "NON_HANDICAP", "number_of_runners": 0}\n'
)


def test_plain_csv_path_builds_csv_provider(tmp_path):
    path = tmp_path / "races.csv"
    path.write_text(CSV_CONTENT, encoding="utf-8")
    provider = build_race_provider_from_path(path)
    assert isinstance(provider, CsvRaceDataProvider)


def test_gzipped_csv_path_builds_csv_provider_and_reads_correctly(tmp_path):
    path = tmp_path / "races.csv.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(CSV_CONTENT)

    provider = build_race_provider_from_path(path)
    assert isinstance(provider, CsvRaceDataProvider)

    from datetime import date

    races = list(provider.fetch_races(date(2026, 1, 1), date(2026, 12, 31)))
    assert len(races) == 1
    assert races[0].racecourse == "Fixture Course"


def test_gzipped_jsonl_path_builds_json_provider_and_reads_correctly(tmp_path):
    path = tmp_path / "races.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(JSONL_CONTENT)

    provider = build_race_provider_from_path(path)
    assert isinstance(provider, GenericJsonRaceDataProvider)

    from datetime import date

    races = list(provider.fetch_races(date(2026, 1, 1), date(2026, 12, 31)))
    assert len(races) == 1
    assert races[0].racecourse == "Fixture Course"


def test_unrecognized_extension_raises(tmp_path):
    import pytest

    path = tmp_path / "races.txt"
    path.write_text("not a real format", encoding="utf-8")
    with pytest.raises(ValueError, match="Unrecognized file type"):
        build_race_provider_from_path(path)

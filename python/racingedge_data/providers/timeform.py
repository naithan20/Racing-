"""Stub adapter for a licensed "Timeform"-style historical form/ratings
provider.

**This adapter does not make any network call and does not scrape
timeform.com or any other website.** No credentials were available when
this was built. It exists to prove the adapter/field-mapping pattern for
`HistoricalResultsProvider` and to be fully testable via
`FixtureBackedProvider`.

To connect this to a real account, a maintainer needs to:
1. Obtain a licensed data feed or API subscription and credentials — set
   them via environment variables, e.g. `TIMEFORM_API_KEY`.
2. Implement an HTTP client inside `TimeformProvider.fetch_form_entries`
   that calls the provider's documented historical-form endpoint and
   returns data shaped like `fixtures/timeform_sample.json` (or whatever the
   real response shape turns out to be — the field-mapping constants below
   would need updating to match the real API's actual field names, which
   this build has not verified against real documentation).
3. Respect the provider's terms of service and licensing restrictions.

The fixture's field names below are an illustrative, plausible shape chosen
to demonstrate field translation — NOT verified against Timeform's actual
API/export contract.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterator

from racingedge_data.canonical import CanonicalFormEntry, CanonicalHorse
from racingedge_data.providers.base import FixtureBackedProvider, HistoricalResultsProvider
from racingedge_data.providers.csv_provider import parse_race_date


def _map_form_entry(obj: dict[str, Any]) -> CanonicalFormEntry:
    horse = CanonicalHorse(name=obj.get("horse", ""), provider_horse_id=obj.get("horse_id"))
    return CanonicalFormEntry(
        horse=horse,
        race_date=parse_race_date(obj["date"]),
        course=obj.get("course", ""),
        country=obj.get("country"),
        distance_furlongs=obj.get("distance_f"),
        going=obj.get("going"),
        race_class=obj.get("class"),
        field_size=obj.get("field_size"),
        finishing_position=obj.get("position"),
        finish_status=obj.get("finish_status"),
        beaten_distance_lengths=obj.get("beaten_lengths"),
        starting_price_decimal=obj.get("sp_decimal"),
        official_rating=obj.get("or"),
        draw=obj.get("draw"),
        jockey_name=obj.get("jockey"),
        headgear=obj.get("headgear"),
        race_comment=obj.get("comment"),
        halfway_position=obj.get("halfway_pos"),
        position_3f_out=obj.get("pos_3f_out"),
        position_2f_out=obj.get("pos_2f_out"),
        position_1f_out=obj.get("pos_1f_out"),
        finishing_speed_percentage=obj.get("finishing_speed_pct"),
        linked_race_provider_id=obj.get("race_id"),
    )


class TimeformProvider(FixtureBackedProvider, HistoricalResultsProvider):
    name = "timeform"
    required_credentials_note = (
        "a licensed Timeform data feed subscription (credentials via "
        "TIMEFORM_API_KEY env var) plus an HTTP client implementation in "
        "TimeformProvider.fetch_form_entries — neither exists in this build"
    )

    def fetch_form_entries(self, start_date: date, end_date: date) -> Iterator[CanonicalFormEntry]:
        payload = self._load_fixture_json()
        records = payload.get("form", []) if isinstance(payload, dict) else payload
        for obj in records:
            entry = _map_form_entry(obj)
            if start_date <= entry.race_date.date() <= end_date:
                yield entry

"""Provider-agnostic ingestion adapters.

Each module here maps ONE external data source's field names/quirks onto
the canonical dataclasses in `racingedge_data.canonical`. Nothing outside
this package should ever branch on "which provider" — importers and
downstream code only ever see canonical objects.

Supported today:
- `csv_provider.CsvRaceDataProvider` — user-supplied CSV files.
- `generic_json_provider.GenericJsonRaceDataProvider` — user-supplied JSON/JSONL files.
- `racing_api.RacingApiProvider`, `timeform.TimeformProvider`,
  `betfair.BetfairProvider` — fixture-backed stub adapters demonstrating the
  interface for named commercial providers. None of these make network
  calls or scrape any website — see each module's docstring for exactly
  what a real deployment would need to supply.
"""

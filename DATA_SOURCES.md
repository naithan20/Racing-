# Data Sources — Phase 3A

RacingEdge's overriding objective for Phase 3A is **data integrity**, not predictive power. This
document explains exactly where data is allowed to come from, how the provider abstraction works,
and — for every adapter that isn't yet connected to a real feed — precisely what credentials or
files a maintainer needs to supply to make it real.

## The rule: no scraping, ever

RacingEdge does not scrape websites, and never will. The only supported data sources are:

1. **Licensed or authorised APIs** — a commercial racing-data provider with an actual API contract
   and credentials (e.g. a racecards/results API, Timeform, a betting exchange).
2. **User-provided CSV/JSON/JSONL files** — including compressed (`.gz`) variants for large files.
3. **Purchased historical datasets** — delivered as files, imported the same way as (2).

If you don't have real credentials or a real dataset, the correct move is to build and fully test
the provider *interface* against fixtures (which is what this repository does — see below), then
report exactly what's missing. Fabricating "realistic-looking" racing data and presenting it as
real is explicitly disallowed by this project's own design.

## The provider abstraction

Every data domain has its own narrow interface, defined in
`python/racingedge_data/providers/base.py`:

| Interface | Purpose |
|---|---|
| `RaceDataProvider` | Race cards: race + runners + place terms |
| `HistoricalResultsProvider` | Historical per-horse form/results |
| `OddsDataProvider` | Timestamped odds observations (fixed-odds or exchange) |
| `SectionalDataProvider` | Optional granular in-running tracking data |
| `WeatherDataProvider` | Optional weather readings, kept separate from official going |

An adapter implements one or more of these and maps its provider's field names onto the canonical
dataclasses in `racingedge_data/canonical.py` (`CanonicalRace`, `CanonicalRunner`,
`CanonicalHorse`, `CanonicalOddsPoint`, `CanonicalFormEntry`, `CanonicalSectionalPoint`,
`CanonicalWeatherReading`). Nothing downstream of the canonical layer — entity resolution,
importers, feature engineering — ever needs to know which provider supplied the data.

## Adapters shipped in this repository

### `csv_provider.CsvRaceDataProvider` — ready to use today

Reads a "wide" CSV (one row per runner, race fields repeated per runner). Column names match the
`Canonical*` field names in snake_case — see `RACE_FIELDS` / `RUNNER_FIELDS` in
`racingedge_data/providers/csv_provider.py` for the exact recognized headers. This is the primary
supported path for a purchased historical dataset delivered as CSV.

### `generic_json_provider.GenericJsonRaceDataProvider` — ready to use today

Reads a JSON array or JSON Lines file of race objects (nested `"runners"` array). Unknown keys are
ignored, so a provider's richer export can be pointed at this adapter without a translation step
for every field. Use this when a provider's native export is JSON and doesn't flatten cleanly into
the CSV provider's wide-row format.

### `racing_api.RacingApiProvider` — fixture-only, NOT connected to a live feed

**Status: interface built and tested against a fixture (`providers/fixtures/racing_api_sample.json`),
no real API integration.** This adapter demonstrates non-trivial field translation (provider field
names like `meeting`, `off_dt`, `type`, `distance_f` mapped to canonical names) for a
racecards-API-shaped provider. To make it real, a maintainer needs to:

1. Obtain a licensed racecards/results API subscription.
2. Set credentials via environment variables — this build expects `RACING_API_USERNAME` /
   `RACING_API_PASSWORD` (adjust to whatever the real provider actually requires).
3. Implement an HTTP client inside `RacingApiProvider.fetch_races` that calls the provider's
   documented endpoint for a date range and returns JSON. **The field names used in the fixture are
   illustrative and have not been verified against any real provider's actual API — update
   `_map_race` / `_map_runner` in `racing_api.py` to match the real contract once you have it.**

### `timeform.TimeformProvider` — fixture-only, NOT connected to a live feed

Same status as above, for historical form/ratings data (`HistoricalResultsProvider`). Requires a
licensed Timeform (or equivalent) data feed subscription; this build expects a `TIMEFORM_API_KEY`
environment variable and has no HTTP client implemented. See
`providers/fixtures/timeform_sample.json` for the illustrative fixture shape and
`TimeformProvider.fetch_form_entries` for where to add a real client.

### `betfair.BetfairProvider` — fixture-only, NOT connected to a live feed

Same status, for exchange odds (`OddsDataProvider`) — the one adapter that demonstrates
exchange-specific fields (back/lay prices, matched volume, market status) that fixed-odds
bookmaker feeds don't have. Requires a Betfair (or equivalent exchange) API app key and session
token; this build expects `BETFAIR_APP_KEY` / `BETFAIR_SESSION_TOKEN` and has no client
implemented. See `providers/fixtures/betfair_sample.json` and `BetfairProvider.fetch_odds`.

## Exactly what's needed to go from fixture-only to real

For each of the three stub adapters above:

1. **Credentials** — obtain the licensed subscription and the specific environment variables noted
   in that adapter's docstring.
2. **Real API documentation** — the field-mapping constants in each adapter file were written to
   demonstrate the translation pattern, not copied from a verified real API contract. Update them
   once you have the provider's actual documented response shape.
3. **An HTTP client** — none of the three stub adapters make a network call. Add one (e.g. using
   `requests` or `httpx`), respecting the provider's rate limits and terms of service.
4. **Re-run the adapter's tests** (`python/tests/test_providers.py`) against the fixture to confirm
   the field-mapping logic still holds, then add an integration test (not committed here, since it
   would require real credentials) that exercises the live client.

No other code needs to change: once an adapter yields `CanonicalRace` / `CanonicalFormEntry` /
`CanonicalOddsPoint` objects, `racingedge_data.importers.import_runner.import_races` and the rest
of the pipeline work identically regardless of where the data came from.

## Importing data once you have a real source

```python
from datetime import date
from racingedge_data.importers.file_io import build_race_provider_from_path
from racingedge_data.importers.import_runner import import_races
from racingedge_model import db

conn = db.get_connection()
provider = build_race_provider_from_path("historical_races.csv.gz")  # or .json/.jsonl, gzip optional
result = import_races(
    conn, provider,
    start_date=date(2015, 1, 1), end_date=date(2025, 1, 1),
    source_type="REAL",              # explicit — never silently guessed
    idempotency_key="acme-2015-2025-v1",  # safe to re-run with the same key
)
print(result.status, result.success_count, result.duplicate_rows, result.error_count)
```

`import_races` streams the provider's races one at a time (never loading a whole 1,000,000-row
file into memory), tracks progress/duplicates/errors on the `ImportBatch` row as it goes, and is
safe to re-run with the same `idempotency_key`. See `python/racingedge_data/importers/import_runner.py`
for full behaviour (resume support, failed-row reporting) and
[DATA_PROVENANCE.md](./DATA_PROVENANCE.md) for what gets recorded about where each row came from.

## Licensing reminder

Every commercial racing-data provider has its own licensing terms covering redistribution, storage
duration, and permitted use (research vs. commercial). This repository does not include any real
racing data and takes no position on any specific provider's terms — read and comply with whatever
licence governs the data you actually import.

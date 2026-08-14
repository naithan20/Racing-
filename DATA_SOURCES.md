# Data Sources — Phase 3A/3B

RacingEdge's overriding objective for Phase 3A/3B is **data integrity**, not predictive power. This
document explains exactly where data is allowed to come from, how the provider abstraction works,
and — for every adapter — precisely what credentials or files a maintainer needs to supply to
actually pull real data through it.

## The rule: no scraping, ever

RacingEdge does not scrape websites, and never will. The only supported data sources are:

1. **Licensed or authorised APIs** — a commercial racing-data provider with an actual API contract
   and credentials (e.g. a racecards/results API, Timeform, a betting exchange).
2. **User-provided CSV/JSON/JSONL files** — including compressed (`.gz`) variants for large files.
3. **Purchased historical datasets** — delivered as files, imported the same way as (2).

If you don't have real credentials or a real dataset, the correct move is to build and fully test
the provider *interface* against fixtures (which is what this repository does), then report
exactly what's missing. Fabricating "realistic-looking" racing data and presenting it as real is
explicitly disallowed by this project's own design.

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
dataclasses in `racingedge_data/canonical.py`. Nothing downstream of the canonical layer — entity
resolution, importers, feature engineering — ever needs to know which provider supplied the data.

## Adapters shipped in this repository

### `csv_provider.CsvRaceDataProvider` / `generic_json_provider.GenericJsonRaceDataProvider` — ready to use today

Read a wide-format CSV or a JSON/JSONL file of race objects, respectively. This is the primary
supported path for a purchased historical dataset delivered as files (see "Importing data" below).

### `racing_api.RacingApiProvider` — the primary Phase 3B target, real HTTP client implemented, **not run against a live account (no credentials in this environment)**

Adapter for **The Racing API** (`theracingapi.com`), a licensed UK & Irish racecards/results
provider using HTTP Basic Authentication.

**What was verified, and how.** Direct access to `https://api.theracingapi.com/documentation` and
`https://www.theracingapi.com/` was **blocked by this environment's network egress policy**
(`EGRESS_BLOCKED` on every attempt) while building this adapter — so "the official documentation"
could not be read directly from this sandbox. Instead, the following facts were confirmed from the
vendor's own publicly published example scripts on GitHub and their OpenAPI listing in the
`APIs-guru/openapi-directory` repository (genuine primary sources, just not the live docs site):

- Base URL: `https://api.theracingapi.com/v1`
- Auth: HTTP Basic (username + password)
- **Rate limit: 2 requests/second, across all plans**
- Endpoints confirmed to exist: `GET /racecards` (today's/tomorrow's cards), `GET /results`
  (historical, paginated via `start_date`/`end_date`/`limit`/`skip` + a `total` count in the
  response — **this is the endpoint the import CLI uses**), `GET /horses/{horse_id}/results`,
  `GET /horses/search`, `GET /jockeys/*`, `GET /dams/*`, `GET /damsires/*`, `GET /courses`,
  `GET /courses/regions`.
- Confirmed response fields: top-level `racecards` / `results` / `runners` / `total` / `query`;
  per-race `region`, `course`, `off_time`; per-runner `horse`, `horse_id`, `jockey`, `jockey_id`,
  `trainer`, `trainer_id`, `sex_code`/`sex`.
- **NOT verified**: official rating, draw, weight, going, race class, distance, sire/dam/damsire,
  headgear, and starting-price field names. These are almost certainly present in a real response
  (this is a comprehensive commercial API) but this build could not inspect one to confirm the
  exact key spellings. `racing_api.py`'s `_UNVERIFIED_RUNNER_FIELD_CANDIDATES` /
  `_UNVERIFIED_RACE_FIELD_CANDIDATES` list the key names the adapter *tries*, in order — informed
  guesses based on common UK-racing-data-feed naming conventions, explicitly **not** confirmed
  facts. **A maintainer with real credentials must verify these against one real response and
  correct the candidate lists before trusting the resulting data for training.** Nothing in this
  build's own test suite asserts a specific value for any of these unverified fields — only that a
  missing key degrades to `None` rather than raising.

**What's actually implemented**: a real HTTP client (`_RacingApiHttpClient`, using `requests`) with
the confirmed rate limit, `limit`/`skip`/`total` pagination, and retry with exponential backoff on
429/5xx/connection errors (5 attempts). `RacingApiProvider.fetch_races` pages through `/results` for
a date range — the correct endpoint for historical ingestion.

**To go live**, set two environment variables (a licensed theracingapi.com subscription):

```bash
export RACING_API_USERNAME="..."
export RACING_API_PASSWORD="..."
```

Neither is set anywhere in this repository or environment. Without them,
`RacingApiProvider.fetch_races` raises `ProviderConfigurationError` (or, for the CLI, prints a
clear message and exits) rather than falling back to fixtures or fabricating data.

### `timeform.TimeformProvider` — fixture-only, not this phase's target

Unchanged from Phase 3A: interface built and tested against a fixture, no live HTTP client. Needs a
licensed Timeform (or equivalent) subscription (`TIMEFORM_API_KEY`) and an implemented client in
`TimeformProvider.fetch_form_entries` before it can pull real data. Not prioritised in Phase 3B
since Racing API's `/results` already carries historical results and runners.

### `betfair.BetfairProvider` — fixture-only live-feed shape, not this phase's target

Unchanged from Phase 3A: models a live/streaming exchange feed shape, needs `BETFAIR_APP_KEY` /
`BETFAIR_SESSION_TOKEN` and a real streaming client. **For historical exchange odds, use
`betfair_historical.py` instead — see below.**

### `betfair_historical.py` — parser for *purchased* Betfair Historical Data files (Phase 3B)

Separate from `betfair.py` (which models a *live* exchange feed): this module parses files a
maintainer has already **purchased and downloaded** from `historicdata.betfair.com` and extracted
locally. It makes no network call and this build purchased nothing automatically, per instruction.

**Format**: Betfair Historical Data files are recordings of the Exchange Stream API's "market
change message" (`mcm`) wire format — newline-delimited JSON, one message per line, optionally
gzip-compressed. This is a long-stable, extremely widely documented public format (used by
`betfairlightweight`, `flumine`, and countless other independent clients), unlike Racing API's
proprietary REST field names above — this build has high confidence in it without needing live
verification. Each message carries:

- `pt` — publish time in **epoch milliseconds**, the genuine timestamp of that price update. Every
  `CanonicalOddsPoint` this parser produces carries this exact timestamp, never an inferred one.
- `mc[].marketDefinition.runners[]` — `{id, name}` pairs; Betfair's `id` (selection id) is an
  exchange-internal identifier with no meaning outside Betfair, so `name` is the only link back to
  a horse's real identity.
- `mc[].rc[]` — per-selection price changes: `id` (selection id), `ltp` (last traded price),
  `atb`/`atl` (available-to-back/lay ladders), `tv` (total matched volume).

**Mapping to runner identities**: `import_betfair_historical_file` resolves each selection's
`marketDefinition` name through `entity_resolution.resolve_horse` (exact-normalized-name matching
— never fuzzy) to find the corresponding RacingEdge `Runner`. **This module does not create new
races/runners** — the exchange feed alone doesn't carry going/class/distance/etc., so a race's card
must already be imported (e.g. via Racing API) before its odds history can be attached. A selection
that can't be resolved (unknown horse name, or a horse with no `Runner` row yet) is reported in the
returned `unresolved` list — never guessed or silently dropped.

**What you need to actually use this**:

1. A Betfair Historical Data purchase from `historicdata.betfair.com` covering horse racing (WIN
   market type) for the desired date range. **This environment could not reach
   `historicdata.betfair.com` or `support.developer.betfair.com` to confirm current plan
   names/pricing/file packaging** (both `EGRESS_BLOCKED`) — confirm current tiers (historically
   BASIC/ADVANCED/PRO) and exact bundling at purchase time.
2. Extract the purchased archive with standard tools (`tar -xf ...`, `gunzip ...` as needed) —
   this module parses already-extracted, newline-delimited-JSON market files; it does not do
   archive extraction.
3. Import the race card first (Racing API or a CSV/JSON file), then:

```python
from racingedge_data.providers.betfair_historical import import_betfair_historical_file
from racingedge_model import db

conn = db.get_connection()
inserted, unresolved = import_betfair_historical_file(conn, "1.999000001.jsonl.gz")
conn.commit()
print(f"{inserted} price points inserted, {len(unresolved)} selections unresolved")
for u in unresolved:
    print(u)  # UnresolvedSelection(market_id=..., selection_id=..., horse_name=..., reason=...)
```

**Do not block Racing API ingestion on this being available** — Phase 3B's baseline retrain uses
starting prices already carried in `/results` (once verified — see the unverified-fields note
above), not exchange price histories.

## Importing race cards + results once you have credentials

```bash
npm run data:racingapi -- --from 2024-01-01 --to 2026-08-01
```

or equivalently, directly:

```bash
RACING_API_USERNAME=... RACING_API_PASSWORD=... \
  python -m racingedge_data.cli.import_racing_api --from 2024-01-01 --to 2026-08-01
```

This command is resumable (`--resume-batch-id`), idempotent (defaults to a key derived from the
date range), rate-limit aware (respects the confirmed 2 req/s ceiling), pagination-aware, retries
with exponential backoff, reports progress live, logs failed records without aborting the whole
run, skips duplicates, and leaves a full `ImportBatch` audit trail. Without
`RACING_API_USERNAME`/`RACING_API_PASSWORD` set, it prints exactly that and exits — it does not
fall back to synthetic/sample data.

For a CSV/JSON file (a purchased dataset, or any other provider's export):

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
safe to re-run with the same `idempotency_key`. See
[DATA_PROVENANCE.md](./DATA_PROVENANCE.md) for what gets recorded about where each row came from.

## Licensing reminder

Every commercial racing-data provider has its own licensing terms covering redistribution, storage
duration, and permitted use (research vs. commercial). This repository does not include any real
racing data and takes no position on any specific provider's terms — read and comply with whatever
licence governs the data you actually import.

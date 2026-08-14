# Real-Data Baseline — Phase 3B

**Status: not produced.** This document is the honest, unedited account of what Phase 3B attempted,
exactly where it stopped, and precisely what's required to complete it. Per explicit instruction,
nothing here is fabricated, no synthetic data was substituted for real data, and no website was
scraped to work around the gap.

## What Phase 3B was asked to do

Connect RacingEdge to The Racing API, ingest ≥24 months of UK & Irish flat + jumps historical
races, create the first REAL `DatasetVersion`, run the temporal leakage auditor against it, and —
only if it passes and clears the minimum real-data gate — re-run the existing, unmodified Phase 2
models as a genuine real-data baseline, reported honestly against the market.

## What actually happened

### 1. No credentials exist in this environment

```
$ env | grep -iE "racing|betfair|timeform|api_key|api_username|api_password"
no matching env vars found
```

`.env` and `.env.example` contain only `DATABASE_URL`. There is no `RACING_API_USERNAME`,
`RACING_API_PASSWORD`, `BETFAIR_APP_KEY`, or `BETFAIR_SESSION_TOKEN` anywhere in this repository or
this environment's shell.

### 2. The official documentation site was also unreachable

Direct attempts to fetch `https://api.theracingapi.com/documentation` and
`https://www.theracingapi.com/` both returned `EGRESS_BLOCKED` — this environment's network egress
policy does not allow reaching those hosts, independent of the credentials question. The same
applied to `historicdata.betfair.com`, `support.developer.betfair.com`, and `rapidapi.com`.

What COULD be reached and used as genuine (if secondary) sources: the vendor's own publicly
published Python example scripts on GitHub Gists (`gist.github.com/theracingapi/...`) and their
OpenAPI listing in the community-maintained `APIs-guru/openapi-directory` repository on
`raw.githubusercontent.com`. These confirmed the base URL, authentication method, the `/results`
endpoint and its pagination scheme, the confirmed 2 req/s rate limit, and roughly a dozen
race/runner field names — but NOT the full field-level schema for official rating, draw, weight,
going, race class, distance, pedigree, headgear, or starting price. See `DATA_SOURCES.md` and
`python/racingedge_data/providers/racing_api.py`'s module docstring for the complete, itemized
confirmed-vs-unverified breakdown with citations.

### 3. Everything that doesn't require live credentials was built and tested

- `RacingApiProvider` — a real HTTP client (`requests`-based) implementing the confirmed contract:
  base URL, HTTP Basic Auth, `/results` pagination (`limit`/`skip`/`total`), the 2 req/s rate
  limit, and retry with exponential backoff. 21 tests in
  `python/tests/test_providers.py::TestRacingApiLiveClient` verify pagination, 401 handling
  (raises `ProviderConfigurationError`, no retry), 5xx retry-then-succeed, and retry exhaustion —
  all against a **mocked** `requests.get`, since there is no live account to call.
- The `npm run data:racingapi` / `python -m racingedge_data.cli.import_racing_api` command — built,
  tested (`python/tests/test_cli_import_racing_api.py`), and **actually run in this environment**:

```
$ npm run data:racingapi -- --from 2024-01-01 --to 2024-01-31

> racingedge@0.1.0 data:racingapi
> cd python && ../.venv/bin/python -m racingedge_data.cli.import_racing_api --from 2024-01-01 --to 2024-01-31

Racing API credentials are not configured — nothing has been imported.

This command requires a licensed theracingapi.com subscription. Set these
environment variables and re-run:

  RACING_API_USERNAME
  RACING_API_PASSWORD

No data has been fabricated or substituted with synthetic data. See
DATA_SOURCES.md for exactly what plan/subscription tier is required for
historical /results access, and what this adapter has and hasn't verified
about the API's field-level schema.
```

Exit code 2. No network call was even attempted — the command stops at the credential check before
touching the provider.

- `betfair_historical.py` — a parser for purchased/downloaded Betfair Historical Data files (the
  well-documented Exchange Stream wire format), fully tested against a hand-built fixture matching
  that public format. No Betfair account exists in this environment either, and nothing was
  purchased. See `DATA_SOURCES.md` for exactly what a maintainer needs to buy and how to point this
  parser at it.

### 4. Nothing downstream of ingestion was run

Because no race was imported:

- **No REAL `DatasetVersion` exists.** `racingedge_data.dataset_version.create_dataset_version`
  requires at least one `Race` row with `sourceType='REAL'`; there are none.
- **The temporal leakage auditor was NOT run against real data** — there is no real data for it to
  audit. (It continues to run automatically at the start of every `python -m racingedge_model.train`
  invocation against whatever data does exist, and reports PASSED against the current
  synthetic/sample database — see MODEL_CARD.md.)
- **No baseline retrain happened.** `python -m racingedge_model.train` (REAL-only by default) was
  already exercised as part of the CLI-integration work and correctly reports:

```
No resulted races found with sourceType in ['REAL'].
Training aborted — this is the Phase 3A real/synthetic separation gate working as
intended, not a bug. To train a research model on synthetic data, re-run with
--include-synthetic. To train on real data, first import real historical races via
racingedge_data.importers (see DATA_SOURCES.md).
```

- **No Brier/log loss/AUC numbers, no calibration plots, no market-baseline delta, no strike rates**
  are reported here for real data, because none exist. Any number claiming to be a "real-data
  baseline result" anywhere else in this repository would be fabricated — there is no such number.

## Exactly what is required to produce this document for real

1. **A licensed theracingapi.com subscription** covering historical `/results` access for UK &
   Irish flat + jumps racing over the target window (≥24 months, per the brief). Set:
   ```bash
   export RACING_API_USERNAME="..."
   export RACING_API_PASSWORD="..."
   ```
2. Run `npm run data:racingapi -- --from 2024-01-01 --to 2026-08-01` (or whatever range the
   subscription covers). Watch the actual response shape and **correct**
   `_UNVERIFIED_RUNNER_FIELD_CANDIDATES` / `_UNVERIFIED_RACE_FIELD_CANDIDATES` in
   `python/racingedge_data/providers/racing_api.py` against the real field names for official
   rating, draw, weight, going, race class, distance, sire/dam/damsire, headgear, and starting
   price — the current lists are informed guesses, not confirmed.
3. After ingestion, report (this is what this document should then contain):
   - Total races, total runners, date range, courses covered, Flat/jumps breakdown
   - Missing OR %, missing draw %, missing going %, missing odds %, missing historical-form %
   - Any entity-resolution queue items requiring manual review
4. Create the REAL `DatasetVersion` (the import CLI does this automatically) and confirm the
   temporal leakage auditor reports PASSED against it — training refuses to proceed otherwise.
5. Check the minimum real-data gate
   (`racingedge_data.dataset_version.classify_readiness`, ≥10,000 races / ≥100,000 runners). If not
   cleared, the resulting `ModelVersion` stays labelled `RESEARCH MODEL — INSUFFICIENT HISTORICAL
   DATA` — that's an honest label, not a blocker to running the baseline retrain itself.
6. Run `python -m racingedge_model.train` (REAL-only by default, no flag needed) with the EXISTING,
   UNCHANGED Phase 2 models — chronological 70/15/15 split, and report, without optimising
   anything based on the results:
   - Race counts and runner counts per split
   - LightGBM and logistic regression Brier score, log loss, ROC-AUC on the held-out test split
   - top2–top6 place-model calibration
   - The market-implied-probability baseline's Brier score and log loss on the same split
   - The delta between RacingEdge and the market baseline
   - Calibration buckets (already computed by `evaluate.calibration_buckets`, printable as plots)
   - Top-ranked-selection strike rate
7. Replace this document's "not produced" status with those genuine numbers.

## Optional: Betfair Historical Data

Not required to reach the milestone above (Racing API alone provides starting prices for the
market-baseline comparison, once the SP field name is verified per step 2). If exchange-depth odds
history is wanted later: purchase from `historicdata.betfair.com` (current plan tiers/pricing not
verified from this environment — confirm at purchase time), extract the archive, and run
`racingedge_data.providers.betfair_historical.import_betfair_historical_file` against each market
file, after the corresponding race card is already imported. See `DATA_SOURCES.md` for the full
walkthrough.

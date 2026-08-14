# Data Provenance — Phase 3A/3B/3C

Every imported record must distinguish **source data** (what a provider actually reported) from
**derived features** (what RacingEdge computes from it), and must be traceable back to exactly
where it came from and when. This document describes the provenance model.

## The `DataProvenance` table

One row per imported "domain" of data for one entity — a race card, an odds observation, a result,
a sectional feed, place terms — tracing:

| Column | Meaning |
|---|---|
| `entityType` / `entityId` | Which row this provenance record describes, e.g. `"Race"` / a `Race.id` |
| `dataDomain` | `"RACE_CARD"`, `"ODDS"`, `"RESULT"`, `"SECTIONAL"`, `"WEATHER"`, `"PLACE_TERMS"` |
| `provider` | e.g. `"csv"`, `"generic-json"`, `"racing-api"`, `"timeform"`, `"betfair"` |
| `providerRecordId` | The provider's own identifier for this record, if any |
| `providerTimestamp` | When the *provider* says this data is/was true |
| `retrievedAt` | When RacingEdge actually fetched/imported it |
| `effectiveAt` | When this data became true in the real world — the point-in-time field |
| `sourceVersion` | Provider API/schema version, dataset release version, etc. |
| `rawPayloadHash` | SHA-256 of the raw source payload |
| `importBatchId` | Which `ImportBatch` produced this row |

This is deliberately polymorphic (`entityType` + `entityId`) rather than one provenance column set
per table, so adding a new importable domain never requires a schema migration.

**Why a hash, not the raw payload:** the goal is traceability and duplicate detection, not a raw
data warehouse. Storing every provider's raw JSON/CSV row verbatim for hundreds of thousands of
records would multiply storage for no benefit once the canonical row is written — a hash lets
`racingedge_data.provenance.hash_payload` detect "have I seen this exact payload before" (useful
for dedup and audit) without keeping the payload itself.

Implementation: `python/racingedge_data/provenance.py` — `record_provenance()`,
`ProvenanceRecord`, `hash_payload()`.

## Point-in-time field history

Provenance answers "where did this come from"; **field history** answers "what was the value of
this specific field at a specific moment" — the two are related but distinct, and this project
needs both. See [POINT_IN_TIME_ARCHITECTURE.md](./POINT_IN_TIME_ARCHITECTURE.md) for the full
design of `RaceFieldHistory`, `RunnerFieldHistory`, and `RacePlaceTermsHistory`.

## Entity provenance: `EntityAlias`

Every time a raw name (horse, trainer, jockey, course) is resolved to a canonical entity, an
`EntityAlias` row records: the raw name, its normalized form, which provider reported it, the
provider's own entity id (if any), and which matching strategy resolved it
(`PROVIDER_ID` / `EXACT_NORMALIZED_NAME` / `MANUAL_REVIEW`). This is what makes every entity merge
auditable — see `python/racingedge_data/entity_resolution.py`.

## Import batch provenance

`ImportBatch` (extended in Phase 3A) tracks the whole run a set of provenance rows came from:
`providerName`, `idempotencyKey`, `totalRows`/`processedRows`/`duplicateRows`, and an optional
`datasetVersionId` linking the batch to whichever `DatasetVersion` later included its races.

## What is NOT tracked at the provenance level

- **Derived features** (the ~166-feature Python pipeline output) are not written back into
  `DataProvenance` — they are reproducible from source data plus code version
  (`ModelVersion.featureSetVersion`), so tracking their provenance separately would duplicate the
  model-versioning system that already exists for that purpose.
- **Raw payloads themselves** are hashed, not stored (see above) — if you need the literal original
  file, keep it outside the database (e.g. wherever your purchased dataset was delivered) and
  reference it via `sourceVersion` / `providerRecordId`.

## Phase 3B: provenance for the Racing API and Betfair historical imports

`racingedge_data.importers.import_runner.import_races`, driven by
`racingedge_data.providers.racing_api.RacingApiProvider`, records `provider="racing-api"` on every
`DataProvenance` row it writes, with `providerRecordId` set to the race's `race_id` from the API
response and `effectiveAt` set to the race's own off-time (Racing API's `/results` endpoint only
returns settled races, so there is no finer-grained "when did this field become true" timestamp
available from the API itself — see [POINT_IN_TIME_ARCHITECTURE.md](./POINT_IN_TIME_ARCHITECTURE.md)
for what that limitation does and doesn't affect).

`racingedge_data.providers.betfair_historical.import_betfair_historical_file` does **not** write
`DataProvenance` rows for the `RunnerMarketPrice` rows it inserts (unlike the main import pipeline)
— odds price points are a high-volume, already-timestamped time series where the provenance is
implicit in the `Bookmaker.name = "Betfair Exchange"` + the row's own `timestamp`; adding a
provenance row per price point would multiply the table's size for no practical traceability
benefit over what's already in `RunnerMarketPrice` itself.

## Phase 3C: reuse-rights provenance (`ProvenanceStatus`), separate from authenticity (`DataSourceType`)

Phase 3A/3B's `DataSourceType` (`REAL`/`SYNTHETIC`/`SAMPLE`) answers "is this genuine racing data or
generated/example data" — a question about **authenticity**. Phase 3C's £0-cost strategy pulls data
from free/community sources whose reuse rights vary widely, which is an orthogonal question: a race
can be `REAL` and still have reuse rights that are `UNKNOWN` or explicitly `RESTRICTED`. Conflating
the two would either wrongly exclude genuine real data from training (if reuse-rights uncertainty
were folded into authenticity) or wrongly let unclear-licence data train production models silently
(if authenticity alone gated training) — so `DataProvenance` gained its own, separate
`provenanceStatus` column:

| Status | Meaning |
|---|---|
| `VERIFIED_OPEN` | Source's open-reuse licence was actually read and confirmed (e.g. a stated CC0/CC-BY licence) |
| `PUBLIC_RESEARCH` | Publicly available and evidently intended for research/analysis use, without a formally confirmed licence |
| `COMMUNITY_UNVERIFIED` | From a community source (e.g. an unreviewed Kaggle upload) with no licence check performed yet |
| `USER_SUPPLIED` | Provided directly by a user/maintainer, provenance/licence as they describe it |
| `UNKNOWN` | Default. No provenance status has been established at all |
| `RESTRICTED` | Explicitly known to have reuse terms incompatible with this project's use |

`racingedge_data.dataset_version.filter_race_ids_excluding_provenance` — called automatically inside
`racingedge_model.train`'s dataset-build step — drops every race whose `DataProvenance` row (if any)
is `RESTRICTED` from training datasets by default. Races with **no** `DataProvenance` row at all
(Phase 1 seed data, the Phase 2 synthetic generator, anything imported before Phase 3C) are never
excluded by this filter — it only removes races explicitly classified as restricted, never silently
distrusts undocumented legacy data. `UNKNOWN` and `COMMUNITY_UNVERIFIED` are not excluded, but the
free-dataset importer (`racingedge_data.importers.free_dataset_importer.import_free_dataset`)
attaches an explicit warning to the import outcome whenever either status is used, so the
uncertainty is visible at import time rather than discovered later.

## Phase 3C: `DatasetReview` — licence review before import

`DatasetReview` (`racingedge_data.dataset_review`) is a separate, lightweight record created
**before** importing a free/community dataset, capturing what's actually known about its licence:
dataset name, source, the licence as stated (text/URL), the original data provider, three
permission flags (`redistributionPermitted`/`researchUsePermitted`/`commercialUsePermitted` — each
nullable, since "not established" must never look like "false"), a `provenanceConfidence`
classification (the same `ProvenanceStatus` enum above), and free-text reviewer notes. This module
deliberately does not attempt to give legal advice or make a licence determination on the
maintainer's behalf — it only makes whatever licence uncertainty exists **visible**, structured, and
queryable, rather than left as tribal knowledge or discovered after the fact. See
`FREE_DATA_SOURCES.md` for how this is meant to be filled in for a real candidate dataset.

## Querying provenance

The Dataset Explorer (`/data-explorer/race/[raceId]`) shows every `DataProvenance` row for a race
directly. Programmatically:

```python
rows = conn.execute(
    'SELECT * FROM "DataProvenance" WHERE entityType = ? AND entityId = ?',
    ("Race", race_id),
).fetchall()
```

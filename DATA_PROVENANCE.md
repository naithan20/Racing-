# Data Provenance — Phase 3A/3B

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

## Querying provenance

The Dataset Explorer (`/data-explorer/race/[raceId]`) shows every `DataProvenance` row for a race
directly. Programmatically:

```python
rows = conn.execute(
    'SELECT * FROM "DataProvenance" WHERE entityType = ? AND entityId = ?',
    ("Race", race_id),
).fetchall()
```

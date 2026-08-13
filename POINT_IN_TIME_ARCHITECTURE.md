# Point-in-Time Architecture — Phase 3A

The central question this architecture exists to answer: **"what did RacingEdge actually know
before this race went off — and specifically, what did it know at 10:00am, if that's the moment
being reconstructed — versus what it knows now, with the result and every subsequent update baked
in?"** Every historical prediction must be reproducible using ONLY information that genuinely
existed before that race, and no query should be able to accidentally reach into the future.

## Why this matters more than model accuracy

A model trained on data that silently includes post-race information (the actual going after
the rail moved, a draw correction made after declaration, an odds move that only happened because
the market reacted to news after the model would have run) looks better in backtesting than it
ever could in production — and the gap is invisible unless the pipeline is built, from the ground
up, to make that leakage structurally difficult rather than relying on careful querying every time.

## What's mutable, and how it's tracked

`Race` and `Runner` rows hold **current-state** fields — going, rail position, draw, jockey,
weight, non-runner status, and so on — that can legitimately change between a race being first
carded and its actual off-time. Two generic, append-only history tables capture every prior value:

- **`RaceFieldHistory`** — `(raceId, fieldName, fieldValue, effectiveAt, source, importBatchId)`
- **`RunnerFieldHistory`** — `(runnerId, fieldName, fieldValue, effectiveAt, source, importBatchId)`

A generic `(fieldName, fieldValue)` log was chosen over one dedicated history table per field to
keep the schema manageable — the tradeoff is that consumers must know each `fieldName`'s expected
value type (all Phase 3A code treats `fieldValue` as a string and parses it per-field, matching the
fields listed in `racingedge_data.point_in_time.RACE_MUTABLE_FIELDS` /
`RUNNER_MUTABLE_FIELDS`).

**Bookmaker place terms** get their own dedicated history table, `RacePlaceTermsHistory`, since
promotions can change mid-day and the live `RacePlaceTerms` row always holds the CURRENT terms (so
every existing "get the place terms for this bookmaker" query keeps working unmodified) while the
history table is what point-in-time queries read from.

## The reconstruction rule

For every mutable field, reconstruction as of some timestamp `T` is: **the most recent history row
with `effectiveAt <= T`, or unknown (`null`) if no such row exists.**

Critically: a field with no qualifying history row is reported as **unknown**, never backfilled
from the live row's current value. A live value could have been set after `T` (e.g. the final
confirmed going, recorded once and only once, after the race). Falling back to it would silently
leak exactly the information this whole system exists to prevent.

Implemented in two places that are kept in sync by convention (see each module's docstring for the
cross-reference):

- **Python**: `racingedge_data/point_in_time.py` —
  `reconstruct_race_as_of`, `reconstruct_runner_as_of`, `reconstruct_place_terms_as_of`,
  `market_prices_as_of`, `field_value_as_of`.
- **TypeScript**: `src/data/explorer.ts` — `reconstructRaceFieldsAsOf`,
  `reconstructRunnerFieldsAsOf`. The two languages never call into each other at runtime (Phase
  1/2's architecture keeps them decoupled, sharing only the SQLite file), so the logic is
  deliberately reimplemented rather than shelled out — if the reconstruction rule ever changes,
  update both.

## Historical odds

`RunnerMarketPrice` is already a timestamped time series (bookmaker/exchange, runner, timestamp,
decimal odds, back/lay/volume for exchanges, market status). Named snapshots — opening, 24h/6h/1h/
30m/10m/5m pre-race, off-time, SP/BSP — are **derived views over that stream**, never separately
reported values, computed in `racingedge_data/odds_snapshots.py`.

The rule mirrors field-history reconstruction: each "N before off-time" snapshot is the most recent
price known **at or before** that moment — found by filtering to `timestamp <= moment` and taking
the last one. Never the price point numerically closest in time, which could be a price observed
slightly *after* that moment and therefore leak future market information into a supposedly
earlier snapshot. `derive_named_snapshots` and its tests
(`python/tests/test_odds_snapshots.py`) enforce this explicitly, including a case where a
post-off-time price is deliberately inserted and confirmed to never appear in the `sp`/`off_time`
snapshots.

## Horse timelines

`racingedge_data/timeline.py` provides the project's required point-in-time-safe horse-history
functions — `get_previous_runs`, `get_last_n_runs`, `get_course_history_before`,
`get_distance_history_before`, `get_going_history_before`, `get_rating_history_before` — every one
of which takes an explicit `before_date` and is guaranteed (checked twice: once in the SQL `WHERE`
clause, once again in Python as defense-in-depth) to return only rows strictly before it.

The **bulk training pipeline** (`racingedge_model.features.build`) enforces the identical
`raceDate < as_of_date` invariant independently, operating on whole DataFrames at once for
performance rather than per-horse queries — the two are not meant to be called together in a hot
loop, but both exist because they serve different callers: `timeline.py` for ad-hoc research (the
Dataset Explorer, notebooks), `features/build.py` for training/prediction at scale.

## The temporal leakage auditor

`racingedge_data/leakage_audit.py` upgrades the Phase 2 in-training-pipeline guard
(`racingedge_model.features.build.assert_no_leakage`, which raises immediately on the first
violation — appropriate as a runtime guard) into a full, storable audit:
`audit_training_data(conn)` checks **every** history row for **every** runner in **every** resulted
race, collects **every** violation (not just the first), and returns a `LeakageAuditReport` with a
`"LEAKAGE AUDIT PASSED"` / `"LEAKAGE AUDIT FAILED"` headline plus full per-violation detail
(`save_audit_run` persists it to the `LeakageAuditRun` table).

Two independent things are checked per runner:

1. **Date filtering correctness** — re-derives the exact `raceDate < as_of_date` filter the
   training pipeline applies, then re-checks the filtered result (defense-in-depth against a filter
   bug — wrong comparison operator, wrong column).
2. **Self-referential leaks** — a `FormEntry` row whose `linkedRaceId` points at the race
   *currently being predicted* is flagged regardless of its recorded date, since a data-entry error
   backdating such a row would defeat a date-only check. This is the deliberately malicious
   scenario `python/tests/test_leakage_audit.py` constructs and confirms gets caught.

`racingedge_model/train.py` runs this audit **before touching any training data** and aborts if it
reports FAILED — a leakage-positive database must never be trained on.

## Deliberately malicious test coverage

Per the project's requirement to generate scenarios where future information is inserted and
confirm RacingEdge blocks it, `python/tests/test_malicious_leakage_scenarios.py` covers:

- A race's own `ResultEntry` mutated to a fabricated outcome — confirmed to never change that
  race's computed FEATURE values (only its target label).
- A price recorded minutes after a race's off-time, flagged as if it were the starting price —
  confirmed excluded from both `market_prices_as_of` and the derived odds snapshots.
- Place-terms history rows inserted out of chronological order — confirmed that reconstruction
  keys off `effectiveAt`, never insertion order.
- `DatasetVersion` immutability — creating a second version never alters an earlier one, and the
  module exposes no update function by design.
- A large-file streaming import (thousands of rows via the same generator-based path a
  100,000+-row real import would use).

See [DATA_PROVENANCE.md](./DATA_PROVENANCE.md) for how provenance and point-in-time history relate,
and [DATA_SOURCES.md](./DATA_SOURCES.md) for where the underlying data is allowed to come from.

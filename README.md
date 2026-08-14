# RacingEdge — Phase 3B

RacingEdge is a local-first horse-racing **analysis and decision-support** application. It is not a
tip generator. It estimates win probability, place probability (against actual bookmaker place
terms), model confidence, fair odds, market-implied probability, and value/edge versus market
price — then tracks results against those pre-race predictions so the model's calibration can be
judged honestly.

**Phase 1** shipped the architecture, database, UI and result-tracking system with no probability
model. **Phase 2** added a transparent, trainable, backtestable baseline model on top of that
architecture — see [MODEL_CARD.md](./MODEL_CARD.md) for its intended use, design, and limitations
before reading anything into its numbers. **Phase 3A** built the data-integrity infrastructure —
provider-agnostic ingestion, point-in-time-correct historical data, entity resolution, dataset
versioning, a temporal leakage auditor, and a real/synthetic/sample separation gate — without
touching the Phase 2 model algorithms. **Phase 3B** (this phase) attempted to connect that
infrastructure to a real provider (The Racing API) and produce the first REAL `DatasetVersion`.
**It stopped at the credential boundary, exactly as instructed**: this environment has no Racing
API subscription credentials and could not reach the provider's documentation site to verify its
full field-level schema, so **no real data was imported, no REAL DatasetVersion exists, and no
real-data baseline retrain happened.** See [REAL_DATA_BASELINE.md](./REAL_DATA_BASELINE.md) for the
full, honest account of exactly what was and wasn't possible and precisely what's needed to
complete it, and [DATA_SOURCES.md](./DATA_SOURCES.md), [DATA_PROVENANCE.md](./DATA_PROVENANCE.md),
and [POINT_IN_TIME_ARCHITECTURE.md](./POINT_IN_TIME_ARCHITECTURE.md) for the underlying design.

**There is still no non-trivial amount of real racing data in this system** — every `ModelVersion`
bundled here remains trained on synthetic data and is explicitly labelled
`SYNTHETIC TEST MODEL — NOT FOR BETTING USE` everywhere it appears in the UI, and every
`DatasetVersion` built from it is labelled `RESEARCH MODEL — INSUFFICIENT HISTORICAL DATA`.

## Tech stack

- **Next.js 16** (App Router, Turbopack) + **TypeScript** + **Tailwind CSS v4** — the web app
- **SQLite** via **Prisma 7** (`@prisma/adapter-better-sqlite3`) — field types are
  PostgreSQL-compatible, so migrating later is a provider swap, not a redesign
- **Python 3.11** + **pandas / scikit-learn / LightGBM** — the Phase 2 modelling package
  (`python/racingedge_model`), reading and writing the *same* SQLite file via `sqlite3`, no Prisma
  runtime dependency
- **Recharts** for odds-history and calibration charts
- **Zod** for import validation
- **Vitest** (TypeScript) + **pytest** (Python) for tests
- Dark, dense, Bloomberg-style analytics UI

## Project structure

```
prisma/
  schema.prisma        Full data model, including Phase 2 ModelVersion / PlaceProbabilityBand
  seed.ts               Seeds Phase 1 SAMPLE DATA (3 demo races) for every UI screen
python/
  racingedge_model/
    synthetic/            Synthetic historical race generator (data-generating process only)
    features/              Feature engineering pipeline, one module per feature group + registry
    models/                 Win models (logistic, LightGBM), place models, preprocessing
    dataset.py               Race-grouped training dataset builder + date-based split
    calibration.py            Platt/isotonic calibration
    confidence.py              Rule-based ModelConfidence
    value.py                    Fair odds / value formulas (mirrors src/lib/odds.ts)
    train.py / predict.py / backtest.py   CLI entry points (see Commands below)
  racingedge_data/           Phase 3A data infrastructure (sibling package, see below)
    canonical.py                Provider-agnostic canonical data shapes
    provenance.py                 DataProvenance + point-in-time field-history recording
    entity_resolution.py            Horse/trainer/jockey/course resolution, auditable via EntityAlias
    timeline.py                       Point-in-time-safe per-horse history queries
    point_in_time.py                    As-of-timestamp Race/Runner/place-terms/odds reconstruction
    odds_snapshots.py                     Named odds snapshots derived from the RunnerMarketPrice stream
    leakage_audit.py                        Full "LEAKAGE AUDIT PASSED/FAILED" auditor
    dataset_version.py                        DatasetVersion creation + minimum-real-data gate
    market_baseline.py                          Market-implied-probability baseline + comparison
    providers/                                    RaceDataProvider/HistoricalResultsProvider/
                                                    OddsDataProvider/SectionalDataProvider/
                                                    WeatherDataProvider interfaces + csv/generic-json/
                                                    racing-api (real HTTP client, Phase 3B) /
                                                    timeform/betfair (fixture-only) adapters +
                                                    betfair_historical.py (purchased-file parser)
    importers/                                      Streaming/chunked/resumable/idempotent import pipeline
    cli/                                              import_racing_api.py — the `data:racingapi` CLI
  tests/                  pytest suite, including the explicit anti-leakage test + Phase 3A malicious
                             leakage scenarios
src/
  app/                  Next.js App Router pages + a couple of route handlers
    data-quality/         Data Quality Dashboard (Phase 3A)
    data-explorer/          Dataset Explorer: race/runner/horse point-in-time inspection (Phase 3A)
  actions/               Server Actions (mutations): imports, results, race creation, Lucky 15
  components/             UI components, grouped by feature area
  data/                    Server-side read queries, import schema + persistence
    dataQuality.ts            Data Quality Dashboard aggregates (Phase 3A)
    explorer.ts                  Dataset Explorer queries + TS-side point-in-time reconstruction (Phase 3A)
  database/                 Prisma client singleton (driver-adapter wired up)
  features/                  Phase 1 Feature Store (TS-side definitions; Python has its own registry)
  lib/                        Generic utilities: odds conversion, CSV parsing, badges, explanation engine
  models/                      Placeholder model-output contract (superseded by real snapshots where present)
  pace/                         Pace/race-shape types — 3 concepts kept strictly separate
  results/                       Result settlement (finish position -> place outcome, P/L)
  value/                          Value engine (fair odds, edge), place-term handling, place-band selection
  backtesting/                    Scoring rules (Brier/log loss/calibration/ROI) + breakdown grouping
tests/                     Vitest unit tests
```

## Database schema

SQLite locally; every model uses Postgres-friendly types. Key entities:

- **Race** — full race context (course, going, distance, class, weather, prize money, each-way
  fraction, etc.) plus **RacePlaceTerms**, a *separate, bookmaker-specific* table for place count
  and each-way fraction. Place probability is **never** assumed to mean "top 3" — every place
  figure in the UI is computed against, and labelled with, a specific `RacePlaceTerms` row.
- **Horse** / **Runner** — Runner is the horse-race join row (draw, weight, ratings, jockey,
  headgear, market odds snapshot fields, etc).
- **FormEntry** — detailed historic performance records per horse (sectionals, in-running
  positions at 3f/2f/1f out, pace classification, comments, etc). This is the primary
  feature-engineering source for a horse's own current-form/pace history.
- **FeatureDefinition** / **Feature** — the flexible Phase 1 **Model Feature Store** (TypeScript
  side). Phase 2's Python feature pipeline has its own, more detailed registry
  (`python/racingedge_model/features/registry.py`, ~166 features); the two are documented
  separately rather than forced into one schema, since the Python registry needed calculation-
  method/missing-behaviour metadata the TS store wasn't designed to carry per-feature.
- **RunnerPaceProfile** — pace/race-shape modelling. Three concepts are stored/computed as
  **distinct fields, never combined into one score**: position acquisition, transition speed, late
  sustainability. Used both as UI display and — via the horse's own FormEntry history — as the
  Python feature pipeline's source for these three concepts.
- **EvidenceProfile** — the Evidence Confidence cache (current-state, UI-facing). Phase 2's
  actual evidence-density *feature* is always recomputed as-of a given date in Python
  (`features/evidence.py`) rather than trusted from this table, since this table only reflects
  "now" and using it for a historical race would leak future starts into the past.
- **Bookmaker** / **RunnerMarketPrice** — multi-bookmaker odds time series.
- **ModelVersion** *(Phase 2)* — every trained model's immutable metadata: algorithm,
  hyperparameters, calibration method, feature-set version, training/validation/test date ranges
  and row/race counts, summary metrics, feature importance, and the path to its saved artifact.
  Never overwritten — retraining creates a new row.
- **PredictionSnapshot** — the model's pre-race output (win probability, place probability +
  which place count it's based on, model confidence, fair odds, market-implied probability, value
  edge), now with an optional `modelVersionId` FK. **Locked (`isLocked: true`) by default and
  never overwritten by results or by re-running prediction** — every prediction run only ever
  `INSERT`s new rows (`python/racingedge_model/db.py:insert_prediction_snapshot`). This is what
  lets the dashboard judge calibration honestly instead of retrofitting a story after the fact.
- **PlaceProbabilityBand** *(Phase 2)* — raw + calibrated P(finish ≤ N) for N = 2..6, one set per
  `PredictionSnapshot`, monotonicity-enforced. Lets the UI pick the exact band matching whichever
  bookmaker's place terms are selected without needing a snapshot per bookmaker.
- **ResultEntry** / **RunnerObservation** — actual outcome (finish position, SP, closing odds,
  place outcome, P/L) plus manual observation tags and a free-text field.
- **Lucky15Slip** / **Lucky15Leg** — data structures + filters for the Lucky 15 builder
  placeholder (leg-selection algorithm is explicitly out of scope until Phase 3/4).
- **ImportBatch** — tracks every manual/CSV/JSON import.

Run `npx prisma studio` (or `npm run db:studio`) to browse the schema and data directly.

## Running locally

```bash
cp .env.example .env      # DATABASE_URL="file:./dev.db" — no secrets, just the local db path
npm install                 # also runs `prisma generate` (postinstall)
npm run db:migrate            # creates dev.db and applies the schema
npm run db:seed                 # loads Phase 1 SAMPLE DATA — safe to re-run, it clears and reloads

npm run model:setup               # creates .venv and installs python/requirements.txt
npm run model:history               # generates ~175 SYNTHETIC HISTORY races into dev.db
npm run model:train                   # trains + calibrates the baseline models
npm run model:predict                   # generates predictions for today's SAMPLE DATA races
npm run model:backtest                    # backtests the model's held-out test window

npm run dev                                 # http://localhost:3000
```

`dev.db`, the generated Prisma client (`src/generated/prisma`), and the Python `.venv` /
`python/artifacts` / `python/reports` are all gitignored — they're regenerated by the commands
above, not committed. **Order matters**: re-running `npm run db:seed` wipes the whole database
(including synthetic history and trained-model predictions) back to just the 3 Phase 1 demo
races — if you do that, re-run `model:history` → `model:train` → `model:predict` afterwards.

Other useful scripts:

```bash
npm run build          # production build
npm run test            # vitest run (TypeScript unit tests)
npm run model:test       # pytest (Python unit tests, incl. the leakage test)
npm run lint               # eslint
npm run db:studio           # Prisma Studio, browse the SQLite DB visually
npm run db:reset              # drop + recreate + reseed (destructive — wipes everything, see above)
```

## Feature engineering (Phase 2)

`python/racingedge_model/features/` computes ~166 features per (runner, race), one module per
group from the brief: current form, rating/handicap, weight, class, course/distance/going, draw,
pace (position acquisition / transition speed / late sustainability kept as three separate
concepts, plus race-shape interaction), trainer/jockey, headgear/changes, age/experience, and
evidence density. Every feature is documented in
`python/racingedge_model/features/registry.py` — group, category, calculation method, source
fields, and missing-value behaviour — and a test (`tests/test_registry_coverage.py`) asserts the
registry and the actual computed columns never drift apart.

**Leakage prevention** is the single most load-bearing property of this pipeline:

- Every feature is computed from history filtered to `raceDate < as_of_date` (strict inequality),
  enforced in one place (`features/build.py:build_features_for_race`) so every caller — training,
  prediction, and backtesting — goes through the same leakage-safe path.
- `features/build.py:assert_no_leakage` is a defense-in-depth runtime check: it raises
  `LeakageError` if any history frame passed in isn't strictly before the target date.
- `python/tests/test_leakage.py` mutates a **future** race's result (flips finishing positions to
  an impossible value, inflates ratings) on an isolated database copy and asserts an **earlier**
  race's computed features are byte-for-byte unchanged.
- Trainer/jockey rolling stats and draw bias need cross-horse data that the per-horse `FormEntry`
  table can't provide, so they're computed from a *global* prior-runs table
  (`features/build.py:build_global_prior_runs`, joining Runner→Race→ResultEntry) — also filtered
  to strictly-prior rows.

**Missing data** is never silently treated as zero when zero has racing meaning: features with
missingness get a `<feature>__isnan` indicator column at training time
(`models/preprocessing.py:FeaturePreprocessor`), fit only on the training split.

**Draw bias** is only reported when the exact `(course, distance-band, field-size-band)` bucket
has at least `MIN_SAMPLES_DRAW_BIAS` (30) prior runs — a hard gate, not a soft preference.

## Model algorithms

Two baseline win models are trained every run, both read directly by the dashboard's model
selector for comparison:

- **Model A — L2-regularized logistic regression** (`models/win_logistic.py`). `C=0.02`, chosen
  via a one-off validation-set AUC comparison across a small grid (not tuned against test) —
  needed because the feature-to-training-row ratio is high (166 features vs ~1,100 rows).
  Fully interpretable: every coefficient is a directly-readable log-odds weight.
- **Model B — LightGBM** (`models/win_gbm.py`), conservative fixed hyperparameters (not searched):
  200 trees, depth-limited via `num_leaves=15`, `min_child_samples=20`, L1/L2 regularization,
  row/column subsampling. On this dataset it generalizes noticeably better than logistic
  regression at the same feature count — see MODEL_CARD.md for the actual numbers.

One of the two (LightGBM by default, `--primary` flag in `train.py`) becomes the **primary
serving model**: its calibrated output is what `PredictionSnapshot` rows actually store, and it's
the one used for the five **place models** (`models/place_models.py`), independent LightGBM
binary classifiers for P(finish ≤ 2) .. P(finish ≤ 6) — **never** a multiplier of win probability.

**Race-level normalization** (win probability): a classifier's raw output is an independent
per-runner probability that doesn't sum to 1 across a race. Documented method
(`normalize.py`): clip to a small positive epsilon, then `P(win_i) = score_i / Σ score_j` within
the race — exactly the method suggested in the project brief.

**Place-probability post-processing** (`models/place_models.py`), applied in this order:
calibrate → **race-level rescale** (calibrated probabilities for depth N are rescaled so they sum
to `min(N, field size)` within the race — a consistency check, not a re-fit) → **monotonicity
enforcement** (`P(top2) ≤ P(top3) ≤ ... ≤ P(top6)` via a running maximum over increasing depth).

## Calibration

Both Platt (sigmoid) and isotonic calibration are implemented (`calibration.py`), fit **only** on
the validation split, one calibrator per win model and per place depth. `select_best_calibration`
compares raw/sigmoid/isotonic Brier score on validation and picks the winner (or `"none"` if
neither helps) — the chosen method is stored on `ModelVersion.calibrationMethod` and printed
during training.

## Model confidence & evidence density

Two deliberately separate, transparent 0-100 (stored as 0-1) rule-based scores — **neither is win
probability, and confidence is never derived from it**:

- **Evidence density** (`features/evidence.py`) — weighted sum of career starts, recent starts,
  course/distance evidence, sectional/comment/rating-history availability, and trainer/jockey
  sample adequacy. Reflects how much reliable information exists, not how likely the horse is to
  win — a lightly-raced favourite can have high win probability and low evidence density.
- **Model confidence** (`confidence.py`) — weighted sum of evidence density, feature completeness,
  agreement between the two win models, a probability-stability proxy (win-vs-place-model rank
  agreement within the race), historical calibration quality for the same flat/jumps type, and an
  out-of-distribution flag (`models/preprocessing.py:OutOfDistributionDetector`, fraction of
  features outside the training set's 5th–95th percentile band).

Both modules document their exact weights in their own docstrings.

## Fair odds / value

`python/racingedge_model/value.py` is a line-for-line mirror of `src/lib/odds.ts` +
`src/value/engine.ts` (market implied probability = 1/odds; fair odds = 1/probability; edge =
model − implied). `python/tests/test_value.py` and `tests/odds.test.ts` /
`tests/value.test.ts` share the same numeric fixtures so both sides are checked against the same
hand-computed examples.

## Model versioning

Every training run writes two `ModelVersion` rows (comparison-only logistic + primary serving
model) with full metadata (see schema section above) and **never** overwrites a prior version —
retraining always inserts new rows, and old `PredictionSnapshot`s keep pointing at whichever
version produced them.

## Backtesting

`python/racingedge_model/backtest.py` re-creates exactly what a given `ModelVersion` would have
predicted for races in a date window, using the same leakage-safe feature pipeline as training,
then compares against actual results. By default it uses the model's own held-out **test** window
(the only genuinely fair check); passing an explicit window that overlaps training prints a loud
warning. Metrics: Brier score, log loss, ROC-AUC (secondary), win/place strike rates, expected vs
actual wins, top-ranked-selection strike rate, calibration buckets, and hypothetical flat-stake
ROI broken down by odds band and confidence band. **ROI is an evaluation output, never a training
target** — nothing in the pipeline optimizes for it.

Predictions generated during a backtest **are persisted** as ordinary `PredictionSnapshot` rows
(this is legitimate — they still only use information from before each race's own date) so the
**Backtest Mode** page (`/backtest`) can show exactly what was predicted before any historical,
resulted race, next to what actually happened.

## Leakage prevention summary

1. Feature computation always filters history to `raceDate < as_of_date` (strict), in one shared
   function, with a runtime assertion as a second line of defense.
2. `python/tests/test_leakage.py` is an explicit, DB-level test: mutating a future race's result
   must not change an earlier race's computed features. It does, and is verified on every
   `npm run model:test` run.
3. Train/validation/test splits are by **race** (never split a race's runners across sets) and are
   chronological (`dataset.py:date_based_split`).
4. Calibration is fit on validation only; final evaluation happens once, on test, and is reported
   even when it's weak.
5. `PredictionSnapshot` rows are immutable inserts — a model can never retroactively "improve" a
   past prediction once the result is known.

## Model limitations

See [MODEL_CARD.md](./MODEL_CARD.md) for the full list. Headline points: **the shipped model is
trained substantially on synthetic data and must not be interpreted as having any real-world
racing edge**; the real-data component is a single 7-runner Phase 1 demo race, far too little to
train or validate anything on its own; hyperparameters are baseline defaults, not tuned; and no
SHAP/causal analysis has been done — feature importance is association, not causal effect.

## Commands

```bash
npm run model:setup       # one-time: create .venv, install Python dependencies
npm run model:history     # generate/regenerate the synthetic historical dataset
npm run model:features    # build the training dataset and print its shape/date-split (no training)
npm run model:train       # train + calibrate both win models and the 5 place models
npm run model:predict     # predict for upcoming (SCHEDULED/DELAYED) races using the latest model
npm run model:backtest    # backtest the latest model over its held-out test window
npm run model:test        # pytest — feature/leakage/calibration/monotonicity/versioning tests
npm run data:racingapi -- --from YYYY-MM-DD --to YYYY-MM-DD   # import real historical races
                           # (Phase 3B) — requires RACING_API_USERNAME/PASSWORD, see DATA_SOURCES.md
```

Flags (run the underlying Python module directly for these, e.g.
`cd python && ../.venv/bin/python -m racingedge_model.train --primary logistic`):

- `train.py --primary {gbm,logistic}` — which win model becomes the serving model (default `gbm`)
- `train.py --include-synthetic` — train on SYNTHETIC/SAMPLE races too. **Without this flag,
  training uses REAL races ONLY** (Phase 3A default) and aborts with a clear message if there are
  none yet — this repository currently has none, so `npm run model:train` will abort unless you
  pass this flag or import real data first.
- `predict.py --model-version-id ID --date YYYY-MM-DD` — predict a specific model/date
- `backtest.py --model-version-id ID --start-date ... --end-date ...` — backtest an arbitrary
  window (prints a warning if it overlaps training)

Every `train.py` / `backtest.py` run also: runs the temporal leakage auditor first (aborting on
FAILED), creates an immutable `DatasetVersion`, reports the minimum-real-data production-readiness
gate, and reports the market-implied-probability baseline comparison — see
[POINT_IN_TIME_ARCHITECTURE.md](./POINT_IN_TIME_ARCHITECTURE.md) and
[DATA_SOURCES.md](./DATA_SOURCES.md).

## Data import

For the Phase 1/2 UI (small, manual/ad-hoc): three paths, all going through the same validated
schema (`src/data/importSchema.ts`) and the same persistence function (`src/data/importRaces.ts`):

1. **Manual entry** — `/races/new`, a form for the race plus a quick-entry runner list.
2. **CSV import** — `/import`, one row per **runner**; rows sharing the same
   `(race_date, race_time, racecourse)` are grouped into one race. Download the column template
   from the Import page (`GET /import/template`).
3. **JSON import** — `/import`, `{ "races": [ { ...race fields, "runners": [...] } ] }`.

For real, large-scale historical ingestion (Phase 3A/3B, hundreds/thousands of races): the Python
`racingedge_data` package — see [DATA_SOURCES.md](./DATA_SOURCES.md) and
`npm run data:racingapi -- --from ... --to ...` above.

RacingEdge does not scrape any website.

## Sample & synthetic data

- `prisma/seed.ts` creates three **SAMPLE DATA** Phase 1 demo races (flagged `isSampleData: true`,
  named e.g. "SAMPLE Handicap Chase") so every UI screen has data to render.
- `python -m racingedge_model.synthetic.generate_history` creates ~175 **SYNTHETIC HISTORY** races
  spanning ~300 days (`Race.racecourse` always prefixed `"Synthetic "`, `Horse.countryBred = "SYN"`,
  trainer/jockey names prefixed `"Synth "`), simulated via a sequential Plackett-Luce model over a
  latent ability the model never observes directly — see MODEL_CARD.md for the full data-generating
  process. **Any model trained on this data is labelled `SYNTHETIC TEST MODEL — NOT FOR BETTING
  USE`** in `ModelVersion.isSynthetic` and rendered as a banner everywhere its predictions appear.

## Testing

```bash
npm run test        # TypeScript (vitest) — 105 tests
npm run model:test  # Python (pytest) — ~188 tests, incl. the leakage test, Phase 3A malicious
                    # leakage scenarios, and Phase 3B's Racing API/Betfair-historical adapter tests
```

TypeScript covers: odds/probability math, place-term settlement, result settlement, CSV
validation, the Phase 1 feature store, badge thresholds, place-band selection, the deterministic
explanation engine, and dashboard breakdown grouping.

Python covers: every feature group on crafted fixtures, the explicit anti-leakage test, race-level
win-probability normalization (sums to 1, preserves ranking), place-probability monotonicity and
race-level rescaling, target derivation (WIN_TARGET/PLACE_2..6) including non-finisher edge cases,
date-based train/val/test splitting (no race split across sets), calibration (Brier score
improves), value/fair-odds formulas (same fixtures as the TypeScript side), model-version
immutability, and prediction-snapshot immutability (always `INSERT`, never `UPDATE`).

## Phase 3A — data infrastructure

Phase 3A's brief was explicit: **do not** optimise the probability models, tune LightGBM, add
predictive complexity, or build the Lucky 15 optimiser. The overriding objective is data
integrity. What was built:

- **Provider-agnostic ingestion** (`python/racingedge_data/providers/`) — five narrow interfaces
  (`RaceDataProvider`, `HistoricalResultsProvider`, `OddsDataProvider`, `SectionalDataProvider`,
  `WeatherDataProvider`), a ready-to-use CSV adapter and a ready-to-use generic-JSON/JSONL adapter,
  plus three fixture-backed stub adapters (`racing_api`, `timeform`, `betfair`) that prove the
  interface and report exactly what credentials each would need to go live — see
  [DATA_SOURCES.md](./DATA_SOURCES.md). **No website scraping anywhere.**
- **Point-in-time correctness** — every mutable Race/Runner field, and bookmaker place terms, has
  an append-only history log; reconstruction as of any timestamp reads only from that history,
  never falling back to a live (possibly post-race) value. Named odds snapshots (opening, 24h/6h/
  1h/30m/10m/5m pre-race, off-time, SP/BSP) are derived from the timestamped price stream the same
  way. Full design in [POINT_IN_TIME_ARCHITECTURE.md](./POINT_IN_TIME_ARCHITECTURE.md).
- **Streaming/chunked import pipeline** (`racingedge_data/importers/`) — CSV/JSON/JSONL, optionally
  gzip-compressed, processed one race at a time (never fully loaded into memory), with progress
  tracking, failed-row reporting, duplicate detection, and idempotent re-imports via an explicit
  key.
- **Entity resolution** (`racingedge_data/entity_resolution.py`) — horses/trainers/jockeys/courses
  resolved via provider ID or exact normalized-name match ONLY; no fuzzy matching. Ambiguous
  matches are never silently merged — a new entity is created and the ambiguity is queued
  (`EntityResolutionQueueItem`) for manual review, auditable via `EntityAlias`.
- **Dataset versioning + real-data gate** (`racingedge_data/dataset_version.py`) — every training
  run creates an immutable `DatasetVersion` (exact race set, source classification, data-quality
  snapshot). A dataset isn't "production-ready" below 10,000 real races / 100,000 real runners
  (configurable) — below that, it's labelled `RESEARCH MODEL — INSUFFICIENT HISTORICAL DATA`
  everywhere it's surfaced.
- **Real/synthetic/sample separation** — `train.py` defaults to REAL races only and requires an
  explicit `--include-synthetic` flag to train on anything else; every `Race`/`Horse` row is
  explicitly classified `REAL` / `SYNTHETIC` / `SAMPLE`.
- **Market baseline** (`racingedge_data/market_baseline.py`) — normalized market-implied
  probabilities (overround removed) as the benchmark RacingEdge is measured against, reported
  alongside every training/backtest run: does the model add information beyond the market?
- **Temporal leakage auditor** (`racingedge_data/leakage_audit.py`) — a full,
  collect-every-violation "LEAKAGE AUDIT PASSED/FAILED" report (not just the first-violation
  runtime guard Phase 2 had), run automatically before every training run and persisted to
  `LeakageAuditRun`.
- **Data Quality Dashboard** (`/data-quality`) and **Dataset Explorer** (`/data-explorer`) — live
  coverage/missingness/provenance reporting, and a point-in-time viewer for any historical race,
  runner, or horse timeline.

Run `npm run model:test` to see the ~188 Python tests, including
`python/tests/test_malicious_leakage_scenarios.py` — deliberately malicious cases (future-dated
FormEntry rows, post-off-time odds, out-of-order place-terms history, self-referential leaks) each
confirmed blocked.

## Phase 3B — connecting a real provider (stopped at the credential boundary)

Phase 3B's brief: connect the Phase 3A infrastructure to The Racing API, ingest real UK & Irish
historical races, create the first REAL `DatasetVersion`, and re-run the *existing, unchanged*
Phase 2 models against it as an honest baseline. **This did not complete — by design.** There are
no Racing API credentials anywhere in this environment, and this environment's network egress
policy blocks `api.theracingapi.com` / `www.theracingapi.com` (so even the documentation couldn't
be read directly). Per explicit instruction, work stopped at that boundary rather than fabricating
a response or substituting synthetic data. **[REAL_DATA_BASELINE.md](./REAL_DATA_BASELINE.md) is
the complete, honest record of this — read it before assuming any real-data numbers exist
anywhere in this repository. They don't.**

What Phase 3B **did** build, fully tested against fixtures/mocks (no live account used):

- **`RacingApiProvider`** (`python/racingedge_data/providers/racing_api.py`) — a real HTTP client
  (`requests`-based) implementing the base URL, HTTP Basic Auth, `/results` pagination
  (`limit`/`skip`/`total`), the confirmed 2 req/s rate limit, and retry with exponential backoff on
  429/5xx — all verified against the vendor's own published example scripts (direct docs access was
  blocked; see the module's docstring and [DATA_SOURCES.md](./DATA_SOURCES.md) for exactly what's
  confirmed vs. best-effort/unverified in the field mapping).
- **`npm run data:racingapi -- --from YYYY-MM-DD --to YYYY-MM-DD`** (or
  `python -m racingedge_data.cli.import_racing_api`) — resumable, idempotent, rate-limit-aware,
  pagination-aware, retrying, progress-reporting, failed-record-logging, duplicate-handling,
  audit-trailed. Stops immediately with a clear message if `RACING_API_USERNAME` /
  `RACING_API_PASSWORD` aren't set — verified in this repository's own test suite AND by actually
  running the command in this environment (see REAL_DATA_BASELINE.md for the transcript).
- **`betfair_historical.py`** — a parser for *purchased* Betfair Historical Data files (the
  well-documented Exchange Stream `mcm`/`marketDefinition`/`rc` wire format), resolving selections
  to RacingEdge runners via exact-normalized-name matching, never fuzzy. Not blocking Racing API
  ingestion, per instruction — see [DATA_SOURCES.md](./DATA_SOURCES.md) for exactly what purchase
  and file-extraction steps a maintainer needs to complete before using it.

### Next steps to actually get real data flowing

1. **Obtain a licensed theracingapi.com subscription** and set `RACING_API_USERNAME` /
   `RACING_API_PASSWORD` as environment variables.
2. Run `npm run data:racingapi -- --from 2024-01-01 --to 2026-08-01` (or any date range the
   subscription covers). Watch the first response and **verify/correct**
   `_UNVERIFIED_RUNNER_FIELD_CANDIDATES` / `_UNVERIFIED_RACE_FIELD_CANDIDATES` in `racing_api.py`
   against what the API actually returns for official rating, draw, weight, going, race class,
   distance, pedigree, headgear, and starting price — these were informed guesses, not confirmed.
3. The temporal leakage auditor (`racingedge_data.leakage_audit.audit_training_data`) runs
   automatically at the start of `python -m racingedge_model.train` and aborts training if it
   reports FAILED — no separate step needed, but it can also be called directly for an
   ad-hoc check.
4. Create the REAL `DatasetVersion` (the import CLI does this automatically via
   `racingedge_data.dataset_version.create_dataset_version`) and check the readiness gate
   (`racingedge_data.dataset_version.classify_readiness`, ≥10,000 races / ≥100,000 runners).
5. Run `python -m racingedge_model.train` (REAL-only by default, no flag needed once real data
   exists) and report the results — chronological 70/15/15 split, Brier/log loss/AUC for both win
   models, top2–top6 place calibration, and the market-baseline comparison — honestly, in an
   updated `REAL_DATA_BASELINE.md`, without optimising anything based on them.
6. (Optional, not blocking) Purchase Betfair Historical Data for exchange-odds depth and run it
   through `betfair_historical.import_betfair_historical_file` against the already-imported race
   cards.

## Recommended next phase

1. Phase 3B: acquire and ingest genuine historical racing data via the infrastructure above.
2. Hyperparameter search (currently baseline defaults) and feature selection, still governed by
   validation-only tuning — never test — and only once trained on real data.
3. Race-shape/pace modelling is currently derived from a horse's own historical positional data;
   a proper pre-race pace/race-shape simulation (using the whole field's projected roles together)
   is a natural next increment.
4. SHAP-based feature attribution, if it stays cheap enough to compute at prediction time.
5. Wire the Lucky 15 leg-selection algorithm (expected value + place probability + confidence +
   enhanced place terms + diversification — explicitly out of scope here).
6. Consider a Postgres migration once multi-user or hosted deployment is in scope.
7. Only after real data is trained on and genuine out-of-sample evidence of edge beyond the market
   baseline exists: staking logic. Not before.

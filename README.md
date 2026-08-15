# RacingEdge — Phase 3D

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
complete it. **Phase 3C** builds a parallel, £0-cost data path — free/community datasets, a
schema-agnostic inspector, provenance/licence review, a free market-benchmark importer, reduced
feature profiles, dataset bias analysis, a behavioural-observation dataset, and value-cohort
backtesting — since it stops at the same kind of boundary as Phase 3B (no local dataset file had
been supplied at the time), see [REAL_FREE_BASELINE.md](./REAL_FREE_BASELINE.md) and
[FREE_DATA_SOURCES.md](./FREE_DATA_SOURCES.md) for that honest account. **Phase 3D** (this phase)
turns Phase 3C's terminal/file-path workflow into a consumer UX: a **`/data-sources`** page (select
a source → Connect → Import), a Kaggle integration using the official Kaggle API, one-click
streaming downloads with resume/checksum/retry, an "Add data source from URL" flow, automatic
schema-mapping with a browser review UI for anything below high confidence, a free-data discovery
page, first-run onboarding, and a post-import summary with an explicit "Train Baseline Model"
action. The CLI/`npm run data:*` workflow from Phase 3C remains fully available as the advanced
fallback — nothing was removed, only wrapped in a UI. See the **Phase 3D** section below for the
full account, and [DATA_SOURCES.md](./DATA_SOURCES.md), [DATA_PROVENANCE.md](./DATA_PROVENANCE.md),
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
                                                    betfair_historical.py (purchased-file parser) +
                                                    betfair_sp.py (free SP CSV, Phase 3C) /
                                                    formfav.py (honest non-implementation, Phase 3C)
    importers/                                      Streaming/chunked/resumable/idempotent import
                                                       pipeline + free_dataset_importer.py (Phase 3C)
    cli/                                              import_racing_api.py / inspect_dataset.py /
                                                        import_free_dataset.py / bias_analysis.py
    inspector.py                                        Schema-agnostic dataset inspector (Phase 3C)
    dataset_review.py                                     Licence/provenance review (Phase 3C)
    bias_analysis.py                                        Dataset bias/skew report (Phase 3C)
    behavioural_observations.py                              RACINGEDGE_BEHAVIOURAL_DATA (Phase 3C)
    value_backtest.py                                         Value-cohort backtesting (Phase 3C)
  tests/                  pytest suite, including the explicit anti-leakage test, Phase 3A malicious
                             leakage scenarios, and Phase 3C's free-data infrastructure tests
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

## Deployment (Vercel + Postgres)

RacingEdge can be deployed as a normal, publicly-reachable Next.js app on Vercel's free tier —
useful for browsing the app (races, dashboard, value scanner, data quality, CSV/JSON import) from
any device without running a local dev environment. **Read the whole section before deploying**,
especially "What does NOT work on Vercel" below — most of the free-data import pipeline (Phase 3D's
`/data-sources` advanced/CLI path) and model training are local/dev-only capabilities, not a Vercel
limitation to be worked around, but a genuine architectural boundary. The exception is the "one-tap
free setup" card on `/data-sources` (Phase 3E) — it reimplements download/parse/import as plain
Node code specifically so it works on Vercel; see below for exactly what it does and doesn't cover.

### Why not SQLite in production

SQLite is a single local *file*. Vercel serverless functions have an ephemeral, per-invocation
filesystem — a write from one request is never guaranteed to be visible to the next (a different
invocation, possibly a different machine, gets a fresh copy of the deployed filesystem). SQLite is
correct and appropriate for local development (a single, persistent machine) and is unsuitable for
Vercel's execution model regardless of how the app code is written.

### Why Postgres (Neon), and why this app supports two databases at once

[Neon](https://neon.tech) offers a genuinely free tier (no credit card, generous enough for this
project: 0.5 GB storage, autosuspend when idle) of serverless Postgres, and Prisma has first-party
driver-adapter support for it via the plain `pg` (node-postgres) client — both `@prisma/adapter-pg`
and `pg` are free, open-source npm packages; nothing paid was introduced.

Prisma's `provider` field (`sqlite` vs `postgresql`) is fixed per schema file — it cannot be an
environment variable — so this repo has **two** schema files with **one** shared source of truth:

- **`prisma/schema.prisma`** — SQLite, hand-maintained, used for local development exactly as
  before. Nothing about the local dev workflow above changed.
- **`prisma/postgres/schema.prisma`** — Postgres, **generated, never hand-edited** — derived from
  `prisma/schema.prisma` by `scripts/generate-postgres-schema.mjs`, which swaps only the
  `datasource` block. The schema was written in Postgres-compatible types from the very start (see
  the comment at the top of `schema.prisma`), so no field-level differences exist between the two —
  editing models always happens in `schema.prisma` only, then re-running `npm run
  db:generate:postgres` (or the automatic Vercel build step below) regenerates the Postgres file.

`src/database/client.ts` picks the matching driver adapter (`PrismaBetterSqlite3` vs `PrismaPg`) at
runtime based on whether `DATABASE_URL` starts with `postgres(ql)://` — it always matches whichever
schema was used to `prisma generate` in that environment, because the generated client
(`src/generated/prisma`, gitignored, never committed) is regenerated fresh by each environment's own
build command: `npm run build`/`postinstall` generate the SQLite client locally; `npm run
vercel-build` (which Vercel runs automatically instead of `build` when the script exists — no
dashboard configuration needed) generates the Postgres one.

### What does NOT work on Vercel

Most of the **Phase 3A–3D real-data pipeline** — the advanced/CLI side of `/data-sources`
(Connect/Import/Sync via `SourceCard`'s form), schema inspection, the mapping-review UI for those
jobs, `racingedge_data.import_pipeline`, and the "Train Baseline Model" action — works by spawning a
**local Python virtual environment** as a subprocess (`src/lib/pythonRunner.ts`). This is
fundamentally incompatible with Vercel's serverless Node.js functions, independent of the database
choice:

- There is no Python interpreter or virtualenv available in a Vercel serverless function.
- Serverless functions cannot reliably spawn long-running background processes — the import
  pipeline (download → inspect → import → leakage audit → …) can run for minutes, far past a
  serverless function's execution limit, and a detached child process has no guarantee of
  outliving the parent invocation.
- The pipeline's file-based working storage (`python/storage/import_jobs/`) requires a persistent
  local filesystem, which Vercel does not provide.

On a Vercel deployment, clicking that **Import**/**Sync**/**Train Baseline Model** will fail cleanly
with an error (`RACINGEDGE_PYTHON_BIN is not set` or similar) rather than silently doing nothing —
this is expected, not a bug to fix. These features remain genuinely local/dev-only.

**The exception (Phase 3E): "one-tap free setup".** The highlighted card at the top of
`/data-sources` — "Add free historical data" / "Set up free UK/Ireland racing data" — runs a
separate, Vercel-compatible pipeline (`src/lib/serverlessImport/`) written as plain Node code: it
downloads over `fetch()`, extracts ZIPs with a small built-in reader (`zlib`, no dependency),
proposes a column mapping with a heuristic scorer, and writes rows straight to Postgres via Prisma —
no subprocess, no local filesystem, all within one Server Action request (bounded by
`maxDuration = 60` — see `src/actions/serverlessImport.ts`). It genuinely works on Vercel. It is
also genuinely narrower than the CLI pipeline: no entity-resolution review queue beyond simple
name-based horse dedup, no temporal leakage audit, no `DatasetVersion`/quality report, and a 60MB
download cap — a dataset too big or a leakage-audited version still needs the CLI path (local dev).
See `FREE_DATA_SOURCES.md`'s Phase 3E section for the full scope.

Everything else — viewing races/results/dashboard/value-scanner/backtest/data-quality/data-explorer
pages, and CSV/JSON import via `/import` (pure Prisma, no Python involved) — works identically
against Postgres.

### First-time production database setup

Do this once, before the first deploy (or any time the schema changes and you want production to
pick it up):

```bash
DATABASE_URL="<your Neon connection string>" npm run db:push:postgres
```

`db:push:postgres` regenerates `prisma/postgres/schema.prisma` and pushes it directly to the target
database (`prisma db push` — schema-first sync, no migration history yet; appropriate for a
single-environment early-stage deployment). Optionally seed sample data the same way:

```bash
DATABASE_URL="<your Neon connection string>" npm run db:seed
```

See "Deploying from scratch" below for the exact account-creation and dashboard steps — those
require your own Neon/Vercel login, which nothing here can do on your behalf.

### Deploying from scratch

Every step below happens on neon.tech / vercel.com / github.com, using **your own** account —
nothing here can sign up for an account, click a button, or grant access on your behalf, so this
is the exact sequence to follow yourself.

1. **Create a free Neon Postgres database.**
   - Go to [neon.tech](https://neon.tech) → Sign up (free, no card required) → **Create a project**.
   - Once created, open the project's **Connection Details** / **Dashboard** and copy the
     connection string (looks like `postgresql://USER:PASSWORD@HOST/DBNAME?sslmode=require`).

2. **Push the schema to it** (run this locally, once, with the connection string from step 1):
   ```bash
   DATABASE_URL="<paste the Neon connection string>" npm run db:push:postgres
   ```
   Optionally seed sample data so the deployed app isn't empty on first load:
   ```bash
   DATABASE_URL="<paste the Neon connection string>" npm run db:seed
   ```
   (Ask your assistant to run these two commands for you if you'd rather not use a terminal —
   it only needs the connection string you copied, not your Neon login.)

3. **Import the repo into Vercel.**
   - Go to [vercel.com](https://vercel.com) → sign in (GitHub sign-in is simplest) → **Add New… →
     Project**.
   - Choose **Import Git Repository**, and select this GitHub repo
     (`naithan20/Racing-`) — grant Vercel access to it if prompted (a GitHub permission screen you
     approve yourself).
   - Vercel auto-detects Next.js. Leave the Framework Preset as-is — you do **not** need to
     manually set a Build Command; this repo's `package.json` has a `vercel-build` script that
     Vercel picks up automatically.

4. **Set the one required environment variable, before the first deploy.**
   - In the Vercel project's **Settings → Environment Variables**, add:
     - `DATABASE_URL` = the same Neon connection string from step 1 (all environments).
   - Nothing else is required to view the app. See `.env.example` for optional variables (Kaggle,
     Racing API, FormFav) — none of those matter for basic browsing, and the Kaggle/import/training
     features won't work on Vercel regardless (see "What does NOT work on Vercel" above).

5. **Deploy.** Click **Deploy**. Vercel builds and gives you a public URL
   (`https://<project-name>.vercel.app`) — open that on your phone.

6. **Redeploying later**: pushing to the connected branch on GitHub triggers an automatic
   redeploy. If you change the Prisma schema, re-run step 2's `db:push:postgres` command against
   the same `DATABASE_URL` so the live database matches before/after the redeploy.

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
npm run data:inspect -- --file <path>          # (Phase 3C) profile a free dataset file, propose a mapping
npm run data:import-free -- --file <path> --mapping <path> --source-label ... --provenance-status ...
                           # (Phase 3C) import a confirmed-mapping free dataset — see DATA_SOURCES.md
npm run data:bias-report                        # (Phase 3C) missing years/tracks/classes, odds/DNF/
                                                  # non-runner coverage — see FREE_DATA_SOURCES.md
```

Flags (run the underlying Python module directly for these, e.g.
`cd python && ../.venv/bin/python -m racingedge_model.train --primary logistic`):

- `train.py --primary {gbm,logistic}` — which win model becomes the serving model (default `gbm`)
- `train.py --include-synthetic` — train on SYNTHETIC/SAMPLE races too. **Without this flag,
  training uses REAL races ONLY** (Phase 3A default) and aborts with a clear message if there are
  none yet — this repository currently has none, so `npm run model:train` will abort unless you
  pass this flag or import real data first.
- `train.py --feature-profile {CORE_FREE_MODEL,ENRICHED_FREE_MODEL,FULL_MODEL}` — (Phase 3C)
  restricts training to a feature-GROUP allowlist matching what a free dataset can actually supply.
  `CORE_FREE_MODEL` excludes pace/headgear-change features (no sectional/positional data in most
  free sources); `ENRICHED_FREE_MODEL` adds headgear back in; `FULL_MODEL` (default) uses every
  registered feature. Every `ModelVersion` records which profile trained it.
- `predict.py --model-version-id ID --date YYYY-MM-DD` — predict a specific model/date
- `backtest.py --model-version-id ID --start-date ... --end-date ...` — backtest an arbitrary
  window (prints a warning if it overlaps training)

Every `train.py` / `backtest.py` run also: runs the temporal leakage auditor first (aborting on
FAILED), excludes any race whose provenance is classified `RESTRICTED` (Phase 3C, see
`DATA_PROVENANCE.md`), creates an immutable `DatasetVersion`, reports the minimum-real-data
production-readiness gate, and reports the market-implied-probability baseline comparison —
`backtest.py` additionally reports a value-cohort breakdown (Phase 3C, see
`racingedge_data/value_backtest.py`): actual win rate and flat-stake ROI observed in each
model-vs-market value-edge bucket. See
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
npm run model:test  # Python (pytest) — ~280 tests, incl. the leakage test, Phase 3A malicious
                    # leakage scenarios, Phase 3B's Racing API/Betfair-historical adapter tests, and
                    # Phase 3C's inspector/free-importer/provenance/bias-analysis/behavioural-
                    # observation/value-backtest tests
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

## Phase 3C — £0 free-data strategy (stopped at the same kind of boundary as Phase 3B)

Phase 3C's brief: build a complete £0-cost path to genuine UK/Ireland historical racing data —
free/community datasets, a schema-agnostic inspector, mapping-driven import, licence/provenance
review, a free market-benchmark importer, reduced feature profiles for what free data can actually
supply, dataset bias reporting, a first-class behavioural-observation dataset, and evaluation-only
value-cohort backtesting — **without scraping, without paying for anything, and without fabricating
data**. Every piece of infrastructure listed below is built and tested. **No real free dataset has
been imported** — per explicit instruction, this repository does not download external datasets
automatically, and no local dataset file was supplied in this environment (`www.kaggle.com` was
also unreachable — `EGRESS_BLOCKED` — so even a permitted automated download wasn't possible here
regardless). **[REAL_FREE_BASELINE.md](./REAL_FREE_BASELINE.md) is the complete, honest record of
this — read it before assuming any free-real-data numbers exist anywhere in this repository. They
don't.**

What Phase 3C **did** build, fully tested:

- **Schema-agnostic dataset inspector** (`racingedge_data/inspector.py`,
  `npm run data:inspect`) — profiles any `.db`/`.sqlite`/`.csv`/`.json`/`.jsonl` file and proposes a
  column-role mapping with a confidence tier per column, instead of hard-coding against one exact
  dataset schema.
- **Mapping-driven free-dataset importer** (`racingedge_data/importers/free_dataset_importer.py`,
  `npm run data:import-free`) — imports only once every ambiguous column has been explicitly
  confirmed, requires an explicit `--provenance-status` (no default), and writes any embedded
  historical result to `ResultEntry` — never to a `Runner`'s own pre-race fields.
- **Reuse-rights provenance** (`ProvenanceStatus` on `DataProvenance`, `DatasetReview`) — separate
  from `DataSourceType` (authenticity). `RESTRICTED` data is excluded from training by default;
  `UNKNOWN`/`COMMUNITY_UNVERIFIED` produce explicit import-time warnings. See
  [DATA_PROVENANCE.md](./DATA_PROVENANCE.md).
- **Free Betfair SP historical CSV importer** (`racingedge_data/providers/betfair_sp.py`) — the
  free (not the paid `historicdata.betfair.com`) CSV format, for post-race CLOSING/SP MARKET
  BENCHMARK use only — never a pre-race feature. Entity-matches on exact horse name + exact date
  only; ambiguous matches go to manual review, never guessed.
- **FormFav enrichment adapter** — an honest non-implementation. `formfav.com`'s documentation was
  unreachable from this environment and no secondary source could confirm its API contract, so
  `FormFavProvider` is a tested stub, not a guessed implementation.
- **Feature Availability Matrix** (`/data-quality`) — per-feature-group availability percentages,
  computed live, so a missing field is visible evidence rather than a silent assumption.
- **Reduced feature profiles** (`CORE_FREE_MODEL`/`ENRICHED_FREE_MODEL`/`FULL_MODEL`,
  `train.py --feature-profile`) — feature-group allowlists matching what free data can genuinely
  supply, never inventing sectional/positional data a free source doesn't have.
- **Dataset bias analysis** (`racingedge_data/bias_analysis.py`, `npm run data:bias-report`) —
  missing years/tracks/classes, Flat/jumps split, favourite/outsider distribution, field size, odds
  distribution, non-runner/DNF coverage, year-over-year comparison, with explicit (never pass/fail)
  warnings.
- **`RACINGEDGE_BEHAVIOURAL_DATA`** (`racingedge_data/behavioural_observations.py`) — a transparent,
  fixed numeric mapping over `RunnerObservation` tags (break quality, early position,
  position-acquisition cost, pace-pressure response, 2f transition, final-furlong sustainability,
  pace-collapse interaction, plus confidence flags), never learned from outcomes, with raw
  observations kept permanently and insert-only (never overwritten).
- **Value-cohort backtesting** (`racingedge_data/value_backtest.py`, wired into
  `racingedge_model/backtest.py`) — buckets runners by model-vs-market value edge and reports actual
  win rate / ROI per bucket, using model probabilities generated without the target race's own
  SP/BSP. Evaluation-only — nothing is trained to maximise these figures.

See [FREE_DATA_SOURCES.md](./FREE_DATA_SOURCES.md) for the full source-by-source discovery record
(RECOMMENDED / USE WITH CAUTION / REJECTED) and exactly what a maintainer needs to supply next.

## Phase 3D — consumer data-source UX

Phase 3C's free-data path worked, but required a terminal, a filesystem path, and manually running
`npm run data:inspect`/`data:import-free`. Phase 3D's brief: make **SELECT DATA SOURCE → CONNECT →
IMPORT** the normal way to add historical data — a non-technical user should be able to click
through it in a browser, with the CLI kept only as an advanced fallback.

**`/data-sources`** — every entry in `src/data/sourceCatalog.ts` (the single, centralized source
registry — nothing about a specific source is hard-coded elsewhere) as a card: name, description,
coverage, expected fields, cost (always FREE — see the £0 rule), auth-required, connection status,
last sync, races/runners imported. Connect / Import / Sync / View Data Quality / Disconnect buttons,
shown or hidden based on live state.

**One-click import pipeline** (`racingedge_data/import_pipeline.py`) — clicking Import creates an
`ImportJob` row and spawns the pipeline as a background process: download (or use an already-local
file) → inspect → propose a mapping → pause for review only if something's below high confidence →
validate → import → resolve entities → an auto-drafted provenance/licence review → temporal leakage
audit → `DatasetVersion` → data-quality summary → done. Every step updates `ImportJob` directly (the
same "Python writes SQLite, Next.js reads it via Prisma" pattern the rest of the data layer uses),
so the browser polls a database row for progress rather than reading a subprocess's stdout.

**Kaggle** (`racingedge_data/providers/kaggle_adapter.py`) — the official `kaggle` Python package
only, no scraping. **Verified against the real, installed package, not guessed**: `kaggle==1.6.17`
is pinned deliberately, after discovering (by actually installing and running it) that the newer
2.x package's OAuth-first flow crashes on import under non-interactive stdio — exactly the
condition a Next.js-spawned subprocess always runs under. Terms-not-accepted (HTTP 403) is detected
and surfaced as "open the dataset page and accept its terms" — never bypassed. Connect once in
**Settings → Data Connections**; credentials are written to a server-only, gitignored file
(`.data-connections/kaggle.json`, mode 600) and a `KAGGLE_CONFIG_DIR` env var points the spawned
Python process at it — never sent to or rendered in the browser.

**Streaming downloads** (`racingedge_data/providers/download_adapter.py`) — resume via HTTP Range,
SHA-256 checksum, retry with exponential backoff, and a fixed allowlisted-extension check
(csv/json/jsonl/db/sqlite/zip/gz) that exists specifically so a pasted URL can never be used to fetch
an executable. Tested entirely against a mocked `requests` — this sandbox's network egress policy
blocks most external hosts, which is a property of the development environment, not of the feature;
see the module's docstring.

**"Add data source from URL"** — paste a URL, see hostname/file type/expected size before anything
downloads, and explicitly confirm ("I've reviewed this source...") before the import can start.

**Automatic schema mapping** — the Phase 3C inspector runs automatically; HIGH-confidence fields
proceed without asking anything, and the UI states plainly ("12 fields mapped automatically, 2
fields need confirmation") rather than pointing at a CLI. Anything below HIGH shows a browser table
(external field → dropdown of RacingEdge fields, with example source values) before the import can
continue.

**Find free data** (`/data-sources/discover`) — every catalog entry, including disabled/unavailable
ones, filterable by category/region/code, labelled VERIFIED / AVAILABLE BUT UNVERIFIED / REQUIRES
CONNECTION / UNAVAILABLE — never claims a source works unless its adapter has actually been
exercised.

**First-run onboarding** — `/dashboard` shows "RacingEdge needs historical racing data" → **Add
Free Racing Data** whenever no `REAL` race exists yet, linking straight to `/data-sources`.

**Post-import summary + Train Baseline Model** — races/runners imported, date coverage, a
completeness score (100 minus the average of the DatasetVersion's own missing-OR/draw/SP
percentages — labelled "completeness", not "quality", since it says nothing about correctness),
leakage-audit status, and a dataset-size label (EXPERIMENTAL/RESEARCH/LARGE RESEARCH per Phase 3C's
own thresholds). Training is never triggered automatically — an explicit **Train Baseline Model**
click spawns `racingedge_model.train` unchanged.

**A genuine build bug found and fixed along the way**: `.venv/bin/python` is a symlink pointing
outside the project directory, and passing that path straight to `child_process.spawn()` made
Turbopack's build tracer try to statically resolve it as a bundleable asset and panic on every
`next build`. Fixed by reading the interpreter path from a `RACINGEDGE_PYTHON_BIN` environment
variable at runtime instead of a `path.join(process.cwd(), ...)` literal — see
`src/lib/pythonRunner.ts`'s docstring for the full story and `.env.example` for the default.

**Command line remains available** — every `npm run data:*` script from Phase 3C still works
unchanged, including a new `data:run-import-job` wrapping the same pipeline the UI uses
(`racingedge_data.cli.run_import_job`), for scripting, automation, and large/unattended imports.

**What genuinely still requires a human**: connecting a real Kaggle account (an API key, entered
once), accepting a dataset's terms on kaggle.com when Kaggle requires it, and — as in Phase 3C —
supplying the actual dataset file/URL in the first place, since nothing here fabricates real
racing data or downloads anything the user hasn't pointed at or confirmed.

## Recommended next phase

1. Phase 3B/3C: acquire and ingest genuine historical racing data — either a licensed
   theracingapi.com subscription (Phase 3B, see `REAL_DATA_BASELINE.md`) or a manually-downloaded
   free dataset file (Phase 3C, see `REAL_FREE_BASELINE.md` and `FREE_DATA_SOURCES.md`).
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
8. Once real free data exists: the CORE_FREE_MODEL vs. CORE_FREE_MODEL+RACINGEDGE_BEHAVIOURAL_DATA
   observation-learning experiment (Phase 3C section 15) — does transition speed / position-
   acquisition cost / late sustainability improve out-of-sample predictions? Not yet run; no claim
   of improvement should be made until it's validated chronologically.

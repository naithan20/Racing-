# RacingEdge — Phase 1

RacingEdge is a local-first horse-racing **analysis and decision-support** application. It is not a
tip generator. Its purpose is to eventually estimate win probability, place probability (against
actual bookmaker place terms), model confidence, fair odds, market-implied probability, and
value/edge versus market price — then track results against those pre-race predictions so the
model's calibration can be judged honestly.

**Phase 1 ships the architecture, database, data structures, UI and result-tracking system.
It deliberately ships no probability model.** Every probability field in the UI reads "Model not
yet configured" until Phase 2 exists. See [What Phase 1 deliberately does NOT implement](#what-phase-1-deliberately-does-not-implement).

## Tech stack

- **Next.js 16** (App Router, Turbopack) + **TypeScript** + **Tailwind CSS v4**
- **SQLite** via **Prisma 7** (using the `@prisma/adapter-better-sqlite3` driver adapter) — field
  types are chosen to be PostgreSQL-compatible, so migrating later is a provider swap, not a
  redesign
- **Recharts** for the odds-history chart
- **Zod** for import validation
- **Vitest** for unit tests
- Dark, dense, Bloomberg-style analytics UI

## Project structure

```
prisma/
  schema.prisma        Full data model (see below)
  seed.ts               Seeds SAMPLE DATA for every screen
src/
  app/                  Next.js App Router pages + a couple of route handlers
  actions/               Server Actions (mutations): imports, results, race creation, Lucky 15
  components/             UI components, grouped by feature area
  data/                    Server-side read queries, import schema + persistence
  database/                 Prisma client singleton (driver-adapter wired up)
  features/                  The flexible Feature Store: definitions + typed read/write helpers
  lib/                        Generic utilities: odds conversion, CSV parsing, formatting
  models/                      Placeholder model-output contract (all-null in Phase 1)
  pace/                         Pace/race-shape types — 3 concepts kept strictly separate
  results/                       Result settlement (finish position -> place outcome, P/L)
  value/                          Value engine (fair odds, edge) + each-way place-term handling
  backtesting/                    Scoring-rule math (Brier score, log loss, calibration, ROI)
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
  positions at 3f/2f/1f out, pace classification, comments, etc).
- **FeatureDefinition** / **Feature** — the flexible **Model Feature Store**. Every feature is
  `(runnerId, key) -> value`, self-described by a `FeatureDefinition` (category, label,
  description, value type). `src/features/definitions.ts` seeds ~70 feature keys spanning current
  ability, class, handicap, weight, course/distance/ground, draw, pace (see below), trainer/jockey,
  headgear, pedigree and evidence/uncertainty. **No feature here implies a weight or formula.**
- **RunnerPaceProfile** — pace/race-shape modelling. Three concepts are stored as **distinct
  fields, never combined into one score**:
  1. Position acquisition (usual early position, break speed, energy cost)
  2. Transition speed (position change 3f→2f, 2f→1f, relative acceleration)
  3. Late sustainability (finishing speed, position change in the final furlong, weakens/stays-on
     rates)
- **EvidenceProfile** — the Evidence Confidence system: career starts, recent starts,
  `evidenceDensityScore`/`Label`. High evidence density means the estimate is *more trustworthy*,
  not that win probability is *higher* — the schema and UI keep these concepts separate everywhere.
- **Bookmaker** / **RunnerMarketPrice** — multi-bookmaker odds time series (opening/current/SP/
  closing flags), designed so more bookmakers can be added without a schema change.
- **PredictionSnapshot** — the model's pre-race output (win probability, place probability +
  which place count it's based on, model confidence, fair odds, market-implied probability, value
  edge). **Locked (`isLocked: true`) by default and never overwritten by results** — see
  `src/results/settlement.ts:assertSnapshotMutable`. This is what lets the dashboard later judge
  calibration honestly instead of retrofitting a story after the fact.
- **ResultEntry** / **RunnerObservation** — actual outcome (finish position, SP, closing odds,
  place outcome, P/L) plus manual observation tags (21 tags from the spec, e.g. "pace collapse
  benefited", "bad ride/positioning") and a free-text field.
- **Lucky15Slip** / **Lucky15Leg** — data structures + filters (odds range, confidence, place
  edge, runners, enhanced places, flat/jumps, country, bookmaker) for the Lucky 15 builder
  placeholder.
- **ImportBatch** — tracks every manual/CSV/JSON import (source, filename, row/success/error
  counts, error log).

Run `npx prisma studio` (or `npm run db:studio`) to browse the schema and data directly.

## Running locally

```bash
cp .env.example .env   # DATABASE_URL="file:./dev.db" — no secrets, just the local db path
npm install              # also runs `prisma generate` (postinstall)
npm run db:migrate         # creates dev.db and applies the schema
npm run db:seed              # loads SAMPLE DATA — safe to re-run, it clears and reloads
npm run dev                    # http://localhost:3000
```

`dev.db` and the generated Prisma client (`src/generated/prisma`) are gitignored — they're
regenerated by the commands above, not committed.

Other useful scripts:

```bash
npm run build          # production build
npm run test            # vitest run (unit tests)
npm run lint              # eslint
npm run db:studio          # Prisma Studio, browse the SQLite DB visually
npm run db:reset             # drop + recreate + reseed (destructive, asks nothing — be sure)
```

## Data import

Three supported paths, all going through the same validated schema
(`src/data/importSchema.ts`) and the same persistence function (`src/data/importRaces.ts`), so
behaviour never drifts between them:

1. **Manual entry** — `/races/new`, a form for the race plus a quick-entry runner list
   (`Horse Name | Trainer | Jockey | OR | Odds | Draw`, one per line).
2. **CSV import** — `/import`, one row per **runner**; rows sharing the same
   `(race_date, race_time, racecourse)` are grouped into one race. Download the column template
   from the Import page (`GET /import/template`) or see `CSV_IMPORT_TEMPLATE_HEADER` in
   `src/data/importSchema.ts` for the full 36-column reference. Only `race_date`, `race_time`,
   `racecourse`, `country`, `race_name`, `flat_jumps`, `surface`, `distance_furlongs`,
   `handicap_type`, `number_of_runners` and `horse_name` are required — everything else may be
   left blank.
3. **JSON import** — `/import`, `{ "races": [ { ...race fields, "runners": [...] } ] }`. See
   `RaceImportSchema` / `RunnerImportSchema` in `src/data/importSchema.ts`.

RacingEdge does not scrape any website. A licensed/API data feed can be added later by writing a
new source that produces the same `RaceImport[]` shape and calling `importRaces()` — nothing else
needs to change.

## Sample data

`prisma/seed.ts` creates three **SAMPLE DATA** races (flagged `isSampleData: true` on every row,
and named things like "Fair Odds Fella" / "SAMPLE Handicap Chase" so they can never be mistaken
for real racing data):

- An 8-runner handicap chase and a 6-runner novice stakes, both "today", with full runner form,
  pace profiles, evidence profiles and multi-bookmaker market prices, so every screen (daily race
  screen, race analysis, runner detail, Lucky 15) has data to render.
- A 7-runner "yesterday" handicap hurdle that has already been **resulted**, with finish
  positions, starting/closing prices, profit/loss, and a full set of manual observation tags —
  so the Results and Dashboard screens have something to show.

## What Phase 1 deliberately does NOT implement

- **No probability model.** No `form = 30%, jockey = 10%, ...` scoring formula exists anywhere.
  Every `winProbability` / `placeProbability` / `modelConfidence` / `fairOdds` / `valueEdge` field
  in the seeded data is `null`, and the UI renders "Model not yet configured" for all of them.
- **No pace/feature weighting.** The Feature Store and pace profile fields are storage +
  validation only — nothing combines them into a score.
- **No "why the model likes this horse" text.** The runner detail page has the section, empty by
  design — Phase 2 should populate it from concrete, traceable feature comparisons, never
  free-form/LLM-generated text.
- **No Lucky 15 leg-selection algorithm.** The builder is a real, working data-structure +
  filters + persistence layer; a human picks the four legs. Phase 2's algorithm must not simply
  pick the four highest win probabilities.
- **No backtesting math beyond generic scoring rules.** `src/backtesting/scoring.ts` implements
  Brier score, log loss, calibration buckets and ROI — standard statistics, not a racing model —
  ready for Phase 2 to feed real `(predictedProbability, outcome)` pairs into.
- **No web scraping, no licensed data feed integration.** Import is manual/CSV/JSON only.
- **No authentication/multi-user support.** This is a local-first, single-user tool.

## Recommended next phase

1. Design the actual probability model (win probability, place probability conditioned on
   bookmaker place terms, model confidence) reading from the Feature Store — this is explicitly
   out of scope for Phase 1 by request.
2. Have the model write `PredictionSnapshot` rows (`isLocked: true`, `snapshotType: PRE_RACE`)
   before each race goes off; never edit them afterwards.
3. Wire the Lucky 15 leg-selection algorithm (expected value + place probability + confidence +
   enhanced place terms + diversification) against `getLucky15Candidates()`.
4. Once enough `PredictionSnapshot` + `ResultEntry` pairs exist, the Dashboard page's calibration
   section (`src/backtesting/scoring.ts`) activates automatically — no dashboard changes needed.
5. Add a licensed/API data source behind `importRaces()`.
6. Consider a Postgres migration (`prisma/schema.prisma` datasource provider + a Postgres driver
   adapter) once multi-user or hosted deployment is in scope.

## Testing

```bash
npm run test
```

Covers: decimal/fractional odds conversion, implied probability, book overround, each-way place-term
settlement (explicitly verifying place is **never** hardcoded to top 3), full result-settlement
structure (including the prediction-snapshot immutability guard), CSV parsing + schema validation,
value-engine edge calculations, feature-store read/write validation, and the Brier
score/log-loss/calibration/ROI scoring utilities.

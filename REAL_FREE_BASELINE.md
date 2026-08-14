# Real Free-Data Baseline — Phase 3C

**Status: not produced.** Exactly like `REAL_DATA_BASELINE.md` (Phase 3B) before it, this is the
honest, unedited account of what Phase 3C built, precisely where it stopped, and exactly what a
maintainer needs to do to complete it. Nothing here is fabricated, no synthetic data was
substituted for real data, and — per Phase 3C's explicit £0 constraint — nothing was scraped,
purchased, or downloaded automatically.

## What Phase 3C was asked to do

Build the full £0 free-data ingestion/validation layer (schema-agnostic inspector, mapping-driven
importer, provenance/licence review, free Betfair SP market-benchmark importer, feature-availability
reporting, reduced feature-profile models, dataset bias analysis, behavioural-observation dataset,
value-cohort backtesting) and then — once a real free dataset file is supplied — inspect it, review
its provenance, import it, audit it for leakage, create a real `DatasetVersion`, and retrain the
existing, unmodified Phase 2 models against it as a genuine free-data baseline.

## What actually happened

### 1. No local dataset file exists in this environment

```
$ find / -maxdepth 4 -iname "*raceform*" -o -iname "*horse*racing*"
(no matches, outside node_modules/.git)
$ ls ~/Downloads
(does not exist)
```

Per Phase 3C section 23's explicit instruction — "do NOT download external datasets automatically
unless direct downloading is clearly permitted... if the file is not present locally, stop cleanly
and report" — no download was attempted. `www.kaggle.com` also returned `EGRESS_BLOCKED` from this
environment on every attempt during Phase 3C's research, so even a permitted automated download
would not have been possible here regardless.

### 2. Everything that doesn't require a real file was built and tested

All of the following ship in this repository, with passing tests (`python -m pytest python/tests`,
279 tests as of this document — see the final validation section of this repo's commit history):

| Component | File(s) | Status |
|---|---|---|
| Schema-agnostic dataset inspector + CLI | `racingedge_data/inspector.py`, `cli/inspect_dataset.py` | Built, tested against SQLite/CSV/JSON fixtures |
| Mapping-driven free-dataset importer + CLI | `racingedge_data/importers/free_dataset_importer.py`, `cli/import_free_dataset.py` | Built, tested; requires an explicitly confirmed mapping file before it will import anything |
| Provenance/licence review | `racingedge_data/dataset_review.py`, `prisma` `DatasetReview` model | Built, tested; not yet populated with a real review (no dataset to review) |
| Free Betfair SP market-benchmark importer | `racingedge_data/providers/betfair_sp.py` | Built, tested against a hand-built fixture in the well-known public CSV format — **not run against a real downloaded file**, since none exists locally |
| FormFav enrichment adapter | `racingedge_data/providers/formfav.py` | Honest non-implementation — see boundary note below |
| Feature Availability Matrix | `src/data/dataQuality.ts` (`getFeatureAvailabilityMatrix`), shown on `/data-quality` | Built, live against whatever data currently exists (Phase 1/2 synthetic + sample) |
| Reduced feature-profile models | `racingedge_model/features/registry.py` (`FEATURE_PROFILES`), `train.py --feature-profile` | Built, tested, smoke-tested end-to-end against the current (synthetic) database |
| Dataset bias analysis | `racingedge_data/bias_analysis.py`, `cli/bias_analysis.py` (`npm run data:bias-report`) | Built, tested; runnable today against whatever's in the database |
| Behavioural observation dataset (`RACINGEDGE_BEHAVIOURAL_DATA`) | `racingedge_data/behavioural_observations.py` | Built, tested; the underlying `RunnerObservation` table is currently empty (no observations have been recorded) |
| Value-cohort backtesting | `racingedge_data/value_backtest.py`, wired into `racingedge_model/backtest.py` | Built, tested, and exercised live against the current (synthetic) test-window backtest |

### 3. The FormFav boundary

Section 5 of the Phase 3C brief is conditional: "implement a provider adapter for FormFav *if
official current documentation confirms a free API tier*." `formfav.com` returned `EGRESS_BLOCKED`
from this environment on every attempt, and — unlike The Racing API in Phase 3B, where GitHub-hosted
example scripts and an OpenAPI listing served as a genuine secondary source — no such secondary
source for FormFav's API contract was found. The condition in the brief was therefore never met, so
`FormFavProvider` is a fully-typed stub that reads `FORMFAV_API_KEY` and raises
`FormFavNotImplementedError` from every method, rather than a guessed implementation. See
`FREE_DATA_SOURCES.md` for the full writeup.

### 4. Nothing downstream of ingestion was run

Because no free dataset file was ever supplied:

- **No `DatasetReview` exists for a real free dataset** — the module is tested with synthetic
  review inputs only.
- **No new REAL `Race` rows exist beyond whatever Phase 3B produced (none)** — Phase 3C added
  zero real rows to the database. Every `Race` currently in `dev.db` remains Phase 1 seed/sample
  data or Phase 2's synthetic generator output.
- **The free Betfair SP importer has never run against a real file** — only against its own test
  fixture.
- **The dataset bias analysis, feature availability matrix, and behavioural-observation dataset
  currently describe the SAME synthetic/sample database Phase 1/2 always used** — running
  `npm run data:bias-report` or viewing `/data-quality` today shows real, honestly-computed
  figures, but they are figures *about synthetic data*, not about free real-world racing data. The
  live run captured below makes this explicit rather than leaving it implied.
- **No `CORE_FREE_MODEL`/`ENRICHED_FREE_MODEL` has been trained on real free data** — the feature
  profiles were smoke-tested with `--include-synthetic`, which is explicitly a research/testing
  invocation, not a baseline claim.
- **No free-data value-backtest numbers are reported here** — `value_backtest.py` was exercised
  live inside `backtest.py`'s own run against the current synthetic test window; that run is not a
  free-real-data result and is not reproduced in this document as if it were one.

### 5. What the built infrastructure reports today, for transparency

Run against the current (synthetic + sample) database, so the numbers below describe **that**
data, not free real-world data — reproduced here only to show the tooling works, not as a Phase 3C
deliverable result:

```
$ npm run data:bias-report
Bias analysis — 179 races, 1,868 runners
Years present: [2025, 2026]
...
2 warning(s):
  - 4 track(s) have fewer than 10 races recorded ...
  - Zero non-runners recorded across the whole dataset ...
```

Both warnings are correct and expected for the Phase 2 synthetic generator's output — they are
exactly the kind of signal this tool is meant to surface once run against a real dataset.

## Exactly what is required to produce this document for real

1. **Download a free UK/Ireland historical racing dataset manually** — see `FREE_DATA_SOURCES.md`
   for candidates (Kaggle's "UK/Ireland horse racing results" dataset or equivalent) — and note the
   licence actually stated on its source page.
2. Run:
   ```bash
   npm run data:inspect -- --file /path/to/dataset.db
   ```
   Review the generated `<name>.mapping.json`, correcting/confirming every column flagged as
   ambiguous (anything below "high" confidence).
3. Record a `DatasetReview` (`racingedge_data.dataset_review.create_dataset_review`) with the
   dataset's actual stated licence, source, and a `provenanceConfidence` that honestly reflects how
   sure you are of its reuse rights — `UNKNOWN`/`COMMUNITY_UNVERIFIED` are legitimate answers if
   that's genuinely the state of knowledge.
4. Import:
   ```bash
   npm run data:import-free -- --file /path/to/dataset.db --mapping /path/to/dataset.mapping.json \
     --source-label "Kaggle UK/IRE 1988-2026" --provenance-status <status> --source-type REAL \
     --from 1988-01-01 --to 2026-12-31
   ```
5. (Optional) Download free Betfair SP CSV files covering the same period and import via
   `racingedge_data.providers.betfair_sp.import_betfair_sp_file` for post-race market benchmarking.
6. Confirm the temporal leakage auditor reports PASSED against the new data — it runs automatically
   at the start of every `python -m racingedge_model.train` invocation.
7. Run `npm run data:bias-report` and view `/data-quality`'s Feature Availability Matrix — read the
   warnings and missing-field percentages before trusting anything downstream.
8. Train the unchanged Phase 2 models against the real import, choosing a feature profile the
   Feature Availability Matrix actually supports:
   ```bash
   npm run model:train -- --feature-profile CORE_FREE_MODEL
   ```
   (add `--feature-profile ENRICHED_FREE_MODEL` only if FormFav or another enrichment source is
   later verified and imported.)
9. Report, without optimising anything based on the results: race/runner counts, date range,
   course/class/Flat-jumps coverage (from the bias report), LightGBM/logistic Brier score, log
   loss, ROC-AUC, calibration, top-ranked strike rate, place-depth calibration, the market-baseline
   delta, and the value-cohort backtest table — then replace this document's "not produced" status
   with those genuine numbers.

## What this phase concludes about the free-data ceiling

The infrastructure to genuinely progress at £0 cost is now fully built and tested — schema-agnostic
import, provenance/licence controls, a market-benchmark importer, honest enrichment-source handling,
feature-availability reporting, reduced-feature model profiles that don't fabricate missing
sectionals/positional data, dataset bias reporting, a first-class behavioural-observation dataset,
and evaluation-only value-cohort backtesting. What free UK/Ireland racing data can genuinely
deliver — how large a `DatasetVersion` it produces, how complete its Feature Availability Matrix
is, how it compares to the market baseline — remains unanswered **until a human supplies the first
real file**, exactly the same credential/access boundary Phase 3B hit, this time for a download
rather than an API key.

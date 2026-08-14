# Model Card — RacingEdge Phase 2 Baseline

This card describes the baseline win/place probability models shipped with RacingEdge Phase 2.
Read it before interpreting any number the app shows you.

**Phase 3A update:** the model algorithms described below are unchanged — Phase 3A explicitly did
not touch them. What changed is everything *around* them: every `ModelVersion` now references an
immutable `DatasetVersion` (exact race set, source classification, data-quality snapshot at
creation time); training defaults to REAL races only (`--include-synthetic` required otherwise);
a full temporal-leakage audit runs before every training run and aborts training on FAILED; and
every training/backtest run reports a market-implied-probability baseline comparison alongside the
model's own metrics. The `ModelVersion` rows currently in this database were trained
with `--include-synthetic` (there is no real data yet) and are labelled both
`SYNTHETIC TEST MODEL — NOT FOR BETTING USE` and `RESEARCH MODEL — INSUFFICIENT HISTORICAL DATA` —
the second label reflects Phase 3A's minimum real-data gate (≥10,000 races / ≥100,000 runners),
which nothing in this database is remotely close to clearing regardless of synthetic/real status.
See [POINT_IN_TIME_ARCHITECTURE.md](./POINT_IN_TIME_ARCHITECTURE.md),
[DATA_PROVENANCE.md](./DATA_PROVENANCE.md), and [DATA_SOURCES.md](./DATA_SOURCES.md) for the full
Phase 3A design.

**Phase 3B update:** Phase 3B attempted to connect a real provider (The Racing API) and produce a
REAL `DatasetVersion` for a genuine baseline retrain. **It did not — there are no Racing API
credentials in this environment, so nothing was imported, no REAL `DatasetVersion` exists, and no
retrain happened.** Everything in this model card remains exactly what it was under Phase 2/3A:
synthetic-data numbers, unchanged. See [REAL_DATA_BASELINE.md](./REAL_DATA_BASELINE.md) for the
full, honest account of what was attempted and what's needed to actually produce a real baseline.

**Phase 3C update:** Phase 3C built a parallel, £0-cost path to real data — a schema-agnostic
dataset inspector/importer, reuse-rights provenance tracking (`ProvenanceStatus`/`DatasetReview`,
separate from the `REAL`/`SYNTHETIC`/`SAMPLE` authenticity classification above), a free Betfair SP
market-benchmark importer, reduced `CORE_FREE_MODEL`/`ENRICHED_FREE_MODEL` feature profiles, dataset
bias analysis, a behavioural-observation dataset, and value-cohort backtesting. **The model
algorithms are, again, unchanged.** No free dataset file was supplied in this environment, so — just
as with Phase 3B — nothing here was imported and every number in this card remains exactly what it
was under Phase 2/3A: synthetic-data numbers. See
[REAL_FREE_BASELINE.md](./REAL_FREE_BASELINE.md) and [FREE_DATA_SOURCES.md](./FREE_DATA_SOURCES.md)
for the full account.

## Intended use

- **Research and architecture demonstration.** These models exist to prove the feature
  engineering, training, calibration, place-probability, confidence, and backtesting pipeline
  works end-to-end and is auditable — not to generate betting advice.
- **Decision support inputs, not outputs.** Win probability, place probability, fair odds, and
  value edge are analytical inputs a human should weigh alongside everything else on the runner
  detail page (form, pace, evidence density, explanation bullets) — never a standalone signal to
  act on.
- **Explicitly NOT intended for real-money betting.** The bundled `ModelVersion` rows are trained
  substantially (in most configurations, entirely) on synthetic data — see "Training data" below —
  and are flagged `isSynthetic: true`. Every UI surface that shows a synthetic model's output
  displays a `SYNTHETIC TEST MODEL — NOT FOR BETTING USE` banner. Treat any number from this model
  as illustrative only.

## Model design

**Win probability**: two independently-trained baseline classifiers over ~166 leakage-safe
features (see README "Feature engineering"):

- Model A: L2-regularized logistic regression (`C=0.02`), fully interpretable.
- Model B: LightGBM gradient-boosted trees, conservative fixed hyperparameters.

One is designated the *primary serving model* (LightGBM by default); its raw output is calibrated
(Platt or isotonic, whichever wins on validation) then normalized within each race so
probabilities sum to ~1 (`P(win_i) = score_i / Σ score_j`). The other model's calibrated output is
kept only as an input to the "model agreement" confidence sub-score and for side-by-side
comparison on the dashboard.

**Place probability**: five independent LightGBM binary classifiers, P(finish ≤ N) for N in
{2,3,4,5,6} — never a multiplier of win probability. Each is calibrated on validation, then
rescaled within-race so predicted probabilities for a given depth sum to `min(depth, field size)`,
then monotonicity is enforced across depth (`P(top2) ≤ P(top3) ≤ ... ≤ P(top6)`) via a running
maximum. The bookmaker-specific place probability shown in the UI is whichever depth matches that
bookmaker's actual place terms (falling back to the nearest modelled depth, flagged `exact:
false`, if a bookmaker pays a depth outside 2–6).

**Model confidence** and **evidence density** are separate, transparent, rule-based 0-100 scores —
weighted sums of interpretable sub-scores, documented in full in
`python/racingedge_model/confidence.py` and `python/racingedge_model/features/evidence.py`. Neither
is derived from win probability, and win probability is never derived from them.

### Feature profiles (Phase 3C)

Free/community datasets rarely carry every field a licensed feed does — most lack sectional times,
in-running positional data, and sometimes headgear-change history. Rather than inventing values for
missing feature groups, `train.py --feature-profile` restricts training to a feature-**group**
allowlist chosen up front:

| Profile | Feature groups included | Excludes |
|---|---|---|
| `CORE_FREE_MODEL` | current form, rating, weight, class, course/distance/going, draw, trainer/jockey, age/experience, evidence density | pace (position acquisition / transition speed / late sustainability), headgear changes |
| `ENRICHED_FREE_MODEL` | everything in `CORE_FREE_MODEL` + headgear changes | pace |
| `FULL_MODEL` (default) | every registered feature group | — |

Every `ModelVersion.featureProfile` records which allowlist trained it — this is a **group-level**
restriction (`racingedge_model/features/registry.py:feature_keys_for_profile`), not a per-feature
missing-data flag; it exists so a model trained on a free dataset never silently gets fed a whole
feature group (e.g. sectional-derived pace features) that the underlying data can't actually
support, rather than each of those ~15 features individually degrading to its missing-data default.

## Training data

Two possible sources, both visible in `ModelVersion.trainingRowCount` / `isSynthetic`:

1. **Synthetic historical races** (`python -m racingedge_model.synthetic.generate_history`) — by
   default ~175 races over ~300 days, ~1,850 runner-rows. Generated by a sequential Plackett-Luce
   simulation over a **latent ability** score the model never sees directly:
   - Observable features (official rating, market price, recent form) are noisy, *lagged*
     functions of that latent ability, computed causally (a horse's rating going into race N only
     ever reflects races 1..N-1).
   - The market price itself carries independent noise on top of the latent ability, so the model
     is not artificially guaranteed to "beat" the market — the synthetic favourite win rate came
     out around 38% against a ~10-runner average field (vs. a ~9.5% uniform-random baseline),
     which is realistic market efficiency, not a rigged giveaway.
   - A small, documented pace-interaction effect exists (hold-up types get a modest boost when
     projected pace pressure is high; front-runners get a modest penalty) so the pace features
     have *some* genuine signal to find, without hand-tuning the model to find it.
   - All entities are unambiguously tagged: `Race.racecourse` prefixed `"Synthetic "`,
     `Horse.countryBred = "SYN"`, trainer/jockey names prefixed `"Synth "`.
2. **Real Phase 1 demo data** — a single 7-runner sample race (`SAMPLE Handicap Hurdle`). Far too
   small to train or meaningfully validate anything on its own; it's included in the training set
   only because it happens to be resulted data, and its presence is why `isSynthetic` would still
   read `true` for a model trained on "real + synthetic" — the flag is `true` if **any** training
   race is synthetic, which it always currently is.

**There is currently no non-trivial amount of real racing data in this system.** Anyone connecting
a licensed feed (Phase 3B, see `REAL_DATA_BASELINE.md`) or importing a free/community dataset
(Phase 3C, see `REAL_FREE_BASELINE.md`) should retrain from scratch and treat the resulting
`ModelVersion.isSynthetic: false` models as the first ones worth any real scrutiny.

**Reuse-rights filtering (Phase 3C).** Every training run also drops any race whose
`DataProvenance.provenanceStatus` is `RESTRICTED` before building the dataset (races with no
provenance row at all — all current Phase 1/2 data — are never affected). A dataset imported from a
free/community source with `UNKNOWN` or `COMMUNITY_UNVERIFIED` reuse-rights confidence is **not**
excluded from training, but is flagged with an explicit warning at import time — see
`DATA_PROVENANCE.md`.

## Evaluation

Chronological train/validation/test split by **race** (a race's runners are never split across
sets): roughly 60/20/20 by race count, sorted by date. Calibration is fit on validation only,
final numbers are reported once, on test, and reported here without cherry-picking.

Actual test-set results from the training run bundled with this repository (401 runners / 36
races; re-run `npm run model:train` to reproduce with regenerated synthetic data — exact numbers
will shift slightly with a different random seed/history):

| Metric (test split, 401 runners / 36 races) | Logistic regression | LightGBM (primary) |
|---|---|---|
| Brier score (win) | 0.0826 | 0.0803 |
| Log loss (win) | 0.3239 | 0.2977 |
| ROC-AUC (win, secondary metric) | 0.598 | 0.613 |
| Flat £1 win ROI, backing every runner at SP | — | −25.2% |

Place-model test AUC rises with depth as expected: top2 = 0.645, top3 = 0.659, top4 = 0.680,
top5 = 0.693, top6 = 0.713. 0 monotonicity violations were observed on the test split after
post-processing.

**Read those numbers honestly**: an AUC around 0.60–0.61 is *modestly* better than chance
(0.50) and shows the pipeline can extract *some* signal from the engineered features — it is not
evidence of a strong or exploitable racing model. The negative flat-stake ROI is exactly what
should be expected from an unbiased baseline backing every runner blind (bookmaker overround
alone should produce a negative ROI even for a perfectly calibrated model) and is reported here,
not hidden, per the project's explicit instruction not to manufacture impressive-looking numbers.

**Phase 3A market baseline comparison** (same test split, 401 runners): the market's own
normalized implied win probabilities (overround removed) score Brier = 0.0676, versus this
model's Brier = 0.0790 — **the market baseline beats the primary model on this test split.** This
is reported honestly, not smoothed over: it is exactly what should be expected from a baseline
features-only model trained on ~1,100 rows of substantially synthetic data going up against an
efficient market, and it is the correct way to read "does RacingEdge add information beyond the
market" — right now, on this data, the answer is no. Re-run `npm run model:train` to reproduce
(the market-baseline line is printed during training and stored in
`ModelVersion.metricsJson.market_baseline_comparison`).

Live, always-current versions of every metric above (plus calibration curves and breakdowns by
class/course/going/distance/age/confidence/evidence band) are on the `/dashboard` page, recomputed
directly from stored `PredictionSnapshot` + `ResultEntry` rows — never cached or hand-edited.

## Known limitations

- **Synthetic training data dominates.** See "Training data" above. This is the single most
  important limitation — nothing else on this list matters until real data replaces it.
- **Below the Phase 3A minimum real-data gate.** Every `DatasetVersion` built from this database is
  labelled `RESEARCH MODEL — INSUFFICIENT HISTORICAL DATA` (< 10,000 races / 100,000 runners,
  configurable in `racingedge_data.dataset_version`) — a threshold this synthetic dataset doesn't
  clear either, and wouldn't even if it were entirely real.
- **Small dataset.** ~1,100 training rows against ~166 features is a thin ratio; this is exactly
  why logistic regression needed heavy regularization and why LightGBM's conservative
  hyperparameters (shallow trees, row/column subsampling, L1/L2 penalties) matter more than usual.
- **No hyperparameter search.** Both models use fixed, documented, conservative defaults chosen by
  standard practice and a single validation-set check (for logistic regression's `C`), not a
  search. Phase 3 should add proper cross-validated tuning — still validation-only, never test.
- **Pace/race-shape features are historically-derived, not simulated pre-race.** A horse's own
  transition-speed/late-sustainability numbers come from its past `FormEntry` rows; "race-shape"
  features (expected leaders, pace pressure) come from today's field's `RunnerPaceProfile.
  projectedRole` values, which in a real deployment would themselves need to be produced by some
  upstream process — this pipeline consumes them, it doesn't generate them.
- **Surface (turf/all-weather) history is approximated.** `FormEntry` doesn't capture true
  surface, only flat/jumps type, so "surface record" features are really "race-type record".
  Documented in the feature registry (`features/registry.py`).
- **No SHAP / causal analysis.** Feature importance shown on the dashboard is standardized logistic
  coefficients or LightGBM split-count importance — **association, not causal effect** — and is
  labelled as such everywhere it's displayed.
- **Confidence and evidence-density weights are hand-set, not fitted.** This is explicitly
  sanctioned by the project brief for these two scores specifically (unlike win/place probability,
  which must never use hand-set weights) — but they are still a simplification, documented in full
  in their source modules, and could be replaced by a learned confidence calibration in a later
  phase.
- **Draw bias, trainer/jockey stats, and course/distance/going records all use additive smoothing**
  towards a population prior rather than raw rates, specifically to stop tiny samples from
  dominating — but the smoothing constants themselves (`config.py`) are chosen by judgement, not
  fitted.

## Known biases

- The synthetic data generator's market-efficiency parameters (overround ≈ 12%, market noise
  variance) were chosen to look "reasonably realistic", not calibrated against real market data —
  any ROI/edge figure computed against synthetic starting prices reflects the simulation's
  assumptions, not real bookmaker behaviour.
- Class/rating bands used to keep synthetic race fields plausible are UK/IRE-handicapping-style
  approximations and may not generalize to jurisdictions with different rating scales.
- Trainer/jockey identity in the synthetic data has **no simulated skill effect** — any apparent
  trainer/jockey strike-rate variation in the synthetic dataset is sampling noise, not a genuine
  trainer-skill signal, and the model should not be expected to find real trainer/jockey signal
  from this data (this was a deliberate choice: the generator does not fabricate a fake "trainer
  skill" signal just to make that feature group look powerful).

## Warnings against interpreting probability as certainty

- A win probability of, say, 15% means the model expects this outcome roughly 1 time in 7 **if the
  model is well-calibrated** — it is not a guarantee, and the calibration dashboard is exactly the
  tool for checking whether "15%" predictions actually happen ~15% of the time in aggregate.
- **Model confidence is not win probability.** A horse can have low win probability and high
  confidence (a well-exposed, moderately-rated handicapper the model is quite sure won't win) or
  high win probability and low confidence (a lightly-raced favourite with almost no form to judge
  it on) — both are valid, expected combinations.
- **Evidence density is not win probability either.** High evidence density means the estimate is
  well-supported by data, not that the horse is likely to win.
- A positive value edge is a statement about *this model's* probability versus the market's
  implied probability — it is not a statement that the model is right and the market is wrong.
  Markets are frequently more accurate than a features-only baseline model, especially one trained
  on ~1,100 rows of substantially synthetic data.
- **No staking logic exists anywhere in this codebase**, by design. Nothing here should be read as
  a recommendation to place a bet of any size.

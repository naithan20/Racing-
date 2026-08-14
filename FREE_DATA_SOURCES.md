# Free Data Sources — Phase 3C

Phase 3C's hard constraint is **£0 data cost**: no paid API, no paid dataset, no paid subscription,
no scraping, no bypassing website protections, and no data whose reuse rights are clearly
incompatible with this project. This document is the discovery record — every free/community
source considered, what's actually known about it (not assumed), and a verdict of
**RECOMMENDED** / **USE WITH CAUTION** / **REJECTED**.

Nothing in this table is downloaded automatically. A **RECOMMENDED** or **USE WITH CAUTION**
verdict means "worth a human fetching this and running it through the inspector/importer", never
"already imported" — see `REAL_FREE_BASELINE.md` for what has actually happened with real data
(as of this document: nothing has been imported yet).

## Verdicts at a glance

| Source | Format | Verdict |
|---|---|---|
| Betfair Historical SP data (free CSVs) | CSV / gzip / ZIP | **RECOMMENDED** |
| Kaggle "UK/Ireland horse racing results" datasets | SQLite / CSV | **RECOMMENDED — pending user download + `DatasetReview`** |
| FormFav API | JSON over HTTP | **USE WITH CAUTION** |
| Racing Post / Sporting Life / Timeform / At The Races (any scraping route) | — | **REJECTED** |

---

## Betfair Historical SP data (free tier) — RECOMMENDED

- **URL**: `https://promo.betfair.com/betfairsp/prices` (the well-known free Betfair Starting Price
  CSV download area — not the paid Betfair Historical Data product at
  `historicdata.betfair.com`, which is a separate, paid service covered instead in
  `DATA_SOURCES.md` under `betfair_historical.py`).
- **Format**: plain CSV, optionally gzip/ZIP-compressed. Stable, long-published, widely used format
  — the same 17-column schema (`EVENT_ID, MENU_HINT, EVENT_NAME, EVENT_DT, SELECTION_ID,
  SELECTION_NAME, WIN_LOSE, BSP, PPWAP, MORNINGWAP, PPMAX, PPMIN, IPMAX, IPMIN,
  MORNINGTRADEDVOL, PPTRADEDVOL, IPTRADEDVOL`) referenced independently by third-party tooling
  (e.g. the `betfairlightweight`/community ecosystem), which is why this build has reasonable
  confidence in the column layout without having fetched a live file — `promo.betfair.com` itself
  returned `EGRESS_BLOCKED` from this environment, so the exact current page layout and file-naming
  convention were **not** directly verified here.
- **Date coverage**: historically back to the mid-2000s for major UK/Ireland meetings (not verified
  from this environment — confirm on first real download).
- **Expected fields**: event identity, off-time, selection (horse) name, win/lose flag, Betfair
  Starting Price (BSP), and several pre-off weighted-average-price/volume fields. **No going, no
  official rating, no draw, no jockey/trainer, no finishing position or distance beaten** — this is
  a pure market/price file, not a form file. It only supplies the CLOSING/SP MARKET BENCHMARK layer
  (see `POINT_IN_TIME_ARCHITECTURE.md` and section below) on top of a results dataset imported from
  elsewhere.
- **Licence / provenance status**: Betfair publishes this data for public download without a paid
  tier; it does not, in this build's own testing, come with an explicit machine-readable licence
  file at the point of download. Treat as **PUBLIC_RESEARCH** by default, and record it as such
  explicitly via `DatasetReview` — do not assume commercial-use permission.
- **Recommended use**: post-race market benchmarking only (ROI backtesting, value-cohort analysis,
  closing-price comparison) via `racingedge_data.providers.betfair_sp.import_betfair_sp_file`. It
  must never be treated as a pre-race feature — see the CLOSING/SP MARKET BENCHMARK note below.
- **Known limitations**: `EVENT_NAME` bundles course + race type + time as free text rather than
  clean fields, so this build's importer matches on (exact normalized horse name + exact race date)
  only — not course — and reports same-day multi-course name collisions as unresolved rather than
  guessing (see `racingedge_data/providers/betfair_sp.py`). Selection names occasionally differ in
  punctuation/country-suffix from a results feed's horse names; those also land in the unresolved
  queue, never a fuzzy match.

**CLOSING/SP MARKET BENCHMARK — read before using this data for anything.** BSP/SP is a
*post-race* settlement price, not a snapshot of pre-race live odds hours before the off. Per Phase
3C section 7, this data must never be fed into a model as if it were available at prediction time
for the SAME race — it belongs strictly to post-hoc benchmarking (fair-odds comparison, ROI
analysis) via `racingedge_data.value_backtest`, never to a pre-race `PredictionSnapshot`'s inputs.

---

## Kaggle "UK/Ireland horse racing results 1988–2026" (and similar community datasets) — RECOMMENDED, pending user download + `DatasetReview`

- **URL**: `kaggle.com` — the specific dataset was not directly inspected from this environment;
  `www.kaggle.com` returned `EGRESS_BLOCKED` on every attempt. This entry is therefore a *candidate
  category*, not a verified specific dataset — see "First target dataset" in `REAL_FREE_BASELINE.md`
  for the exact boundary this hit.
- **Format**: per Kaggle's usual conventions for this class of dataset, likely SQLite (`.db`) or CSV
  — not confirmed. `racingedge_data.inspector.inspect_file` is deliberately schema-agnostic and
  handles either.
- **Date coverage**: claimed 1988–2026 in the dataset title as referenced in the Phase 3C brief;
  **not independently verified** from this environment.
- **Expected fields**: race/runner/result-level UK & Ireland racing data — likely finishing
  position, SP, going, class, distance, jockey/trainer, official rating, draw. Community Kaggle
  racing datasets typically do **not** include Racing Post Rating, Timeform rating, sectionals, or
  positional/in-running data — treat these as absent until the inspector's Feature Availability
  Matrix says otherwise for the specific file supplied.
- **Licence / provenance status**: Kaggle datasets carry a licence chosen by the uploader (commonly
  CC0, CC-BY, or a custom "for non-commercial/educational use" statement) — this varies per dataset
  and was not checked here. **A `DatasetReview` record is mandatory before import** — see
  `racingedge_data.dataset_review` — with the licence actually stated on the dataset's Kaggle page
  entered verbatim, not assumed. Default `provenanceConfidence` for an uninspected Kaggle dataset is
  `UNKNOWN`, which produces an import-time warning (never silently upgraded to a stronger status).
- **Recommended use**: primary historical dataset for `CORE_FREE_MODEL`/`ENRICHED_FREE_MODEL`
  training, once a `DatasetReview` records what its actual licence permits.
- **Known limitations**: unverified schema and unverified licence, per above — both must be resolved
  by a human (inspector run + explicit review) before training on it, per this project's explicit
  human-in-the-loop requirement.
- **Phase 3D update**: the official `kaggle` Python package (not the website) was installed and
  actually run in this environment — `racingedge_data.providers.kaggle_adapter` is built against
  genuine, verified behaviour of the package, not guessed. Two real findings: (1) `kaggle==1.6.17`
  authenticates via a `kaggle.json` file (`KAGGLE_CONFIG_DIR` or `~/.config/kaggle`/`~/.kaggle`) or
  `KAGGLE_USERNAME`/`KAGGLE_KEY` env vars, and behaves predictably under non-interactive stdio,
  raising a clean `OSError` when unconfigured; (2) the newer `kaggle` 2.x package's OAuth-first
  `kaggle auth login` flow crashes on import specifically under non-interactive/piped stdio — the
  exact condition a Next.js-spawned subprocess always runs under — so `1.6.17` is pinned
  deliberately in `python/requirements.txt`, not by default/inertia. No real Kaggle account or
  dataset was reachable from this sandbox (kaggle.com itself is still network-blocked here), so the
  actual download call (`dataset_download_files`) remains tested only against a mocked client.

Connecting Kaggle no longer requires editing a config file by hand: **Settings → Data Connections
→ Kaggle** in the RacingEdge UI writes the credentials server-side
(`.data-connections/kaggle.json`, gitignored, mode 600) and never displays them back — see the
README's "Phase 3D" section.

This repository does **not** download Kaggle datasets automatically, even though direct download
via the Kaggle API/website is often permitted for public datasets — per Phase 3C section 23's
explicit instruction, automated download is only appropriate when it's unambiguous that doing so is
permitted, and this build could not even reach `kaggle.com` to check the specific dataset's terms.
The correct, and only supported, path is: download the file manually, then run
`npm run data:inspect -- --file <path>`.

---

## FormFav API — USE WITH CAUTION

- **URL**: `formfav.com` (its documented API, if one exists). `formfav.com` returned
  `EGRESS_BLOCKED` from this environment on every attempt, and no secondary source (GitHub example
  scripts, OpenAPI listing, etc. — the fallback that worked for The Racing API in Phase 3B) was
  found for FormFav specifically.
- **Format**: presumed JSON over HTTPS, if a free tier exists — **not confirmed**.
- **Date coverage / expected fields**: not confirmed. Phase 3C's brief anticipates form/career/
  jockey/trainer/course statistics as enrichment, but this build has **no verified evidence** that
  FormFav publishes UK/Ireland official race results, so it must never be assumed to supply
  anything beyond enrichment-layer stats.
- **Licence / provenance status**: unknown — no documentation was reachable to check.
- **Recommended use**: none, currently. `racingedge_data.providers.formfav.FormFavProvider` exists
  as a fully-typed, tested stub (reads `FORMFAV_API_KEY`, raises a clear
  `FormFavNotImplementedError` from every fetch method) so the adapter shape is ready, but every
  method is intentionally unimplemented. See `DATA_SOURCES.md`/`REAL_FREE_BASELINE.md` for the
  credential/documentation boundary this hit.
- **Known limitations**: the entire adapter is unverified against real documentation. A maintainer
  who can actually reach `formfav.com`'s docs (or has a `FORMFAV_API_KEY` and can read example
  responses) must confirm the free-tier terms and real field/endpoint names before any code is
  written against it — this build will not guess a REST contract from a marketing page.

---

## Racing Post / Sporting Life / Timeform / At The Races (any scraping route) — REJECTED

Explicitly and permanently rejected by Phase 3C's own instruction, regardless of what any
third-party GitHub repository claims to offer:

> Under no circumstances implement automated scraping of: Racing Post, Sporting Life, Timeform, At
> The Races, bookmaker websites, other commercial racing sites. Even if public GitHub repositories
> contain scrapers for these sources, do not use or copy those scraping components.

No adapter, importer, or fixture in this repository touches any of these sites. If a maintainer has
a **licensed, credentialed API relationship** with any of them (e.g. an official Timeform data
licence), that is a *paid* data source and belongs in `DATA_SOURCES.md` (Phase 3A/3B), not here —
Phase 3C is strictly £0.

---

## Sources considered but not pursued further

No other free/public UK & Ireland historical racing dataset or API was identified with enough
information (from a reachable source) to write a confident entry above. `WebSearch` (a different
backend from `WebFetch` in this environment) surfaced general awareness of the free-data landscape
described above, but did not substitute for actually reaching a site's documentation or terms page
— nothing is listed here as RECOMMENDED on the strength of a search snippet alone.

## Summary for a maintainer

To make real progress on Phase 3C at £0 cost:

1. **Download** a UK/Ireland historical racing dataset from Kaggle (or an equivalent community
   source) manually, and provide the local file path.
2. Run `npm run data:inspect -- --file <path>` to get a schema profile + proposed mapping.
3. Fill in a `DatasetReview` (licence, source, confidence) based on what the dataset's actual page
   states — see `racingedge_data.dataset_review`.
4. Review/confirm the mapping, then `npm run data:import-free -- --file <path> --mapping <path> ...`.
5. Optionally, separately download free Betfair SP CSV files for post-race market benchmarking via
   `racingedge_data.providers.betfair_sp.import_betfair_sp_file`.

See `REAL_FREE_BASELINE.md` for exactly where this stands right now (as of this document: no file
has been supplied, so no real free data has been imported).

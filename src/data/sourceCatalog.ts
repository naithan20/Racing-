/**
 * The single, centralized list of data sources RacingEdge knows how to
 * connect to. Nothing about a specific source (name, coverage, licence
 * status, which Python adapter handles it) is hard-coded anywhere else in
 * the app — every page that lists, filters, or imports a source reads from
 * `SOURCE_CATALOG` below. This mirrors the Python side's own registry
 * pattern (`racingedge_model/features/registry.py`): one file documents
 * every entry's real properties, so nothing drifts out of sync with what's
 * actually implemented.
 *
 * £0 rule (Phase 3C/3D): every entry in this catalog is a FREE source.
 * Paid-provider adapters (Racing API, purchased Betfair Historical Data —
 * see DATA_SOURCES.md) keep their own Python adapters but are deliberately
 * NOT listed here, so the consumer-facing "Add Free Racing Data" flow can
 * never surface a paid source as a default option.
 */

export type DataCategory =
  | "HISTORICAL_RESULTS"
  | "RACECARDS_FORM"
  | "MARKET_SP"
  | "SECTIONALS"
  | "WEATHER";

export type DownloadMechanism =
  | "DIRECT_DOWNLOAD"
  | "PUBLIC_API"
  | "KAGGLE"
  | "GITHUB_RELEASE"
  | "USER_URL"
  | "LOCAL_FILE";

export type AuthMechanism = "none" | "kaggle" | "api_key";

/**
 * Distinct from `ProvenanceStatus` (per-record reuse-rights, tracked in the
 * database once data is actually imported — see DATA_PROVENANCE.md). This
 * is a catalog-level, pre-import claim about whether RacingEdge's own
 * adapter for this source has actually been exercised against it.
 *
 *   VERIFIED               — this build has run the adapter against real
 *                             data/responses from this source (fixtures
 *                             derived from a genuine sample, or a real run).
 *   AVAILABLE_BUT_UNVERIFIED — the format is well-documented/stable and an
 *                             adapter exists and is tested against a
 *                             hand-built fixture, but no live response from
 *                             the real source has been inspected (usually
 *                             because this environment's network egress
 *                             policy blocked it — see FREE_DATA_SOURCES.md).
 *   REQUIRES_CONNECTION     — the adapter is real, but nothing can happen
 *                             until the user connects (e.g. Kaggle auth).
 *   UNAVAILABLE             — this build could not confirm the source even
 *                             has a usable free API/contract; the adapter is
 *                             an honest stub, not a guessed implementation.
 */
export type VerificationStatus =
  | "VERIFIED"
  | "AVAILABLE_BUT_UNVERIFIED"
  | "REQUIRES_CONNECTION"
  | "UNAVAILABLE";

export interface SourceCatalogEntry {
  id: string;
  name: string;
  description: string;
  homepage: string;
  category: DataCategory;

  /** Geographic coverage, e.g. ["UK", "Ireland"]. */
  regions: string[];
  /** Human-readable historical coverage claim, e.g. "1988–present". Marked (unverified) when this build could not confirm it directly. */
  historicalCoverage: string;
  /** Racing codes covered. */
  codes: Array<"FLAT" | "JUMPS">;

  downloadMechanism: DownloadMechanism;
  authMechanism: AuthMechanism;
  /** Fields this source is expected to supply, for the cards' "Expected fields" line — not a schema contract, just a summary for the user. */
  expectedFields: string[];

  /** Always "FREE" in this catalog — see the £0 rule above. */
  cost: "FREE";
  verificationStatus: VerificationStatus;

  /** Identifier of the Python adapter module that implements this source, for developer/CLI reference. Not used by the UI directly. */
  adapter: string;

  /** Whether this source is offered to users at all. A disabled entry can still be referenced by an existing ImportJob's history. */
  enabled: boolean;

  /** Free-text note surfaced on the card — caveats, terms-acceptance requirements, etc. */
  note?: string;

  /** For KAGGLE sources: the owner/slug identifying the specific dataset once one is confirmed — left undefined when only a category of dataset is known, not a specific verified one. */
  kaggleDatasetRef?: string;
}

export const SOURCE_CATALOG: SourceCatalogEntry[] = [
  {
    id: "kaggle-uk-ire-historical",
    name: "UK & Ireland Historical Racing (Kaggle)",
    description:
      "Community-published historical UK & Ireland race results dataset on Kaggle — the primary candidate for RacingEdge's free historical training data.",
    homepage: "https://www.kaggle.com/",
    category: "HISTORICAL_RESULTS",
    regions: ["UK", "Ireland"],
    historicalCoverage: "1988–present (unverified — confirm on the dataset's own Kaggle page)",
    codes: ["FLAT", "JUMPS"],
    downloadMechanism: "KAGGLE",
    authMechanism: "kaggle",
    expectedFields: [
      "Race date",
      "Course",
      "Horse name",
      "Finishing position",
      "Starting price",
      "Going",
      "Official rating",
      "Jockey",
      "Trainer",
    ],
    cost: "FREE",
    verificationStatus: "REQUIRES_CONNECTION",
    adapter: "racingedge_data.providers.kaggle_adapter",
    enabled: true,
    note: "Requires a Kaggle account connection. Licence varies by uploader — RacingEdge records a DatasetReview before import and never assumes redistribution/commercial rights.",
  },
  {
    id: "betfair-sp-free-csv",
    name: "Betfair Starting Price (free historical CSVs)",
    description:
      "Betfair's free downloadable Starting Price CSV files — post-race market benchmark data (BSP/SP), used for value-cohort backtesting, never as a pre-race feature.",
    homepage: "https://promo.betfair.com/betfairsp/prices",
    category: "MARKET_SP",
    regions: ["UK", "Ireland"],
    historicalCoverage: "Mid-2000s–present (unverified from this environment — confirm at download time)",
    codes: ["FLAT", "JUMPS"],
    downloadMechanism: "USER_URL",
    authMechanism: "none",
    expectedFields: ["Event date/time", "Course/event name", "Selection (horse) name", "BSP", "Win/lose"],
    cost: "FREE",
    verificationStatus: "AVAILABLE_BUT_UNVERIFIED",
    adapter: "racingedge_data.providers.betfair_sp",
    enabled: true,
    note: "This build could not reach promo.betfair.com to confirm the current page layout or a stable direct-download URL — paste the CSV link from the Betfair page yourself via \"Add data source from URL\". CLOSING/SP MARKET BENCHMARK only; see MODEL_CARD.md.",
  },
  {
    id: "formfav-api",
    name: "FormFav",
    description: "Free-tier racing statistics API (form/career/jockey/trainer/course stats), as an enrichment source.",
    homepage: "https://formfav.com/",
    category: "RACECARDS_FORM",
    regions: ["UK", "Ireland"],
    historicalCoverage: "Unknown",
    codes: ["FLAT", "JUMPS"],
    downloadMechanism: "PUBLIC_API",
    authMechanism: "api_key",
    expectedFields: ["Form statistics", "Career statistics", "Jockey/trainer/course statistics"],
    cost: "FREE",
    verificationStatus: "UNAVAILABLE",
    adapter: "racingedge_data.providers.formfav",
    enabled: false,
    note: "formfav.com's documentation could not be reached to confirm a free API tier or real field names. The adapter is an honest stub — connecting/importing is disabled until this is verified. See FREE_DATA_SOURCES.md.",
  },
  {
    id: "user-url",
    name: "Add data source from URL",
    description: "Paste a direct link to a CSV, JSON, JSONL, SQLite, ZIP, or GZIP file of racing data you've found yourself.",
    homepage: "",
    category: "HISTORICAL_RESULTS",
    regions: ["UK", "Ireland", "Other"],
    historicalCoverage: "Depends on the source you provide",
    codes: ["FLAT", "JUMPS"],
    downloadMechanism: "USER_URL",
    authMechanism: "none",
    expectedFields: [],
    cost: "FREE",
    verificationStatus: "AVAILABLE_BUT_UNVERIFIED",
    adapter: "racingedge_data.providers.download_adapter",
    enabled: true,
    note: "You are responsible for confirming this source's reuse rights — RacingEdge records a DatasetReview and never assumes permission.",
  },
  {
    id: "local-file",
    name: "Local file (advanced)",
    description: "Import from a file already on disk — the original Phase 3C workflow. Kept as an advanced fallback for developers and large/manual imports.",
    homepage: "",
    category: "HISTORICAL_RESULTS",
    regions: ["UK", "Ireland", "Other"],
    historicalCoverage: "Depends on the file you provide",
    codes: ["FLAT", "JUMPS"],
    downloadMechanism: "LOCAL_FILE",
    authMechanism: "none",
    expectedFields: [],
    cost: "FREE",
    verificationStatus: "VERIFIED",
    adapter: "racingedge_data.importers.free_dataset_importer",
    enabled: true,
    note: "Requires a filesystem path on the server running RacingEdge — the same npm run data:inspect / data:import-free workflow, now also reachable from this UI.",
  },
];

export function getSourceCatalogEntry(id: string): SourceCatalogEntry | undefined {
  return SOURCE_CATALOG.find((entry) => entry.id === id);
}

export function listEnabledSources(): SourceCatalogEntry[] {
  return SOURCE_CATALOG.filter((entry) => entry.enabled);
}

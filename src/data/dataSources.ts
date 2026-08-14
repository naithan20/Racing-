/**
 * Read-only queries backing the /data-sources consumer UX (Phase 3D).
 * Combines the static `SOURCE_CATALOG` (src/data/sourceCatalog.ts) with
 * live per-source connection/import state from the database — nothing
 * here is cached, matching every other data-layer read query in this
 * project.
 */
import "server-only";

import fs from "node:fs";
import path from "node:path";

import { prisma } from "@/database/client";
import type { ImportJobStatus } from "@/generated/prisma/enums";
import {
  getSourceCatalogEntry,
  listEnabledSources,
  type SourceCatalogEntry,
} from "@/data/sourceCatalog";

export type EffectiveConnectionStatus = "NOT_REQUIRED" | "NOT_CONNECTED" | "CONNECTED" | "ERROR";

export interface DataSourceCard {
  source: SourceCatalogEntry;
  connectionStatus: EffectiveConnectionStatus;
  connectionErrorMessage: string | null;
  lastSyncAt: Date | null;
  racesImported: number | null;
  runnersImported: number | null;
  datasetVersionId: string | null;
  /** The most recent job for this source that hasn't reached a terminal state — present means an import is in progress or needs mapping review. */
  activeJobId: string | null;
  activeJobStatus: string | null;
}

const KAGGLE_PSEUDO_SOURCE_ID = "kaggle";
const TERMINAL_STATUSES: ImportJobStatus[] = ["COMPLETED", "FAILED"];

async function getKaggleConnection() {
  return prisma.dataSourceConnection.findUnique({ where: { sourceId: KAGGLE_PSEUDO_SOURCE_ID } });
}

export async function getKaggleConnectionStatus(): Promise<{
  connected: boolean;
  connectedAt: Date | null;
  errorMessage: string | null;
}> {
  const connection = await getKaggleConnection();
  return {
    connected: connection?.status === "CONNECTED",
    connectedAt: connection?.connectedAt ?? null,
    errorMessage: connection?.errorMessage ?? null,
  };
}

async function effectiveConnectionStatus(source: SourceCatalogEntry): Promise<{
  status: EffectiveConnectionStatus;
  errorMessage: string | null;
}> {
  if (source.authMechanism === "none") {
    return { status: "NOT_REQUIRED", errorMessage: null };
  }
  if (source.authMechanism === "kaggle") {
    const kaggle = await getKaggleConnection();
    if (!kaggle) return { status: "NOT_CONNECTED", errorMessage: null };
    return { status: kaggle.status as EffectiveConnectionStatus, errorMessage: kaggle.errorMessage };
  }
  // authMechanism === "api_key" (e.g. FormFav) — no connect UI wired up
  // yet since the source itself is UNAVAILABLE; treat as not connected.
  return { status: "NOT_CONNECTED", errorMessage: null };
}

export async function getDataSourceCards(): Promise<DataSourceCard[]> {
  const sources = listEnabledSources();
  const cards: DataSourceCard[] = [];

  for (const source of sources) {
    const { status, errorMessage } = await effectiveConnectionStatus(source);

    const [latestCompleted, activeJob] = await Promise.all([
      prisma.importJob.findFirst({
        where: { sourceId: source.id, status: "COMPLETED" },
        orderBy: { completedAt: "desc" },
      }),
      prisma.importJob.findFirst({
        where: { sourceId: source.id, status: { notIn: TERMINAL_STATUSES } },
        orderBy: { startedAt: "desc" },
      }),
    ]);

    cards.push({
      source,
      connectionStatus: status,
      connectionErrorMessage: errorMessage,
      lastSyncAt: latestCompleted?.completedAt ?? null,
      racesImported: latestCompleted?.racesImported ?? null,
      runnersImported: latestCompleted?.runnersImported ?? null,
      datasetVersionId: latestCompleted?.datasetVersionId ?? null,
      activeJobId: activeJob?.id ?? null,
      activeJobStatus: activeJob?.status ?? null,
    });
  }

  return cards;
}

export async function getDataSourceCard(sourceId: string): Promise<DataSourceCard | null> {
  const source = getSourceCatalogEntry(sourceId);
  if (!source || !source.enabled) return null;
  const cards = await getDataSourceCards();
  return cards.find((c) => c.source.id === sourceId) ?? null;
}

export async function getImportJobById(jobId: string) {
  return prisma.importJob.findUnique({ where: { id: jobId } });
}

export interface ImportJobCompletionSummary {
  coverageStart: Date | null;
  coverageEnd: Date | null;
  /** A simple, transparent completeness score — 100 minus the average of
   * the DatasetVersion's own frozen missing-OR/draw/SP percentages (see
   * racingedge_data.dataset_version.build_data_quality_snapshot). Labelled
   * "completeness" rather than "quality" deliberately: it says nothing
   * about correctness, only about how much of a few key fields is present. */
  completenessScore: number | null;
  leakageAuditStatus: "PASSED" | "FAILED" | null;
}

export async function getImportJobCompletionSummary(jobId: string): Promise<ImportJobCompletionSummary | null> {
  const job = await prisma.importJob.findUnique({ where: { id: jobId } });
  if (!job || !job.datasetVersionId) return null;

  const [datasetVersion, latestAudit] = await Promise.all([
    prisma.datasetVersion.findUnique({ where: { id: job.datasetVersionId } }),
    prisma.leakageAuditRun.findFirst({
      where: { datasetVersionId: job.datasetVersionId },
      orderBy: { createdAt: "desc" },
    }),
  ]);
  if (!datasetVersion) return null;

  let completenessScore: number | null = null;
  if (datasetVersion.dataQualityMetricsJson) {
    const metrics = JSON.parse(datasetVersion.dataQualityMetricsJson) as Record<string, number | null>;
    const missingPcts = [metrics.missing_official_rating_pct, metrics.missing_draw_pct, metrics.missing_starting_price_pct].filter(
      (v): v is number => typeof v === "number"
    );
    if (missingPcts.length > 0) {
      const avgMissing = missingPcts.reduce((a, b) => a + b, 0) / missingPcts.length;
      completenessScore = Math.round((100 - avgMissing) * 10) / 10;
    }
  }

  return {
    coverageStart: datasetVersion.dateRangeStart,
    coverageEnd: datasetVersion.dateRangeEnd,
    completenessScore,
    leakageAuditStatus: (latestAudit?.status as "PASSED" | "FAILED" | undefined) ?? null,
  };
}

export async function hasAnyRealData(): Promise<boolean> {
  const race = await prisma.race.findFirst({ where: { sourceType: "REAL" }, select: { id: true } });
  return race !== null;
}

// ---------------------------------------------------------------------------
// Mapping review — reads the inspector's raw output straight off disk (the
// same files racingedge_data.import_pipeline wrote); there is no database
// table for this, it's ephemeral per-job working state.
// ---------------------------------------------------------------------------

export interface MappingReviewColumn {
  table: string;
  column: string;
  proposedRole: string | null;
  confidence: "high" | "medium" | "low" | "unmapped";
  confirmed: boolean;
  sampleValues: string[];
}

export interface MappingReviewData {
  sourcePath: string;
  columnsNeedingReview: MappingReviewColumn[];
  autoMappedCount: number;
}

const CANONICAL_ROLES = [
  "race_date", "race_time", "course", "country", "race_name", "race_type", "race_class",
  "distance", "going", "flat_jumps", "field_size", "horse_name", "horse_id", "draw", "weight",
  "age", "sex", "official_rating", "jockey", "trainer", "sire", "dam", "damsire", "headgear",
  "finishing_position", "beaten_distance", "starting_price", "bsp", "comment", "sectional",
  "non_runner",
] as const;

export function listCanonicalRoles(): readonly string[] {
  return CANONICAL_ROLES;
}

function jobStorageDir(jobId: string): string {
  return path.join(process.cwd(), "python", "storage", "import_jobs", jobId);
}

export async function getMappingReviewData(jobId: string): Promise<MappingReviewData | null> {
  const dir = jobStorageDir(jobId);
  const mappingPath = path.join(dir, "mapping.json");
  const inspectionPath = path.join(dir, "inspection.json");
  if (!fs.existsSync(mappingPath) || !fs.existsSync(inspectionPath)) return null;

  const mapping = JSON.parse(fs.readFileSync(mappingPath, "utf-8"));
  const inspection = JSON.parse(fs.readFileSync(inspectionPath, "utf-8"));

  const sampleValuesByTableColumn = new Map<string, string[]>();
  for (const table of inspection.tables ?? []) {
    for (const column of table.columns ?? []) {
      sampleValuesByTableColumn.set(`${table.name}.${column.name}`, column.sample_values ?? []);
    }
  }

  const columnsNeedingReview: MappingReviewColumn[] = [];
  let autoMappedCount = 0;

  for (const [tableName, tableData] of Object.entries<{ columns?: Record<string, { role: string | null; confidence: string; confirmed: boolean }> }>(
    mapping.tables ?? {}
  )) {
    for (const [columnName, columnData] of Object.entries(tableData.columns ?? {})) {
      if (columnData.confidence === "high" && columnData.confirmed) {
        autoMappedCount += 1;
        continue;
      }
      columnsNeedingReview.push({
        table: tableName,
        column: columnName,
        proposedRole: columnData.role,
        confidence: columnData.confidence as MappingReviewColumn["confidence"],
        confirmed: columnData.confirmed,
        sampleValues: sampleValuesByTableColumn.get(`${tableName}.${columnName}`) ?? [],
      });
    }
  }

  return { sourcePath: mapping.source_path, columnsNeedingReview, autoMappedCount };
}

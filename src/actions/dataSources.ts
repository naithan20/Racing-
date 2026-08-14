"use server";

/**
 * Mutations behind the /data-sources consumer UX (Phase 3D): connecting a
 * source (currently just Kaggle), starting/resuming an import job, and
 * confirming a mapping review. Every credential lives server-side only —
 * see `connectKaggleAction` — and every actual pipeline step runs in the
 * Python `racingedge_data` package (spawned via src/lib/pythonRunner.ts),
 * never reimplemented here.
 */

import fs from "node:fs";
import path from "node:path";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { prisma } from "@/database/client";
import { getSourceCatalogEntry } from "@/data/sourceCatalog";
import { getKaggleConnectionStatus } from "@/data/dataSources";
import { runImportJobCliDetached, runImportJobCliSync } from "@/lib/pythonRunner";
import { classifyUrl } from "@/lib/urlPreview";
import type { DataConnectionActionState, ImportJobFormState } from "@/actions/state";

const DATA_CONNECTIONS_DIR = path.join(process.cwd(), ".data-connections");
const KAGGLE_CREDENTIALS_FILE = path.join(DATA_CONNECTIONS_DIR, "kaggle.json");
const KAGGLE_PSEUDO_SOURCE_ID = "kaggle";

function kaggleEnvFor(source: { authMechanism: string }): Record<string, string> {
  if (source.authMechanism !== "kaggle") return {};
  return { KAGGLE_CONFIG_DIR: DATA_CONNECTIONS_DIR };
}

// ---------------------------------------------------------------------------
// Settings -> Data Connections -> Kaggle
// ---------------------------------------------------------------------------

export async function connectKaggleAction(
  _prevState: DataConnectionActionState,
  formData: FormData
): Promise<DataConnectionActionState> {
  const username = String(formData.get("username") ?? "").trim();
  const apiKey = String(formData.get("apiKey") ?? "").trim();

  if (!username || !apiKey) {
    return { status: "error", message: "Username and API key are both required." };
  }

  fs.mkdirSync(DATA_CONNECTIONS_DIR, { recursive: true, mode: 0o700 });
  fs.writeFileSync(KAGGLE_CREDENTIALS_FILE, JSON.stringify({ username, key: apiKey }), { mode: 0o600 });

  await prisma.dataSourceConnection.upsert({
    where: { sourceId: KAGGLE_PSEUDO_SOURCE_ID },
    update: { status: "CONNECTED", connectedAt: new Date(), errorMessage: null },
    create: { sourceId: KAGGLE_PSEUDO_SOURCE_ID, status: "CONNECTED", connectedAt: new Date() },
  });

  revalidatePath("/settings/data-connections");
  revalidatePath("/data-sources");
  return { status: "success", message: "Kaggle connected." };
}

export async function disconnectKaggleAction(): Promise<void> {
  if (fs.existsSync(KAGGLE_CREDENTIALS_FILE)) {
    fs.unlinkSync(KAGGLE_CREDENTIALS_FILE);
  }
  await prisma.dataSourceConnection.updateMany({
    where: { sourceId: KAGGLE_PSEUDO_SOURCE_ID },
    data: { status: "NOT_CONNECTED", connectedAt: null, errorMessage: null },
  });
  revalidatePath("/settings/data-connections");
  revalidatePath("/data-sources");
}

// ---------------------------------------------------------------------------
// "Add data source from URL" — preview before download
// ---------------------------------------------------------------------------

export interface UrlPreviewResult {
  valid: boolean;
  error: string | null;
  hostname: string;
  scheme: string;
  fileExtension: string | null;
  isAllowedExtension: boolean;
  contentLengthBytes: number | null;
  contentType: string | null;
}

/** A best-effort HEAD request server-side (avoids CORS issues a browser-side fetch would hit, and keeps the network call out of the client bundle) — shown to the user BEFORE any download happens, per Phase 3D section 6. Never itself downloads the file. */
export async function previewUrlAction(rawUrl: string): Promise<UrlPreviewResult> {
  const classification = classifyUrl(rawUrl);
  if (!classification.valid) {
    return { ...classification, contentLengthBytes: null, contentType: null };
  }

  let contentLengthBytes: number | null = null;
  let contentType: string | null = null;
  try {
    const response = await fetch(rawUrl, { method: "HEAD", redirect: "follow", signal: AbortSignal.timeout(10_000) });
    if (response.ok) {
      const len = response.headers.get("content-length");
      contentLengthBytes = len ? Number(len) : null;
      contentType = response.headers.get("content-type");
    }
  } catch {
    // Best-effort — some servers reject HEAD, or the host is unreachable; the actual download step is the real validation.
  }

  return { ...classification, contentLengthBytes, contentType };
}

// ---------------------------------------------------------------------------
// Start / resume an import job
// ---------------------------------------------------------------------------

export interface StartImportJobInput {
  sourceId: string;
  provenanceStatus: string;
  sourceLabel?: string;
  downloadUrl?: string;
  kaggleDatasetRef?: string;
  localFilePath?: string;
  sourceType?: "REAL" | "SYNTHETIC" | "SAMPLE";
  dateFrom?: string;
  dateTo?: string;
}

export interface StartImportJobResult {
  ok: boolean;
  jobId?: string;
  message?: string;
}

export async function startImportJobAction(input: StartImportJobInput): Promise<StartImportJobResult> {
  const source = getSourceCatalogEntry(input.sourceId);
  if (!source || !source.enabled) {
    return { ok: false, message: "This data source is not available." };
  }

  if (source.authMechanism === "kaggle") {
    const kaggle = await getKaggleConnectionStatus();
    if (!kaggle.connected) {
      return { ok: false, message: "Connect Kaggle first — Settings -> Data Connections -> Kaggle." };
    }
  }

  const args = ["--create-only", "--source-id", input.sourceId, "--source-type", input.sourceType ?? "REAL"];
  if (input.provenanceStatus) args.push("--provenance-status", input.provenanceStatus);
  if (input.sourceLabel) args.push("--source-label", input.sourceLabel);
  if (input.downloadUrl) args.push("--download-url", input.downloadUrl);
  if (input.kaggleDatasetRef) args.push("--kaggle-dataset-ref", input.kaggleDatasetRef);
  if (input.localFilePath) args.push("--local-file", input.localFilePath);
  if (input.dateFrom) args.push("--from", input.dateFrom);
  if (input.dateTo) args.push("--to", input.dateTo);

  const extraEnv = kaggleEnvFor(source);
  const created = runImportJobCliSync(args, extraEnv);
  if (!created.ok) {
    return { ok: false, message: created.stderr.trim() || "Failed to create the import job." };
  }

  let jobId: string;
  try {
    jobId = (JSON.parse(created.stdout.trim()) as { job_id: string }).job_id;
  } catch {
    return { ok: false, message: "Unexpected output while creating the import job." };
  }

  // Long-running (download/inspect/import/leakage-audit/dataset-version) —
  // spawned detached. Progress is read back from the ImportJob row via
  // Prisma polling, never from this process's own output.
  runImportJobCliDetached(["--job-id", jobId], extraEnv);

  revalidatePath("/data-sources");
  return { ok: true, jobId };
}

export interface MappingUpdate {
  role: string | null;
  confirmed: boolean;
}

export async function confirmMappingAction(
  jobId: string,
  updates: Record<string, MappingUpdate>
): Promise<StartImportJobResult> {
  const job = await prisma.importJob.findUnique({ where: { id: jobId } });
  if (!job) return { ok: false, message: "Import job not found." };
  if (job.status !== "AWAITING_MAPPING_REVIEW") {
    return { ok: false, message: `This job isn't waiting for mapping review (status: ${job.status}).` };
  }

  const patchDir = path.join(process.cwd(), "python", "storage", "import_jobs", jobId);
  fs.mkdirSync(patchDir, { recursive: true });
  const patchPath = path.join(patchDir, `mapping_review_${Date.now()}.json`);
  fs.writeFileSync(patchPath, JSON.stringify(updates));

  const source = getSourceCatalogEntry(job.sourceId);
  const extraEnv = source ? kaggleEnvFor(source) : {};

  // Fast synchronous patch (a JSON file edit)...
  const applied = runImportJobCliSync(["--job-id", jobId, "--apply-mapping-json", patchPath], extraEnv);
  if (!applied.ok) {
    return { ok: false, message: applied.stderr.trim() || "Failed to apply the mapping review." };
  }

  // ...then the (potentially slow) rest of the pipeline, detached.
  runImportJobCliDetached(["--job-id", jobId], extraEnv);

  revalidatePath("/data-sources");
  return { ok: true, jobId };
}

/** Form-friendly wrapper for `startImportJobAction`, for the card's inline "Import" form — redirects straight to the job's progress page on success, matching the useActionState + <form action> pattern used elsewhere in this app. */
export async function startImportJobFormAction(
  _prevState: ImportJobFormState,
  formData: FormData
): Promise<ImportJobFormState> {
  const sourceId = String(formData.get("sourceId") ?? "");
  const provenanceStatus = String(formData.get("provenanceStatus") ?? "");
  const sourceLabel = String(formData.get("sourceLabel") ?? "").trim() || undefined;
  const downloadUrl = String(formData.get("downloadUrl") ?? "").trim() || undefined;
  const kaggleDatasetRef = String(formData.get("kaggleDatasetRef") ?? "").trim() || undefined;
  const localFilePath = String(formData.get("localFilePath") ?? "").trim() || undefined;

  if (!sourceId || !provenanceStatus) {
    return { status: "error", message: "Missing required fields." };
  }

  const result = await startImportJobAction({
    sourceId,
    provenanceStatus,
    sourceLabel,
    downloadUrl,
    kaggleDatasetRef,
    localFilePath,
  });

  if (!result.ok || !result.jobId) {
    return { status: "error", message: result.message ?? "Could not start the import." };
  }

  redirect(`/data-sources/jobs/${result.jobId}`);
}

export async function syncSourceAction(sourceId: string, provenanceStatus: string): Promise<StartImportJobResult> {
  const source = getSourceCatalogEntry(sourceId);
  if (!source) return { ok: false, message: "Unknown data source." };

  const lastCompleted = await prisma.importJob.findFirst({
    where: { sourceId, status: "COMPLETED" },
    orderBy: { completedAt: "desc" },
  });

  return startImportJobAction({
    sourceId,
    provenanceStatus,
    sourceLabel: lastCompleted?.sourceLabel ?? source.name,
    downloadUrl: lastCompleted?.downloadUrl ?? undefined,
    kaggleDatasetRef: source.kaggleDatasetRef,
  });
}

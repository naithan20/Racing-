/**
 * The serverless ("one-tap") import pipeline — download -> extract -> parse
 * -> map -> (pause for review if needed) -> import, run entirely as plain
 * `await`ed Node code inside a Next.js Server Action. No subprocess, no
 * filesystem write, no detached process: everything Vercel's serverless
 * runtime can't do (see README.md's "What does NOT work on Vercel"), this
 * pipeline simply doesn't attempt.
 *
 * Deliberately narrower than `racingedge_data.import_pipeline` (the Python
 * CLI pipeline): it stops after writing Race/Runner/ResultEntry/DataProvenance
 * rows. It does not run the entity-resolution review queue, the temporal
 * leakage auditor, or create a DatasetVersion/quality report — those stay
 * CLI-only (see FREE_DATA_SOURCES.md). This is a genuine capability gap,
 * not something the UI should hide: pages that need a DatasetVersion (the
 * "Train Baseline Model" action) already handle a missing one by saying so.
 */

import "server-only";

import { prisma } from "@/database/client";
import { parseCsvToRecords } from "@/lib/csv";
import { extractZip, isZip, pickPrimaryCsvEntry } from "@/lib/serverlessImport/zip";
import { downloadKaggleDataset, downloadWithCap } from "@/lib/serverlessImport/download";
import {
  buildRoleToColumn,
  computeMappingProposal,
  mapRecordsToRaces,
  type ProposedColumn,
} from "@/lib/serverlessImport/columnMapper";
import { writeMappedRaces } from "@/lib/serverlessImport/writeMappedRaces";
import { appendJobLog, markJobFailed, updateJobStatus } from "@/lib/serverlessImport/jobStatus";
import type { DataSourceType } from "@/generated/prisma/enums";

export interface ServerlessJobParams {
  kind: "KAGGLE" | "URL";
  kaggleDatasetRef?: string;
  downloadUrl?: string;
  sourceId: string;
  sourceLabel: string;
  sourceType: DataSourceType;
  provenanceStatus: "VERIFIED_OPEN" | "PUBLIC_RESEARCH" | "COMMUNITY_UNVERIFIED" | "USER_SUPPLIED" | "UNKNOWN" | "RESTRICTED";
}

export type MappingReviewOverride = { role: string | null; confirmed: boolean };

interface MappingDataJson {
  columns: ProposedColumn[];
  resolvedUrl: string;
  resolvedFilename?: string;
}

/** Runs (or resumes, after mapping review) a serverless import job. Safe to call again after AWAITING_MAPPING_REVIEW with `mappingOverrides` — it re-downloads (this pipeline holds nothing in memory between Server Action invocations) rather than caching the parsed file, trading a repeat download for not storing a potentially large blob in Postgres. */
export async function runServerlessImportJob(jobId: string, mappingOverrides?: Record<string, MappingReviewOverride>): Promise<void> {
  const job = await prisma.importJob.findUnique({ where: { id: jobId } });
  if (!job || !job.paramsJson) {
    throw new Error(`Import job ${jobId} not found or missing params.`);
  }
  const params = JSON.parse(job.paramsJson) as ServerlessJobParams;

  try {
    await updateJobStatus(jobId, "DOWNLOADING", { progressPercent: 10, currentStepLabel: "Downloading" });
    await appendJobLog(jobId, "download", `Downloading from ${params.kind === "KAGGLE" ? `Kaggle dataset ${params.kaggleDatasetRef}` : params.downloadUrl}`);

    const { buffer, resolvedUrl } =
      params.kind === "KAGGLE"
        ? { buffer: (await downloadKaggleDataset(params.kaggleDatasetRef!)).buffer, resolvedUrl: `https://www.kaggle.com/datasets/${params.kaggleDatasetRef}` }
        : { buffer: (await downloadWithCap(params.downloadUrl!)).buffer, resolvedUrl: params.downloadUrl! };

    await appendJobLog(jobId, "download", `Downloaded ${(buffer.byteLength / 1024).toFixed(0)}KB.`);

    await updateJobStatus(jobId, "INSPECTING", { progressPercent: 30, currentStepLabel: "Reading file" });

    let text: string;
    let resolvedFilename: string | undefined;
    if (isZip(buffer)) {
      const entries = extractZip(buffer);
      const csvEntry = pickPrimaryCsvEntry(entries);
      if (!csvEntry) {
        await markJobFailed(jobId, "inspect", "No CSV file was found inside the downloaded archive.");
        return;
      }
      text = csvEntry.data.toString("utf-8");
      resolvedFilename = csvEntry.name;
    } else {
      text = buffer.toString("utf-8");
    }

    const records = parseCsvToRecords(text);
    if (records.length === 0) {
      await markJobFailed(jobId, "inspect", "The downloaded file has no data rows to import.");
      return;
    }
    const headers = Object.keys(records[0]);
    await appendJobLog(jobId, "inspect", `Found ${records.length.toLocaleString()} rows, ${headers.length} columns.`);

    const proposal = computeMappingProposal(records, headers);
    const roleToColumn = buildRoleToColumn(proposal.columns, mappingOverrides);

    const stillNeedsReview = proposal.columns.filter((col) => {
      if (col.proposedRole === null) return false;
      if (col.confidence === "high") return false;
      const override = mappingOverrides?.[col.column];
      return !override || !override.confirmed;
    });

    if (stillNeedsReview.length > 0) {
      if (!mappingOverrides) {
        const mappingData: MappingDataJson = { columns: proposal.columns, resolvedUrl, resolvedFilename };
        await updateJobStatus(jobId, "AWAITING_MAPPING_REVIEW", {
          progressPercent: 40,
          currentStepLabel: `${stillNeedsReview.length} field(s) need review`,
          mappingDataJson: JSON.stringify(mappingData),
        });
        await appendJobLog(
          jobId,
          "inspect",
          `${proposal.autoMappedCount} field(s) auto-mapped with high confidence; ${stillNeedsReview.length} need review before import.`
        );
        return;
      }
      // A confirm call arrived but some columns are still unresolved — a
      // guard, not an expected path (the mapping review UI always sends a
      // decision for every listed column).
      await markJobFailed(jobId, "mapping", "Some fields still need review — please confirm every listed field.");
      return;
    }

    await updateJobStatus(jobId, "IMPORTING", { progressPercent: 60, currentStepLabel: "Importing races" });
    const { races, droppedRowCount } = mapRecordsToRaces(records, roleToColumn);
    if (races.length === 0) {
      await markJobFailed(jobId, "import", "No races could be built from this file — every row was missing a course or a parseable race date.");
      return;
    }
    if (droppedRowCount > 0) {
      await appendJobLog(jobId, "import", `${droppedRowCount} row(s) dropped — missing course or unparseable race date.`);
    }

    const result = await writeMappedRaces(races, {
      sourceType: params.sourceType,
      provenanceProvider: params.kind === "KAGGLE" ? `kaggle:${params.kaggleDatasetRef}` : `url:${new URL(resolvedUrl).hostname}`,
      provenanceStatus: params.provenanceStatus,
      sourceUrl: resolvedUrl,
      filename: resolvedFilename,
    });

    await upsertDatasetReview(params, resolvedUrl);

    await appendJobLog(
      jobId,
      "import",
      `Imported ${result.racesCreated.toLocaleString()} races, ${result.runnersCreated.toLocaleString()} runners, ${result.resultsCreated.toLocaleString()} results.`
    );
    await updateJobStatus(jobId, "COMPLETED", {
      progressPercent: 100,
      currentStepLabel: "Completed",
      racesImported: result.racesCreated,
      runnersImported: result.runnersCreated,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await markJobFailed(jobId, "error", message);
  }
}

async function upsertDatasetReview(params: ServerlessJobParams, resolvedUrl: string): Promise<void> {
  const datasetName = params.sourceLabel;
  const source = params.kind === "KAGGLE" ? `Kaggle: ${params.kaggleDatasetRef}` : resolvedUrl;

  const existing = await prisma.datasetReview.findFirst({ where: { datasetName, source } });
  if (existing) return;

  await prisma.datasetReview.create({
    data: {
      datasetName,
      source,
      licenceStated: params.kind === "KAGGLE" ? "Varies by uploader — not confirmed by RacingEdge" : null,
      provenanceConfidence: params.provenanceStatus,
      reviewerNotes:
        params.kind === "KAGGLE"
          ? "Imported via the one-tap serverless pipeline. RacingEdge did not verify redistribution/commercial-use rights for this community dataset — treat as research use only until reviewed."
          : "Imported via the one-tap serverless pipeline from a user-supplied URL — reuse rights not verified.",
    },
  });
}

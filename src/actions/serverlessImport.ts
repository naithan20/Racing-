"use server";

/**
 * The "one-tap free setup" import path — Vercel-compatible replacement for
 * the relevant parts of src/actions/dataSources.ts's `startImportJobAction`/
 * `confirmMappingAction`, which spawn the Python CLI pipeline (subprocess +
 * local filesystem, unavailable on Vercel — see README.md). Runs the whole
 * download -> parse -> map -> import sequence as plain awaited Node code
 * inside this Server Action's own request, bounded by `maxDuration` below.
 */

import { revalidatePath } from "next/cache";

import { prisma } from "@/database/client";
import { getSourceCatalogEntry } from "@/data/sourceCatalog";
import { runServerlessImportJob, type MappingReviewOverride, type ServerlessJobParams } from "@/lib/serverlessImport/pipeline";
import type { StartImportJobResult } from "@/actions/dataSources";

// How long Vercel keeps this Server Action's serverless function alive is
// bounded by `export const maxDuration` on the PAGE that invokes it (a
// "use server" actions file may only export async functions — see
// src/app/data-sources/page.tsx and src/app/data-sources/jobs/[jobId]/page.tsx).
// 60s is the highest value the Hobby plan honours without extra config;
// Pro/Enterprise projects can raise it in vercel.json. A dataset that
// genuinely needs longer than this (huge CSV, slow connection) should use
// the CLI pipeline instead — see FREE_DATA_SOURCES.md.

export interface StartOneTapImportInput {
  sourceId: string;
  provenanceStatus: ServerlessJobParams["provenanceStatus"];
  sourceLabel?: string;
  downloadUrl?: string;
}

export async function startOneTapImportAction(input: StartOneTapImportInput): Promise<StartImportJobResult> {
  const source = getSourceCatalogEntry(input.sourceId);
  if (!source || !source.enabled) {
    return { ok: false, message: "This data source is not available." };
  }

  const params: ServerlessJobParams = source.downloadMechanism === "KAGGLE"
    ? {
        kind: "KAGGLE",
        kaggleDatasetRef: source.kaggleDatasetRef,
        sourceId: input.sourceId,
        sourceLabel: input.sourceLabel || source.name,
        sourceType: "REAL",
        provenanceStatus: input.provenanceStatus,
      }
    : {
        kind: "URL",
        downloadUrl: input.downloadUrl,
        sourceId: input.sourceId,
        sourceLabel: input.sourceLabel || source.name,
        sourceType: "REAL",
        provenanceStatus: input.provenanceStatus,
      };

  if (params.kind === "KAGGLE" && !params.kaggleDatasetRef) {
    return { ok: false, message: "This Kaggle source has no dataset reference configured." };
  }
  if (params.kind === "URL" && !params.downloadUrl) {
    return { ok: false, message: "A download URL is required." };
  }

  const job = await prisma.importJob.create({
    data: {
      sourceId: input.sourceId,
      runtime: "SERVERLESS_NODE",
      status: "PENDING",
      sourceLabel: params.sourceLabel,
      provenanceStatus: input.provenanceStatus,
      downloadUrl: params.downloadUrl,
      paramsJson: JSON.stringify(params),
    },
  });

  await runServerlessImportJob(job.id);

  revalidatePath("/data-sources");
  return { ok: true, jobId: job.id };
}

export async function confirmOneTapMappingAction(
  jobId: string,
  updates: Record<string, MappingReviewOverride>
): Promise<StartImportJobResult> {
  const job = await prisma.importJob.findUnique({ where: { id: jobId } });
  if (!job) return { ok: false, message: "Import job not found." };
  if (job.runtime !== "SERVERLESS_NODE") {
    return { ok: false, message: "This job does not use the serverless pipeline." };
  }
  if (job.status !== "AWAITING_MAPPING_REVIEW") {
    return { ok: false, message: `This job isn't waiting for mapping review (status: ${job.status}).` };
  }

  await runServerlessImportJob(jobId, updates);

  revalidatePath("/data-sources");
  return { ok: true, jobId };
}

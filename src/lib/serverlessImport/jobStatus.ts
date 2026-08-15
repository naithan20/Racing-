/**
 * ImportJob status/log helpers shared by the serverless pipeline. Mirrors
 * the `{ts, step, message}` log-entry shape and status-field semantics the
 * Python pipeline already writes (see prisma/schema.prisma's ImportJob.logJson
 * comment) so the existing JobProgressView UI needs no changes to render
 * either runtime's jobs.
 */

import type { ImportJobStatus } from "@/generated/prisma/enums";
import { prisma } from "@/database/client";

interface LogEntry {
  ts: string;
  step: string;
  message: string;
}

export async function appendJobLog(jobId: string, step: string, message: string): Promise<void> {
  const job = await prisma.importJob.findUnique({ where: { id: jobId }, select: { logJson: true } });
  const log: LogEntry[] = job?.logJson ? JSON.parse(job.logJson) : [];
  log.push({ ts: new Date().toISOString(), step, message });
  await prisma.importJob.update({ where: { id: jobId }, data: { logJson: JSON.stringify(log) } });
}

export async function updateJobStatus(
  jobId: string,
  status: ImportJobStatus,
  extra: {
    progressPercent?: number;
    currentStepLabel?: string;
    mappingDataJson?: string | null;
    racesImported?: number;
    runnersImported?: number;
    errorMessage?: string | null;
    downloadUrl?: string;
  } = {}
): Promise<void> {
  await prisma.importJob.update({
    where: { id: jobId },
    data: {
      status,
      ...extra,
      ...(status === "COMPLETED" || status === "FAILED" ? { completedAt: new Date() } : {}),
    },
  });
}

export async function markJobFailed(jobId: string, step: string, message: string): Promise<void> {
  await appendJobLog(jobId, step, message);
  await updateJobStatus(jobId, "FAILED", { errorMessage: message, currentStepLabel: "Failed" });
}

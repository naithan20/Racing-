/**
 * Dataset Explorer queries (Phase 3A).
 *
 * Point-in-time reconstruction, mirrored in TypeScript from
 * `python/racingedge_data/point_in_time.py` — the two languages never call
 * into each other at runtime (they only ever share the SQLite file, per
 * Phase 1/2's architecture), so this logic is deliberately re-implemented
 * here rather than shelled out to Python. Keep the two in sync if the
 * reconstruction rule ever changes: pick the most recent history row with
 * `effectiveAt <= asOf`; a field with no qualifying row is reported as
 * unknown (`null`), never backfilled from the live (possibly post-race)
 * value.
 */
import "server-only";

import { prisma } from "@/database/client";

const RACE_MUTABLE_FIELDS = [
  "going",
  "goingDescription",
  "railPosition",
  "stallsPosition",
  "weatherSummary",
  "raceStatus",
  "resultStatus",
] as const;

const RUNNER_MUTABLE_FIELDS = [
  "draw",
  "jockeyName",
  "trainerName",
  "weightLbsTotal",
  "nonRunner",
  "headgear",
  "officialRating",
] as const;

export async function getExplorerRaces(limit = 100) {
  return prisma.race.findMany({
    orderBy: { date: "desc" },
    take: limit,
    select: {
      id: true,
      date: true,
      raceTime: true,
      racecourse: true,
      raceName: true,
      sourceType: true,
      raceStatus: true,
      numberOfRunners: true,
    },
  });
}

export async function getRaceExplorerDetail(raceId: string) {
  const race = await prisma.race.findUnique({
    where: { id: raceId },
    include: {
      runners: { include: { horse: true }, orderBy: { clothNumber: "asc" } },
      placeTerms: { include: { bookmaker: true } },
      importBatch: true,
    },
  });
  if (!race) return null;

  const [raceFieldHistory, provenance] = await Promise.all([
    prisma.raceFieldHistory.findMany({ where: { raceId }, orderBy: { effectiveAt: "asc" } }),
    prisma.dataProvenance.findMany({ where: { entityType: "Race", entityId: raceId }, orderBy: { retrievedAt: "asc" } }),
  ]);

  return { race, raceFieldHistory, provenance };
}

type RaceFieldName = (typeof RACE_MUTABLE_FIELDS)[number];
type RunnerFieldName = (typeof RUNNER_MUTABLE_FIELDS)[number];

export interface ReconstructedRaceFields {
  asOf: Date;
  fields: Record<RaceFieldName, string | null>;
}

export async function reconstructRaceFieldsAsOf(raceId: string, asOf: Date): Promise<ReconstructedRaceFields> {
  const fields = {} as Record<RaceFieldName, string | null>;
  await Promise.all(
    RACE_MUTABLE_FIELDS.map(async (fieldName) => {
      const row = await prisma.raceFieldHistory.findFirst({
        where: { raceId, fieldName, effectiveAt: { lte: asOf } },
        orderBy: { effectiveAt: "desc" },
      });
      fields[fieldName] = row?.fieldValue ?? null;
    })
  );
  return { asOf, fields };
}

export interface ReconstructedRunnerFields {
  runnerId: string;
  asOf: Date;
  fields: Record<RunnerFieldName, string | null>;
}

export async function reconstructRunnerFieldsAsOf(runnerId: string, asOf: Date): Promise<ReconstructedRunnerFields> {
  const fields = {} as Record<RunnerFieldName, string | null>;
  await Promise.all(
    RUNNER_MUTABLE_FIELDS.map(async (fieldName) => {
      const row = await prisma.runnerFieldHistory.findFirst({
        where: { runnerId, fieldName, effectiveAt: { lte: asOf } },
        orderBy: { effectiveAt: "desc" },
      });
      fields[fieldName] = row?.fieldValue ?? null;
    })
  );
  return { runnerId, asOf, fields };
}

export async function getRunnerOddsTimeline(runnerId: string, asOf?: Date) {
  return prisma.runnerMarketPrice.findMany({
    where: asOf ? { runnerId, timestamp: { lte: asOf } } : { runnerId },
    include: { bookmaker: true },
    orderBy: { timestamp: "asc" },
  });
}

export async function getRunnerFieldHistory(runnerId: string) {
  return prisma.runnerFieldHistory.findMany({ where: { runnerId }, orderBy: { effectiveAt: "asc" } });
}

export async function getRunnerExplorerDetail(runnerId: string) {
  const runner = await prisma.runner.findUnique({
    where: { id: runnerId },
    include: { horse: true, race: true, result: true },
  });
  if (!runner) return null;

  const [fieldHistory, oddsTimeline, provenance] = await Promise.all([
    getRunnerFieldHistory(runnerId),
    getRunnerOddsTimeline(runnerId),
    prisma.dataProvenance.findMany({ where: { entityType: "Runner", entityId: runnerId }, orderBy: { retrievedAt: "asc" } }),
  ]);

  return { runner, fieldHistory, oddsTimeline, provenance };
}

export async function getHorseTimeline(horseId: string) {
  const horse = await prisma.horse.findUnique({ where: { id: horseId } });
  if (!horse) return null;

  const [formEntries, runners, aliases] = await Promise.all([
    prisma.formEntry.findMany({ where: { horseId }, orderBy: { raceDate: "desc" } }),
    prisma.runner.findMany({
      where: { horseId },
      include: { race: true },
      orderBy: { race: { date: "desc" } },
    }),
    prisma.entityAlias.findMany({ where: { entityType: "HORSE", canonicalId: horseId }, orderBy: { createdAt: "asc" } }),
  ]);

  return { horse, formEntries, runners, aliases };
}

export async function searchHorsesByName(query: string, limit = 20) {
  if (!query.trim()) return [];
  return prisma.horse.findMany({
    where: { name: { contains: query } },
    take: limit,
    orderBy: { name: "asc" },
  });
}

export async function getEntityResolutionQueue(limit = 100) {
  return prisma.entityResolutionQueueItem.findMany({
    where: { status: "PENDING" },
    orderBy: { createdAt: "desc" },
    take: limit,
  });
}

export async function getDatasetVersions(limit = 50) {
  return prisma.datasetVersion.findMany({
    orderBy: { createdAt: "desc" },
    take: limit,
    include: { modelVersions: { select: { id: true, name: true, version: true } } },
  });
}

export async function getLeakageAuditRuns(limit = 50) {
  return prisma.leakageAuditRun.findMany({
    orderBy: { createdAt: "desc" },
    take: limit,
    include: {
      datasetVersion: { select: { id: true, name: true } },
      modelVersion: { select: { id: true, name: true, version: true } },
    },
  });
}

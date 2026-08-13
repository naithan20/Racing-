/**
 * Server-side read queries backing the UI. Pages call these directly (React
 * Server Components) rather than going through a REST layer — there is only
 * one local SQLite database, so an extra HTTP hop buys nothing in Phase 1.
 */
import "server-only";

import { prisma } from "@/database/client";

function startOfDay(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

function endOfDay(date: Date): Date {
  const d = new Date(date);
  d.setHours(23, 59, 59, 999);
  return d;
}

export async function getRacesForDate(date: Date) {
  return prisma.race.findMany({
    where: { date: { gte: startOfDay(date), lte: endOfDay(date) } },
    orderBy: { raceTime: "asc" },
    include: {
      placeTerms: { include: { bookmaker: true } },
      runners: {
        select: { id: true, nonRunner: true },
      },
    },
  });
}

export async function getDistinctRaceDates() {
  const races = await prisma.race.findMany({ select: { date: true }, distinct: ["date"] });
  return races.map((r) => r.date).sort((a, b) => a.getTime() - b.getTime());
}

export async function getRaceDetail(raceId: string) {
  return prisma.race.findUnique({
    where: { id: raceId },
    include: {
      placeTerms: { include: { bookmaker: true } },
      runners: {
        orderBy: { clothNumber: "asc" },
        include: {
          horse: {
            include: {
              evidenceProfile: true,
              formEntries: { orderBy: { raceDate: "desc" }, take: 6 },
            },
          },
          paceProfile: true,
          predictionSnapshots: {
            where: { snapshotType: "PRE_RACE" },
            orderBy: { createdAt: "desc" },
            take: 1,
          },
          result: { include: { observations: true } },
        },
      },
    },
  });
}

export async function getRunnerDetail(runnerId: string) {
  const runner = await prisma.runner.findUnique({
    where: { id: runnerId },
    include: {
      race: { include: { placeTerms: { include: { bookmaker: true } } } },
      horse: { include: { evidenceProfile: true } },
      paceProfile: true,
      marketPrices: { include: { bookmaker: true }, orderBy: { timestamp: "asc" } },
      predictionSnapshots: { orderBy: { createdAt: "desc" } },
      result: { include: { observations: true } },
      features: { include: { definition: true } },
    },
  });
  if (!runner) return null;

  const formEntries = await prisma.formEntry.findMany({
    where: { horseId: runner.horseId },
    orderBy: { raceDate: "desc" },
  });

  return { runner, formEntries };
}

export async function getResultTrackingRaces() {
  return prisma.race.findMany({
    orderBy: [{ date: "desc" }, { raceTime: "asc" }],
    include: {
      runners: {
        include: { horse: true, result: true },
        orderBy: { clothNumber: "asc" },
      },
      placeTerms: { include: { bookmaker: true } },
    },
  });
}

export async function getRaceForResultEntry(raceId: string) {
  return prisma.race.findUnique({
    where: { id: raceId },
    include: {
      placeTerms: { include: { bookmaker: true } },
      runners: {
        orderBy: { clothNumber: "asc" },
        include: {
          horse: true,
          result: { include: { observations: true } },
          predictionSnapshots: { where: { snapshotType: "PRE_RACE" } },
        },
      },
    },
  });
}

export async function getImportBatches() {
  return prisma.importBatch.findMany({
    orderBy: { importedAt: "desc" },
    take: 25,
    include: { _count: { select: { races: true } } },
  });
}

export async function getLucky15Candidates() {
  const runners = await prisma.runner.findMany({
    where: { nonRunner: false, race: { raceStatus: { in: ["SCHEDULED", "DELAYED"] } } },
    include: {
      horse: { include: { evidenceProfile: true } },
      race: { include: { placeTerms: { include: { bookmaker: true } } } },
      predictionSnapshots: {
        where: { snapshotType: "PRE_RACE" },
        orderBy: { createdAt: "desc" },
        take: 1,
      },
    },
    orderBy: [{ race: { date: "asc" } }, { race: { raceTime: "asc" } }],
  });
  return runners;
}

export async function getLucky15Slips() {
  return prisma.lucky15Slip.findMany({
    orderBy: { createdAt: "desc" },
    include: { legs: { include: { runner: { include: { horse: true, race: true } } } } },
  });
}

export async function getBookmakers() {
  return prisma.bookmaker.findMany({ orderBy: { name: "asc" } });
}

export async function getPerformanceData() {
  const results = await prisma.resultEntry.findMany({
    include: {
      runner: {
        include: {
          race: true,
          predictionSnapshots: { where: { snapshotType: "PRE_RACE" }, take: 1 },
        },
      },
    },
  });
  return results;
}

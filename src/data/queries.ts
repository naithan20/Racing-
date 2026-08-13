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
            include: { placeProbabilityBands: true, modelVersionRef: true },
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
      race: {
        include: {
          placeTerms: { include: { bookmaker: true } },
          // Sibling runners in the same field — needed so the runner-detail
          // explanation engine can express pace/weight/rating facts
          // relative to today's actual field, not in a vacuum.
          runners: { select: { id: true, officialRating: true, weightLbsTotal: true, paceProfile: true } },
        },
      },
      horse: { include: { evidenceProfile: true } },
      paceProfile: true,
      marketPrices: { include: { bookmaker: true }, orderBy: { timestamp: "asc" } },
      predictionSnapshots: {
        orderBy: { createdAt: "desc" },
        include: { placeProbabilityBands: true, modelVersionRef: true },
      },
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

/** Lightweight, model-agnostic result summary — deliberately selects only
 * the columns the dashboard's legacy "all recorded results" card needs, to
 * stay fast as ResultEntry grows into the thousands (a full relational
 * include here previously blew SQLite's bound-parameter limit). */
export async function getPerformanceData() {
  return prisma.resultEntry.findMany({
    select: { finishingPosition: true, placeOutcome: true, profitLossWinStake: true },
  });
}

// ---------------------------------------------------------------------------
// Phase 2: model versioning, calibration dashboard, value scanner, backtest mode
// ---------------------------------------------------------------------------

export async function getModelVersions() {
  return prisma.modelVersion.findMany({ orderBy: { createdAt: "desc" } });
}

export async function getModelVersionById(modelVersionId: string) {
  return prisma.modelVersion.findUnique({ where: { id: modelVersionId } });
}

/**
 * Every PredictionSnapshot produced by a given ModelVersion, joined to the
 * runner/race/result needed to compute live calibration + breakdown
 * metrics in TypeScript (see src/backtesting/scoring.ts). Deliberately
 * recomputed from raw snapshots + results on every dashboard load rather
 * than trusting a cached summary, so the dashboard can never go stale.
 */
export async function getPredictionsForModelVersion(modelVersionId: string) {
  return prisma.predictionSnapshot.findMany({
    where: { modelVersionId },
    include: {
      placeProbabilityBands: true,
      runner: {
        include: {
          horse: { include: { evidenceProfile: true } },
          race: true,
          result: true,
        },
      },
    },
  });
}

/**
 * Candidates for the Daily Value Scanner: every non-runner in a scheduled/
 * delayed race that has a Phase 2 model prediction attached, across ALL
 * races (not scoped to one race, unlike the race analysis table).
 */
export async function getValueScannerCandidates() {
  return prisma.runner.findMany({
    where: {
      nonRunner: false,
      race: { raceStatus: { in: ["SCHEDULED", "DELAYED"] } },
      predictionSnapshots: { some: { snapshotType: "PRE_RACE", modelVersionId: { not: null } } },
    },
    include: {
      horse: { include: { evidenceProfile: true } },
      race: { include: { placeTerms: { include: { bookmaker: true } } } },
      predictionSnapshots: {
        where: { snapshotType: "PRE_RACE", modelVersionId: { not: null } },
        orderBy: { createdAt: "desc" },
        take: 1,
        include: { placeProbabilityBands: true, modelVersionRef: true },
      },
    },
    orderBy: [{ race: { date: "asc" } }, { race: { raceTime: "asc" } }],
  });
}

/** Distinct race dates that have at least one model-generated (Phase 2)
 * PredictionSnapshot AND a known result — i.e. dates the Backtest Mode
 * page can show a genuine predicted-vs-actual comparison for. Upcoming
 * (not-yet-resulted) predictions are deliberately excluded here; they're
 * already visible via the Races and Value Scanner pages. */
export async function getBacktestAvailableDates() {
  const snapshots = await prisma.predictionSnapshot.findMany({
    where: { modelVersionId: { not: null }, runner: { race: { raceStatus: "RESULTED" } } },
    select: { runner: { select: { race: { select: { date: true } } } } },
    distinct: ["runnerId"],
  });
  const dates = new Set(snapshots.map((s) => s.runner.race.date.toISOString().slice(0, 10)));
  return Array.from(dates).sort();
}

/** Everything predicted (by any model) for RESULTED races on a given date,
 * alongside the actual outcome — the core of "what would RacingEdge have
 * said before this race, and what actually happened". */
export async function getBacktestPredictionsForDate(date: Date) {
  return prisma.race.findMany({
    where: { date: { gte: startOfDay(date), lte: endOfDay(date) }, raceStatus: "RESULTED" },
    orderBy: { raceTime: "asc" },
    include: {
      placeTerms: { include: { bookmaker: true } },
      runners: {
        orderBy: { clothNumber: "asc" },
        include: {
          horse: true,
          result: true,
          predictionSnapshots: {
            where: { snapshotType: "PRE_RACE", modelVersionId: { not: null } },
            orderBy: { createdAt: "desc" },
            take: 1,
            include: { placeProbabilityBands: true, modelVersionRef: true },
          },
        },
      },
    },
  });
}

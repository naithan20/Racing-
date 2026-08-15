/**
 * Persists `MappedRace[]` (see columnMapper.ts) into the database — the
 * serverless pipeline's equivalent of `racingedge_data.importers.import_runner.import_races`,
 * but written directly against Prisma/Postgres instead of raw sqlite3, and
 * deliberately narrower in scope (see the module docstring in
 * prisma/schema.prisma's `ImportJobRuntime` enum for exactly what this
 * pipeline does NOT do: entity-resolution queueing beyond simple
 * name-based horse dedup, temporal leakage audit, DatasetVersion/bias
 * report).
 *
 * Unlike src/data/importRaces.ts (the Phase 1 manual CSV/JSON import,
 * which is pre-race-card-only and has no result fields at all), this also
 * writes ResultEntry rows — a free HISTORICAL RESULTS dataset is pointless
 * to import without finishing positions and starting prices, which is the
 * whole reason this module exists rather than reusing importRaces().
 */

import { DataSourceType, ImportSourceType, ImportStatus, ResultStatus, Sex } from "@/generated/prisma/enums";
import { prisma } from "@/database/client";
import type { MappedRace, MappedRunner } from "@/lib/serverlessImport/columnMapper";
import { DEFAULT_HANDICAP_TYPE, DEFAULT_SURFACE } from "@/lib/serverlessImport/columnMapper";

// Free-text "sex" columns use short codes or full words inconsistently
// across sources — normalize well-known ones, leave anything unrecognized
// unmapped rather than guessing (matching this pipeline's "never fabricate
// a missing/ambiguous field" rule throughout).
const SEX_SYNONYMS: Record<string, Sex> = {
  c: Sex.COLT,
  colt: Sex.COLT,
  f: Sex.FILLY,
  filly: Sex.FILLY,
  g: Sex.GELDING,
  gelding: Sex.GELDING,
  m: Sex.MARE,
  mare: Sex.MARE,
  h: Sex.HORSE,
  horse: Sex.HORSE,
  r: Sex.RIG,
  rig: Sex.RIG,
};

function normalizeSex(raw: string | undefined): Sex | undefined {
  if (!raw) return undefined;
  return SEX_SYNONYMS[raw.trim().toLowerCase()];
}

export interface WriteMappedRacesOptions {
  sourceType: DataSourceType;
  provenanceProvider: string; // e.g. "kaggle:deltaromeo/horse-racing-results-ukireland-2015-2025"
  provenanceStatus: "VERIFIED_OPEN" | "PUBLIC_RESEARCH" | "COMMUNITY_UNVERIFIED" | "USER_SUPPLIED" | "UNKNOWN" | "RESTRICTED";
  sourceUrl: string;
  filename?: string;
}

export interface WriteMappedRacesResult {
  importBatchId: string;
  racesCreated: number;
  runnersCreated: number;
  resultsCreated: number;
}

async function findOrCreateHorse(runner: MappedRunner) {
  const existing = await prisma.horse.findFirst({
    where: { name: runner.horseName, ...(runner.trainerName ? { trainerName: runner.trainerName } : {}) },
  });
  if (existing) return existing;

  return prisma.horse.create({
    data: {
      name: runner.horseName,
      sex: normalizeSex(runner.sex),
      sireName: runner.sireName,
      damName: runner.damName,
      damsireName: runner.damsireName,
    },
  });
}

function hasResultData(runner: MappedRunner): boolean {
  return (
    runner.finishingPosition !== undefined ||
    runner.beatenDistanceLengths !== undefined ||
    runner.startingPriceDecimal !== undefined ||
    runner.bspDecimal !== undefined
  );
}

export async function writeMappedRaces(races: MappedRace[], options: WriteMappedRacesOptions): Promise<WriteMappedRacesResult> {
  let runnersCreated = 0;
  let resultsCreated = 0;

  const importBatch = await prisma.importBatch.create({
    data: {
      sourceType: ImportSourceType.CSV,
      filename: options.filename,
      status: ImportStatus.PENDING,
      rowCount: races.reduce((sum, race) => sum + race.runners.length, 0),
    },
  });

  try {
    for (const race of races) {
      const createdRace = await prisma.race.create({
        data: {
          sourceType: options.sourceType,
          date: race.raceDate,
          raceTime: race.raceTime,
          racecourse: race.racecourse,
          country: race.country,
          raceName: race.raceName,
          raceType: race.raceType,
          flatJumps: race.flatJumps,
          surface: DEFAULT_SURFACE,
          distanceFurlongs: race.distanceFurlongs,
          raceClass: race.raceClass,
          handicapType: DEFAULT_HANDICAP_TYPE,
          numberOfRunners: race.numberOfRunners,
          going: race.going,
          raceStatus: "RESULTED",
          resultStatus: "CONFIRMED",
          importBatchId: importBatch.id,
        },
      });

      await prisma.dataProvenance.create({
        data: {
          entityType: "Race",
          entityId: createdRace.id,
          dataDomain: "RACE_CARD",
          provider: options.provenanceProvider,
          provenanceStatus: options.provenanceStatus,
          sourceUrl: options.sourceUrl,
          importBatchId: importBatch.id,
        },
      });

      for (const runner of race.runners) {
        const horse = await findOrCreateHorse(runner);

        const createdRunner = await prisma.runner.create({
          data: {
            raceId: createdRace.id,
            horseId: horse.id,
            draw: runner.draw,
            weightLbsTotal: runner.weightLbs,
            officialRating: runner.officialRating,
            jockeyName: runner.jockeyName,
            trainerName: runner.trainerName,
            headgear: runner.headgear,
            nonRunner: runner.nonRunner,
            startingPriceDecimal: runner.startingPriceDecimal,
          },
        });
        runnersCreated += 1;

        if (hasResultData(runner) && !runner.nonRunner) {
          await prisma.resultEntry.create({
            data: {
              runnerId: createdRunner.id,
              finishingPosition: runner.finishingPosition,
              beatenDistanceLengths: runner.beatenDistanceLengths,
              startingPriceDecimal: runner.startingPriceDecimal,
              bspDecimal: runner.bspDecimal,
              resultStatus: ResultStatus.CONFIRMED,
            },
          });
          resultsCreated += 1;
        }
      }
    }

    await prisma.importBatch.update({
      where: { id: importBatch.id },
      data: { status: ImportStatus.SUCCESS, successCount: runnersCreated, errorCount: 0 },
    });
  } catch (error) {
    await prisma.importBatch.update({
      where: { id: importBatch.id },
      data: {
        status: ImportStatus.FAILED,
        errorLog: JSON.stringify([{ message: error instanceof Error ? error.message : String(error) }]),
      },
    });
    throw error;
  }

  return { importBatchId: importBatch.id, racesCreated: races.length, runnersCreated, resultsCreated };
}

export { DataSourceType };

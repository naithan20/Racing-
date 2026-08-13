/**
 * Persists validated RaceImport documents (see importSchema.ts) into the
 * database. Shared by the CSV and JSON import API routes so both paths
 * behave identically once validation has passed.
 */

import { ImportSourceType, ImportStatus } from "@/generated/prisma/enums";
import { prisma } from "@/database/client";
import type { RaceImport } from "@/data/importSchema";

export interface ImportRacesResult {
  importBatchId: string;
  racesCreated: number;
  runnersCreated: number;
}

export async function importRaces(
  races: RaceImport[],
  source: { sourceType: ImportSourceType; filename?: string }
): Promise<ImportRacesResult> {
  let runnersCreated = 0;

  const importBatch = await prisma.importBatch.create({
    data: {
      sourceType: source.sourceType,
      filename: source.filename,
      status: ImportStatus.PENDING,
      rowCount: races.reduce((sum, race) => sum + race.runners.length, 0),
    },
  });

  try {
    for (const race of races) {
      const createdRace = await prisma.race.create({
        data: {
          date: new Date(race.raceDate),
          raceTime: race.raceTime,
          racecourse: race.racecourse,
          country: race.country,
          raceName: race.raceName,
          flatJumps: race.flatJumps,
          surface: race.surface,
          distanceFurlongs: race.distanceFurlongs,
          raceClass: race.raceClass,
          gradeGroup: race.gradeGroup,
          handicapType: race.handicapType,
          ageRestriction: race.ageRestriction,
          sexRestriction: race.sexRestriction,
          numberOfRunners: race.numberOfRunners,
          going: race.going,
          eachWayFraction: race.eachWayFraction,
          bookmakerPlaces: race.bookmakerPlaces,
          importBatchId: importBatch.id,
        },
      });

      for (const runner of race.runners) {
        const horse = await findOrCreateHorse(runner);

        await prisma.runner.create({
          data: {
            raceId: createdRace.id,
            horseId: horse.id,
            draw: runner.draw,
            clothNumber: runner.clothNumber,
            ageAtRace: runner.age,
            weightLbsTotal: runner.weightLbs,
            officialRating: runner.officialRating,
            jockeyName: runner.jockeyName,
            jockeyClaimLbs: runner.jockeyClaimLbs,
            trainerName: runner.trainerName,
            headgear: runner.headgear,
            firstTimeHeadgear: runner.firstTimeHeadgear ?? false,
            daysSinceLastRun: runner.daysSinceLastRun,
            currentOddsDecimal: runner.currentOddsDecimal,
            startingPriceDecimal: runner.startingPriceDecimal,
          },
        });
        runnersCreated += 1;
      }
    }

    await prisma.importBatch.update({
      where: { id: importBatch.id },
      data: {
        status: ImportStatus.SUCCESS,
        successCount: runnersCreated,
        errorCount: 0,
      },
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

  return { importBatchId: importBatch.id, racesCreated: races.length, runnersCreated };
}

/**
 * Finds an existing horse by name (+ trainer, as a light disambiguator) or
 * creates a new one. Phase 1 keeps horse identity resolution simple and
 * name-based; a licensed data feed would key off a stable horse id instead.
 */
async function findOrCreateHorse(runner: {
  horseName: string;
  horseCountryBred?: string;
  trainerName?: string;
  sireName?: string;
  damName?: string;
  damsireName?: string;
}) {
  const existing = await prisma.horse.findFirst({
    where: {
      name: runner.horseName,
      ...(runner.trainerName ? { trainerName: runner.trainerName } : {}),
    },
  });
  if (existing) return existing;

  return prisma.horse.create({
    data: {
      name: runner.horseName,
      countryBred: runner.horseCountryBred,
      trainerName: runner.trainerName,
      sireName: runner.sireName,
      damName: runner.damName,
      damsireName: runner.damsireName,
    },
  });
}

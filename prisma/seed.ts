/**
 * Seeds sample data so every screen in RacingEdge can be exercised without a
 * licensed data feed. Everything created here is flagged `isSampleData:
 * true` and uses obviously fictional horse/race names — this is NOT real
 * racing data and must never be mistaken for it.
 *
 * Run with: npm run db:seed
 */
import { PrismaBetterSqlite3 } from "@prisma/adapter-better-sqlite3";

import { PrismaClient } from "../src/generated/prisma/client";
import {
  FlatJumps,
  HandicapType,
  ImportSourceType,
  ImportStatus,
  ObservationTagType,
  PaceRole,
  RaceStatus,
  RaceSurface,
  ResultStatus,
  Sex,
  SnapshotType,
} from "../src/generated/prisma/enums";
import { FEATURE_DEFINITIONS } from "../src/features/definitions";

const adapter = new PrismaBetterSqlite3({ url: process.env.DATABASE_URL ?? "file:./dev.db" });
const prisma = new PrismaClient({ adapter });

const TODAY = new Date();
TODAY.setHours(0, 0, 0, 0);
const YESTERDAY = new Date(TODAY);
YESTERDAY.setDate(YESTERDAY.getDate() - 1);

async function main() {
  console.log("Seeding RacingEdge SAMPLE DATA...");

  await clearExisting();

  for (const def of FEATURE_DEFINITIONS) {
    await prisma.featureDefinition.create({ data: def });
  }
  console.log(`Seeded ${FEATURE_DEFINITIONS.length} feature definitions.`);

  const [bet365, skyBet, paddyPower, betfairExchange] = await Promise.all([
    prisma.bookmaker.create({ data: { name: "Bet365 (sample)" } }),
    prisma.bookmaker.create({ data: { name: "Sky Bet (sample)" } }),
    prisma.bookmaker.create({ data: { name: "Paddy Power (sample)" } }),
    prisma.bookmaker.create({ data: { name: "Betfair Exchange (sample)", isExchange: true } }),
  ]);

  const importBatch = await prisma.importBatch.create({
    data: {
      sourceType: ImportSourceType.MANUAL,
      filename: "seed-sample-data",
      status: ImportStatus.SUCCESS,
      rowCount: 0,
      successCount: 0,
      errorCount: 0,
    },
  });

  await seedAscotChase(importBatch.id, { bet365, skyBet, paddyPower, betfairExchange });
  await seedNewmarketNoviceStakes(importBatch.id, { bet365, skyBet, paddyPower, betfairExchange });
  await seedCheltenhamResultedRace(importBatch.id, { bet365, skyBet, paddyPower, betfairExchange });

  console.log("Seed complete.");
}

async function clearExisting() {
  await prisma.runnerObservation.deleteMany();
  await prisma.resultEntry.deleteMany();
  await prisma.predictionSnapshot.deleteMany();
  await prisma.lucky15Leg.deleteMany();
  await prisma.lucky15Slip.deleteMany();
  await prisma.feature.deleteMany();
  await prisma.featureDefinition.deleteMany();
  await prisma.runnerPaceProfile.deleteMany();
  await prisma.runnerMarketPrice.deleteMany();
  await prisma.racePlaceTerms.deleteMany();
  await prisma.runner.deleteMany();
  await prisma.formEntry.deleteMany();
  await prisma.evidenceProfile.deleteMany();
  await prisma.horse.deleteMany();
  await prisma.race.deleteMany();
  await prisma.importBatch.deleteMany();
  await prisma.bookmaker.deleteMany();
}

interface Bookmakers {
  bet365: { id: string };
  skyBet: { id: string };
  paddyPower: { id: string };
  betfairExchange: { id: string };
}

async function createHorseWithHistory(input: {
  name: string;
  yearOfBirth: number;
  sex: Sex;
  trainerName: string;
  ownerName: string;
  sireName: string;
  damName: string;
  damsireName: string;
  countryBred: string;
  careerStarts: number;
  startsLast12Months: number;
  evidenceDensityScore: number;
  evidenceDensityLabel: "VERY_LOW" | "LOW" | "MODERATE" | "HIGH" | "VERY_HIGH";
  formLines: Array<{
    daysAgo: number;
    course: string;
    country: string;
    distanceFurlongs: number;
    going: string;
    raceClass: number;
    flatJumps: FlatJumps;
    fieldSize: number;
    finishingPosition: number | null;
    finishStatus: string;
    beatenDistanceLengths: number | null;
    startingPriceDecimal: number;
    officialRating: number;
    weightPounds: number;
    draw: number | null;
    jockeyName: string;
    headgear: string | null;
    raceComment: string;
    paceClassification: string;
  }>;
}) {
  const horse = await prisma.horse.create({
    data: {
      isSampleData: true,
      name: input.name,
      yearOfBirth: input.yearOfBirth,
      sex: input.sex,
      trainerName: input.trainerName,
      ownerName: input.ownerName,
      sireName: input.sireName,
      damName: input.damName,
      damsireName: input.damsireName,
      countryBred: input.countryBred,
    },
  });

  await prisma.evidenceProfile.create({
    data: {
      horseId: horse.id,
      careerStarts: input.careerStarts,
      startsLast12Months: input.startsLast12Months,
      startsAtCourse: Math.min(2, input.careerStarts),
      startsAtDistance: Math.min(4, input.careerStarts),
      startsOnGoing: Math.min(3, input.careerStarts),
      evidenceDensityScore: input.evidenceDensityScore,
      evidenceDensityLabel: input.evidenceDensityLabel,
    },
  });

  for (const line of input.formLines) {
    const raceDate = new Date(TODAY);
    raceDate.setDate(raceDate.getDate() - line.daysAgo);
    await prisma.formEntry.create({
      data: {
        isSampleData: true,
        horseId: horse.id,
        raceDate,
        course: line.course,
        country: line.country,
        distanceFurlongs: line.distanceFurlongs,
        going: line.going,
        raceClass: line.raceClass,
        flatJumps: line.flatJumps,
        fieldSize: line.fieldSize,
        finishingPosition: line.finishingPosition,
        finishStatus: line.finishStatus,
        beatenDistanceLengths: line.beatenDistanceLengths,
        startingPriceDecimal: line.startingPriceDecimal,
        officialRating: line.officialRating,
        weightPounds: line.weightPounds,
        draw: line.draw,
        jockeyName: line.jockeyName,
        headgear: line.headgear,
        raceComment: line.raceComment,
        paceClassification: line.paceClassification,
      },
    });
  }

  return horse;
}

async function seedMarketPrices(
  runnerId: string,
  bookmakers: Bookmakers,
  opening: number,
  current: number
) {
  const now = new Date();
  const openTime = new Date(now.getTime() - 1000 * 60 * 60 * 20);

  await prisma.runnerMarketPrice.createMany({
    data: [
      {
        runnerId,
        bookmakerId: bookmakers.bet365.id,
        timestamp: openTime,
        winOddsDecimal: opening,
        isOpeningPrice: true,
      },
      {
        runnerId,
        bookmakerId: bookmakers.bet365.id,
        timestamp: now,
        winOddsDecimal: current,
      },
      {
        runnerId,
        bookmakerId: bookmakers.skyBet.id,
        timestamp: now,
        winOddsDecimal: Math.round((current + 0.25) * 100) / 100,
      },
      {
        runnerId,
        bookmakerId: bookmakers.betfairExchange.id,
        timestamp: now,
        winOddsDecimal: Math.round((current - 0.1) * 100) / 100,
      },
    ],
  });
}

async function seedPaceProfile(
  runnerId: string,
  role: PaceRole,
  values: {
    usualEarlyPosition: number;
    breaksQuicklyRate: number;
    slowStartRate: number;
    energyToObtainPositionIndex: number;
    positionChange3fTo2f: number;
    positionChange2fTo1f: number;
    relativeAccelerationIndex: number;
    finishingSpeedIndex: number;
    positionChangeFinalFurlong: number;
    weakensLateRate: number;
    staysOnStronglyRate: number;
  }
) {
  await prisma.runnerPaceProfile.create({
    data: {
      runnerId,
      projectedRole: role,
      usualEarlyPosition: values.usualEarlyPosition,
      breaksQuicklyRate: values.breaksQuicklyRate,
      slowStartRate: values.slowStartRate,
      energyToObtainPositionIndex: values.energyToObtainPositionIndex,
      positionChange3fTo2f: values.positionChange3fTo2f,
      positionChange2fTo1f: values.positionChange2fTo1f,
      relativeAccelerationIndex: values.relativeAccelerationIndex,
      finishingSpeedIndex: values.finishingSpeedIndex,
      positionChangeFinalFurlong: values.positionChangeFinalFurlong,
      weakensLateRate: values.weakensLateRate,
      staysOnStronglyRate: values.staysOnStronglyRate,
      competitionForLeadIndex: 0.5,
      pacePressureIndex: 0.5,
      paceCollapseProbability: 0.3,
    },
  });
}

async function seedUnconfiguredSnapshot(runnerId: string, placeBasisPlaces: number, bookmakerId: string) {
  await prisma.predictionSnapshot.create({
    data: {
      runnerId,
      snapshotType: SnapshotType.PRE_RACE,
      modelVersion: "unconfigured",
      placeBasisPlaces,
      placeBasisBookmakerId: bookmakerId,
      isLocked: true,
      // winProbability, placeProbability, modelConfidence, fairOddsDecimal,
      // marketImpliedProbability and valueEdge fields are intentionally left
      // null — Phase 1 ships no probability model.
    },
  });
}

async function seedAscotChase(importBatchId: string, bookmakers: Bookmakers) {
  const race = await prisma.race.create({
    data: {
      isSampleData: true,
      date: TODAY,
      raceTime: "14:35",
      racecourse: "Ascot (sample)",
      country: "GB",
      raceName: "SAMPLE Handicap Chase",
      raceType: "Handicap Chase",
      flatJumps: FlatJumps.JUMPS,
      surface: RaceSurface.TURF,
      distanceFurlongs: 24,
      distanceYards: 24 * 220,
      raceClass: 3,
      handicapType: HandicapType.HANDICAP,
      ageRestriction: "5yo+",
      numberOfRunners: 8,
      going: "Good to Soft",
      goingDescription: "Good to Soft, Soft in places",
      weatherSummary: "Overcast, light wind",
      temperatureCelsius: 14,
      prizeMoneyTotal: 25000,
      eachWayFraction: 0.2,
      bookmakerPlaces: 4,
      raceStatus: RaceStatus.SCHEDULED,
      resultStatus: ResultStatus.PENDING,
      importBatchId,
    },
  });

  await prisma.racePlaceTerms.createMany({
    data: [
      { raceId: race.id, bookmakerId: bookmakers.bet365.id, places: 4, eachWayFraction: 0.2 },
      {
        raceId: race.id,
        bookmakerId: bookmakers.skyBet.id,
        places: 5,
        eachWayFraction: 0.2,
        extraPlaces: true,
        terms: "Enhanced: 5 places if 12+ declared runners",
      },
      { raceId: race.id, bookmakerId: bookmakers.paddyPower.id, places: 4, eachWayFraction: 0.25 },
    ],
  });

  const runnersInput = [
    {
      name: "Fair Odds Fella",
      officialRating: 145,
      opening: 4.5,
      current: 3.75,
      favouriteRank: 1,
      role: PaceRole.PRONOUNCED_PACE,
    },
    { name: "Edge Of Dawn", officialRating: 142, opening: 5.0, current: 4.5, favouriteRank: 2, role: PaceRole.LEADER },
    {
      name: "Confidence Interval",
      officialRating: 140,
      opening: 6.5,
      current: 5.5,
      favouriteRank: 3,
      role: PaceRole.MIDDIVISION,
    },
    { name: "Prime Value", officialRating: 138, opening: 7.0, current: 6.0, favouriteRank: 4, role: PaceRole.HOLD_UP },
    {
      name: "Market Mover",
      officialRating: 135,
      opening: 9.0,
      current: 8.0,
      favouriteRank: 5,
      role: PaceRole.MIDDIVISION,
    },
    {
      name: "Northern Ledger",
      officialRating: 130,
      opening: 10.0,
      current: 9.0,
      favouriteRank: 6,
      role: PaceRole.HOLD_UP,
    },
    { name: "Quantum Leap", officialRating: 128, opening: 12.0, current: 11.0, favouriteRank: 7, role: PaceRole.LEADER },
    {
      name: "Each Way Eddie",
      officialRating: 125,
      opening: 17.0,
      current: 15.0,
      favouriteRank: 8,
      role: PaceRole.HOLD_UP,
    },
  ];

  for (const [index, r] of runnersInput.entries()) {
    const horse = await createHorseWithHistory({
      name: r.name,
      yearOfBirth: TODAY.getFullYear() - 8,
      sex: Sex.GELDING,
      trainerName: ["J. Sample", "A. Trainer", "M. Yard", "P. Stables"][index % 4],
      ownerName: "Sample Racing Partnership",
      sireName: "Sample Sire",
      damName: "Sample Dam",
      damsireName: "Sample Damsire",
      countryBred: "IRE",
      careerStarts: 18 + index,
      startsLast12Months: 5,
      evidenceDensityScore: 0.55 + index * 0.03,
      evidenceDensityLabel: index < 3 ? "HIGH" : "MODERATE",
      formLines: [
        {
          daysAgo: 28,
          course: "Cheltenham (sample)",
          country: "GB",
          distanceFurlongs: 20,
          going: "Soft",
          raceClass: 3,
          flatJumps: FlatJumps.JUMPS,
          fieldSize: 9,
          finishingPosition: (index % 5) + 1,
          finishStatus: "RAN",
          beatenDistanceLengths: (index % 5) * 1.5,
          startingPriceDecimal: r.opening,
          officialRating: r.officialRating - 2,
          weightPounds: 154,
          draw: null,
          jockeyName: "R. Rider",
          headgear: null,
          raceComment: "Travelled well, kept on under pressure.",
          paceClassification: "Prominent",
        },
        {
          daysAgo: 63,
          course: "Kempton (sample)",
          country: "GB",
          distanceFurlongs: 22,
          going: "Good to Soft",
          raceClass: 3,
          flatJumps: FlatJumps.JUMPS,
          fieldSize: 11,
          finishingPosition: ((index + 2) % 6) + 1,
          finishStatus: "RAN",
          beatenDistanceLengths: ((index + 2) % 6) * 1.2,
          startingPriceDecimal: r.opening + 1,
          officialRating: r.officialRating - 4,
          weightPounds: 152,
          draw: null,
          jockeyName: "R. Rider",
          headgear: null,
          raceComment: "Held up, stayed on in the closing stages.",
          paceClassification: "Held up",
        },
      ],
    });

    const runner = await prisma.runner.create({
      data: {
        isSampleData: true,
        raceId: race.id,
        horseId: horse.id,
        clothNumber: index + 1,
        ageAtRace: 8,
        weightLbsTotal: 154 - index,
        officialRating: r.officialRating,
        currentOddsDecimal: r.current,
        openingOddsDecimal: r.opening,
        favouriteRank: r.favouriteRank,
        jockeyName: "R. Rider",
        trainerName: ["J. Sample", "A. Trainer", "M. Yard", "P. Stables"][index % 4],
      },
    });

    await seedMarketPrices(runner.id, bookmakers, r.opening, r.current);
    await seedPaceProfile(runner.id, r.role, {
      usualEarlyPosition: 3 + (index % 4),
      breaksQuicklyRate: 0.6,
      slowStartRate: 0.15,
      energyToObtainPositionIndex: 0.4,
      positionChange3fTo2f: 0.5 - index * 0.05,
      positionChange2fTo1f: 0.3 - index * 0.02,
      relativeAccelerationIndex: 0.5,
      finishingSpeedIndex: 0.5 + (index % 3) * 0.05,
      positionChangeFinalFurlong: 0.2,
      weakensLateRate: 0.2,
      staysOnStronglyRate: 0.5,
    });
    await seedUnconfiguredSnapshot(runner.id, 4, bookmakers.bet365.id);
  }
}

async function seedNewmarketNoviceStakes(importBatchId: string, bookmakers: Bookmakers) {
  const race = await prisma.race.create({
    data: {
      isSampleData: true,
      date: TODAY,
      raceTime: "15:10",
      racecourse: "Newmarket (sample)",
      country: "GB",
      raceName: "SAMPLE Novice Stakes",
      raceType: "Novice Stakes",
      flatJumps: FlatJumps.FLAT,
      surface: RaceSurface.TURF,
      distanceFurlongs: 8,
      distanceYards: 8 * 220,
      raceClass: 4,
      handicapType: HandicapType.NON_HANDICAP,
      ageRestriction: "3yo+",
      numberOfRunners: 6,
      going: "Good",
      goingDescription: "Good, Good to Firm in places",
      weatherSummary: "Sunny intervals",
      temperatureCelsius: 19,
      prizeMoneyTotal: 9000,
      eachWayFraction: 0.2,
      bookmakerPlaces: 3,
      raceStatus: RaceStatus.SCHEDULED,
      resultStatus: ResultStatus.PENDING,
      importBatchId,
    },
  });

  await prisma.racePlaceTerms.createMany({
    data: [
      { raceId: race.id, bookmakerId: bookmakers.bet365.id, places: 3, eachWayFraction: 0.2 },
      { raceId: race.id, bookmakerId: bookmakers.skyBet.id, places: 3, eachWayFraction: 0.2 },
    ],
  });

  const runnersInput = [
    { name: "Data Point", draw: 3, opening: 3.5, current: 3.0, favouriteRank: 1, role: PaceRole.LEADER },
    { name: "Bayes Theorem", draw: 1, opening: 6.0, current: 5.0, favouriteRank: 2, role: PaceRole.PRONOUNCED_PACE },
    { name: "Sample Size", draw: 6, opening: 8.0, current: 7.0, favouriteRank: 3, role: PaceRole.MIDDIVISION },
    { name: "Night Shift", draw: 2, opening: 10.0, current: 9.0, favouriteRank: 4, role: PaceRole.HOLD_UP },
    { name: "Chalk Talk", draw: 4, opening: 14.0, current: 12.0, favouriteRank: 5, role: PaceRole.MIDDIVISION },
    { name: "Long Shot Larry", draw: 5, opening: 29.0, current: 26.0, favouriteRank: 6, role: PaceRole.HOLD_UP },
  ];

  for (const [index, r] of runnersInput.entries()) {
    const horse = await createHorseWithHistory({
      name: r.name,
      yearOfBirth: TODAY.getFullYear() - 3,
      sex: index % 2 === 0 ? Sex.COLT : Sex.FILLY,
      trainerName: ["S. Newmarket", "T. Handler"][index % 2],
      ownerName: "Sample Bloodstock Ltd",
      sireName: "Sample Speed",
      damName: "Sample Grace",
      damsireName: "Sample Legacy",
      countryBred: "GB",
      careerStarts: 2 + (index % 3),
      startsLast12Months: 2 + (index % 3),
      evidenceDensityScore: 0.15 + index * 0.05,
      evidenceDensityLabel: index === 0 ? "MODERATE" : "LOW",
      formLines:
        index === 0
          ? [
              {
                daysAgo: 21,
                course: "Goodwood (sample)",
                country: "GB",
                distanceFurlongs: 7,
                going: "Good",
                raceClass: 5,
                flatJumps: FlatJumps.FLAT,
                fieldSize: 8,
                finishingPosition: 1,
                finishStatus: "RAN",
                beatenDistanceLengths: 0,
                startingPriceDecimal: 4.0,
                officialRating: 78,
                weightPounds: 126,
                draw: 4,
                jockeyName: "L. Apprentice",
                headgear: null,
                raceComment: "Led inside the final furlong, ran on well.",
                paceClassification: "Prominent",
              },
            ]
          : [
              {
                daysAgo: 35,
                course: "Windsor (sample)",
                country: "GB",
                distanceFurlongs: 8,
                going: "Good to Firm",
                raceClass: 5,
                flatJumps: FlatJumps.FLAT,
                fieldSize: 10,
                finishingPosition: 4 + (index % 4),
                finishStatus: "RAN",
                beatenDistanceLengths: 3 + index,
                startingPriceDecimal: r.opening,
                officialRating: 68,
                weightPounds: 124,
                draw: r.draw,
                jockeyName: "L. Apprentice",
                headgear: null,
                raceComment: "Green and needed the experience.",
                paceClassification: "Held up",
              },
            ],
    });

    const runner = await prisma.runner.create({
      data: {
        isSampleData: true,
        raceId: race.id,
        horseId: horse.id,
        clothNumber: index + 1,
        draw: r.draw,
        ageAtRace: 3,
        weightLbsTotal: 126,
        currentOddsDecimal: r.current,
        openingOddsDecimal: r.opening,
        favouriteRank: r.favouriteRank,
        jockeyName: "L. Apprentice",
        trainerName: ["S. Newmarket", "T. Handler"][index % 2],
      },
    });

    await seedMarketPrices(runner.id, bookmakers, r.opening, r.current);
    await seedPaceProfile(runner.id, r.role, {
      usualEarlyPosition: 2 + (index % 4),
      breaksQuicklyRate: 0.55,
      slowStartRate: 0.2,
      energyToObtainPositionIndex: 0.45,
      positionChange3fTo2f: 0.3,
      positionChange2fTo1f: 0.25,
      relativeAccelerationIndex: 0.5,
      finishingSpeedIndex: 0.5,
      positionChangeFinalFurlong: 0.15,
      weakensLateRate: 0.25,
      staysOnStronglyRate: 0.4,
    });
    await seedUnconfiguredSnapshot(runner.id, 3, bookmakers.bet365.id);
  }
}

async function seedCheltenhamResultedRace(importBatchId: string, bookmakers: Bookmakers) {
  const race = await prisma.race.create({
    data: {
      isSampleData: true,
      date: YESTERDAY,
      raceTime: "14:00",
      racecourse: "Cheltenham (sample)",
      country: "GB",
      raceName: "SAMPLE Handicap Hurdle",
      raceType: "Handicap Hurdle",
      flatJumps: FlatJumps.JUMPS,
      surface: RaceSurface.TURF,
      distanceFurlongs: 20,
      distanceYards: 20 * 220,
      raceClass: 2,
      handicapType: HandicapType.HANDICAP,
      ageRestriction: "4yo+",
      numberOfRunners: 7,
      going: "Soft",
      goingDescription: "Soft, Heavy in places",
      weatherSummary: "Rain",
      temperatureCelsius: 11,
      prizeMoneyTotal: 40000,
      eachWayFraction: 0.25,
      bookmakerPlaces: 4,
      raceStatus: RaceStatus.RESULTED,
      resultStatus: ResultStatus.CONFIRMED,
      importBatchId,
    },
  });

  await prisma.racePlaceTerms.createMany({
    data: [
      { raceId: race.id, bookmakerId: bookmakers.bet365.id, places: 4, eachWayFraction: 0.25 },
      { raceId: race.id, bookmakerId: bookmakers.skyBet.id, places: 4, eachWayFraction: 0.25 },
    ],
  });

  const runnersInput = [
    {
      name: "The Closer",
      officialRating: 150,
      startingPrice: 3.25,
      closing: 3.0,
      finishingPosition: 1,
      finishStatus: "WON",
      beaten: 0,
      tags: [ObservationTagType.TRAVELLED_STRONGLY, ObservationTagType.STAYED_ON_STRONGLY, ObservationTagType.CLEAN_TEST_OF_THESIS],
      freeText: "Travelled powerfully throughout and asserted from two out. A fair result.",
    },
    {
      name: "Southbound",
      officialRating: 148,
      startingPrice: 5.0,
      closing: 4.5,
      finishingPosition: 2,
      finishStatus: "RAN",
      beaten: 1.75,
      tags: [ObservationTagType.RACED_PROMINENTLY, ObservationTagType.WEAKENED_FINAL_FURLONG],
      freeText: "Went down fighting, edged out close home.",
    },
    {
      name: "Winning Margin",
      officialRating: 146,
      startingPrice: 8.0,
      closing: 9.0,
      finishingPosition: 3,
      finishStatus: "RAN",
      beaten: 4.5,
      tags: [ObservationTagType.HELD_UP, ObservationTagType.STRONG_TRANSITION],
      freeText: "Strong late progress from off the pace, may find one better next time.",
    },
    {
      name: "Course Record",
      officialRating: 144,
      startingPrice: 7.0,
      closing: 6.5,
      finishingPosition: 4,
      finishStatus: "RAN",
      beaten: 6.0,
      tags: [ObservationTagType.TRAPPED_WIDE, ObservationTagType.BAD_RIDE_POSITIONING],
      freeText: "Never got a clear passage, race not fully representative of ability.",
    },
    {
      name: "Autumn Ledger",
      officialRating: 140,
      startingPrice: 12.0,
      closing: 13.0,
      finishingPosition: 5,
      finishStatus: "RAN",
      beaten: 9.0,
      tags: [ObservationTagType.SLOW_BREAK, ObservationTagType.LOST_GROUND_SEEKING_RUN],
      freeText: null,
    },
    {
      name: "Steady Gallop",
      officialRating: 137,
      startingPrice: 15.0,
      closing: 17.0,
      finishingPosition: 6,
      finishStatus: "RAN",
      beaten: 14.0,
      tags: [ObservationTagType.RACE_NOT_REPRESENTATIVE],
      freeText: "Never travelled, reportedly coughing post-race.",
    },
    {
      name: "Silent Analyst",
      officialRating: 143,
      startingPrice: 9.0,
      closing: 8.5,
      finishingPosition: null,
      finishStatus: "PU",
      beaten: null,
      tags: [ObservationTagType.PACE_COLLAPSE_HURT],
      freeText: "Pulled up after a strong pace collapsed the race in the home straight.",
    },
  ];

  for (const [index, r] of runnersInput.entries()) {
    const horse = await createHorseWithHistory({
      name: r.name,
      yearOfBirth: TODAY.getFullYear() - 7,
      sex: Sex.GELDING,
      trainerName: ["W. Cotswold", "H. Hurdler"][index % 2],
      ownerName: "Sample Syndicate",
      sireName: "Sample Sire II",
      damName: "Sample Dam II",
      damsireName: "Sample Damsire II",
      countryBred: "IRE",
      careerStarts: 22 + index,
      startsLast12Months: 6,
      evidenceDensityScore: 0.65,
      evidenceDensityLabel: "HIGH",
      formLines: [
        {
          daysAgo: 49,
          course: "Sandown (sample)",
          country: "GB",
          distanceFurlongs: 18,
          going: "Soft",
          raceClass: 2,
          flatJumps: FlatJumps.JUMPS,
          fieldSize: 10,
          finishingPosition: ((index + 1) % 5) + 1,
          finishStatus: "RAN",
          beatenDistanceLengths: ((index + 1) % 5) * 2,
          startingPriceDecimal: r.startingPrice,
          officialRating: r.officialRating - 3,
          weightPounds: 158,
          draw: null,
          jockeyName: "K. Hurdles",
          headgear: null,
          raceComment: "Ran on into places having been outpaced early.",
          paceClassification: "Held up",
        },
      ],
    });

    const runner = await prisma.runner.create({
      data: {
        isSampleData: true,
        raceId: race.id,
        horseId: horse.id,
        clothNumber: index + 1,
        ageAtRace: 7,
        weightLbsTotal: 158 - index,
        officialRating: r.officialRating,
        currentOddsDecimal: r.startingPrice,
        openingOddsDecimal: r.startingPrice + 1,
        startingPriceDecimal: r.startingPrice,
        favouriteRank: index + 1,
        jockeyName: "K. Hurdles",
        trainerName: ["W. Cotswold", "H. Hurdler"][index % 2],
        nonRunner: false,
      },
    });

    await seedMarketPrices(runner.id, bookmakers, r.startingPrice + 1, r.startingPrice);
    await seedPaceProfile(runner.id, index % 2 === 0 ? PaceRole.PRONOUNCED_PACE : PaceRole.HOLD_UP, {
      usualEarlyPosition: 2 + (index % 5),
      breaksQuicklyRate: 0.5,
      slowStartRate: 0.2,
      energyToObtainPositionIndex: 0.5,
      positionChange3fTo2f: 0.3,
      positionChange2fTo1f: 0.2,
      relativeAccelerationIndex: 0.45,
      finishingSpeedIndex: 0.5,
      positionChangeFinalFurlong: 0.1,
      weakensLateRate: 0.3,
      staysOnStronglyRate: 0.4,
    });

    await seedUnconfiguredSnapshot(runner.id, 4, bookmakers.bet365.id);

    const result = await prisma.resultEntry.create({
      data: {
        runnerId: runner.id,
        finishingPosition: r.finishingPosition,
        finishStatus: r.finishStatus,
        beatenDistanceLengths: r.beaten,
        startingPriceDecimal: r.startingPrice,
        closingOddsDecimal: r.closing,
        placeOutcome: r.finishingPosition !== null ? r.finishingPosition <= 4 : false,
        profitLossWinStake: r.finishingPosition === 1 ? r.startingPrice - 1 : -1,
        profitLossEachWayStake:
          r.finishingPosition === 1
            ? r.startingPrice - 1 + ((r.startingPrice - 1) * 0.25 + 1) - 1
            : r.finishingPosition !== null && r.finishingPosition <= 4
              ? (r.startingPrice - 1) * 0.25 - 1
              : -2,
        resultStatus: ResultStatus.CONFIRMED,
      },
    });

    for (const tag of r.tags) {
      await prisma.runnerObservation.create({
        data: { resultId: result.id, tag },
      });
    }
    if (r.freeText) {
      await prisma.runnerObservation.create({
        data: { resultId: result.id, freeText: r.freeText },
      });
    }
  }
}

main()
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });

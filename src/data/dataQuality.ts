/**
 * Data Quality Dashboard queries (Phase 3A).
 *
 * Read-only aggregates over the same tables the Python data-infrastructure
 * package writes to (DataProvenance, EntityResolutionQueueItem, ImportBatch,
 * ...) plus the core Race/Runner/FormEntry tables. Nothing here is cached —
 * every figure is recomputed live from current rows, same as the Phase 2
 * model dashboard.
 */
import "server-only";

import { prisma } from "@/database/client";

export interface YearBreakdown {
  year: number;
  raceCount: number;
  runnerCount: number;
}

export interface ProviderBreakdown {
  provider: string;
  raceCount: number;
}

export interface SourceTypeBreakdown {
  sourceType: string;
  raceCount: number;
}

export interface DataQualityReport {
  totalRaces: number;
  totalRunners: number;
  dateRange: { earliest: Date | null; latest: Date | null };
  courseCoverage: number;
  sourceTypeCounts: SourceTypeBreakdown[];
  missingness: {
    officialRatingPct: number | null;
    drawPct: number | null;
    startingPriceDecimalPct: number | null;
    goingPct: number | null;
    positionalDataPct: number | null;
    sectionalDataPct: number | null;
  };
  duplicateRate: number | null;
  unresolvedEntityCount: number;
  byYear: YearBreakdown[];
  byProvider: ProviderBreakdown[];
  warnings: string[];
}

function pct(missing: number, total: number): number | null {
  return total > 0 ? Math.round((missing / total) * 1000) / 10 : null;
}

export async function getDataQualityReport(): Promise<DataQualityReport> {
  const [
    totalRaces,
    totalRunners,
    dateAgg,
    distinctCourses,
    sourceTypeGroups,
    missingOfficialRating,
    missingDraw,
    missingStartingPrice,
    missingGoing,
    totalFormEntries,
    formWithoutPositional,
    formWithoutSectional,
    importBatchAgg,
    unresolvedEntityCount,
    providerGroups,
    raceIdDates,
    runnersByRace,
  ] = await Promise.all([
    prisma.race.count(),
    prisma.runner.count(),
    prisma.race.aggregate({ _min: { date: true }, _max: { date: true } }),
    prisma.race.findMany({ select: { racecourse: true }, distinct: ["racecourse"] }),
    prisma.race.groupBy({ by: ["sourceType"], _count: { _all: true } }),
    prisma.runner.count({ where: { officialRating: null } }),
    prisma.runner.count({ where: { draw: null } }),
    prisma.runner.count({ where: { startingPriceDecimal: null } }),
    prisma.race.count({ where: { going: null } }),
    prisma.formEntry.count(),
    prisma.formEntry.count({ where: { hasPositionalData: false } }),
    prisma.formEntry.count({ where: { hasSectionalData: false } }),
    prisma.importBatch.aggregate({ _sum: { duplicateRows: true, totalRows: true } }),
    prisma.entityResolutionQueueItem.count({ where: { status: "PENDING" } }),
    prisma.dataProvenance.groupBy({
      by: ["provider"],
      where: { entityType: "Race", dataDomain: "RACE_CARD" },
      _count: { _all: true },
    }),
    prisma.race.findMany({ select: { id: true, date: true } }),
    prisma.runner.groupBy({ by: ["raceId"], _count: { _all: true } }),
  ]);

  const runnerCountByRaceId = new Map(runnersByRace.map((r) => [r.raceId, r._count._all]));
  const byYearMap = new Map<number, { raceCount: number; runnerCount: number }>();
  for (const race of raceIdDates) {
    const year = race.date.getFullYear();
    const existing = byYearMap.get(year) ?? { raceCount: 0, runnerCount: 0 };
    existing.raceCount += 1;
    existing.runnerCount += runnerCountByRaceId.get(race.id) ?? 0;
    byYearMap.set(year, existing);
  }

  const byYear: YearBreakdown[] = Array.from(byYearMap.entries())
    .map(([year, v]) => ({ year, ...v }))
    .sort((a, b) => a.year - b.year);

  const byProvider: ProviderBreakdown[] = providerGroups
    .map((g) => ({ provider: g.provider, raceCount: g._count._all }))
    .sort((a, b) => b.raceCount - a.raceCount);

  const sourceTypeCounts: SourceTypeBreakdown[] = sourceTypeGroups.map((g) => ({
    sourceType: g.sourceType,
    raceCount: g._count._all,
  }));

  const duplicateRows = importBatchAgg._sum.duplicateRows ?? 0;
  const totalImportRows = importBatchAgg._sum.totalRows ?? 0;
  const duplicateRate = totalImportRows > 0 ? Math.round((duplicateRows / totalImportRows) * 1000) / 10 : null;

  const missingness = {
    officialRatingPct: pct(missingOfficialRating, totalRunners),
    drawPct: pct(missingDraw, totalRunners),
    startingPriceDecimalPct: pct(missingStartingPrice, totalRunners),
    goingPct: pct(missingGoing, totalRaces),
    positionalDataPct: pct(formWithoutPositional, totalFormEntries),
    sectionalDataPct: pct(formWithoutSectional, totalFormEntries),
  };

  const warnings: string[] = [];
  if (missingness.officialRatingPct !== null && missingness.officialRatingPct > 50) {
    warnings.push(`${missingness.officialRatingPct}% of runners are missing an official rating.`);
  }
  if (missingness.startingPriceDecimalPct !== null && missingness.startingPriceDecimalPct > 50) {
    warnings.push(`${missingness.startingPriceDecimalPct}% of runners are missing a starting price.`);
  }
  if (duplicateRate !== null && duplicateRate > 5) {
    warnings.push(`Duplicate rate across imports is ${duplicateRate}% — check provider dedup keys.`);
  }
  if (unresolvedEntityCount > 20) {
    warnings.push(`${unresolvedEntityCount} entity-resolution items are still pending manual review.`);
  }
  if (byYear.length > 1) {
    const maxRaceCount = Math.max(...byYear.map((y) => y.raceCount));
    for (const y of byYear) {
      if (y.raceCount < maxRaceCount * 0.1) {
        warnings.push(`${y.year} has unusually low race coverage (${y.raceCount} races) relative to other years.`);
      }
    }
  }
  const nonRealCount = sourceTypeCounts
    .filter((s) => s.sourceType !== "REAL")
    .reduce((sum, s) => sum + s.raceCount, 0);
  if (nonRealCount > 0 && sourceTypeCounts.every((s) => s.sourceType !== "REAL")) {
    warnings.push("No REAL races are present yet — every race in this database is SYNTHETIC or SAMPLE data.");
  }

  return {
    totalRaces,
    totalRunners,
    dateRange: { earliest: dateAgg._min.date, latest: dateAgg._max.date },
    courseCoverage: distinctCourses.length,
    sourceTypeCounts,
    missingness,
    duplicateRate,
    unresolvedEntityCount,
    byYear,
    byProvider,
    warnings,
  };
}

// ---------------------------------------------------------------------------
// Phase 3C: Feature Availability Matrix
//
// Free datasets are often missing fields a licensed feed would carry
// (sectionals, positional data, pedigree, official ratings). This reports
// exactly what % of rows actually carry each field — never inferred,
// never treated as 0 when it has racing meaning — so a model's feature
// profile (CORE_FREE_MODEL / ENRICHED_FREE_MODEL / FULL_MODEL) can be
// chosen from real evidence, not assumption. See MODEL_CARD.md.
// ---------------------------------------------------------------------------

export interface FeatureAvailabilityRow {
  feature: string;
  availablePct: number | null;
  sampleSize: number;
}

export async function getFeatureAvailabilityMatrix(): Promise<FeatureAvailabilityRow[]> {
  const [
    totalRunners,
    totalRaces,
    totalFormEntries,
    horsesWithFormEntry,
    totalHorses,
    officialRatingPresent,
    weightPresent,
    classPresent,
    coursePresent,
    goingPresent,
    drawPresent,
    jockeyPresent,
    trainerPresent,
    runnersWithSp,
    runnersWithMarketPrice,
    formCommentsPresent,
    formWithSectionals,
    formWithPositional,
    headgearPresent,
    horsesWithSire,
  ] = await Promise.all([
    prisma.runner.count(),
    prisma.race.count(),
    prisma.formEntry.count(),
    prisma.formEntry.findMany({ select: { horseId: true }, distinct: ["horseId"] }).then((r) => r.length),
    prisma.horse.count(),
    prisma.runner.count({ where: { officialRating: { not: null } } }),
    prisma.runner.count({ where: { weightLbsTotal: { not: null } } }),
    prisma.race.count({ where: { raceClass: { not: null } } }),
    prisma.race.count({ where: { NOT: { racecourse: "" } } }),
    prisma.race.count({ where: { going: { not: null } } }),
    prisma.runner.count({ where: { draw: { not: null } } }),
    prisma.runner.count({ where: { jockeyName: { not: null } } }),
    prisma.runner.count({ where: { trainerName: { not: null } } }),
    prisma.resultEntry.count({ where: { startingPriceDecimal: { not: null } } }),
    prisma.runnerMarketPrice.findMany({ select: { runnerId: true }, distinct: ["runnerId"] }).then((r) => r.length),
    prisma.formEntry.count({ where: { raceComment: { not: null } } }),
    prisma.formEntry.count({ where: { hasSectionalData: true } }),
    prisma.formEntry.count({ where: { hasPositionalData: true } }),
    prisma.runner.count({ where: { headgear: { not: null } } }),
    prisma.horse.count({ where: { sireName: { not: null } } }),
  ]);

  const runnersWithOddsOrSp = Math.max(runnersWithSp, runnersWithMarketPrice);

  const pct = (numerator: number, denominator: number): number | null =>
    denominator > 0 ? Math.round((numerator / denominator) * 1000) / 10 : null;

  return [
    { feature: "Current form (any FormEntry)", availablePct: pct(horsesWithFormEntry, totalHorses), sampleSize: totalHorses },
    { feature: "Official rating", availablePct: pct(officialRatingPresent, totalRunners), sampleSize: totalRunners },
    { feature: "Weight", availablePct: pct(weightPresent, totalRunners), sampleSize: totalRunners },
    { feature: "Class", availablePct: pct(classPresent, totalRaces), sampleSize: totalRaces },
    { feature: "Course", availablePct: pct(coursePresent, totalRaces), sampleSize: totalRaces },
    // distanceFurlongs is a required (non-nullable) field — always 100% by construction.
    { feature: "Distance", availablePct: pct(totalRaces, totalRaces), sampleSize: totalRaces },
    { feature: "Going", availablePct: pct(goingPresent, totalRaces), sampleSize: totalRaces },
    { feature: "Draw", availablePct: pct(drawPresent, totalRunners), sampleSize: totalRunners },
    { feature: "Jockey", availablePct: pct(jockeyPresent, totalRunners), sampleSize: totalRunners },
    { feature: "Trainer", availablePct: pct(trainerPresent, totalRunners), sampleSize: totalRunners },
    { feature: "Odds / SP", availablePct: pct(runnersWithOddsOrSp, totalRunners), sampleSize: totalRunners },
    { feature: "Race comments", availablePct: pct(formCommentsPresent, totalFormEntries), sampleSize: totalFormEntries },
    { feature: "Sectionals", availablePct: pct(formWithSectionals, totalFormEntries), sampleSize: totalFormEntries },
    { feature: "Positional data", availablePct: pct(formWithPositional, totalFormEntries), sampleSize: totalFormEntries },
    { feature: "Headgear", availablePct: pct(headgearPresent, totalRunners), sampleSize: totalRunners },
    { feature: "Pedigree (sire)", availablePct: pct(horsesWithSire, totalHorses), sampleSize: totalHorses },
  ];
}

"use server";

import { revalidatePath } from "next/cache";

import { ObservationTagType, RaceStatus, ResultStatus } from "@/generated/prisma/enums";
import { prisma } from "@/database/client";
import { computeRunnerResult } from "@/results/settlement";
import type { EachWayTerms } from "@/value/place";
import type { ResultActionState } from "@/actions/state";

const OBSERVATION_TAG_VALUES = new Set(Object.values(ObservationTagType));

export async function submitRaceResultsAction(
  _prevState: ResultActionState,
  formData: FormData
): Promise<ResultActionState> {
  const raceId = formData.get("raceId");
  if (typeof raceId !== "string" || !raceId) {
    return { status: "error", message: "Missing raceId." };
  }

  const race = await prisma.race.findUnique({
    where: { id: raceId },
    include: { runners: true },
  });
  if (!race) {
    return { status: "error", message: "Race not found." };
  }

  const placeTerms: EachWayTerms | null =
    race.bookmakerPlaces && race.eachWayFraction
      ? { places: race.bookmakerPlaces, eachWayFraction: race.eachWayFraction }
      : null;

  for (const runner of race.runners) {
    const positionRaw = formData.get(`position_${runner.id}`);
    const statusRaw = formData.get(`status_${runner.id}`);
    const spRaw = formData.get(`sp_${runner.id}`);
    const closingRaw = formData.get(`closing_${runner.id}`);
    const freeText = formData.get(`freetext_${runner.id}`);
    const tags = formData.getAll(`tags_${runner.id}`).filter(
      (t): t is string => typeof t === "string" && OBSERVATION_TAG_VALUES.has(t as ObservationTagType)
    );

    const finishingPosition =
      typeof positionRaw === "string" && positionRaw.trim() !== "" ? Number(positionRaw) : null;
    const finishStatus = typeof statusRaw === "string" && statusRaw ? statusRaw : null;
    const startingPriceDecimal =
      typeof spRaw === "string" && spRaw.trim() !== "" ? Number(spRaw) : (runner.currentOddsDecimal ?? null);
    const closingOddsDecimal =
      typeof closingRaw === "string" && closingRaw.trim() !== "" ? Number(closingRaw) : null;

    // Skip runners with no result data submitted at all.
    if (finishingPosition === null && !finishStatus && startingPriceDecimal === null) continue;

    const computed = computeRunnerResult({
      finishingPosition,
      finishStatus,
      startingPriceDecimal,
      placeTerms,
    });

    const result = await prisma.resultEntry.upsert({
      where: { runnerId: runner.id },
      update: {
        finishingPosition,
        finishStatus,
        startingPriceDecimal,
        closingOddsDecimal,
        placeOutcome: computed.placeOutcome,
        profitLossWinStake: computed.profitLossWinStake,
        profitLossEachWayStake: computed.profitLossEachWayStake,
        resultStatus: ResultStatus.CONFIRMED,
      },
      create: {
        runnerId: runner.id,
        finishingPosition,
        finishStatus,
        startingPriceDecimal,
        closingOddsDecimal,
        placeOutcome: computed.placeOutcome,
        profitLossWinStake: computed.profitLossWinStake,
        profitLossEachWayStake: computed.profitLossEachWayStake,
        resultStatus: ResultStatus.CONFIRMED,
      },
    });

    await prisma.runnerObservation.deleteMany({ where: { resultId: result.id } });
    for (const tag of tags) {
      await prisma.runnerObservation.create({
        data: { resultId: result.id, tag: tag as ObservationTagType },
      });
    }
    if (typeof freeText === "string" && freeText.trim()) {
      await prisma.runnerObservation.create({
        data: { resultId: result.id, freeText: freeText.trim() },
      });
    }
  }

  await prisma.race.update({
    where: { id: raceId },
    data: { raceStatus: RaceStatus.RESULTED, resultStatus: ResultStatus.CONFIRMED },
  });

  revalidatePath("/results");
  revalidatePath(`/results/${raceId}`);
  revalidatePath("/dashboard");

  return { status: "success", message: "Results saved." };
}

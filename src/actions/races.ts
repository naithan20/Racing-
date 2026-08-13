"use server";

import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";

import { FlatJumps, HandicapType, ImportSourceType, RaceSurface } from "@/generated/prisma/enums";
import { RaceImportSchema } from "@/data/importSchema";
import { importRaces } from "@/data/importRaces";
import type { CreateRaceActionState } from "@/actions/state";

/**
 * Quick-entry runner line format, one horse per line:
 *   Horse Name | Trainer | Jockey | OR | Odds (decimal) | Draw
 * Only Horse Name is required; trailing fields may be left blank.
 */
function parseRunnerLines(text: string) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [horseName, trainerName, jockeyName, officialRating, currentOddsDecimal, draw] = line
        .split("|")
        .map((part) => part.trim());
      return {
        horseName,
        trainerName: trainerName || undefined,
        jockeyName: jockeyName || undefined,
        officialRating: officialRating ? Number(officialRating) : undefined,
        currentOddsDecimal: currentOddsDecimal ? Number(currentOddsDecimal) : undefined,
        draw: draw ? Number(draw) : undefined,
      };
    })
    .filter((r) => r.horseName);
}

export async function createRaceAction(
  _prevState: CreateRaceActionState,
  formData: FormData
): Promise<CreateRaceActionState> {
  const get = (key: string) => (formData.get(key)?.toString().trim() ?? "") || undefined;

  const runnerLines = get("runnerLines") ?? "";
  const runners = parseRunnerLines(runnerLines);
  if (runners.length === 0) {
    return { status: "error", message: "Add at least one runner (one per line)." };
  }

  const candidate = {
    raceDate: get("raceDate"),
    raceTime: get("raceTime"),
    racecourse: get("racecourse"),
    country: get("country"),
    raceName: get("raceName"),
    flatJumps: get("flatJumps") as FlatJumps | undefined,
    surface: get("surface") as RaceSurface | undefined,
    distanceFurlongs: get("distanceFurlongs") ? Number(get("distanceFurlongs")) : undefined,
    raceClass: get("raceClass") ? Number(get("raceClass")) : undefined,
    gradeGroup: get("gradeGroup"),
    handicapType: get("handicapType") as HandicapType | undefined,
    ageRestriction: get("ageRestriction"),
    sexRestriction: get("sexRestriction"),
    numberOfRunners: runners.length,
    going: get("going"),
    eachWayFraction: get("eachWayFraction") ? Number(get("eachWayFraction")) : undefined,
    bookmakerPlaces: get("bookmakerPlaces") ? Number(get("bookmakerPlaces")) : undefined,
    runners,
  };

  const validation = RaceImportSchema.safeParse(candidate);
  if (!validation.success) {
    const message = validation.error.issues.map((i) => `${i.path.join(".")}: ${i.message}`).join("; ");
    return { status: "error", message };
  }

  const result = await importRaces([validation.data], { sourceType: ImportSourceType.MANUAL });

  revalidatePath("/races");
  const race = await import("@/database/client").then(({ prisma }) =>
    prisma.race.findFirst({ where: { importBatchId: result.importBatchId }, orderBy: { createdAt: "desc" } })
  );

  if (race) redirect(`/races/${race.id}`);
  redirect("/races");
}

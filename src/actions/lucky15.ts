"use server";

import { revalidatePath } from "next/cache";

import { prisma } from "@/database/client";
import { FlatJumps } from "@/generated/prisma/enums";
import type { Lucky15ActionState } from "@/actions/state";

export async function createLucky15SlipAction(
  _prevState: Lucky15ActionState,
  formData: FormData
): Promise<Lucky15ActionState> {
  const runnerIds = formData.getAll("runnerIds").filter((v): v is string => typeof v === "string");
  if (runnerIds.length !== 4) {
    return {
      status: "error",
      message: `Lucky 15 requires exactly 4 legs (${runnerIds.length} selected). This is a data-structure placeholder — leg selection is not yet optimised.`,
    };
  }

  const get = (key: string) => formData.get(key)?.toString().trim() || undefined;
  const numeric = (key: string) => {
    const v = get(key);
    return v ? Number(v) : undefined;
  };

  const slip = await prisma.lucky15Slip.create({
    data: {
      name: get("name") ?? `Lucky 15 — ${new Date().toISOString().slice(0, 10)}`,
      date: new Date(),
      minOddsDecimal: numeric("minOddsDecimal"),
      maxOddsDecimal: numeric("maxOddsDecimal"),
      minConfidence: numeric("minConfidence"),
      minPlaceEdge: numeric("minPlaceEdge"),
      minRunners: numeric("minRunners"),
      enhancedPlacesOnly: formData.get("enhancedPlacesOnly") === "on",
      flatJumpsFilter: (get("flatJumpsFilter") as FlatJumps | undefined) ?? undefined,
      countryFilter: get("countryFilter"),
      bookmakerId: get("bookmakerId"),
      legs: {
        create: runnerIds.map((runnerId, index) => ({
          runnerId,
          sortOrder: index,
          rationale:
            "Placeholder selection — Phase 2 will rank legs by expected value, place probability, confidence and diversification rather than raw win probability.",
        })),
      },
    },
  });

  revalidatePath("/lucky15");

  return { status: "success", message: `Saved Lucky 15 slip "${slip.name}".` };
}

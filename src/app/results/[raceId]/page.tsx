import { notFound } from "next/navigation";
import Link from "next/link";

import { getRaceForResultEntry } from "@/data/queries";
import { ResultEntryForm, type ResultRunnerInput } from "@/components/results/ResultEntryForm";
import type { ObservationTagType } from "@/generated/prisma/enums";

export default async function ResultEntryPage({ params }: PageProps<"/results/[raceId]">) {
  const { raceId } = await params;
  const race = await getRaceForResultEntry(raceId);
  if (!race) notFound();

  const runners: ResultRunnerInput[] = race.runners.map((runner) => ({
    runnerId: runner.id,
    horseName: runner.horse.name,
    clothNumber: runner.clothNumber,
    defaultOddsDecimal: runner.currentOddsDecimal,
    existingFinishingPosition: runner.result?.finishingPosition ?? null,
    existingFinishStatus: runner.result?.finishStatus ?? null,
    existingSp: runner.result?.startingPriceDecimal ?? null,
    existingClosing: runner.result?.closingOddsDecimal ?? null,
    existingTags: (runner.result?.observations
      .map((o) => o.tag)
      .filter((t): t is ObservationTagType => t !== null)) ?? [],
    existingFreeText: runner.result?.observations.find((o) => o.freeText)?.freeText ?? "",
  }));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <Link href="/results" className="hover:text-text-secondary">
            Results
          </Link>
          <span>/</span>
          <span>{race.racecourse}</span>
        </div>
        <h1 className="mt-1 text-lg font-semibold text-text-primary">
          {race.raceTime} {race.racecourse} — {race.raceName}
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          Place terms: {race.placeTerms.map((t) => `${t.bookmaker.name} (${t.places} places)`).join(", ") || "—"}
        </p>
      </div>

      <ResultEntryForm raceId={race.id} runners={runners} />
    </div>
  );
}

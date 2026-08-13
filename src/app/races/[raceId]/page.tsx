import { notFound } from "next/navigation";
import Link from "next/link";

import { getRaceDetail } from "@/data/queries";
import { decimalToFractional } from "@/lib/odds";
import { formatDistance } from "@/lib/format";
import { paceRoleLabel } from "@/pace/types";
import { Badge } from "@/components/ui/Badge";
import { RunnerTable, type BookmakerPlaceOption, type RunnerRow } from "@/components/races/RunnerTable";
import { SyntheticModelBanner } from "@/components/model/SyntheticModelBanner";

export default async function RaceDetailPage({ params }: PageProps<"/races/[raceId]">) {
  const { raceId } = await params;
  const race = await getRaceDetail(raceId);
  if (!race) notFound();

  const isSynthetic = race.runners.some((r) => r.predictionSnapshots[0]?.modelVersionRef?.isSynthetic);

  const bookmakerOptions: BookmakerPlaceOption[] = race.placeTerms.map((term) => ({
    bookmakerId: term.bookmakerId,
    bookmakerName: term.bookmaker.name,
    places: term.places,
  }));

  const rows: RunnerRow[] = race.runners.map((runner) => {
    const snapshot = runner.predictionSnapshots[0] ?? null;
    const formString =
      runner.horse.formEntries.length > 0
        ? runner.horse.formEntries
            .map((f) => (f.finishingPosition ? f.finishingPosition.toString() : f.finishStatus ?? "-"))
            .join("-")
        : "—";

    return {
      runnerId: runner.id,
      horseName: runner.horse.name,
      clothNumber: runner.clothNumber,
      headgear: runner.headgear,
      nonRunner: runner.nonRunner,
      oddsDecimal: runner.currentOddsDecimal,
      oddsFractional: runner.currentOddsDecimal ? decimalToFractional(runner.currentOddsDecimal) : null,
      winProbability: snapshot?.winProbability ?? null,
      placeProbability: snapshot?.placeProbability ?? null,
      placeBasisPlaces: snapshot?.placeBasisPlaces ?? race.bookmakerPlaces ?? null,
      placeProbabilityBands: snapshot?.placeProbabilityBands.map((b) => ({ topN: b.topN, probabilityCalibrated: b.probabilityCalibrated })) ?? [],
      confidence: snapshot?.modelConfidence ?? null,
      fairOddsDecimal: snapshot?.fairOddsDecimal ?? null,
      valueEdge: snapshot?.valueEdgeAbsolute ?? null,
      officialRating: runner.officialRating,
      weightLbs: runner.weightLbsTotal,
      draw: runner.draw,
      fieldSize: race.numberOfRunners,
      paceCollapseProbability: runner.paceProfile?.paceCollapseProbability ?? null,
      form: formString,
      paceStyle: runner.paceProfile ? paceRoleLabel(runner.paceProfile.projectedRole) : "—",
      transitionScore: runner.paceProfile?.relativeAccelerationIndex ?? null,
      lateSustainability: runner.paceProfile?.finishingSpeedIndex ?? null,
      evidenceDensity: runner.horse.evidenceProfile?.evidenceDensityScore ?? null,
      evidenceLabel: runner.horse.evidenceProfile?.evidenceDensityLabel ?? null,
    };
  });

  const hasModelOutput = rows.some((r) => r.winProbability !== null);

  return (
    <div className="flex flex-col gap-6">
      {isSynthetic && <SyntheticModelBanner />}

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <Link href="/races" className="hover:text-text-secondary">
              Races
            </Link>
            <span>/</span>
            <span>{race.racecourse}</span>
          </div>
          <h1 className="mt-1 text-lg font-semibold text-text-primary">
            {race.raceTime} {race.racecourse} — {race.raceName}
          </h1>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge>{race.flatJumps}</Badge>
            <Badge>{race.surface}</Badge>
            <Badge>{race.handicapType === "HANDICAP" ? "Handicap" : "Non-handicap"}</Badge>
            {race.raceClass && <Badge>Class {race.raceClass}</Badge>}
            {race.gradeGroup && <Badge tone="accent">{race.gradeGroup}</Badge>}
            <Badge>{formatDistance(race.distanceFurlongs)}</Badge>
            {race.going && <Badge>{race.going}</Badge>}
            <Badge>{race.numberOfRunners} runners</Badge>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1 text-xs text-text-secondary">
          {race.placeTerms.map((term) => (
            <span key={term.id}>
              <span className="text-text-muted">{term.bookmaker.name}:</span> {term.places} places @{" "}
              {term.eachWayFraction}
              {term.extraPlaces ? " (extra places)" : ""}
            </span>
          ))}
        </div>
      </div>

      <RunnerTable rows={rows} bookmakerOptions={bookmakerOptions} />

      <p className="text-xs text-text-muted">
        {hasModelOutput
          ? "Win %, Place %, Confidence, Fair Odds and Value Edge are model outputs — see the Dashboard for calibration quality. Place % is picked from the bookmaker place-terms selector above; a * marks a nearest-available depth when the exact one isn't modelled."
          : 'Win %, Place %, Confidence, Fair Odds and Value Edge are populated by the probability model and currently read "Model not yet configured" for this race — run `npm run model:predict`.'}
      </p>
    </div>
  );
}

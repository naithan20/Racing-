import { getBookmakers, getValueScannerCandidates } from "@/data/queries";
import { impliedProbability } from "@/lib/odds";
import { placeOddsDecimal } from "@/value/place";
import { selectPlaceBand } from "@/value/placeBands";
import { ValueScanner, type ValueCandidate } from "@/components/value/ValueScanner";

export default async function ValueScannerPage() {
  const [candidatesRaw, bookmakers] = await Promise.all([getValueScannerCandidates(), getBookmakers()]);

  const candidates: ValueCandidate[] = candidatesRaw
    .map((r): ValueCandidate | null => {
      const snapshot = r.predictionSnapshots[0];
      if (!snapshot || snapshot.winProbability === null || r.currentOddsDecimal === null) return null;

      const eachWayFraction = r.race.eachWayFraction ?? 0.2;
      const defaultPlaces = r.race.bookmakerPlaces ?? snapshot.placeBasisPlaces ?? 3;
      const band = selectPlaceBand(
        snapshot.placeProbabilityBands.map((b) => ({ topN: b.topN, probabilityCalibrated: b.probabilityCalibrated })),
        defaultPlaces
      );
      const modelPlaceProbability = band?.probability ?? snapshot.placeProbability ?? null;

      let placeValueEdge: number | null = null;
      let marketImpliedPlaceProbability: number | null = null;
      try {
        const placeOdds = placeOddsDecimal(r.currentOddsDecimal, eachWayFraction);
        marketImpliedPlaceProbability = impliedProbability(placeOdds);
        if (modelPlaceProbability !== null) {
          placeValueEdge = modelPlaceProbability - marketImpliedPlaceProbability;
        }
      } catch {
        // odds/fraction out of the valid range — leave place value fields null
      }

      const winValueEdge = snapshot.valueEdgeAbsolute;
      const ewValueScore =
        winValueEdge !== null && placeValueEdge !== null ? (winValueEdge + placeValueEdge) / 2 : null;

      return {
        runnerId: r.id,
        horseName: r.horse.name,
        raceId: r.raceId,
        raceLabel: r.race.raceName,
        raceTime: r.race.raceTime,
        racecourse: r.race.racecourse,
        country: r.race.country,
        flatJumps: r.race.flatJumps,
        numberOfRunners: r.race.numberOfRunners,
        oddsDecimal: r.currentOddsDecimal,
        winProbability: snapshot.winProbability,
        modelConfidence: snapshot.modelConfidence,
        evidenceDensityScore: r.horse.evidenceProfile?.evidenceDensityScore ?? null,
        winValueEdge,
        modelPlaceProbability,
        marketImpliedPlaceProbability,
        placeValueEdge,
        ewValueScore,
        hasEnhancedPlaces: r.race.placeTerms.some((t) => t.extraPlaces),
        defaultPlaces,
      };
    })
    .filter((c): c is ValueCandidate => c !== null);

  const isSynthetic = candidatesRaw.some((r) => r.predictionSnapshots[0]?.modelVersionRef?.isSynthetic);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Daily Value Scanner</h1>
        <p className="mt-1 max-w-3xl text-sm text-text-secondary">
          Every runner across today&apos;s upcoming races with a model prediction, ranked by value edge.
          Place value uses the standard each-way place-odds formula (win odds + each-way fraction) compared
          against the model&apos;s calibrated place probability — not a market place price, since no
          separate place market is modelled. This is a research scanner, not a staking recommendation.
        </p>
      </div>

      <ValueScanner candidates={candidates} bookmakers={bookmakers} isSynthetic={isSynthetic} />
    </div>
  );
}

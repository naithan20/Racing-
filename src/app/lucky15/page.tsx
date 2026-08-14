import Link from "next/link";

import { getBookmakers, getLucky15Candidates, getLucky15Slips } from "@/data/queries";
import { formatDate, formatDecimalOdds } from "@/lib/format";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Lucky15Builder, type Lucky15Candidate } from "@/components/lucky15/Lucky15Builder";

// See src/app/data-explorer/page.tsx for why this is forced dynamic.
export const dynamic = "force-dynamic";

export default async function Lucky15Page() {
  const [candidatesRaw, bookmakers, slips] = await Promise.all([
    getLucky15Candidates(),
    getBookmakers(),
    getLucky15Slips(),
  ]);

  const candidates: Lucky15Candidate[] = candidatesRaw
    .filter((r) => r.currentOddsDecimal !== null)
    .map((r) => {
      const snapshot = r.predictionSnapshots[0] ?? null;
      return {
        runnerId: r.id,
        horseName: r.horse.name,
        raceLabel: r.race.raceName,
        raceTime: r.race.raceTime,
        racecourse: r.race.racecourse,
        country: r.race.country,
        flatJumps: r.race.flatJumps,
        numberOfRunners: r.race.numberOfRunners,
        oddsDecimal: r.currentOddsDecimal,
        distanceFurlongs: r.race.distanceFurlongs,
        hasEnhancedPlaces: r.race.placeTerms.some((t) => t.extraPlaces),
        confidence: snapshot?.modelConfidence ?? null,
        placeEdge: snapshot?.valueEdgeAbsolute ?? null,
      };
    });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Lucky 15 Builder</h1>
        <p className="mt-1 max-w-3xl text-sm text-text-secondary">
          Interface and data-structure placeholder. The eventual leg-selection logic will weigh expected
          value, place probability, confidence, bookmaker-enhanced place terms and diversification —{" "}
          <span className="text-text-primary">it will not simply pick the four highest win probabilities</span>.
          For now, select four legs manually to exercise the data model.
        </p>
      </div>

      <Lucky15Builder candidates={candidates} bookmakers={bookmakers} />

      <Card>
        <CardHeader>
          <CardTitle>Saved slips</CardTitle>
        </CardHeader>
        <CardBody className="flex flex-col gap-3">
          {slips.length === 0 ? (
            <p className="text-sm text-text-muted">No slips saved yet.</p>
          ) : (
            slips.map((slip) => (
              <div key={slip.id} className="rounded-md border border-border-subtle p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-text-primary">{slip.name}</span>
                  <span className="text-xs text-text-muted">{formatDate(slip.date)}</span>
                </div>
                <ul className="mt-2 flex flex-col gap-1">
                  {slip.legs.map((leg) => (
                    <li key={leg.id} className="text-sm text-text-secondary">
                      <Link href={`/runners/${leg.runnerId}`} className="text-accent hover:underline">
                        {leg.runner.horse.name}
                      </Link>{" "}
                      — {leg.runner.race.racecourse} {leg.runner.race.raceTime} @{" "}
                      {formatDecimalOdds(leg.runner.currentOddsDecimal)}
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
        </CardBody>
      </Card>
    </div>
  );
}

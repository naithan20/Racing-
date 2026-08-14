import Link from "next/link";

import { getResultTrackingRaces } from "@/data/queries";
import { formatDate, formatDistance } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody } from "@/components/ui/Card";

// See src/app/data-explorer/page.tsx for why this is forced dynamic.
export const dynamic = "force-dynamic";

export default async function ResultsPage() {
  const races = await getResultTrackingRaces();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Result tracking</h1>
        <p className="mt-1 max-w-3xl text-sm text-text-secondary">
          Record finishing positions, starting prices and manual observation tags after each race.
          Pre-race predictions (once the model exists) are locked and cannot be altered from here — only
          the actual outcome is recorded.
        </p>
      </div>

      {races.length === 0 ? (
        <Card>
          <CardBody className="text-sm text-text-secondary">No races yet.</CardBody>
        </Card>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[800px] text-sm">
            <thead>
              <tr className="border-b border-border bg-bg-elevated text-left text-xs uppercase tracking-wide text-text-muted">
                <th className="px-3 py-2 font-medium">Date</th>
                <th className="px-3 py-2 font-medium">Time</th>
                <th className="px-3 py-2 font-medium">Course</th>
                <th className="px-3 py-2 font-medium">Race</th>
                <th className="px-3 py-2 font-medium">Distance</th>
                <th className="px-3 py-2 font-medium">Runners</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {races.map((race) => {
                const resultedCount = race.runners.filter((r) => r.result).length;
                return (
                  <tr key={race.id} className="border-b border-border-subtle last:border-b-0 hover:bg-bg-hover">
                    <td className="px-3 py-2.5 text-text-secondary">{formatDate(race.date)}</td>
                    <td className="px-3 py-2.5 font-tabular text-text-primary">{race.raceTime}</td>
                    <td className="px-3 py-2.5 text-text-primary">{race.racecourse}</td>
                    <td className="px-3 py-2.5 text-text-secondary">{race.raceName}</td>
                    <td className="px-3 py-2.5 text-text-secondary">{formatDistance(race.distanceFurlongs)}</td>
                    <td className="px-3 py-2.5 font-tabular text-text-secondary">
                      {resultedCount}/{race.runners.length} entered
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge tone={race.raceStatus === "RESULTED" ? "positive" : "neutral"}>
                        {race.raceStatus}
                      </Badge>
                    </td>
                    <td className="px-3 py-2.5">
                      <Link href={`/results/${race.id}`} className="text-accent hover:underline">
                        Enter results
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

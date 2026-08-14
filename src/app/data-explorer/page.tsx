import Link from "next/link";

import { getExplorerRaces } from "@/data/explorer";
import { formatDate } from "@/lib/format";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

// Reads live from the database on every request rather than being frozen
// at build time — important once the DB is production Postgres (Vercel
// deploys can't assume the DB is reachable/populated at build time, and a
// racing app showing build-time-stale data would be actively wrong).
export const dynamic = "force-dynamic";

export default async function DataExplorerPage() {
  const races = await getExplorerRaces(100);

  return (
    <div className="mx-auto max-w-[1200px] space-y-6 px-4 py-6 sm:px-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Dataset Explorer</h1>
        <p className="mt-1 max-w-3xl text-sm text-text-secondary">
          Pick a race to see exactly what RacingEdge knew about it — including at a chosen pre-race
          timestamp, not just the current (possibly post-race) state — with full data provenance.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Find a horse</CardTitle>
        </CardHeader>
        <CardBody>
          <form action="/data-explorer/horses" method="get" className="flex gap-2">
            <input
              type="text"
              name="q"
              placeholder="Horse name..."
              className="w-full max-w-xs rounded-md border border-border bg-bg-elevated px-3 py-1.5 text-sm text-text-primary placeholder:text-text-muted"
            />
            <button
              type="submit"
              className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-bg-base hover:opacity-90"
            >
              Search
            </button>
          </form>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent races ({races.length})</CardTitle>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-xs uppercase tracking-wide text-text-muted">
                <th className="py-1.5 pr-4">Date</th>
                <th className="py-1.5 pr-4">Course</th>
                <th className="py-1.5 pr-4">Race</th>
                <th className="py-1.5 pr-4">Runners</th>
                <th className="py-1.5 pr-4">Source</th>
                <th className="py-1.5">Status</th>
              </tr>
            </thead>
            <tbody>
              {races.map((race) => (
                <tr key={race.id} className="border-b border-border-subtle/60 last:border-0 hover:bg-bg-hover">
                  <td className="py-1.5 pr-4 font-tabular">{formatDate(race.date)}</td>
                  <td className="py-1.5 pr-4">{race.racecourse}</td>
                  <td className="py-1.5 pr-4">
                    <Link href={`/data-explorer/race/${race.id}`} className="text-accent hover:underline">
                      {race.raceName}
                    </Link>
                  </td>
                  <td className="py-1.5 pr-4 font-tabular">{race.numberOfRunners}</td>
                  <td className="py-1.5 pr-4">
                    <Badge tone={race.sourceType === "REAL" ? "positive" : "neutral"}>{race.sourceType}</Badge>
                  </td>
                  <td className="py-1.5">{race.raceStatus}</td>
                </tr>
              ))}
              {races.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-3 text-center text-text-muted">
                    No races yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}

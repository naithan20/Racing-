import Link from "next/link";

import { getRacesForDate } from "@/data/queries";
import { formatDistance } from "@/lib/format";
import { Card, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { DateNav } from "@/components/races/DateNav";

function parseDateParam(value: string | undefined): Date {
  if (!value) return new Date();
  const parsed = new Date(`${value}T00:00:00`);
  return Number.isNaN(parsed.getTime()) ? new Date() : parsed;
}

function toDateInputValue(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export default async function RacesPage({
  searchParams,
}: PageProps<"/races">) {
  const params = await searchParams;
  const dateParam = Array.isArray(params.date) ? params.date[0] : params.date;
  const selectedDate = parseDateParam(dateParam);
  const races = await getRacesForDate(selectedDate);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Daily Race Screen</h1>
          <p className="mt-1 text-sm text-text-secondary">
            All races for the selected day. Probability columns will populate once the Phase 2 model is
            wired up.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <DateNav dateValue={toDateInputValue(selectedDate)} />
          <Link
            href="/races/new"
            className="rounded-md border border-border bg-bg-elevated px-3 py-1.5 text-sm text-text-primary transition-colors hover:bg-bg-hover"
          >
            + New race
          </Link>
        </div>
      </div>

      {races.length === 0 ? (
        <Card>
          <CardBody className="text-sm text-text-secondary">
            No races found for this date.{" "}
            <Link href="/import" className="text-accent hover:underline">
              Import race data
            </Link>{" "}
            or{" "}
            <Link href="/races/new" className="text-accent hover:underline">
              create one manually
            </Link>
            .
          </CardBody>
        </Card>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[900px] text-sm">
            <thead>
              <tr className="border-b border-border bg-bg-elevated text-left text-xs uppercase tracking-wide text-text-muted">
                <th className="px-3 py-2 font-medium">Time</th>
                <th className="px-3 py-2 font-medium">Course</th>
                <th className="px-3 py-2 font-medium">Race</th>
                <th className="px-3 py-2 font-medium">Class</th>
                <th className="px-3 py-2 font-medium">Distance</th>
                <th className="px-3 py-2 font-medium">Going</th>
                <th className="px-3 py-2 font-medium">Runners</th>
                <th className="px-3 py-2 font-medium">Place terms</th>
                <th className="px-3 py-2 font-medium">Top win %</th>
                <th className="px-3 py-2 font-medium">Top value</th>
                <th className="px-3 py-2 font-medium">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {races.map((race) => {
                const activeRunners = race.runners.filter((r) => !r.nonRunner).length;
                return (
                  <tr
                    key={race.id}
                    className="border-b border-border-subtle last:border-b-0 hover:bg-bg-hover"
                  >
                    <td className="px-3 py-2.5 font-tabular text-text-primary">{race.raceTime}</td>
                    <td className="px-3 py-2.5 text-text-primary">{race.racecourse}</td>
                    <td className="px-3 py-2.5">
                      <Link href={`/races/${race.id}`} className="text-accent hover:underline">
                        {race.raceName}
                      </Link>
                      <div className="mt-0.5 flex gap-1.5">
                        <Badge>{race.flatJumps}</Badge>
                        <Badge>{race.handicapType === "HANDICAP" ? "Hcap" : "Non-hcap"}</Badge>
                        {race.raceStatus === "RESULTED" && <Badge tone="neutral">Resulted</Badge>}
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-text-secondary">{race.raceClass ?? "—"}</td>
                    <td className="px-3 py-2.5 text-text-secondary">{formatDistance(race.distanceFurlongs)}</td>
                    <td className="px-3 py-2.5 text-text-secondary">{race.going ?? "—"}</td>
                    <td className="px-3 py-2.5 font-tabular text-text-secondary">{activeRunners}</td>
                    <td className="px-3 py-2.5 text-text-secondary">
                      {race.placeTerms.length === 0 ? (
                        <span className="text-text-muted">—</span>
                      ) : (
                        <div className="flex flex-col gap-0.5">
                          {race.placeTerms.map((term) => (
                            <span key={term.id} className="text-xs">
                              {term.bookmaker.name}: {term.places} places
                              {term.extraPlaces ? " (extra)" : ""}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-text-muted">—</td>
                    <td className="px-3 py-2.5 text-text-muted">—</td>
                    <td className="px-3 py-2.5 text-text-muted">—</td>
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

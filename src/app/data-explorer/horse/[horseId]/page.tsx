import Link from "next/link";
import { notFound } from "next/navigation";

import { getHorseTimeline } from "@/data/explorer";
import { formatDate } from "@/lib/format";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

export default async function HorseTimelinePage({ params }: PageProps<"/data-explorer/horse/[horseId]">) {
  const { horseId } = await params;
  const detail = await getHorseTimeline(horseId);
  if (!detail) notFound();
  const { horse, formEntries, runners, aliases } = detail;

  return (
    <div className="mx-auto max-w-[1100px] space-y-6 px-4 py-6 sm:px-6">
      <div>
        <Link href="/data-explorer" className="text-xs text-accent hover:underline">
          ← Dataset Explorer
        </Link>
        <h1 className="mt-1 text-lg font-semibold text-text-primary">{horse.name}</h1>
        <p className="mt-1 text-sm text-text-secondary">
          <Badge tone={horse.sourceType === "REAL" ? "positive" : "neutral"}>{horse.sourceType}</Badge>
          {horse.countryBred && <span className="ml-2">{horse.countryBred}-bred</span>}
          {horse.trainerName && <span className="ml-2">Trainer: {horse.trainerName}</span>}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Timeline — RacingEdge race entries ({runners.length})</CardTitle>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <p className="mb-3 text-xs text-text-muted">
            Any feature computed for a race below only ever looked BACKWARD from that race&apos;s own
            date — later rows in this table were never visible to it.
          </p>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-xs uppercase tracking-wide text-text-muted">
                <th className="py-1.5 pr-4">Date</th>
                <th className="py-1.5 pr-4">Race</th>
                <th className="py-1.5">Course</th>
              </tr>
            </thead>
            <tbody>
              {runners.map((r) => (
                <tr key={r.id} className="border-b border-border-subtle/60 last:border-0">
                  <td className="py-1.5 pr-4 font-tabular">{formatDate(r.race.date)}</td>
                  <td className="py-1.5 pr-4">
                    <Link href={`/data-explorer/race/${r.raceId}`} className="text-accent hover:underline">
                      {r.race.raceName}
                    </Link>
                  </td>
                  <td className="py-1.5">{r.race.racecourse}</td>
                </tr>
              ))}
              {runners.length === 0 && (
                <tr>
                  <td colSpan={3} className="py-3 text-center text-text-muted">
                    No RacingEdge race entries for this horse.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Historical form ({formEntries.length})</CardTitle>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-xs uppercase tracking-wide text-text-muted">
                <th className="py-1.5 pr-4">Date</th>
                <th className="py-1.5 pr-4">Course</th>
                <th className="py-1.5 pr-4">Pos</th>
                <th className="py-1.5 pr-4">Field</th>
                <th className="py-1.5 pr-4">Going</th>
                <th className="py-1.5">Positional / sectional</th>
              </tr>
            </thead>
            <tbody>
              {formEntries.map((f) => (
                <tr key={f.id} className="border-b border-border-subtle/60 last:border-0">
                  <td className="py-1.5 pr-4 font-tabular">{formatDate(f.raceDate)}</td>
                  <td className="py-1.5 pr-4">{f.course}</td>
                  <td className="py-1.5 pr-4 font-tabular">{f.finishingPosition ?? "—"}</td>
                  <td className="py-1.5 pr-4 font-tabular">{f.fieldSize ?? "—"}</td>
                  <td className="py-1.5 pr-4">{f.going ?? "—"}</td>
                  <td className="py-1.5">
                    {f.hasPositionalData && <Badge tone="accent">positional</Badge>}{" "}
                    {f.hasSectionalData && <Badge tone="accent">sectional</Badge>}
                    {!f.hasPositionalData && !f.hasSectionalData && <span className="text-text-muted">—</span>}
                  </td>
                </tr>
              ))}
              {formEntries.length === 0 && (
                <tr>
                  <td colSpan={6} className="py-3 text-center text-text-muted">
                    No historical form entries for this horse.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Entity aliases ({aliases.length})</CardTitle>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <p className="mb-3 text-xs text-text-muted">
            Every raw name variant that has been resolved to this canonical horse, and how it was
            matched — the auditable trail behind entity resolution.
          </p>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-xs uppercase tracking-wide text-text-muted">
                <th className="py-1.5 pr-4">Raw name</th>
                <th className="py-1.5 pr-4">Provider</th>
                <th className="py-1.5 pr-4">Match method</th>
                <th className="py-1.5">Recorded</th>
              </tr>
            </thead>
            <tbody>
              {aliases.map((a) => (
                <tr key={a.id} className="border-b border-border-subtle/60 last:border-0">
                  <td className="py-1.5 pr-4">{a.rawName}</td>
                  <td className="py-1.5 pr-4">{a.providerName ?? "—"}</td>
                  <td className="py-1.5 pr-4">
                    <Badge tone="neutral">{a.matchMethod}</Badge>
                  </td>
                  <td className="py-1.5 font-tabular">{formatDate(a.createdAt)}</td>
                </tr>
              ))}
              {aliases.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-3 text-center text-text-muted">
                    No aliases recorded (this horse was created before Phase 3A entity resolution
                    existed, or via direct seed data).
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

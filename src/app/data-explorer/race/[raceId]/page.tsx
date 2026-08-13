import Link from "next/link";
import { notFound } from "next/navigation";

import { getRaceExplorerDetail, reconstructRaceFieldsAsOf, reconstructRunnerFieldsAsOf } from "@/data/explorer";
import { formatDate } from "@/lib/format";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

function toDatetimeLocalValue(date: Date): string {
  return date.toISOString().slice(0, 16);
}

export default async function RaceExplorerDetailPage({
  params,
  searchParams,
}: PageProps<"/data-explorer/race/[raceId]">) {
  const { raceId } = await params;
  const search = await searchParams;
  const asOfParam = Array.isArray(search.asOf) ? search.asOf[0] : search.asOf;

  const detail = await getRaceExplorerDetail(raceId);
  if (!detail) notFound();
  const { race, raceFieldHistory, provenance } = detail;

  const asOf = asOfParam ? new Date(asOfParam) : race.date;
  const asOfIsValid = !Number.isNaN(asOf.getTime());
  const effectiveAsOf = asOfIsValid ? asOf : race.date;

  const reconstructedRace = await reconstructRaceFieldsAsOf(raceId, effectiveAsOf);
  const reconstructedRunners = await Promise.all(
    race.runners.map(async (runner) => ({
      runner,
      reconstructed: await reconstructRunnerFieldsAsOf(runner.id, effectiveAsOf),
    }))
  );

  return (
    <div className="mx-auto max-w-[1200px] space-y-6 px-4 py-6 sm:px-6">
      <div>
        <Link href="/data-explorer" className="text-xs text-accent hover:underline">
          ← Dataset Explorer
        </Link>
        <h1 className="mt-1 text-lg font-semibold text-text-primary">{race.raceName}</h1>
        <p className="mt-1 text-sm text-text-secondary">
          {race.racecourse} · {formatDate(race.date)} {race.raceTime} ·{" "}
          <Badge tone={race.sourceType === "REAL" ? "positive" : "neutral"}>{race.sourceType}</Badge>
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Point-in-time reconstruction</CardTitle>
        </CardHeader>
        <CardBody className="space-y-3">
          <p className="text-xs text-text-muted">
            Choose a timestamp to see EXACTLY what RacingEdge knew as of that moment — mutable fields
            (going, draw, jockey, weight, non-runner status, ...) are reconstructed from their
            point-in-time history, never read from the live (possibly post-race) row. A field with no
            recorded history at or before this timestamp shows as <span className="italic">unknown</span>.
          </p>
          <form method="get" className="flex flex-wrap items-end gap-2">
            <div>
              <label className="block text-xs text-text-muted" htmlFor="asOf">
                As of
              </label>
              <input
                id="asOf"
                type="datetime-local"
                name="asOf"
                defaultValue={toDatetimeLocalValue(effectiveAsOf)}
                className="rounded-md border border-border bg-bg-elevated px-3 py-1.5 text-sm text-text-primary"
              />
            </div>
            <button type="submit" className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-bg-base hover:opacity-90">
              Reconstruct
            </button>
            <Link
              href={`/data-explorer/race/${raceId}`}
              className="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-bg-hover"
            >
              Reset to race start
            </Link>
          </form>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {Object.entries(reconstructedRace.fields).map(([field, value]) => (
              <div key={field} className="rounded-md border border-border-subtle bg-bg-elevated p-2">
                <p className="text-[10px] uppercase tracking-wide text-text-muted">{field}</p>
                <p className={`mt-0.5 text-sm ${value === null ? "italic text-text-muted" : "text-text-primary"}`}>
                  {value ?? "unknown"}
                </p>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Runners as of {effectiveAsOf.toISOString()}</CardTitle>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-xs uppercase tracking-wide text-text-muted">
                <th className="py-1.5 pr-4">Horse</th>
                <th className="py-1.5 pr-4">Draw</th>
                <th className="py-1.5 pr-4">Jockey</th>
                <th className="py-1.5 pr-4">Trainer</th>
                <th className="py-1.5 pr-4">Weight (lbs)</th>
                <th className="py-1.5 pr-4">OR</th>
                <th className="py-1.5">Non-runner</th>
              </tr>
            </thead>
            <tbody>
              {reconstructedRunners.map(({ runner, reconstructed }) => (
                <tr key={runner.id} className="border-b border-border-subtle/60 last:border-0">
                  <td className="py-1.5 pr-4">
                    <Link href={`/data-explorer/horse/${runner.horseId}`} className="text-accent hover:underline">
                      {runner.horse.name}
                    </Link>
                  </td>
                  <td className="py-1.5 pr-4 font-tabular">{reconstructed.fields.draw ?? "—"}</td>
                  <td className="py-1.5 pr-4">{reconstructed.fields.jockeyName ?? "—"}</td>
                  <td className="py-1.5 pr-4">{reconstructed.fields.trainerName ?? "—"}</td>
                  <td className="py-1.5 pr-4 font-tabular">{reconstructed.fields.weightLbsTotal ?? "—"}</td>
                  <td className="py-1.5 pr-4 font-tabular">{reconstructed.fields.officialRating ?? "—"}</td>
                  <td className="py-1.5">{reconstructed.fields.nonRunner ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Race field history</CardTitle>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-xs uppercase tracking-wide text-text-muted">
                <th className="py-1.5 pr-4">Field</th>
                <th className="py-1.5 pr-4">Value</th>
                <th className="py-1.5 pr-4">Effective at</th>
                <th className="py-1.5">Source</th>
              </tr>
            </thead>
            <tbody>
              {raceFieldHistory.map((h) => (
                <tr key={h.id} className="border-b border-border-subtle/60 last:border-0">
                  <td className="py-1.5 pr-4">{h.fieldName}</td>
                  <td className="py-1.5 pr-4">{h.fieldValue ?? "—"}</td>
                  <td className="py-1.5 pr-4 font-tabular">{h.effectiveAt.toISOString()}</td>
                  <td className="py-1.5">{h.source ?? "—"}</td>
                </tr>
              ))}
              {raceFieldHistory.length === 0 && (
                <tr>
                  <td colSpan={4} className="py-3 text-center text-text-muted">
                    No field-history rows recorded for this race (imported before Phase 3A tracking, or
                    hand-seeded).
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Data provenance</CardTitle>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-xs uppercase tracking-wide text-text-muted">
                <th className="py-1.5 pr-4">Domain</th>
                <th className="py-1.5 pr-4">Provider</th>
                <th className="py-1.5 pr-4">Provider record id</th>
                <th className="py-1.5 pr-4">Retrieved at</th>
                <th className="py-1.5">Effective at</th>
              </tr>
            </thead>
            <tbody>
              {provenance.map((p) => (
                <tr key={p.id} className="border-b border-border-subtle/60 last:border-0">
                  <td className="py-1.5 pr-4">{p.dataDomain}</td>
                  <td className="py-1.5 pr-4">{p.provider}</td>
                  <td className="py-1.5 pr-4">{p.providerRecordId ?? "—"}</td>
                  <td className="py-1.5 pr-4 font-tabular">{p.retrievedAt.toISOString()}</td>
                  <td className="py-1.5 font-tabular">{p.effectiveAt?.toISOString() ?? "—"}</td>
                </tr>
              ))}
              {provenance.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-3 text-center text-text-muted">
                    No provenance recorded (imported before Phase 3A tracking, or hand-seeded).
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

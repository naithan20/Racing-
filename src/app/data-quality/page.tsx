import { getDataQualityReport } from "@/data/dataQuality";
import { formatDate } from "@/lib/format";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

function MetricTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-md border border-border-subtle bg-bg-elevated p-3">
      <p className="text-xs uppercase tracking-wide text-text-muted">{label}</p>
      <p className="mt-1 font-tabular text-xl text-text-primary">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-text-muted">{hint}</p>}
    </div>
  );
}

function pctLabel(value: number | null): string {
  return value === null ? "—" : `${value}%`;
}

function pctTone(value: number | null): "neutral" | "positive" | "warning" | "negative" {
  if (value === null) return "neutral";
  if (value < 10) return "positive";
  if (value < 40) return "warning";
  return "negative";
}

export default async function DataQualityPage() {
  const report = await getDataQualityReport();

  return (
    <div className="mx-auto max-w-[1200px] space-y-6 px-4 py-6 sm:px-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Data Quality Dashboard</h1>
        <p className="mt-1 text-sm text-text-secondary">
          Live coverage, missingness, and provenance figures recomputed directly from stored rows —
          part of Phase 3A&apos;s data-integrity infrastructure. Nothing here is cached or hand-edited.
        </p>
      </div>

      {report.warnings.length > 0 && (
        <Card className="border-warning/40">
          <CardHeader>
            <CardTitle>Warnings</CardTitle>
          </CardHeader>
          <CardBody>
            <ul className="space-y-1.5 text-sm text-text-secondary">
              {report.warnings.map((warning) => (
                <li key={warning} className="flex items-start gap-2">
                  <Badge tone="warning" className="mt-0.5 shrink-0">
                    !
                  </Badge>
                  <span>{warning}</span>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Overview</CardTitle>
        </CardHeader>
        <CardBody className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MetricTile label="Total races" value={report.totalRaces.toLocaleString()} />
          <MetricTile label="Total runners" value={report.totalRunners.toLocaleString()} />
          <MetricTile label="Course coverage" value={report.courseCoverage.toLocaleString()} hint="distinct racecourses" />
          <MetricTile
            label="Date coverage"
            value={
              report.dateRange.earliest && report.dateRange.latest
                ? `${formatDate(report.dateRange.earliest)} – ${formatDate(report.dateRange.latest)}`
                : "—"
            }
          />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Source classification</CardTitle>
        </CardHeader>
        <CardBody>
          <p className="mb-3 text-xs text-text-muted">
            REAL / SYNTHETIC / SAMPLE races are never mixed silently — see MODEL_CARD.md for what each
            model version was actually trained on.
          </p>
          <div className="flex flex-wrap gap-2">
            {report.sourceTypeCounts.map((s) => (
              <Badge key={s.sourceType} tone={s.sourceType === "REAL" ? "positive" : "neutral"}>
                {s.sourceType}: {s.raceCount.toLocaleString()} races
              </Badge>
            ))}
            {report.sourceTypeCounts.length === 0 && <span className="text-sm text-text-muted">No races yet.</span>}
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Missingness</CardTitle>
        </CardHeader>
        <CardBody className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {(
            [
              ["Official rating", report.missingness.officialRatingPct],
              ["Draw", report.missingness.drawPct],
              ["Starting price", report.missingness.startingPriceDecimalPct],
              ["Going (race-level)", report.missingness.goingPct],
              ["Positional data (form)", report.missingness.positionalDataPct],
              ["Sectional data (form)", report.missingness.sectionalDataPct],
            ] as const
          ).map(([label, value]) => (
            <div key={label} className="rounded-md border border-border-subtle bg-bg-elevated p-3">
              <p className="text-xs uppercase tracking-wide text-text-muted">{label}</p>
              <p className="mt-1 flex items-baseline gap-2">
                <span className="font-tabular text-xl text-text-primary">{pctLabel(value)}</span>
                <Badge tone={pctTone(value)}>missing</Badge>
              </p>
            </div>
          ))}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Import quality</CardTitle>
        </CardHeader>
        <CardBody className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <MetricTile label="Duplicate rate" value={pctLabel(report.duplicateRate)} hint="across all import batches" />
          <MetricTile
            label="Unresolved entities"
            value={report.unresolvedEntityCount.toLocaleString()}
            hint="pending manual-review queue items"
          />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Coverage by year</CardTitle>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-xs uppercase tracking-wide text-text-muted">
                <th className="py-1.5 pr-4">Year</th>
                <th className="py-1.5 pr-4">Races</th>
                <th className="py-1.5">Runners</th>
              </tr>
            </thead>
            <tbody>
              {report.byYear.map((y) => (
                <tr key={y.year} className="border-b border-border-subtle/60 last:border-0">
                  <td className="py-1.5 pr-4 font-tabular">{y.year}</td>
                  <td className="py-1.5 pr-4 font-tabular">{y.raceCount.toLocaleString()}</td>
                  <td className="py-1.5 font-tabular">{y.runnerCount.toLocaleString()}</td>
                </tr>
              ))}
              {report.byYear.length === 0 && (
                <tr>
                  <td colSpan={3} className="py-3 text-center text-text-muted">
                    No races yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Coverage by provider</CardTitle>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <p className="mb-3 text-xs text-text-muted">
            Derived from DataProvenance rows — races imported before Phase 3A&apos;s provenance
            tracking existed (Phase 1 seed data, the Phase 2 synthetic generator) won&apos;t appear
            here even though they&apos;re counted in the totals above.
          </p>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-xs uppercase tracking-wide text-text-muted">
                <th className="py-1.5 pr-4">Provider</th>
                <th className="py-1.5">Races</th>
              </tr>
            </thead>
            <tbody>
              {report.byProvider.map((p) => (
                <tr key={p.provider} className="border-b border-border-subtle/60 last:border-0">
                  <td className="py-1.5 pr-4">{p.provider}</td>
                  <td className="py-1.5 font-tabular">{p.raceCount.toLocaleString()}</td>
                </tr>
              ))}
              {report.byProvider.length === 0 && (
                <tr>
                  <td colSpan={2} className="py-3 text-center text-text-muted">
                    No provenance-tracked imports yet.
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

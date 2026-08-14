import { getImportBatches } from "@/data/queries";
import { formatDate } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { CsvImportForm, JsonImportForm } from "@/components/import/ImportForms";

// See src/app/data-explorer/page.tsx for why this is forced dynamic.
export const dynamic = "force-dynamic";

export default async function ImportPage() {
  const batches = await getImportBatches();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Data import</h1>
        <p className="mt-1 max-w-3xl text-sm text-text-secondary">
          Manual entry, CSV and JSON are supported in Phase 1. RacingEdge does not scrape websites — all
          data here is entered directly or comes from files you provide. A licensed data feed can be added
          later behind the same import schema.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <CsvImportForm />
        <JsonImportForm />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent import batches</CardTitle>
        </CardHeader>
        <CardBody className="overflow-x-auto p-0">
          <table className="w-full min-w-[700px] text-sm">
            <thead>
              <tr className="border-b border-border-subtle bg-bg-elevated text-left text-xs uppercase tracking-wide text-text-muted">
                <th className="px-3 py-2 font-medium">When</th>
                <th className="px-3 py-2 font-medium">Source</th>
                <th className="px-3 py-2 font-medium">File</th>
                <th className="px-3 py-2 font-medium">Races</th>
                <th className="px-3 py-2 font-medium">Rows</th>
                <th className="px-3 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {batches.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-4 text-text-muted">
                    No imports yet.
                  </td>
                </tr>
              ) : (
                batches.map((batch) => (
                  <tr key={batch.id} className="border-b border-border-subtle last:border-b-0">
                    <td className="px-3 py-2 text-text-secondary">{formatDate(batch.importedAt)}</td>
                    <td className="px-3 py-2 text-text-secondary">{batch.sourceType}</td>
                    <td className="px-3 py-2 text-text-primary">{batch.filename ?? "—"}</td>
                    <td className="px-3 py-2 font-tabular text-text-secondary">{batch._count.races}</td>
                    <td className="px-3 py-2 font-tabular text-text-secondary">
                      {batch.successCount ?? "—"}/{batch.rowCount ?? "—"}
                    </td>
                    <td className="px-3 py-2">
                      <Badge
                        tone={
                          batch.status === "SUCCESS" ? "positive" : batch.status === "FAILED" ? "negative" : "neutral"
                        }
                      >
                        {batch.status}
                      </Badge>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  );
}

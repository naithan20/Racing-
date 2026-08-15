import Link from "next/link";

import { getDataSourceCards } from "@/data/dataSources";
import { SourceCard } from "@/components/data-sources/SourceCard";
import { OneTapSetupCard } from "@/components/data-sources/OneTapSetupCard";

const ONE_TAP_SOURCE_ID = "kaggle-uk-ire-historical";

// See src/app/data-explorer/page.tsx for why this is forced dynamic.
export const dynamic = "force-dynamic";
// The "One-tap free setup" button below invokes startOneTapImportAction,
// which downloads + parses + imports a dataset synchronously within this
// Server Action's own request — see src/actions/serverlessImport.ts.
export const maxDuration = 60;

export default async function DataSourcesPage() {
  const cards = await getDataSourceCards();
  const oneTapCard = cards.find((c) => c.source.id === ONE_TAP_SOURCE_ID);
  const otherCards = cards.filter((c) => c.source.id !== ONE_TAP_SOURCE_ID);

  return (
    <div className="mx-auto max-w-[1200px] space-y-6 px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Data sources</h1>
          <p className="mt-1 max-w-2xl text-sm text-text-secondary">
            Select a source, connect it if needed, and click Import — RacingEdge downloads, inspects,
            maps, and imports automatically. Every source here is FREE — see the £0 rule in
            FREE_DATA_SOURCES.md.
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/data-sources/discover" className="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-bg-hover">
            Find free data
          </Link>
          <Link href="/settings/data-connections" className="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-bg-hover">
            Data connections
          </Link>
        </div>
      </div>

      {oneTapCard && <OneTapSetupCard card={oneTapCard} />}

      <div>
        <h2 className="mb-3 text-sm font-semibold text-text-primary">All sources (advanced)</h2>
        <p className="mb-3 max-w-2xl text-xs text-text-secondary">
          The cards below run the full CLI pipeline (schema inspection, entity resolution, leakage audit,
          dataset versioning) — more thorough, but requires a local Python environment (see README.md&apos;s
          Deployment section for what this means on Vercel).
        </p>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {otherCards.map((card) => (
            <SourceCard key={card.source.id} card={card} />
          ))}
        </div>
      </div>
    </div>
  );
}

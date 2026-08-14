import Link from "next/link";

import { getDataSourceCards } from "@/data/dataSources";
import { SourceCard } from "@/components/data-sources/SourceCard";

// See src/app/data-explorer/page.tsx for why this is forced dynamic.
export const dynamic = "force-dynamic";

export default async function DataSourcesPage() {
  const cards = await getDataSourceCards();

  return (
    <div className="mx-auto max-w-[1200px] space-y-6 px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Data sources</h1>
          <p className="mt-1 max-w-2xl text-sm text-text-secondary">
            Select a source, connect it if needed, and click Import — RacingEdge downloads, inspects,
            maps, imports, resolves entities, runs a provenance review and leakage audit, and builds a
            dataset version automatically. Every source here is FREE — see the £0 rule in
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

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {cards.map((card) => (
          <SourceCard key={card.source.id} card={card} />
        ))}
      </div>
    </div>
  );
}

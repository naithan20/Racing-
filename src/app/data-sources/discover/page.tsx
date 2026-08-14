import { DiscoverFilters } from "@/components/data-sources/DiscoverFilters";

export default function DiscoverDataPage() {
  return (
    <div className="mx-auto max-w-[1000px] space-y-6 px-4 py-6 sm:px-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Find free data</h1>
        <p className="mt-1 max-w-2xl text-sm text-text-secondary">
          Every entry here comes from RacingEdge&apos;s own maintained source catalog — this is not web
          search or scraping. A source is only claimed VERIFIED once its adapter has actually been
          exercised; otherwise it&apos;s labelled honestly. See FREE_DATA_SOURCES.md for the full
          discovery record.
        </p>
      </div>
      <DiscoverFilters />
    </div>
  );
}

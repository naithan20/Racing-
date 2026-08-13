import Link from "next/link";

import { searchHorsesByName } from "@/data/explorer";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";

export default async function HorseSearchPage({ searchParams }: PageProps<"/data-explorer/horses">) {
  const params = await searchParams;
  const query = Array.isArray(params.q) ? params.q[0] : (params.q ?? "");
  const horses = query ? await searchHorsesByName(query) : [];

  return (
    <div className="mx-auto max-w-[900px] space-y-6 px-4 py-6 sm:px-6">
      <div>
        <h1 className="text-lg font-semibold text-text-primary">Horse search</h1>
        <p className="mt-1 text-sm text-text-secondary">Find a horse and view its full timeline.</p>
      </div>

      <form action="/data-explorer/horses" method="get" className="flex gap-2">
        <input
          type="text"
          name="q"
          defaultValue={query}
          placeholder="Horse name..."
          className="w-full max-w-xs rounded-md border border-border bg-bg-elevated px-3 py-1.5 text-sm text-text-primary placeholder:text-text-muted"
        />
        <button type="submit" className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-bg-base hover:opacity-90">
          Search
        </button>
      </form>

      <Card>
        <CardHeader>
          <CardTitle>Results {query && `for "${query}"`}</CardTitle>
        </CardHeader>
        <CardBody>
          <ul className="divide-y divide-border-subtle">
            {horses.map((horse) => (
              <li key={horse.id} className="flex items-center justify-between py-2">
                <Link href={`/data-explorer/horse/${horse.id}`} className="text-accent hover:underline">
                  {horse.name}
                </Link>
                <Badge tone={horse.sourceType === "REAL" ? "positive" : "neutral"}>{horse.sourceType}</Badge>
              </li>
            ))}
            {query && horses.length === 0 && <li className="py-3 text-sm text-text-muted">No horses found.</li>}
          </ul>
        </CardBody>
      </Card>
    </div>
  );
}

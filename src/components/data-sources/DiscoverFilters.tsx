"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { SOURCE_CATALOG, type DataCategory, type SourceCatalogEntry } from "@/data/sourceCatalog";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";

const CATEGORY_LABELS: Record<DataCategory, string> = {
  HISTORICAL_RESULTS: "Historical results",
  RACECARDS_FORM: "Racecards / form",
  MARKET_SP: "Market / SP data",
  SECTIONALS: "Sectionals",
  WEATHER: "Weather",
};

const VERIFICATION_TONE: Record<string, "positive" | "warning" | "neutral" | "negative"> = {
  VERIFIED: "positive",
  AVAILABLE_BUT_UNVERIFIED: "warning",
  REQUIRES_CONNECTION: "neutral",
  UNAVAILABLE: "negative",
};

const ALL_REGIONS = Array.from(new Set(SOURCE_CATALOG.flatMap((s) => s.regions))).filter((r) => r !== "Other");
const ALL_CODES = ["FLAT", "JUMPS"] as const;

function Checkbox({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-center gap-1.5 text-xs text-text-secondary">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

export function DiscoverFilters() {
  const [category, setCategory] = useState<DataCategory | "ALL">("ALL");
  const [region, setRegion] = useState<string | "ALL">("ALL");
  const [code, setCode] = useState<(typeof ALL_CODES)[number] | "ALL">("ALL");
  const [freeOnly, setFreeOnly] = useState(true);

  const filtered = useMemo(() => {
    return SOURCE_CATALOG.filter((entry) => {
      if (category !== "ALL" && entry.category !== category) return false;
      if (region !== "ALL" && !entry.regions.includes(region)) return false;
      if (code !== "ALL" && !entry.codes.includes(code)) return false;
      if (freeOnly && entry.cost !== "FREE") return false;
      return true;
    });
  }, [category, region, code, freeOnly]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4 rounded-md border border-border-subtle bg-bg-elevated p-3">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value as DataCategory | "ALL")}
          className="rounded-md border border-border bg-bg-panel px-2 py-1 text-xs text-text-primary"
        >
          <option value="ALL">All categories</option>
          {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>

        <select
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          className="rounded-md border border-border bg-bg-panel px-2 py-1 text-xs text-text-primary"
        >
          <option value="ALL">All regions</option>
          {ALL_REGIONS.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>

        <div className="flex gap-3">
          {ALL_CODES.map((c) => (
            <Checkbox key={c} label={c} checked={code === c} onChange={(checked) => setCode(checked ? c : "ALL")} />
          ))}
        </div>

        <Checkbox label="Free only" checked={freeOnly} onChange={setFreeOnly} />
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {filtered.map((entry) => (
          <DiscoverCard key={entry.id} entry={entry} />
        ))}
        {filtered.length === 0 && <p className="text-sm text-text-muted">No sources match these filters.</p>}
      </div>
    </div>
  );
}

function DiscoverCard({ entry }: { entry: SourceCatalogEntry }) {
  return (
    <Card>
      <CardHeader className="flex items-start justify-between gap-2">
        <CardTitle>{entry.name}</CardTitle>
        <Badge tone={VERIFICATION_TONE[entry.verificationStatus]}>{entry.verificationStatus.replaceAll("_", " ")}</Badge>
      </CardHeader>
      <CardBody className="space-y-2">
        <p className="text-xs text-text-secondary">{entry.description}</p>
        <div className="flex flex-wrap gap-1.5 text-xs text-text-muted">
          <Badge tone="neutral">{CATEGORY_LABELS[entry.category]}</Badge>
          <Badge tone="neutral">{entry.regions.join(", ")}</Badge>
          <Badge tone="neutral">{entry.cost}</Badge>
        </div>
        {entry.enabled ? (
          <Link href="/data-sources" className="inline-block text-xs text-accent hover:underline">
            View on Data sources →
          </Link>
        ) : (
          <p className="text-xs text-text-muted">Not currently available for import — see note below.</p>
        )}
        {entry.note && <p className="text-xs text-text-muted">{entry.note}</p>}
      </CardBody>
    </Card>
  );
}

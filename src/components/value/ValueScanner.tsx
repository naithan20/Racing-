"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { formatDecimalOdds } from "@/lib/format";
import { ValueEdgeBadge, ConfidenceBadge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { SyntheticModelBanner } from "@/components/model/SyntheticModelBanner";

export interface ValueCandidate {
  runnerId: string;
  horseName: string;
  raceId: string;
  raceLabel: string;
  raceTime: string;
  racecourse: string;
  country: string;
  flatJumps: "FLAT" | "JUMPS";
  numberOfRunners: number;
  oddsDecimal: number;
  winProbability: number;
  modelConfidence: number | null;
  evidenceDensityScore: number | null;
  winValueEdge: number | null;
  modelPlaceProbability: number | null;
  marketImpliedPlaceProbability: number | null;
  placeValueEdge: number | null;
  ewValueScore: number | null;
  hasEnhancedPlaces: boolean;
  defaultPlaces: number;
}

const inputClass =
  "w-full rounded-md border border-border bg-bg-elevated px-2.5 py-1.5 text-sm text-text-primary outline-none focus:border-accent [color-scheme:dark]";

function RankedTable({
  title,
  candidates,
  sortKey,
}: {
  title: string;
  candidates: ValueCandidate[];
  sortKey: "winValueEdge" | "placeValueEdge" | "ewValueScore";
}) {
  const ranked = useMemo(() => {
    return [...candidates]
      .filter((c) => c[sortKey] !== null)
      .sort((a, b) => (b[sortKey] as number) - (a[sortKey] as number))
      .slice(0, 10);
  }, [candidates, sortKey]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardBody className="overflow-x-auto p-0">
        <table className="w-full min-w-[600px] text-sm">
          <thead>
            <tr className="border-b border-border-subtle bg-bg-elevated text-left text-xs uppercase tracking-wide text-text-muted">
              <th className="px-3 py-2 font-medium">Horse</th>
              <th className="px-3 py-2 font-medium">Race</th>
              <th className="px-3 py-2 font-medium">Odds</th>
              <th className="px-3 py-2 font-medium">Edge</th>
              <th className="px-3 py-2 font-medium">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {ranked.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-3 py-4 text-text-muted">
                  No candidates match the current filters.
                </td>
              </tr>
            ) : (
              ranked.map((c) => (
                <tr key={c.runnerId} className="border-b border-border-subtle last:border-b-0 hover:bg-bg-hover">
                  <td className="px-3 py-2">
                    <Link href={`/runners/${c.runnerId}`} className="text-accent hover:underline">
                      {c.horseName}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-text-secondary">
                    {c.raceTime} {c.racecourse}
                  </td>
                  <td className="px-3 py-2 font-tabular text-text-primary">{formatDecimalOdds(c.oddsDecimal)}</td>
                  <td className="px-3 py-2">
                    <ValueEdgeBadge value={c[sortKey] as number} />
                  </td>
                  <td className="px-3 py-2">
                    <ConfidenceBadge value={c.modelConfidence} />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}

export function ValueScanner({
  candidates,
  bookmakers,
  isSynthetic,
}: {
  candidates: ValueCandidate[];
  bookmakers: { id: string; name: string }[];
  isSynthetic: boolean;
}) {
  const [minOdds, setMinOdds] = useState("");
  const [maxOdds, setMaxOdds] = useState("");
  const [minWinEdge, setMinWinEdge] = useState("");
  const [minPlaceEdge, setMinPlaceEdge] = useState("");
  const [minConfidence, setMinConfidence] = useState("");
  const [minEvidence, setMinEvidence] = useState("");
  const [enhancedOnly, setEnhancedOnly] = useState(false);
  const [flatJumps, setFlatJumps] = useState("");
  const [country, setCountry] = useState("");
  const [bookmakerId, setBookmakerId] = useState("");

  const filtered = useMemo(() => {
    return candidates.filter((c) => {
      if (minOdds && c.oddsDecimal < Number(minOdds)) return false;
      if (maxOdds && c.oddsDecimal > Number(maxOdds)) return false;
      if (minWinEdge && (c.winValueEdge ?? -Infinity) < Number(minWinEdge)) return false;
      if (minPlaceEdge && (c.placeValueEdge ?? -Infinity) < Number(minPlaceEdge)) return false;
      if (minConfidence && (c.modelConfidence ?? 0) < Number(minConfidence)) return false;
      if (minEvidence && (c.evidenceDensityScore ?? 0) < Number(minEvidence)) return false;
      if (enhancedOnly && !c.hasEnhancedPlaces) return false;
      if (flatJumps && c.flatJumps !== flatJumps) return false;
      if (country && c.country !== country) return false;
      // bookmakerId filter is informational only for now (place terms are
      // already picked from the race's default bookmaker place count).
      void bookmakerId;
      return true;
    });
  }, [candidates, minOdds, maxOdds, minWinEdge, minPlaceEdge, minConfidence, minEvidence, enhancedOnly, flatJumps, country, bookmakerId]);

  return (
    <div className="flex flex-col gap-4">
      {isSynthetic && <SyntheticModelBanner />}

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardBody className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-9">
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Min odds</span>
            <input className={inputClass} type="number" step="0.5" value={minOdds} onChange={(e) => setMinOdds(e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Max odds</span>
            <input className={inputClass} type="number" step="0.5" value={maxOdds} onChange={(e) => setMaxOdds(e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Min win edge</span>
            <input className={inputClass} type="number" step="0.01" value={minWinEdge} onChange={(e) => setMinWinEdge(e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Min place edge</span>
            <input className={inputClass} type="number" step="0.01" value={minPlaceEdge} onChange={(e) => setMinPlaceEdge(e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Min confidence</span>
            <input className={inputClass} type="number" step="0.05" value={minConfidence} onChange={(e) => setMinConfidence(e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Min evidence</span>
            <input className={inputClass} type="number" step="0.05" value={minEvidence} onChange={(e) => setMinEvidence(e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Flat / Jumps</span>
            <select className={inputClass} value={flatJumps} onChange={(e) => setFlatJumps(e.target.value)}>
              <option value="">Any</option>
              <option value="FLAT">Flat</option>
              <option value="JUMPS">Jumps</option>
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Country</span>
            <select className={inputClass} value={country} onChange={(e) => setCountry(e.target.value)}>
              <option value="">Any</option>
              <option value="GB">UK</option>
              <option value="IRE">Ireland</option>
              <option value="FR">France</option>
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Bookmaker</span>
            <select className={inputClass} value={bookmakerId} onChange={(e) => setBookmakerId(e.target.value)}>
              <option value="">Any</option>
              {bookmakers.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
          <label className="col-span-2 flex items-end gap-2 sm:col-span-1">
            <input type="checkbox" checked={enhancedOnly} onChange={(e) => setEnhancedOnly(e.target.checked)} className="h-4 w-4" />
            <span className="text-xs text-text-secondary">Enhanced places only</span>
          </label>
        </CardBody>
      </Card>

      <p className="text-xs text-text-muted">{filtered.length} candidate(s) match current filters.</p>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <RankedTable title="Best win value" candidates={filtered} sortKey="winValueEdge" />
        <RankedTable title="Best place value" candidates={filtered} sortKey="placeValueEdge" />
        <RankedTable title="Best each-way value" candidates={filtered} sortKey="ewValueScore" />
      </div>
    </div>
  );
}

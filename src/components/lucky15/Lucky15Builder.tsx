"use client";

import { useActionState, useMemo, useState } from "react";
import Link from "next/link";

import { createLucky15SlipAction } from "@/actions/lucky15";
import { INITIAL_LUCKY15_STATE } from "@/actions/state";
import { formatDecimalOdds, formatDistance } from "@/lib/format";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { NotConfigured } from "@/components/ui/NotConfigured";

export interface Lucky15Candidate {
  runnerId: string;
  horseName: string;
  raceLabel: string;
  raceTime: string;
  racecourse: string;
  country: string;
  flatJumps: "FLAT" | "JUMPS";
  numberOfRunners: number;
  oddsDecimal: number | null;
  distanceFurlongs: number;
  hasEnhancedPlaces: boolean;
  confidence: number | null;
  placeEdge: number | null;
}

const inputClass =
  "w-full rounded-md border border-border bg-bg-elevated px-2.5 py-1.5 text-sm text-text-primary outline-none focus:border-accent [color-scheme:dark]";

export function Lucky15Builder({
  candidates,
  bookmakers,
}: {
  candidates: Lucky15Candidate[];
  bookmakers: { id: string; name: string }[];
}) {
  const [state, formAction, pending] = useActionState(createLucky15SlipAction, INITIAL_LUCKY15_STATE);

  const [minOdds, setMinOdds] = useState("");
  const [maxOdds, setMaxOdds] = useState("");
  const [minRunners, setMinRunners] = useState("");
  const [enhancedOnly, setEnhancedOnly] = useState(false);
  const [flatJumps, setFlatJumps] = useState("");
  const [country, setCountry] = useState("");
  const [selected, setSelected] = useState<string[]>([]);

  const filtered = useMemo(() => {
    return candidates.filter((c) => {
      if (minOdds && (c.oddsDecimal ?? 0) < Number(minOdds)) return false;
      if (maxOdds && (c.oddsDecimal ?? Infinity) > Number(maxOdds)) return false;
      if (minRunners && c.numberOfRunners < Number(minRunners)) return false;
      if (enhancedOnly && !c.hasEnhancedPlaces) return false;
      if (flatJumps && c.flatJumps !== flatJumps) return false;
      if (country && c.country !== country) return false;
      return true;
    });
  }, [candidates, minOdds, maxOdds, minRunners, enhancedOnly, flatJumps, country]);

  function toggleLeg(runnerId: string) {
    setSelected((prev) => {
      if (prev.includes(runnerId)) return prev.filter((id) => id !== runnerId);
      if (prev.length >= 4) return prev;
      return [...prev, runnerId];
    });
  }

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardBody className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-7">
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Min odds</span>
            <input
              className={inputClass}
              type="number"
              step="0.5"
              name="minOddsDecimal"
              value={minOdds}
              onChange={(e) => setMinOdds(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Max odds</span>
            <input
              className={inputClass}
              type="number"
              step="0.5"
              name="maxOddsDecimal"
              value={maxOdds}
              onChange={(e) => setMaxOdds(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Min confidence</span>
            <input className={inputClass} type="number" step="0.05" name="minConfidence" placeholder="n/a" />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Min place edge</span>
            <input className={inputClass} type="number" step="0.01" name="minPlaceEdge" placeholder="n/a" />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Min runners</span>
            <input
              className={inputClass}
              type="number"
              name="minRunners"
              value={minRunners}
              onChange={(e) => setMinRunners(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Flat / Jumps</span>
            <select
              className={inputClass}
              name="flatJumpsFilter"
              value={flatJumps}
              onChange={(e) => setFlatJumps(e.target.value)}
            >
              <option value="">Any</option>
              <option value="FLAT">Flat</option>
              <option value="JUMPS">Jumps</option>
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Country</span>
            <select
              className={inputClass}
              name="countryFilter"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
            >
              <option value="">Any</option>
              <option value="GB">UK</option>
              <option value="IRE">Ireland</option>
              <option value="FR">France</option>
            </select>
          </label>
          <label className="col-span-2 flex items-end gap-2 sm:col-span-1">
            <input
              type="checkbox"
              name="enhancedPlacesOnly"
              checked={enhancedOnly}
              onChange={(e) => setEnhancedOnly(e.target.checked)}
              className="h-4 w-4"
            />
            <span className="text-xs text-text-secondary">Enhanced places only</span>
          </label>
          <label className="col-span-2 block sm:col-span-2">
            <span className="mb-1 block text-xs text-text-secondary">Bookmaker</span>
            <select className={inputClass} name="bookmakerId" defaultValue="">
              <option value="">Any</option>
              {bookmakers.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
        </CardBody>
      </Card>

      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>Candidates ({filtered.length})</CardTitle>
          <span className="text-xs text-text-muted">{selected.length}/4 legs selected</span>
        </CardHeader>
        <CardBody className="overflow-x-auto p-0">
          <table className="w-full min-w-[900px] text-sm">
            <thead>
              <tr className="border-b border-border-subtle bg-bg-elevated text-left text-xs uppercase tracking-wide text-text-muted">
                <th className="px-3 py-2 font-medium"></th>
                <th className="px-3 py-2 font-medium">Horse</th>
                <th className="px-3 py-2 font-medium">Race</th>
                <th className="px-3 py-2 font-medium">Odds</th>
                <th className="px-3 py-2 font-medium">Runners</th>
                <th className="px-3 py-2 font-medium">Confidence</th>
                <th className="px-3 py-2 font-medium">Place edge</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.runnerId} className="border-b border-border-subtle last:border-b-0 hover:bg-bg-hover">
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      name="runnerIds"
                      value={c.runnerId}
                      checked={selected.includes(c.runnerId)}
                      onChange={() => toggleLeg(c.runnerId)}
                      disabled={!selected.includes(c.runnerId) && selected.length >= 4}
                      className="h-4 w-4"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <Link href={`/runners/${c.runnerId}`} className="text-accent hover:underline">
                      {c.horseName}
                    </Link>
                  </td>
                  <td className="px-3 py-2 text-text-secondary">
                    {c.raceTime} {c.racecourse} · {formatDistance(c.distanceFurlongs)}
                  </td>
                  <td className="px-3 py-2 font-tabular text-text-primary">{formatDecimalOdds(c.oddsDecimal)}</td>
                  <td className="px-3 py-2 font-tabular text-text-secondary">{c.numberOfRunners}</td>
                  <td className="px-3 py-2">{c.confidence !== null ? c.confidence : <NotConfigured compact />}</td>
                  <td className="px-3 py-2">{c.placeEdge !== null ? c.placeEdge : <NotConfigured compact />}</td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-4 text-text-muted">
                    No candidates match these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <div className="flex items-center gap-3">
        <input
          type="text"
          name="name"
          placeholder="Slip name (optional)"
          className={`${inputClass} max-w-xs`}
        />
        <button
          type="submit"
          disabled={pending || selected.length !== 4}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          {pending ? "Saving…" : "Save Lucky 15 slip"}
        </button>
        {state.status !== "idle" && (
          <span className={state.status === "error" ? "text-sm text-negative" : "text-sm text-positive"}>
            {state.message}
          </span>
        )}
      </div>
    </form>
  );
}

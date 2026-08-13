"use client";

import { useActionState } from "react";

import { createRaceAction } from "@/actions/races";
import { INITIAL_CREATE_RACE_STATE } from "@/actions/state";
import { Card, CardBody } from "@/components/ui/Card";

const inputClass =
  "w-full rounded-md border border-border bg-bg-elevated px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent [color-scheme:dark]";
const labelClass = "mb-1 block text-xs font-medium text-text-secondary";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className={labelClass}>{label}</span>
      {children}
    </label>
  );
}

export function NewRaceForm() {
  const [state, formAction, pending] = useActionState(createRaceAction, INITIAL_CREATE_RACE_STATE);

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <Card>
        <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Race date">
            <input type="date" name="raceDate" required className={inputClass} defaultValue={new Date().toISOString().slice(0, 10)} />
          </Field>
          <Field label="Off time (24h, e.g. 14:35)">
            <input type="text" name="raceTime" required placeholder="14:35" className={inputClass} />
          </Field>
          <Field label="Racecourse">
            <input type="text" name="racecourse" required className={inputClass} />
          </Field>
          <Field label="Country">
            <input type="text" name="country" required placeholder="GB" className={inputClass} />
          </Field>
          <Field label="Race name">
            <input type="text" name="raceName" required className={inputClass} />
          </Field>
          <Field label="Flat / Jumps">
            <select name="flatJumps" required className={inputClass} defaultValue="FLAT">
              <option value="FLAT">Flat</option>
              <option value="JUMPS">Jumps</option>
            </select>
          </Field>
          <Field label="Surface">
            <select name="surface" required className={inputClass} defaultValue="TURF">
              <option value="TURF">Turf</option>
              <option value="ALL_WEATHER">All weather</option>
              <option value="DIRT">Dirt</option>
            </select>
          </Field>
          <Field label="Handicap type">
            <select name="handicapType" required className={inputClass} defaultValue="NON_HANDICAP">
              <option value="HANDICAP">Handicap</option>
              <option value="NON_HANDICAP">Non-handicap</option>
            </select>
          </Field>
          <Field label="Distance (furlongs)">
            <input type="number" step="0.1" name="distanceFurlongs" required className={inputClass} />
          </Field>
          <Field label="Class">
            <input type="number" name="raceClass" className={inputClass} />
          </Field>
          <Field label="Grade/Group (optional)">
            <input type="text" name="gradeGroup" placeholder="Group 1 / Grade 2" className={inputClass} />
          </Field>
          <Field label="Going">
            <input type="text" name="going" placeholder="Good to Soft" className={inputClass} />
          </Field>
          <Field label="Age restriction">
            <input type="text" name="ageRestriction" placeholder="3yo+" className={inputClass} />
          </Field>
          <Field label="Sex restriction">
            <input type="text" name="sexRestriction" placeholder="Fillies & Mares" className={inputClass} />
          </Field>
          <Field label="Each-way fraction">
            <input type="number" step="0.05" name="eachWayFraction" placeholder="0.2" className={inputClass} />
          </Field>
          <Field label="Bookmaker places (default)">
            <input type="number" name="bookmakerPlaces" placeholder="3" className={inputClass} />
          </Field>
        </CardBody>
      </Card>

      <Card>
        <CardBody>
          <Field label="Runners — one per line: Horse Name | Trainer | Jockey | OR | Odds (decimal) | Draw">
            <textarea
              name="runnerLines"
              required
              rows={8}
              placeholder={"Sample Star | J. Sample | R. Rider | 132 | 5.5 | 4\nAnother Runner | A. Trainer | S. Jockey | 128 | 8.0 | 2"}
              className={`${inputClass} font-mono-num`}
            />
          </Field>
          <p className="mt-2 text-xs text-text-muted">
            Only the horse name is required — trailing fields may be left blank (e.g. <code>Sample Star | | | | 6.0</code>).
          </p>
        </CardBody>
      </Card>

      {state.status === "error" && (
        <div className="rounded-md border border-negative/40 bg-negative-soft px-3 py-2 text-sm text-negative">
          {state.message}
        </div>
      )}

      <button
        type="submit"
        disabled={pending}
        className="self-start rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
      >
        {pending ? "Creating…" : "Create race"}
      </button>
    </form>
  );
}

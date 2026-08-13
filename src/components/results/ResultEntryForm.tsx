"use client";

import { useActionState, useState } from "react";

import { submitRaceResultsAction } from "@/actions/results";
import { INITIAL_RESULT_STATE } from "@/actions/state";
import { OBSERVATION_TAG_OPTIONS } from "@/results/observationLabels";
import type { ObservationTagType } from "@/generated/prisma/enums";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";

export interface ResultRunnerInput {
  runnerId: string;
  horseName: string;
  clothNumber: number | null;
  defaultOddsDecimal: number | null;
  existingFinishingPosition: number | null;
  existingFinishStatus: string | null;
  existingSp: number | null;
  existingClosing: number | null;
  existingTags: ObservationTagType[];
  existingFreeText: string;
}

const inputClass =
  "w-full rounded-md border border-border bg-bg-elevated px-2 py-1 text-sm text-text-primary outline-none focus:border-accent [color-scheme:dark]";

const FINISH_STATUS_OPTIONS = ["RAN", "PU", "UR", "F", "BD", "DSQ", "NR"];

function RunnerResultRow({ runner }: { runner: ResultRunnerInput }) {
  const [showTags, setShowTags] = useState(false);

  return (
    <div className="border-b border-border-subtle py-3 last:border-b-0">
      <div className="flex flex-wrap items-center gap-3">
        <span className="w-40 shrink-0 text-sm font-medium text-text-primary">
          {runner.clothNumber ? `${runner.clothNumber}. ` : ""}
          {runner.horseName}
        </span>
        <label className="flex items-center gap-1.5 text-xs text-text-secondary">
          Pos
          <input
            type="number"
            min={1}
            name={`position_${runner.runnerId}`}
            defaultValue={runner.existingFinishingPosition ?? ""}
            className={`${inputClass} w-16`}
          />
        </label>
        <label className="flex items-center gap-1.5 text-xs text-text-secondary">
          Status
          <select
            name={`status_${runner.runnerId}`}
            defaultValue={runner.existingFinishStatus ?? "RAN"}
            className={`${inputClass} w-24`}
          >
            {FINISH_STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1.5 text-xs text-text-secondary">
          SP
          <input
            type="number"
            step="0.01"
            name={`sp_${runner.runnerId}`}
            defaultValue={runner.existingSp ?? runner.defaultOddsDecimal ?? ""}
            className={`${inputClass} w-20`}
          />
        </label>
        <label className="flex items-center gap-1.5 text-xs text-text-secondary">
          Closing
          <input
            type="number"
            step="0.01"
            name={`closing_${runner.runnerId}`}
            defaultValue={runner.existingClosing ?? ""}
            className={`${inputClass} w-20`}
          />
        </label>
        <button
          type="button"
          onClick={() => setShowTags((v) => !v)}
          className="ml-auto text-xs text-accent hover:underline"
        >
          {showTags ? "Hide observations" : "Add observations"}
        </button>
      </div>

      {showTags && (
        <div className="mt-3 flex flex-col gap-2 rounded-md border border-border-subtle bg-bg-elevated p-3">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3 lg:grid-cols-4">
            {OBSERVATION_TAG_OPTIONS.map(([value, label]) => (
              <label key={value} className="flex items-center gap-1.5 text-xs text-text-secondary">
                <input
                  type="checkbox"
                  name={`tags_${runner.runnerId}`}
                  value={value}
                  defaultChecked={runner.existingTags.includes(value)}
                  className="h-3.5 w-3.5"
                />
                {label}
              </label>
            ))}
          </div>
          <label className="block">
            <span className="mb-1 block text-xs text-text-secondary">Free-text observation</span>
            <textarea
              name={`freetext_${runner.runnerId}`}
              defaultValue={runner.existingFreeText}
              rows={2}
              className={inputClass}
            />
          </label>
        </div>
      )}
    </div>
  );
}

export function ResultEntryForm({ raceId, runners }: { raceId: string; runners: ResultRunnerInput[] }) {
  const [state, formAction, pending] = useActionState(submitRaceResultsAction, INITIAL_RESULT_STATE);

  return (
    <form action={formAction} className="flex flex-col gap-4">
      <input type="hidden" name="raceId" value={raceId} />
      <Card>
        <CardHeader>
          <CardTitle>Runner results</CardTitle>
        </CardHeader>
        <CardBody>
          {runners.map((runner) => (
            <RunnerResultRow key={runner.runnerId} runner={runner} />
          ))}
        </CardBody>
      </Card>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={pending}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {pending ? "Saving…" : "Save results"}
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

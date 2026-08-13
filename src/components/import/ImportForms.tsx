"use client";

import { useActionState } from "react";

import { importCsvAction, importJsonAction } from "@/actions/imports";
import { INITIAL_IMPORT_STATE, type ImportActionState } from "@/actions/state";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";

function ResultPanel({ state }: { state: ImportActionState }) {
  if (state.status === "idle") return null;
  return (
    <div
      className={`mt-3 rounded-md border px-3 py-2 text-sm ${
        state.status === "error"
          ? "border-negative/40 bg-negative-soft text-negative"
          : "border-positive/40 bg-positive-soft text-positive"
      }`}
    >
      <p>{state.message}</p>
      {state.rowErrors.length > 0 && (
        <ul className="mt-2 max-h-48 overflow-y-auto text-xs text-negative/90">
          {state.rowErrors.map((e, i) => (
            <li key={i}>
              Row {e.row}: {e.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function CsvImportForm() {
  const [state, formAction, pending] = useActionState(importCsvAction, INITIAL_IMPORT_STATE);

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>CSV import</CardTitle>
        <a href="/import/template" className="text-xs text-accent hover:underline">
          Download template
        </a>
      </CardHeader>
      <CardBody>
        <p className="mb-3 text-sm text-text-secondary">
          One row per runner. Rows sharing the same date, time and racecourse are grouped into a single
          race. See the README for the full column reference.
        </p>
        <form action={formAction} className="flex flex-wrap items-center gap-3">
          <input
            type="file"
            name="file"
            accept=".csv,text/csv"
            required
            className="text-sm text-text-secondary file:mr-3 file:rounded-md file:border file:border-border file:bg-bg-elevated file:px-3 file:py-1.5 file:text-sm file:text-text-primary"
          />
          <button
            type="submit"
            disabled={pending}
            className="rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {pending ? "Importing…" : "Import CSV"}
          </button>
        </form>
        <ResultPanel state={state} />
      </CardBody>
    </Card>
  );
}

export function JsonImportForm() {
  const [state, formAction, pending] = useActionState(importJsonAction, INITIAL_IMPORT_STATE);

  return (
    <Card>
      <CardHeader>
        <CardTitle>JSON import</CardTitle>
      </CardHeader>
      <CardBody>
        <p className="mb-3 text-sm text-text-secondary">
          Format: <code className="rounded bg-bg-elevated px-1 py-0.5">{"{ \"races\": [ { ...race, \"runners\": [...] } ] }"}</code>.
          Upload a file or paste JSON below.
        </p>
        <form action={formAction} className="flex flex-col gap-3">
          <input
            type="file"
            name="file"
            accept=".json,application/json"
            className="text-sm text-text-secondary file:mr-3 file:rounded-md file:border file:border-border file:bg-bg-elevated file:px-3 file:py-1.5 file:text-sm file:text-text-primary"
          />
          <textarea
            name="jsonText"
            rows={6}
            placeholder='{"races": [...]}'
            className="w-full rounded-md border border-border bg-bg-elevated px-3 py-2 font-mono-num text-xs text-text-primary outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={pending}
            className="self-start rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {pending ? "Importing…" : "Import JSON"}
          </button>
        </form>
        <ResultPanel state={state} />
      </CardBody>
    </Card>
  );
}

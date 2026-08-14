"use client";

import { useActionState } from "react";

import { connectKaggleAction, disconnectKaggleAction } from "@/actions/dataSources";
import { INITIAL_DATA_CONNECTION_STATE } from "@/actions/state";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/Card";
import { formatDate } from "@/lib/format";

export function KaggleConnectionCard({
  connected,
  connectedAt,
}: {
  connected: boolean;
  connectedAt: Date | null;
}) {
  const [state, formAction, pending] = useActionState(connectKaggleAction, INITIAL_DATA_CONNECTION_STATE);

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>Kaggle</CardTitle>
        <Badge tone={connected ? "positive" : "neutral"}>{connected ? "Connected" : "Not connected"}</Badge>
      </CardHeader>
      <CardBody className="space-y-4">
        <p className="text-sm text-text-secondary">
          Uses the official Kaggle API only — no scraping. Credentials are stored server-side only and
          are never sent to the browser. Get an API token from{" "}
          <span className="font-mono text-xs">kaggle.com/settings/account</span> (&quot;Create New
          API Token&quot;), which gives you a username and key.
        </p>

        {connected ? (
          <div className="flex items-center gap-3">
            {connectedAt && <span className="text-xs text-text-muted">Connected {formatDate(connectedAt)}</span>}
            <button
              type="button"
              onClick={() => disconnectKaggleAction()}
              className="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-bg-hover"
            >
              Disconnect
            </button>
          </div>
        ) : (
          <form action={formAction} className="flex flex-col gap-3 sm:max-w-sm">
            <label className="flex flex-col gap-1 text-xs text-text-secondary">
              Kaggle username
              <input
                type="text"
                name="username"
                required
                className="rounded-md border border-border bg-bg-panel px-2 py-1.5 text-sm text-text-primary"
              />
            </label>
            <label className="flex flex-col gap-1 text-xs text-text-secondary">
              API key
              <input
                type="password"
                name="apiKey"
                required
                className="rounded-md border border-border bg-bg-panel px-2 py-1.5 text-sm text-text-primary"
              />
            </label>
            {state.status === "error" && <p className="text-xs text-negative">{state.message}</p>}
            <button
              type="submit"
              disabled={pending}
              className="self-start rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              {pending ? "Connecting…" : "Connect Kaggle"}
            </button>
          </form>
        )}
      </CardBody>
    </Card>
  );
}

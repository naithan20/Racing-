"use client";

import { useState, useTransition } from "react";

import { previewUrlAction, type UrlPreviewResult } from "@/actions/dataSources";

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "unknown";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

/** The "type a URL -> preview -> confirm" step required before a downloadUrl is submitted as part of the surrounding import form. Renders a hidden `downloadUrl` input once the user has previewed AND confirmed — the surrounding <form> won't have a usable value until then. */
export function UrlSourceForm({ onConfirmed }: { onConfirmed: (url: string) => void }) {
  const [url, setUrl] = useState("");
  const [preview, setPreview] = useState<UrlPreviewResult | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [pending, startTransition] = useTransition();

  function handlePreview() {
    setConfirmed(false);
    onConfirmed("");
    startTransition(async () => {
      const result = await previewUrlAction(url);
      setPreview(result);
    });
  }

  return (
    <div className="flex flex-col gap-2">
      <label className="flex flex-col gap-1 text-xs text-text-secondary">
        Direct file URL
        <div className="flex gap-2">
          <input
            type="url"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setPreview(null);
              setConfirmed(false);
              onConfirmed("");
            }}
            placeholder="https://…"
            className="flex-1 rounded-md border border-border bg-bg-panel px-2 py-1.5 text-sm text-text-primary"
          />
          <button
            type="button"
            onClick={handlePreview}
            disabled={!url || pending}
            className="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary hover:bg-bg-hover disabled:opacity-50"
          >
            {pending ? "Checking…" : "Preview"}
          </button>
        </div>
      </label>

      {preview && (
        <div className="rounded-md border border-border-subtle bg-bg-elevated p-3 text-xs">
          {!preview.valid ? (
            <p className="text-negative">{preview.error}</p>
          ) : (
            <>
              <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
                <dt className="text-text-muted">Hostname</dt>
                <dd className="font-mono text-text-primary">{preview.hostname}</dd>
                <dt className="text-text-muted">File type</dt>
                <dd className="text-text-primary">
                  {preview.fileExtension ?? "unknown"}{" "}
                  {preview.isAllowedExtension ? (
                    <span className="text-positive">(supported)</span>
                  ) : (
                    <span className="text-negative">(not a supported data file)</span>
                  )}
                </dd>
                <dt className="text-text-muted">Expected size</dt>
                <dd className="text-text-primary">{formatBytes(preview.contentLengthBytes)}</dd>
              </dl>

              {preview.isAllowedExtension ? (
                <label className="mt-2 flex items-center gap-2 text-text-secondary">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    onChange={(e) => {
                      setConfirmed(e.target.checked);
                      onConfirmed(e.target.checked ? url : "");
                    }}
                  />
                  I&apos;ve reviewed this source ({preview.hostname}) and want to download from it.
                </label>
              ) : (
                <p className="mt-2 text-negative">
                  RacingEdge only downloads recognised data files (csv/json/jsonl/db/sqlite/zip/gz) — this URL can&apos;t be used.
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Streaming, size-capped, server-side download — the Vercel-compatible
 * replacement for `racingedge_data.providers.download_adapter.download_file`
 * (which writes to a local filesystem path, unavailable on Vercel) and
 * `KaggleAdapter.download_dataset` (which shells out to the official
 * `kaggle` Python package).
 *
 * Runs as plain `fetch()` inside a Next.js Server Action / Route Handler —
 * no subprocess, no disk write, the whole response body is held in memory
 * and returned as a Buffer. Bounded by MAX_DOWNLOAD_BYTES and a wall-clock
 * timeout so one request can't exceed Vercel's serverless function memory
 * or `maxDuration` budget. This is a genuine, documented limit (see
 * FREE_DATA_SOURCES.md) — a dataset larger than the cap gets a clear error
 * telling the user to use the CLI pipeline instead, never a silent partial
 * import.
 */

// 60MB compressed — comfortably inside a Vercel serverless function's
// default 1024MB memory budget even after decompression (racing CSVs
// compress well; a 60MB ZIP is unlikely to inflate past a few hundred MB
// of text, which Node handles fine as a single in-memory string).
export const MAX_DOWNLOAD_BYTES = 60 * 1024 * 1024;
const DOWNLOAD_TIMEOUT_MS = 45_000;

export class DownloadTooLargeError extends Error {
  constructor(limitBytes: number) {
    super(
      `The response exceeded RacingEdge's ${Math.round(limitBytes / (1024 * 1024))}MB one-tap import limit. ` +
        "Use the CLI pipeline (npm run data:import-free) for datasets this size — it streams to disk instead of memory."
    );
    this.name = "DownloadTooLargeError";
  }
}

export interface DownloadResult {
  buffer: Buffer;
  contentType: string | null;
  status: number;
}

/** Fetches a URL with a hard byte cap enforced DURING the stream (not just checked against Content-Length, which a server can omit or lie about) and a wall-clock timeout. */
export async function downloadWithCap(
  url: string,
  init?: RequestInit,
  maxBytes: number = MAX_DOWNLOAD_BYTES
): Promise<DownloadResult> {
  const response = await fetch(url, { ...init, redirect: "follow", signal: AbortSignal.timeout(DOWNLOAD_TIMEOUT_MS) });

  const declaredLength = response.headers.get("content-length");
  if (declaredLength && Number(declaredLength) > maxBytes) {
    throw new DownloadTooLargeError(maxBytes);
  }

  if (!response.body) {
    const buffer = Buffer.from(await response.arrayBuffer());
    if (buffer.byteLength > maxBytes) throw new DownloadTooLargeError(maxBytes);
    return { buffer, contentType: response.headers.get("content-type"), status: response.status };
  }

  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let received = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    received += value.byteLength;
    if (received > maxBytes) {
      await reader.cancel();
      throw new DownloadTooLargeError(maxBytes);
    }
    chunks.push(value);
  }

  return { buffer: Buffer.concat(chunks), contentType: response.headers.get("content-type"), status: response.status };
}

// ---------------------------------------------------------------------------
// Kaggle
// ---------------------------------------------------------------------------

export class KaggleAuthRequiredError extends Error {
  constructor(datasetRef: string) {
    super(
      `Kaggle requires authentication to download "${datasetRef}". Either connect Kaggle in Settings -> ` +
        "Data Connections (local development), or set KAGGLE_USERNAME and KAGGLE_KEY as environment " +
        "variables on your deployment (the same way DATABASE_URL is configured) — RacingEdge never stores " +
        "Kaggle credentials in the database."
    );
    this.name = "KaggleAuthRequiredError";
  }
}

export class KaggleDatasetNotFoundError extends Error {
  constructor(datasetRef: string) {
    super(`Kaggle dataset not found: "${datasetRef}".`);
    this.name = "KaggleDatasetNotFoundError";
  }
}

function kaggleDownloadUrl(datasetRef: string): string {
  return `https://www.kaggle.com/api/v1/datasets/download/${datasetRef}`;
}

/**
 * Downloads a Kaggle dataset's ZIP without any local Python/kaggle-package
 * dependency, using the same public REST endpoint the official `kaggle`
 * CLI/package calls — never scraping kaggle.com's HTML.
 *
 * Kaggle's own policy on whether a PUBLIC dataset's download requires
 * authentication has genuinely conflicting public documentation (an
 * announced April 2024 API change toward anonymous access for public
 * datasets, vs. long-standing account-required behaviour reported
 * elsewhere) — and this build's sandbox has kaggle.com blocked at the
 * network-egress-policy level, so it could not be verified empirically
 * either way (see FREE_DATA_SOURCES.md). Rather than guess, this function
 * ATTEMPTS the request and classifies whatever Kaggle's server actually
 * says at request time: a real deployment (unlike this sandbox) can reach
 * kaggle.com, so the answer becomes a fact instead of an assumption the
 * first time this runs in production.
 */
export async function downloadKaggleDataset(datasetRef: string): Promise<DownloadResult> {
  const username = process.env.KAGGLE_USERNAME;
  const key = process.env.KAGGLE_KEY;
  const headers: Record<string, string> = {};
  if (username && key) {
    headers.Authorization = `Basic ${Buffer.from(`${username}:${key}`).toString("base64")}`;
  }

  const result = await downloadWithCap(kaggleDownloadUrl(datasetRef), { headers });

  if (result.status === 401 || result.status === 403) {
    throw new KaggleAuthRequiredError(datasetRef);
  }
  if (result.status === 404) {
    throw new KaggleDatasetNotFoundError(datasetRef);
  }
  if (result.status >= 400) {
    throw new Error(`Kaggle returned HTTP ${result.status} for "${datasetRef}".`);
  }
  // Kaggle serves its login page (text/html) instead of a clean 401/403
  // for some anonymous-blocked requests — treat that the same way, rather
  // than trying to parse HTML as a dataset.
  if (result.contentType?.includes("text/html")) {
    throw new KaggleAuthRequiredError(datasetRef);
  }

  return result;
}

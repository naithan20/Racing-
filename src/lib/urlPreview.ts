/**
 * Pure URL classification for the "Add data source from URL" flow —
 * deliberately mirrors `racingedge_data.providers.download_adapter`'s
 * `ALLOWED_EXTENSIONS` so the browser-side preview and the Python
 * download step never disagree about what's downloadable. Kept here
 * (not shelling out to Python) since it's a trivial, synchronous check
 * that the UI needs before showing a confirmation step — no network
 * call, no import job created yet.
 */

export const ALLOWED_URL_EXTENSIONS = [".csv", ".json", ".jsonl", ".ndjson", ".db", ".sqlite", ".sqlite3", ".zip", ".gz", ".gzip"] as const;

export interface UrlClassification {
  valid: boolean;
  error: string | null;
  hostname: string;
  scheme: string;
  fileExtension: string | null;
  isAllowedExtension: boolean;
}

export function classifyUrl(rawUrl: string): UrlClassification {
  let parsed: URL;
  try {
    parsed = new URL(rawUrl);
  } catch {
    return { valid: false, error: "Not a valid URL.", hostname: "", scheme: "", fileExtension: null, isAllowedExtension: false };
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return {
      valid: false,
      error: "Only http/https URLs are supported.",
      hostname: parsed.hostname,
      scheme: parsed.protocol.replace(":", ""),
      fileExtension: null,
      isAllowedExtension: false,
    };
  }

  const name = parsed.pathname.split("/").pop() ?? "";
  const dotIndex = name.lastIndexOf(".");
  const fileExtension = dotIndex >= 0 ? name.slice(dotIndex).toLowerCase() : null;
  const isAllowedExtension = fileExtension !== null && (ALLOWED_URL_EXTENSIONS as readonly string[]).includes(fileExtension);

  return {
    valid: true,
    error: null,
    hostname: parsed.hostname,
    scheme: parsed.protocol.replace(":", ""),
    fileExtension,
    isAllowedExtension,
  };
}

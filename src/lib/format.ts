/**
 * Presentation-layer formatting helpers. No business logic lives here.
 */

export function formatPercent(value: number | null | undefined, decimals = 1): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatSignedPercent(value: number | null | undefined, decimals = 1): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const pct = value * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(decimals)}%`;
}

export function formatDecimalOdds(value: number | null | undefined, decimals = 2): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toFixed(decimals);
}

export function formatNumber(value: number | null | undefined, decimals = 1): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toFixed(decimals);
}

export function formatDate(date: Date | string, options?: Intl.DateTimeFormatOptions): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toLocaleDateString("en-GB", options ?? { day: "2-digit", month: "short", year: "numeric" });
}

export function formatDistance(furlongs: number | null | undefined): string {
  if (furlongs == null) return "—";
  const miles = Math.floor(furlongs / 8);
  const remainder = furlongs % 8;
  if (miles === 0) return `${formatFurlongs(remainder)}f`;
  const remainderText = remainder > 0 ? `${formatFurlongs(remainder)}f` : "";
  return `${miles}m${remainderText ? ` ${remainderText}` : ""}`;
}

function formatFurlongs(value: number): string {
  return Number.isInteger(value) ? value.toString() : value.toFixed(1);
}

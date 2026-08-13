/** Percentile of `value` within `series` (0 = lowest, 1 = highest). */
export function percentileRank(value: number, series: number[]): number {
  if (series.length === 0) return 0.5;
  const below = series.filter((v) => v < value).length;
  const equal = series.filter((v) => v === value).length;
  return (below + 0.5 * equal) / series.length;
}

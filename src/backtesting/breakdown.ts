/**
 * Groups evaluable predictions into breakdown buckets (by course, class,
 * odds band, etc.) and computes the same scoring-rule metrics used for the
 * headline dashboard numbers, per bucket. Pure aggregation over data the
 * caller already has — no database access here.
 */

import { brierScore, roiPercent, type PredictionOutcomePair } from "@/backtesting/scoring";

export interface EvaluableRow {
  winProbability: number;
  won: boolean;
  startingPriceDecimal: number | null;
}

export interface BreakdownBucket {
  bucketLabel: string;
  sampleSize: number;
  winStrikeRate: number | null;
  expectedWins: number | null;
  actualWins: number | null;
  brierScoreValue: number | null;
  roiPercentValue: number | null;
}

export function summarizeRows(rows: EvaluableRow[]): BreakdownBucket {
  const pairs: PredictionOutcomePair[] = rows.map((r) => ({ predictedProbability: r.winProbability, outcome: r.won }));
  const staked = rows.filter((r) => r.startingPriceDecimal !== null).length;
  const profit = rows.reduce((sum, r) => {
    if (r.startingPriceDecimal === null) return sum;
    return sum + (r.won ? r.startingPriceDecimal - 1 : -1);
  }, 0);

  return {
    bucketLabel: "",
    sampleSize: rows.length,
    winStrikeRate: rows.length > 0 ? rows.filter((r) => r.won).length / rows.length : null,
    expectedWins: rows.length > 0 ? rows.reduce((s, r) => s + r.winProbability, 0) : null,
    actualWins: rows.length > 0 ? rows.filter((r) => r.won).length : null,
    brierScoreValue: brierScore(pairs),
    roiPercentValue: staked > 0 ? roiPercent(staked, profit) : null,
  };
}

export function groupAndSummarize<T extends EvaluableRow>(
  rows: T[],
  bucketFn: (row: T) => string | null
): BreakdownBucket[] {
  const groups = new Map<string, T[]>();
  for (const row of rows) {
    const label = bucketFn(row);
    if (label === null) continue;
    const existing = groups.get(label);
    if (existing) existing.push(row);
    else groups.set(label, [row]);
  }
  return Array.from(groups.entries())
    .map(([label, groupRows]) => ({ ...summarizeRows(groupRows), bucketLabel: label }))
    .sort((a, b) => a.bucketLabel.localeCompare(b.bucketLabel));
}

// --- Standard bucketing functions ---

export function oddsBandLabel(oddsDecimal: number | null): string | null {
  if (oddsDecimal === null) return null;
  if (oddsDecimal < 2) return "<2 (evens or shorter)";
  if (oddsDecimal < 4) return "2-4";
  if (oddsDecimal < 8) return "4-8";
  if (oddsDecimal < 16) return "8-16";
  return "16+";
}

export function confidenceBandLabel(confidence: number | null): string | null {
  if (confidence === null) return null;
  if (confidence < 0.33) return "low (<33%)";
  if (confidence < 0.5) return "mid-low (33-50%)";
  if (confidence < 0.66) return "mid-high (50-66%)";
  return "high (66%+)";
}

export function evidenceBandLabel(evidenceDensity: number | null): string | null {
  if (evidenceDensity === null) return null;
  if (evidenceDensity < 0.2) return "very low";
  if (evidenceDensity < 0.4) return "low";
  if (evidenceDensity < 0.65) return "moderate";
  if (evidenceDensity < 0.85) return "high";
  return "very high";
}

export function distanceBandLabel(distanceFurlongs: number | null): string | null {
  if (distanceFurlongs === null) return null;
  if (distanceFurlongs < 8) return "sprint (<8f)";
  if (distanceFurlongs < 12) return "mile (8-12f)";
  if (distanceFurlongs < 20) return "middle (12-20f)";
  return "staying (20f+)";
}

export function ageBandLabel(age: number | null): string | null {
  if (age === null) return null;
  if (age <= 3) return "2-3yo";
  if (age <= 5) return "4-5yo";
  if (age <= 7) return "6-7yo";
  return "8yo+";
}

export function fieldSizeBandLabel(fieldSize: number | null): string | null {
  if (fieldSize === null) return null;
  if (fieldSize <= 7) return "small (≤7)";
  if (fieldSize <= 13) return "medium (8-13)";
  return "large (14+)";
}

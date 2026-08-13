/**
 * Model performance dashboard — placeholder metric definitions.
 *
 * No backtesting logic runs yet because there is no model to backtest.
 * These types define the shape the dashboard will render once
 * PredictionSnapshot + ResultEntry rows exist in volume. Every metric is
 * nullable and should render as "Not enough data yet" / "Model not yet
 * configured" until real predictions accumulate.
 */

export interface PerformanceSummary {
  numberOfSelections: number | null;
  winStrikeRate: number | null;
  placeStrikeRate: number | null;
  roiPercent: number | null;
  averageOddsDecimal: number | null;
  expectedWins: number | null;
  actualWins: number | null;
  expectedPlaces: number | null;
  actualPlaces: number | null;
  calibrationScore: number | null;
  brierScore: number | null;
  logLoss: number | null;
  closingLineValuePercent: number | null;
}

export type PerformanceBreakdownDimension =
  | "ODDS_BAND"
  | "RACE_CLASS"
  | "COURSE"
  | "DISTANCE"
  | "GOING"
  | "AGE"
  | "FLAT_JUMPS"
  | "EVIDENCE_CONFIDENCE"
  | "SELECTION_TYPE";

export interface PerformanceBreakdownRow {
  dimension: PerformanceBreakdownDimension;
  bucketLabel: string;
  summary: PerformanceSummary;
}

export const EMPTY_PERFORMANCE_SUMMARY: PerformanceSummary = {
  numberOfSelections: null,
  winStrikeRate: null,
  placeStrikeRate: null,
  roiPercent: null,
  averageOddsDecimal: null,
  expectedWins: null,
  actualWins: null,
  expectedPlaces: null,
  actualPlaces: null,
  calibrationScore: null,
  brierScore: null,
  logLoss: null,
  closingLineValuePercent: null,
};

export const PERFORMANCE_BREAKDOWN_DIMENSIONS: PerformanceBreakdownDimension[] = [
  "ODDS_BAND",
  "RACE_CLASS",
  "COURSE",
  "DISTANCE",
  "GOING",
  "AGE",
  "FLAT_JUMPS",
  "EVIDENCE_CONFIDENCE",
  "SELECTION_TYPE",
];

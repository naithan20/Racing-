/**
 * Transparent, threshold-based badges shown on the race analysis table and
 * runner detail page. Every threshold here is a documented constant, not a
 * hidden model output — badges must always be explainable by pointing at a
 * number and a cutoff.
 */

export const BADGE_THRESHOLDS = {
  /** Value edge (model probability - market implied probability) above which a selection is flagged HIGH VALUE. */
  highValueEdge: 0.05,
  /** Model confidence (0-1) below which a selection is flagged LOW CONFIDENCE. */
  lowConfidence: 0.4,
  /** Evidence density (0-1) above which a selection is flagged HIGH EVIDENCE. */
  highEvidenceDensity: 0.7,
  /** RunnerPaceProfile.paceCollapseProbability above which a runner is flagged PACE RISK. */
  paceCollapseRisk: 0.4,
  /** Draw is flagged DRAW RISK when in the top/bottom this fraction of the field... */
  drawRiskPercentileBand: 0.15,
  /** ...and the field is at least this big (draw bias is negligible in small fields). */
  drawRiskMinFieldSize: 12,
} as const;

export interface RunnerBadgeInputs {
  valueEdgeAbsolute: number | null;
  modelConfidence: number | null;
  evidenceDensityScore: number | null;
  paceCollapseProbability: number | null;
  draw: number | null;
  fieldSize: number;
}

export type RunnerBadge = "HIGH_VALUE" | "LOW_CONFIDENCE" | "HIGH_EVIDENCE" | "PACE_RISK" | "DRAW_RISK";

export const RUNNER_BADGE_LABELS: Record<RunnerBadge, string> = {
  HIGH_VALUE: "High value",
  LOW_CONFIDENCE: "Low confidence",
  HIGH_EVIDENCE: "High evidence",
  PACE_RISK: "Pace risk",
  DRAW_RISK: "Draw risk",
};

export function computeRunnerBadges(input: RunnerBadgeInputs): RunnerBadge[] {
  const badges: RunnerBadge[] = [];

  if (input.valueEdgeAbsolute !== null && input.valueEdgeAbsolute > BADGE_THRESHOLDS.highValueEdge) {
    badges.push("HIGH_VALUE");
  }
  if (input.modelConfidence !== null && input.modelConfidence < BADGE_THRESHOLDS.lowConfidence) {
    badges.push("LOW_CONFIDENCE");
  }
  if (input.evidenceDensityScore !== null && input.evidenceDensityScore > BADGE_THRESHOLDS.highEvidenceDensity) {
    badges.push("HIGH_EVIDENCE");
  }
  if (input.paceCollapseProbability !== null && input.paceCollapseProbability > BADGE_THRESHOLDS.paceCollapseRisk) {
    badges.push("PACE_RISK");
  }
  if (
    input.draw !== null &&
    input.fieldSize >= BADGE_THRESHOLDS.drawRiskMinFieldSize &&
    isExtremeDraw(input.draw, input.fieldSize)
  ) {
    badges.push("DRAW_RISK");
  }

  return badges;
}

function isExtremeDraw(draw: number, fieldSize: number): boolean {
  if (fieldSize <= 1) return false;
  const percentile = (draw - 1) / (fieldSize - 1); // 0 = lowest draw, 1 = highest
  return percentile <= BADGE_THRESHOLDS.drawRiskPercentileBand || percentile >= 1 - BADGE_THRESHOLDS.drawRiskPercentileBand;
}

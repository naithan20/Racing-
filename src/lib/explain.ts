/**
 * Deterministic explanation engine — NO LLM. Every statement is generated
 * from a concrete threshold applied to a concrete data field, so any bullet
 * point can be traced back to exactly the number that produced it. See the
 * per-condition comments below for the exact rule.
 */

import type { RecordSummary } from "@/lib/formAggregates";
import { percentileRank } from "@/lib/percentile";

export interface ExplanationInput {
  recentFinishingPositions: { position: number | null; fieldSize: number | null }[]; // most-recent-first
  courseRecord: RecordSummary;
  distanceRecord: RecordSummary;
  goingRecord: RecordSummary;
  ratingMovement: number | null; // current OR - previous OR
  currentOfficialRating: number | null;
  bestRecentOfficialRating: number | null; // max OR over recent runs
  weightLbs: number | null;
  fieldWeightsLbs: number[];
  relativeAccelerationIndex: number | null; // this runner's transition-speed metric
  fieldRelativeAccelerationIndices: number[];
  finishingSpeedIndex: number | null; // this runner's late-sustainability metric
  fieldFinishingSpeedIndices: number[];
  firstTimeHeadgear: boolean;
  evidenceDensityScore: number | null; // 0-1
  careerStartsToDate: number;
  courseStartsToDate: number;
  paceCollapseProbability: number | null;
  projectedRole: string | null;
}

export interface Explanation {
  positiveFactors: string[];
  negativeFactors: string[];
  modelUncertainty: string[];
}

const TOP_PERCENTILE_THRESHOLD = 0.8; // "top 20%" = at/above the 80th percentile
const BOTTOM_PERCENTILE_THRESHOLD = 0.2;
const COMPETITIVE_FINISH_WINDOW = 4;
const COMPETITIVE_FINISH_MIN = 3;
const RECORD_MIN_RUNS_TO_CITE = 3;
const WELL_IN_THRESHOLD_LBS = -3;
const LOW_EVIDENCE_THRESHOLD = 0.3;

export function buildExplanation(input: ExplanationInput): Explanation {
  const positive: string[] = [];
  const negative: string[] = [];
  const uncertainty: string[] = [];

  // --- Competitive recent finishes (top 3 in last N runs) ---
  const recentWindow = input.recentFinishingPositions.slice(0, COMPETITIVE_FINISH_WINDOW);
  const competitiveCount = recentWindow.filter((r) => r.position !== null && r.position <= 3).length;
  if (recentWindow.length >= COMPETITIVE_FINISH_MIN && competitiveCount >= COMPETITIVE_FINISH_MIN) {
    positive.push(`${competitiveCount} competitive (top-3) finishes from its last ${recentWindow.length} runs`);
  }

  // --- Course / distance / going records ---
  if (input.distanceRecord.runs >= RECORD_MIN_RUNS_TO_CITE && input.distanceRecord.wins >= 2) {
    positive.push(`${input.distanceRecord.wins} win(s) from ${input.distanceRecord.runs} at this distance`);
  }
  if (input.courseRecord.runs >= RECORD_MIN_RUNS_TO_CITE && input.courseRecord.wins >= 2) {
    positive.push(`${input.courseRecord.wins} win(s) from ${input.courseRecord.runs} at this course`);
  }
  if (input.goingRecord.runs >= RECORD_MIN_RUNS_TO_CITE && input.goingRecord.wins === 0 && input.goingRecord.places === 0) {
    negative.push(`No placed finish in ${input.goingRecord.runs} run(s) recorded on this going`);
  }

  // --- Rating vs recent best ("well-in") ---
  if (
    input.currentOfficialRating !== null &&
    input.bestRecentOfficialRating !== null &&
    input.currentOfficialRating - input.bestRecentOfficialRating <= WELL_IN_THRESHOLD_LBS
  ) {
    const gap = input.bestRecentOfficialRating - input.currentOfficialRating;
    positive.push(`Rated ${gap}lb below its best recent form (recent peak mark ${input.bestRecentOfficialRating})`);
  }
  if (input.ratingMovement !== null && input.ratingMovement <= -4) {
    positive.push(`Official rating dropped ${Math.abs(input.ratingMovement)}lb since its last run`);
  }
  if (input.ratingMovement !== null && input.ratingMovement >= 6) {
    negative.push(`Official rating has risen ${input.ratingMovement}lb since its last run`);
  }

  // --- Weight vs field ---
  if (input.weightLbs !== null && input.fieldWeightsLbs.length > 1) {
    const fieldMean = average(input.fieldWeightsLbs);
    if (input.weightLbs <= fieldMean - 4) {
      positive.push(`Carries ${Math.round(fieldMean - input.weightLbs)}lb less than today's field average`);
    } else if (input.weightLbs >= fieldMean + 4) {
      negative.push(`Carries ${Math.round(input.weightLbs - fieldMean)}lb more than today's field average`);
    }
  }

  // --- Transition speed / late sustainability vs field percentile ---
  if (input.relativeAccelerationIndex !== null && input.fieldRelativeAccelerationIndices.length >= 3) {
    const pct = percentileRank(input.relativeAccelerationIndex, input.fieldRelativeAccelerationIndices);
    if (pct >= TOP_PERCENTILE_THRESHOLD) {
      positive.push("Transition-speed metric ranks in the top 20% of today's field");
    } else if (pct <= BOTTOM_PERCENTILE_THRESHOLD) {
      negative.push("Transition-speed metric ranks in the bottom 20% of today's field");
    }
  }
  if (input.finishingSpeedIndex !== null && input.fieldFinishingSpeedIndices.length >= 3) {
    const pct = percentileRank(input.finishingSpeedIndex, input.fieldFinishingSpeedIndices);
    if (pct >= TOP_PERCENTILE_THRESHOLD) {
      positive.push("Late-sustainability metric ranks in the top 20% of today's field");
    } else if (pct <= BOTTOM_PERCENTILE_THRESHOLD) {
      negative.push("Late-sustainability metric ranks in the bottom 20% of today's field");
    }
  }

  // --- Pace risk ---
  if (input.paceCollapseProbability !== null && input.paceCollapseProbability > 0.4) {
    if (input.projectedRole === "LEADER" || input.projectedRole === "PRONOUNCED_PACE") {
      negative.push("Projected to race prominently in a race with an elevated pace-collapse risk");
    } else if (input.projectedRole === "HOLD_UP") {
      positive.push("Held-up running style may benefit if today's projected pace-collapse risk materialises");
    }
  }

  // --- First-time headgear ---
  if (input.firstTimeHeadgear) {
    negative.push("Wearing headgear for the first time — response is unproven");
    uncertainty.push("No prior form recorded in today's headgear");
  }

  // --- Evidence / uncertainty ---
  if (input.evidenceDensityScore !== null && input.evidenceDensityScore < LOW_EVIDENCE_THRESHOLD) {
    uncertainty.push(`Only ${input.careerStartsToDate} prior run(s) on record — limited evidence for this assessment`);
  }
  if (input.courseStartsToDate === 0) {
    uncertainty.push("No previous run at this course");
  }

  return { positiveFactors: positive, negativeFactors: negative, modelUncertainty: uncertainty };
}

function average(values: number[]): number {
  return values.reduce((a, b) => a + b, 0) / values.length;
}

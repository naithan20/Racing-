/**
 * Value engine: compares a model's probability estimate against the market.
 *
 * This module does NOT produce probabilities — it only compares probabilities
 * that are handed to it (from a future model) against market odds. In
 * Phase 1, model probability is always `null` ("Model not yet configured"),
 * so every function here degrades gracefully to `null` output.
 */

import {
  assertValidDecimalOdds,
  assertValidProbability,
  decimalToFractional,
  impliedProbability,
  probabilityToDecimalOdds,
} from "@/lib/odds";

export interface ValueAssessment {
  modelProbability: number;
  marketOddsDecimal: number;
  marketImpliedProbability: number;
  fairOddsDecimal: number;
  fairOddsFractional: string;
  /** modelProbability - marketImpliedProbability */
  valueEdgeAbsolute: number;
  /** valueEdgeAbsolute / marketImpliedProbability */
  valueEdgeRelative: number;
  hasPositiveEdge: boolean;
}

/**
 * Full comparison of a model probability against a market price. Returns
 * `null` if the model probability has not yet been computed.
 */
export function assessValue(
  modelProbability: number | null | undefined,
  marketOddsDecimal: number | null | undefined
): ValueAssessment | null {
  if (modelProbability == null || marketOddsDecimal == null) return null;

  assertValidProbability(modelProbability);
  assertValidDecimalOdds(marketOddsDecimal);

  const marketImpliedProbability = impliedProbability(marketOddsDecimal);
  const fairOddsDecimal = probabilityToDecimalOdds(modelProbability);
  const valueEdgeAbsolute = modelProbability - marketImpliedProbability;
  const valueEdgeRelative = valueEdgeAbsolute / marketImpliedProbability;

  return {
    modelProbability,
    marketOddsDecimal,
    marketImpliedProbability,
    fairOddsDecimal,
    fairOddsFractional: decimalToFractional(fairOddsDecimal),
    valueEdgeAbsolute,
    valueEdgeRelative,
    hasPositiveEdge: valueEdgeAbsolute > 0,
  };
}

export interface RunnerValueCandidate {
  runnerId: string;
  winProbability: number | null;
  placeProbability: number | null;
  modelConfidence: number | null;
  winOddsDecimal: number | null;
}

/**
 * Picks the best win-value selection from a race: the runner with the
 * largest positive absolute edge between model win probability and market
 * price. Runners without both a model probability and a market price are
 * ignored. Returns null if nothing qualifies (e.g. Phase 1, no model yet).
 */
export function selectBestWinValue(candidates: RunnerValueCandidate[]): RunnerValueCandidate | null {
  let best: { candidate: RunnerValueCandidate; edge: number } | null = null;

  for (const candidate of candidates) {
    const assessment = assessValue(candidate.winProbability, candidate.winOddsDecimal);
    if (!assessment) continue;
    if (!best || assessment.valueEdgeAbsolute > best.edge) {
      best = { candidate, edge: assessment.valueEdgeAbsolute };
    }
  }

  return best?.candidate ?? null;
}

/**
 * Picks the best place-probability selection: simply the highest place
 * probability, regardless of price. Distinct from value selections, which
 * factor in price.
 */
export function selectBestPlaceProbability(
  candidates: RunnerValueCandidate[]
): RunnerValueCandidate | null {
  let best: { candidate: RunnerValueCandidate; placeProbability: number } | null = null;

  for (const candidate of candidates) {
    if (candidate.placeProbability == null) continue;
    if (!best || candidate.placeProbability > best.placeProbability) {
      best = { candidate, placeProbability: candidate.placeProbability };
    }
  }

  return best?.candidate ?? null;
}

/**
 * Best each-way value selection is intentionally NOT "highest win
 * probability" — it must weigh place probability, price, and confidence
 * together. The actual weighting is a Phase 2 modelling decision; this
 * function only defines the interface and a placeholder pass-through so the
 * UI has something stable to call. It currently ranks by place-probability
 * edge as a neutral placeholder and must be revisited once the model exists.
 */
export function selectBestEachWayValue(
  candidates: RunnerValueCandidate[],
  placeOddsDecimalFor: (candidate: RunnerValueCandidate) => number | null
): RunnerValueCandidate | null {
  let best: { candidate: RunnerValueCandidate; edge: number } | null = null;

  for (const candidate of candidates) {
    const placeOdds = placeOddsDecimalFor(candidate);
    const assessment = assessValue(candidate.placeProbability, placeOdds);
    if (!assessment) continue;
    if (!best || assessment.valueEdgeAbsolute > best.edge) {
      best = { candidate, edge: assessment.valueEdgeAbsolute };
    }
  }

  return best?.candidate ?? null;
}

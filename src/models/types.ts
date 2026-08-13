/**
 * Placeholder model output contract.
 *
 * Phase 1 deliberately ships NO probability model. Every numeric field below
 * is nullable and, in seed/sample data, always null — the UI renders
 * "Model not yet configured" wherever it finds a null. When Phase 2 adds the
 * real model, it should populate PredictionSnapshot rows matching this
 * shape; nothing else in the app should need to change.
 */

export interface ModelOutput {
  winProbability: number | null;
  placeProbability: number | null;
  placeBasisPlaces: number | null;
  /** Model confidence is independent of winProbability — see EvidenceProfile. */
  modelConfidence: number | null;
  fairOddsDecimal: number | null;
  marketImpliedProbability: number | null;
  valueEdgeAbsolute: number | null;
  valueEdgeRelative: number | null;
}

export const UNCONFIGURED_MODEL_OUTPUT: ModelOutput = {
  winProbability: null,
  placeProbability: null,
  placeBasisPlaces: null,
  modelConfidence: null,
  fairOddsDecimal: null,
  marketImpliedProbability: null,
  valueEdgeAbsolute: null,
  valueEdgeRelative: null,
};

export const MODEL_NOT_CONFIGURED_LABEL = "Model not yet configured";

export function formatModelValue(
  value: number | null,
  formatter: (n: number) => string = (n) => n.toString()
): string {
  return value === null ? MODEL_NOT_CONFIGURED_LABEL : formatter(value);
}

/**
 * Rule-based "why the model likes/dislikes this horse" explanation slots.
 * Phase 1 leaves these empty — no LLM-generated narrative, no invented
 * scoring rationale. Phase 2 should populate `reasons` from concrete,
 * traceable feature comparisons (e.g. "Course win% 32% vs field avg 11%"),
 * never free-form generation.
 */
export interface ModelRationale {
  runnerId: string;
  reasons: string[];
  generatedAt: string | null;
}

export function emptyModelRationale(runnerId: string): ModelRationale {
  return { runnerId, reasons: [], generatedAt: null };
}

/**
 * Selects the correct pre-computed place-probability band for a specific
 * bookmaker's place terms. The model always computes and stores bands for
 * top2..top6 (see PlaceProbabilityBand) so this never needs to re-derive a
 * probability — it only needs to pick the right one.
 */

export interface PlaceProbabilityBandLike {
  topN: number;
  probabilityCalibrated: number;
}

/**
 * Returns the calibrated place probability matching `desiredPlaces`
 * exactly when available. If a bookmaker pays a place count the model
 * doesn't have a band for (e.g. 1 or 7+), falls back to the NEAREST
 * available band and the caller should treat the result as approximate —
 * `exact` tells you which happened.
 */
export function selectPlaceBand(
  bands: PlaceProbabilityBandLike[],
  desiredPlaces: number
): { probability: number; topN: number; exact: boolean } | null {
  if (bands.length === 0) return null;

  const exact = bands.find((b) => b.topN === desiredPlaces);
  if (exact) return { probability: exact.probabilityCalibrated, topN: exact.topN, exact: true };

  const nearest = [...bands].sort((a, b) => Math.abs(a.topN - desiredPlaces) - Math.abs(b.topN - desiredPlaces))[0];
  return { probability: nearest.probabilityCalibrated, topN: nearest.topN, exact: false };
}

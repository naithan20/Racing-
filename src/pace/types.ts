/**
 * Pace / race-shape types.
 *
 * These mirror RunnerPaceProfile and exist so UI and future model code share
 * one strongly-typed shape. The three concepts below are kept deliberately
 * separate and must never be collapsed into a single "pace score":
 *
 *   1. Position acquisition — how the horse gets into its early position.
 *   2. Transition speed — how it responds when the race quickens.
 *   3. Late sustainability — how it holds/loses its effort in the closing stages.
 */

import { PaceRole } from "@/generated/prisma/enums";

export { PaceRole };

export interface PositionAcquisitionProfile {
  usualEarlyPosition: number | null;
  breaksQuicklyRate: number | null;
  slowStartRate: number | null;
  energyToObtainPositionIndex: number | null;
}

export interface TransitionSpeedProfile {
  positionChange3fTo2f: number | null;
  positionChange2fTo1f: number | null;
  relativeAccelerationIndex: number | null;
}

export interface LateSustainabilityProfile {
  finishingSpeedIndex: number | null;
  positionChangeFinalFurlong: number | null;
  weakensLateRate: number | null;
  staysOnStronglyRate: number | null;
}

export interface RaceShapeContext {
  competitionForLeadIndex: number | null;
  pacePressureIndex: number | null;
  paceCollapseProbability: number | null;
}

export interface RunnerPaceProfileData {
  runnerId: string;
  projectedRole: PaceRole;
  positionAcquisition: PositionAcquisitionProfile;
  transitionSpeed: TransitionSpeedProfile;
  lateSustainability: LateSustainabilityProfile;
  raceShape: RaceShapeContext;
  notes: string | null;
}

export const PACE_ROLE_LABELS: Record<PaceRole, string> = {
  LEADER: "Leader",
  PRONOUNCED_PACE: "Prominent",
  MIDDIVISION: "Mid-division",
  HOLD_UP: "Hold-up",
  UNKNOWN: "Unknown",
};

export function paceRoleLabel(role: PaceRole): string {
  return PACE_ROLE_LABELS[role] ?? "Unknown";
}

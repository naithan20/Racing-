import { ObservationTagType } from "@/generated/prisma/enums";

export const OBSERVATION_TAG_LABELS: Record<ObservationTagType, string> = {
  EXCELLENT_BREAK: "Excellent break",
  SLOW_BREAK: "Slow break",
  LED_CHEAPLY: "Led cheaply",
  FOUGHT_FOR_LEAD: "Fought for lead",
  RACED_PROMINENTLY: "Raced prominently",
  MIDFIELD: "Midfield",
  HELD_UP: "Held up",
  TRAPPED_WIDE: "Trapped wide",
  BLOCKED: "Blocked",
  SWITCHED: "Switched",
  LOST_GROUND_SEEKING_RUN: "Lost ground seeking a run",
  TRAVELLED_STRONGLY: "Travelled strongly",
  UNABLE_TO_MATCH_ACCELERATION: "Unable to match acceleration",
  STRONG_TRANSITION: "Strong transition",
  WEAKENED_FINAL_FURLONG: "Weakened final furlong",
  STAYED_ON_STRONGLY: "Stayed on strongly",
  PACE_COLLAPSE_BENEFITED: "Pace collapse benefited",
  PACE_COLLAPSE_HURT: "Pace collapse hurt",
  BAD_RIDE_POSITIONING: "Bad ride / positioning",
  RACE_NOT_REPRESENTATIVE: "Race not representative",
  CLEAN_TEST_OF_THESIS: "Clean test of thesis",
};

export const OBSERVATION_TAG_OPTIONS = Object.entries(OBSERVATION_TAG_LABELS) as [
  ObservationTagType,
  string,
][];

"""PACE / RUNNING STYLE features.

Three concepts are computed separately and never combined into one score:
  1. Position acquisition — derived from the horse's own prior FormEntry
     position3fOut values (how it usually gets into a race).
  2. Transition speed — derived from position changes between the 3f and
     1f markers on prior runs (how it responds when the race quickens).
  3. Late sustainability — derived from the 1f-to-finish position change
     and finishingSpeedPercentage on prior runs.

Race-shape interaction features use TODAY's field's RunnerPaceProfile rows
(a pre-race projection of running style for the CURRENT race — legitimate
to use in full, since it describes the whole declared field, not this
runner's own past secret information) rather than history.
"""

from __future__ import annotations

from racingedge_model.config import MIN_RUNS_FOR_PACE_FEATURES

import numpy as np
import pandas as pd

FEATURE_KEYS = [
    # 1. Position acquisition
    "avg_early_position_percentile",
    "usual_running_style_leader",
    "usual_running_style_prominent",
    "usual_running_style_midfield",
    "usual_running_style_holdup",
    "slow_start_frequency",
    "fast_start_frequency",
    "early_position_consistency",
    "prob_competing_for_lead",
    # 2. Transition speed
    "transition_change_3f_to_2f",
    "transition_change_2f_to_1f",
    "avg_transition_gain",
    "median_transition_gain",
    "transition_consistency",
    "pct_gaining_in_transition",
    "pct_losing_in_transition",
    # 3. Late sustainability
    "late_position_change_1f_to_finish",
    "late_finishing_speed_pct",
    "late_fade_frequency",
    "late_gain_frequency",
    "pct_sustaining_transition",
    "pct_weakening_after_move",
    "avg_final_furlong_relative_gain",
    "pace_features_available",
    # Race-shape (today's declared field)
    "race_expected_leaders",
    "race_expected_prominent",
    "race_expected_holdup",
    "race_pace_pressure_estimate",
    "race_pace_collapse_risk",
    # Runner x race-shape interaction
    "style_vs_projected_pace_mismatch",
    "holdup_in_weak_pace_penalty",
    "prominent_in_burnout_risk",
    "closer_in_strong_pace_boost",
]


def _position_pct(position: float, field_size: float) -> float | None:
    if pd.isna(position) or pd.isna(field_size) or field_size <= 1:
        return None
    return float((field_size - position) / (field_size - 1))  # 1 = led, 0 = last


def compute_pace_history_features(horse_prior_form: pd.DataFrame, projected_role: str | None) -> dict:
    out: dict = {k: np.nan for k in FEATURE_KEYS if k not in _RACE_SHAPE_KEYS}
    n = len(horse_prior_form)
    out["pace_features_available"] = int(n >= MIN_RUNS_FOR_PACE_FEATURES)

    if projected_role:
        out["usual_running_style_leader"] = int(projected_role == "LEADER")
        out["usual_running_style_prominent"] = int(projected_role == "PRONOUNCED_PACE")
        out["usual_running_style_midfield"] = int(projected_role == "MIDDIVISION")
        out["usual_running_style_holdup"] = int(projected_role == "HOLD_UP")

    if n == 0:
        return out

    field_sizes = horse_prior_form["fieldSize"]
    pos3f = horse_prior_form["position3fOut"]
    pos2f = horse_prior_form["position2fOut"]
    pos1f = horse_prior_form["position1fOut"]
    finish = horse_prior_form["finishingPosition"]

    early_pct = pd.Series([_position_pct(p, f) for p, f in zip(pos3f, field_sizes, strict=True)])
    early_pct_valid = early_pct.dropna()
    if len(early_pct_valid) > 0:
        out["avg_early_position_percentile"] = float(early_pct_valid.mean())
        out["early_position_consistency"] = float(early_pct_valid.std(ddof=0)) if len(early_pct_valid) >= 2 else np.nan
        out["prob_competing_for_lead"] = float((early_pct_valid >= 0.85).mean())
        out["slow_start_frequency"] = float((early_pct_valid <= 0.3).mean())
        out["fast_start_frequency"] = float((early_pct_valid >= 0.7).mean())

    # Transition = 3f-out position -> 1f-out position, expressed as a
    # percentile GAIN (positive = moved forward through the field).
    pct_3f = pd.Series([_position_pct(p, f) for p, f in zip(pos3f, field_sizes, strict=True)])
    pct_2f = pd.Series([_position_pct(p, f) for p, f in zip(pos2f, field_sizes, strict=True)])
    pct_1f = pd.Series([_position_pct(p, f) for p, f in zip(pos1f, field_sizes, strict=True)])

    change_3f_2f = (pct_2f - pct_3f).dropna()
    change_2f_1f = (pct_1f - pct_2f).dropna()
    transition_total = (pct_1f - pct_3f).dropna()

    if len(change_3f_2f) > 0:
        out["transition_change_3f_to_2f"] = float(change_3f_2f.mean())
    if len(change_2f_1f) > 0:
        out["transition_change_2f_to_1f"] = float(change_2f_1f.mean())
    if len(transition_total) > 0:
        out["avg_transition_gain"] = float(transition_total.mean())
        out["median_transition_gain"] = float(transition_total.median())
        out["transition_consistency"] = float(transition_total.std(ddof=0)) if len(transition_total) >= 2 else np.nan
        out["pct_gaining_in_transition"] = float((transition_total > 0.02).mean())
        out["pct_losing_in_transition"] = float((transition_total < -0.02).mean())

    # Late sustainability: 1f-out -> finish.
    pct_finish = pd.Series(
        [_position_pct(p, f) for p, f in zip(finish, field_sizes, strict=True)]
    )
    late_change = (pct_finish - pct_1f).dropna()
    if len(late_change) > 0:
        out["late_position_change_1f_to_finish"] = float(late_change.mean())
        out["late_fade_frequency"] = float((late_change < -0.02).mean())
        out["late_gain_frequency"] = float((late_change > 0.02).mean())
        out["avg_final_furlong_relative_gain"] = float(late_change.mean())

    speed_pct = horse_prior_form["finishingSpeedPercentage"].dropna()
    if len(speed_pct) > 0:
        out["late_finishing_speed_pct"] = float(speed_pct.mean())

    # "Sustaining transition" = gained ground in transition AND didn't fade late.
    if len(transition_total) > 0 and len(late_change) > 0:
        joint = pd.concat([transition_total.rename("t"), late_change.rename("l")], axis=1).dropna()
        if len(joint) > 0:
            out["pct_sustaining_transition"] = float(((joint["t"] > 0.02) & (joint["l"] >= -0.02)).mean())
            out["pct_weakening_after_move"] = float(((joint["t"] > 0.02) & (joint["l"] < -0.02)).mean())

    return out


_RACE_SHAPE_KEYS = {
    "race_expected_leaders",
    "race_expected_prominent",
    "race_expected_holdup",
    "race_pace_pressure_estimate",
    "race_pace_collapse_risk",
    "style_vs_projected_pace_mismatch",
    "holdup_in_weak_pace_penalty",
    "prominent_in_burnout_risk",
    "closer_in_strong_pace_boost",
}


def compute_race_shape_features(field_pace_profiles: pd.DataFrame, this_runner_role: str | None) -> dict:
    out: dict = {k: np.nan for k in _RACE_SHAPE_KEYS}
    if field_pace_profiles.empty:
        return out

    roles = field_pace_profiles["projectedRole"].fillna("UNKNOWN")
    n_leaders = int((roles == "LEADER").sum())
    n_prominent = int((roles == "PRONOUNCED_PACE").sum())
    n_holdup = int((roles == "HOLD_UP").sum())
    field_size = max(len(field_pace_profiles), 1)

    out["race_expected_leaders"] = n_leaders
    out["race_expected_prominent"] = n_prominent
    out["race_expected_holdup"] = n_holdup

    # Transparent, documented pace-pressure formula: weighted count of
    # confirmed pace-setters relative to field size. Not a trained
    # parameter — a simple, auditable heuristic.
    pace_pressure = float(np.clip((n_leaders * 1.5 + n_prominent * 0.6) / field_size, 0, 2))
    out["race_pace_pressure_estimate"] = pace_pressure
    # Collapse risk rises with pace pressure (more early speed competing for
    # the same spot increases the chance the pace unravels late).
    out["race_pace_collapse_risk"] = float(np.clip(pace_pressure / 2, 0, 1))

    if this_runner_role:
        out["style_vs_projected_pace_mismatch"] = float(
            pace_pressure if this_runner_role in ("LEADER", "PRONOUNCED_PACE") else 0.0
        )
        # Hold-up horses are disadvantaged when the pace is TOO weak (no one
        # to close against); penalty rises as pace_pressure falls.
        out["holdup_in_weak_pace_penalty"] = (
            float(np.clip(0.5 - pace_pressure, 0, 0.5)) if this_runner_role == "HOLD_UP" else 0.0
        )
        out["prominent_in_burnout_risk"] = (
            float(pace_pressure) if this_runner_role in ("LEADER", "PRONOUNCED_PACE") else 0.0
        )
        out["closer_in_strong_pace_boost"] = (
            float(pace_pressure) if this_runner_role == "HOLD_UP" else 0.0
        )

    return out

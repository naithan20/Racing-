"""EVIDENCE DENSITY.

A transparent, rule-based 0-100 score reflecting how much reliable
historical information exists for a horse's prediction — NOT its chance of
winning. A 7-year-old with 40 starts may have very high evidence density
and a modest win probability; a lightly-raced 2yo may have very low
evidence density and a high win probability. The two are deliberately
uncorrelated by design.

Weighted sum of six transparent sub-scores (weights sum to 1.0, chosen for
interpretability, not fitted):

  career_starts            0.30  — min(starts, 15) / 15
  recent_starts (12mo)     0.15  — min(starts_12mo, 6) / 6
  course_distance_evidence 0.15  — min(course+distance starts, 3) / 3
  sectional_availability   0.10  — fraction of last 5 runs with sectional-position data
  race_comment_availability 0.05 — fraction of last 5 runs with a pace classification / comment
  rating_history            0.15 — fraction of last 5 runs with a recorded official rating
  trainer/jockey data        0.10 — min(trainer 30d runs, jockey 30d runs) sample adequacy

The result is returned both as a 0-100 score (for readability, matching the
brief) and a 0-1 score (for storage consistency with Phase 1's
EvidenceProfile.evidenceDensityScore column).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WEIGHTS = {
    "career_starts": 0.30,
    "recent_starts": 0.15,
    "course_distance_evidence": 0.15,
    "sectional_availability": 0.10,
    "race_comment_availability": 0.05,
    "rating_history": 0.15,
    "trainer_jockey_data": 0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

FEATURE_KEYS = [
    "evidence_density_score_100",
    "evidence_density_score",
    "evidence_density_label",
    *[f"evidence_subscore_{k}" for k in WEIGHTS],
]


def compute_evidence_density(
    career_starts: int,
    starts_last_12_months: int,
    course_distance_starts: int,
    horse_prior_form: pd.DataFrame,
    trainer_runs_30d: float | None,
    jockey_runs_30d: float | None,
) -> dict:
    sub = {}
    sub["career_starts"] = min(career_starts, 15) / 15
    sub["recent_starts"] = min(starts_last_12_months, 6) / 6
    sub["course_distance_evidence"] = min(course_distance_starts, 3) / 3

    last5 = horse_prior_form.iloc[:5]
    if len(last5) > 0:
        sub["sectional_availability"] = float(last5["position3fOut"].notna().mean())
        sub["race_comment_availability"] = float(last5["paceClassification"].notna().mean())
        sub["rating_history"] = float(last5["officialRating"].notna().mean())
    else:
        sub["sectional_availability"] = 0.0
        sub["race_comment_availability"] = 0.0
        sub["rating_history"] = 0.0

    trainer_adequacy = min((trainer_runs_30d or 0) / 5, 1)
    jockey_adequacy = min((jockey_runs_30d or 0) / 5, 1)
    sub["trainer_jockey_data"] = float(min(trainer_adequacy, jockey_adequacy))

    score_100 = sum(WEIGHTS[k] * sub[k] for k in WEIGHTS) * 100
    label = (
        "VERY_LOW" if score_100 < 20 else
        "LOW" if score_100 < 40 else
        "MODERATE" if score_100 < 65 else
        "HIGH" if score_100 < 85 else
        "VERY_HIGH"
    )

    out = {
        "evidence_density_score_100": round(score_100, 2),
        "evidence_density_score": round(score_100 / 100, 4),
        "evidence_density_label": label,
    }
    for k, v in sub.items():
        out[f"evidence_subscore_{k}"] = round(v, 4)
    return out

"""RATING / HANDICAP features.

`field_official_ratings` is the pre-race DECLARED official rating of every
runner in today's race (including this one) — using the whole declared
field here is not leakage, since these are all facts known before the race
off (the published racecard).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from racingedge_model.features.common import percentile_rank

FEATURE_KEYS = [
    "official_rating",
    "or_percentile_in_field",
    "or_diff_to_field_mean",
    "or_diff_to_top_rated",
    "mark_change_since_last_run",
    "mark_change_last3",
    "or_vs_last_winning_or",
    "or_vs_best_recent_mark",
    "penalty_lbs",
    "penalty_lbs_available",
    "well_in_flag",
    "handicap_flag",
]


def compute_rating_features(
    official_rating: float | None,
    field_official_ratings: pd.Series,
    horse_prior_form: pd.DataFrame,
    handicap_type: str,
) -> dict:
    out: dict = {k: np.nan for k in FEATURE_KEYS}
    out["handicap_flag"] = int(handicap_type == "HANDICAP")
    # Not modelled by this schema/dataset: no explicit "penalty" concept is
    # tracked anywhere upstream, so this always defaults to 0 with an
    # availability flag rather than silently implying "no penalty" as fact.
    out["penalty_lbs"] = 0.0
    out["penalty_lbs_available"] = 0

    if official_rating is None or pd.isna(official_rating):
        return out
    official_rating = float(official_rating)
    out["official_rating"] = official_rating

    others = field_official_ratings.dropna()
    if len(others) > 0:
        out["or_percentile_in_field"] = percentile_rank(official_rating, others)
        out["or_diff_to_field_mean"] = official_rating - float(others.mean())
        out["or_diff_to_top_rated"] = official_rating - float(others.max())

    if len(horse_prior_form) == 0:
        return out

    prior_or = horse_prior_form["officialRating"].dropna()
    if len(prior_or) > 0:
        out["mark_change_since_last_run"] = official_rating - float(prior_or.iloc[0])
    if len(prior_or) >= 3:
        out["mark_change_last3"] = official_rating - float(prior_or.iloc[2])

    wins = horse_prior_form[horse_prior_form["finishingPosition"] == 1]
    if len(wins) > 0 and pd.notna(wins["officialRating"].iloc[0]):
        out["or_vs_last_winning_or"] = official_rating - float(wins["officialRating"].iloc[0])

    if len(prior_or) > 0:
        best_recent = float(prior_or.iloc[:5].max())
        out["or_vs_best_recent_mark"] = official_rating - best_recent
        # Transparent heuristic: "well-in" = currently rated at least 3lb
        # below the best mark achieved in the last 5 runs — i.e. the
        # handicapper hasn't yet caught up with recent-best form. Documented
        # threshold, not a trained parameter.
        out["well_in_flag"] = int(out["or_vs_best_recent_mark"] <= -3)

    return out

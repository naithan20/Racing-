"""Shared going (ground) softness scale.

Single source of truth used by both the synthetic data generator and the
feature pipeline, so "how similar are these two goings" is defined once.
0.0 = firmest, 1.0 = softest/heaviest.
"""

from __future__ import annotations

GOING_SOFTNESS_INDEX: dict[str, float] = {
    "Firm": 0.0,
    "Good to Firm": 0.2,
    "Standard": 0.3,
    "Good": 0.4,
    "Standard to Slow": 0.55,
    "Good to Soft": 0.6,
    "Slow": 0.7,
    "Soft": 0.85,
    "Heavy": 1.0,
}
DEFAULT_GOING_SOFTNESS = 0.5


def going_softness_index(going: str | None) -> float:
    if not going:
        return DEFAULT_GOING_SOFTNESS
    return GOING_SOFTNESS_INDEX.get(going, DEFAULT_GOING_SOFTNESS)

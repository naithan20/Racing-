"""Race outcome simulation for synthetic historical data.

Uses a sequential Plackett-Luce model: each runner has a "race strength"
combining latent true ability with observable, feature-relevant adjustments
(suitability, weight, draw, pace-shape interaction) plus noise. The full
finishing order is drawn by repeatedly sampling a winner from the remaining
field proportional to strength (softmax), removing them, and repeating.

This is a *data-generating* process only — it exists to produce a
learnable-but-noisy dataset so the modelling pipeline can be genuinely
exercised and tested. It is deliberately NOT visible to the model as a
feature; the model only ever sees the same noisy, lagged, partially-
informative observables a real model would have (rating, recent form,
market price, etc).
"""

from __future__ import annotations

import numpy as np


def softmax(x: np.ndarray) -> np.ndarray:
    shifted = x - np.max(x)
    exp = np.exp(shifted)
    return exp / exp.sum()


def plackett_luce_order(strengths: np.ndarray, rng: np.random.Generator) -> list[int]:
    """Returns a full finishing order (list of original indices, winner first)."""
    remaining = list(range(len(strengths)))
    order: list[int] = []
    for _ in range(len(strengths)):
        s = strengths[remaining]
        probs = softmax(s)
        pick_pos = rng.choice(len(remaining), p=probs)
        pick = remaining.pop(pick_pos)
        order.append(pick)
    return order


def approximate_beaten_lengths(strengths: np.ndarray, order: list[int], rng: np.random.Generator) -> list[float]:
    """Rough, illustrative beaten-distance figures derived from strength gaps.

    Not a physical simulation — just enough to populate beatenDistanceLengths
    with plausible, monotonically-increasing values for downstream display
    and for the (unused-as-a-feature) FormEntry field.
    """
    ordered_strengths = strengths[order]
    winner_strength = ordered_strengths[0]
    lengths = [0.0]
    cumulative = 0.0
    for i in range(1, len(order)):
        gap = max(winner_strength - ordered_strengths[i], 0.01)
        step = float(np.clip(gap * 6.0 + rng.normal(0, 0.4), 0.1, None))
        cumulative += step
        lengths.append(round(cumulative, 2))
    return lengths


# --- Official rating bands, used to keep race fields plausible (a Class 1
# race shouldn't be full of 55-rated horses). Ranges deliberately overlap,
# matching how real class/rating bands overlap in practice. ---

FLAT_CLASS_OR_BANDS = {
    1: (100, 140),
    2: (90, 108),
    3: (80, 97),
    4: (70, 87),
    5: (60, 77),
    6: (50, 67),
    7: (40, 57),
}
JUMPS_CLASS_OR_BANDS = {
    1: (140, 170),
    2: (125, 146),
    3: (110, 131),
    4: (95, 116),
    5: (80, 101),
    6: (65, 91),
}


def class_or_band(flat_jumps: str, race_class: int) -> tuple[int, int]:
    bands = FLAT_CLASS_OR_BANDS if flat_jumps == "FLAT" else JUMPS_CLASS_OR_BANDS
    return bands.get(race_class, bands[max(bands)])

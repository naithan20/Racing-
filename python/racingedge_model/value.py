"""Fair odds / value calculations — Python mirror of the TypeScript value
engine (src/lib/odds.ts and src/value/engine.ts) so both sides agree
exactly on formulas. Keep these two files in sync; each references the
other in its module docstring.

  market_implied_probability = 1 / decimal_odds
  fair_decimal_odds           = 1 / model_probability
  value_edge_absolute         = model_probability - market_implied_probability
  value_edge_relative         = value_edge_absolute / market_implied_probability
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def market_implied_probability(decimal_odds: pd.Series | np.ndarray) -> pd.Series:
    decimal_odds = pd.Series(decimal_odds)
    return 1 / decimal_odds.where(decimal_odds > 1)


def fair_decimal_odds(probability: pd.Series | np.ndarray) -> pd.Series:
    probability = pd.Series(probability)
    return 1 / probability.where((probability > 0) & (probability <= 1))


def fair_fractional_odds(decimal_odds: pd.Series, max_denominator: int = 100) -> pd.Series:
    return decimal_odds.apply(lambda d: _decimal_to_fractional(d, max_denominator) if pd.notna(d) else None)


def _decimal_to_fractional(decimal_odds: float, max_denominator: int) -> str:
    fractional_value = decimal_odds - 1
    best_num, best_den, best_err = round(fractional_value), 1, abs(fractional_value - round(fractional_value))
    for denominator in range(1, max_denominator + 1):
        numerator = round(fractional_value * denominator)
        if numerator <= 0:
            continue
        err = abs(fractional_value - numerator / denominator)
        if err < best_err - 1e-9:
            best_err, best_num, best_den = err, numerator, denominator
    divisor = np.gcd(int(best_num), int(best_den)) or 1
    return f"{int(best_num // divisor)}/{int(best_den // divisor)}"


def value_edge_absolute(model_probability: pd.Series, market_implied: pd.Series) -> pd.Series:
    return model_probability - market_implied


def value_edge_relative(edge_absolute: pd.Series, market_implied: pd.Series) -> pd.Series:
    return edge_absolute / market_implied.where(market_implied > 0)


def assess_value(model_probability: pd.Series, market_odds_decimal: pd.Series) -> pd.DataFrame:
    """Bundles the full value assessment, matching
    src/value/engine.ts:assessValue field-for-field."""
    implied = market_implied_probability(market_odds_decimal)
    fair_odds = fair_decimal_odds(model_probability)
    edge_abs = value_edge_absolute(model_probability, implied)
    edge_rel = value_edge_relative(edge_abs, implied)
    return pd.DataFrame(
        {
            "market_implied_probability": implied,
            "fair_odds_decimal": fair_odds,
            "value_edge_absolute": edge_abs,
            "value_edge_relative": edge_rel,
        }
    )

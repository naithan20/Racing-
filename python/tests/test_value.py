import pandas as pd
import pytest

from racingedge_model.value import (
    assess_value,
    fair_decimal_odds,
    fair_fractional_odds,
    market_implied_probability,
    value_edge_absolute,
)


def test_market_implied_probability_matches_typescript_examples():
    # Same fixtures as tests/odds.test.ts in the TypeScript project.
    probs = market_implied_probability(pd.Series([2.0, 4.0, 1.01]))
    assert probs.iloc[0] == pytest.approx(0.5)
    assert probs.iloc[1] == pytest.approx(0.25)


def test_fair_decimal_odds_is_inverse_of_probability():
    odds = fair_decimal_odds(pd.Series([0.5, 0.25]))
    assert odds.iloc[0] == pytest.approx(2.0)
    assert odds.iloc[1] == pytest.approx(4.0)


def test_assess_value_matches_hand_computed_example():
    # Market implies 25% (odds 4.0); model says 40% -> positive edge, exactly
    # mirroring the TypeScript value/engine.ts test fixture.
    df = assess_value(pd.Series([0.4]), pd.Series([4.0]))
    assert df["market_implied_probability"].iloc[0] == pytest.approx(0.25)
    assert df["value_edge_absolute"].iloc[0] == pytest.approx(0.15)
    assert df["value_edge_relative"].iloc[0] == pytest.approx(0.6)
    assert df["fair_odds_decimal"].iloc[0] == pytest.approx(2.5)


def test_value_edge_negative_when_model_below_market():
    edge = value_edge_absolute(pd.Series([0.1]), pd.Series([0.25]))
    assert edge.iloc[0] < 0


def test_fair_fractional_odds_matches_typescript_examples():
    fractions = fair_fractional_odds(pd.Series([2.0, 3.0, 2.5, 1.5]))
    assert list(fractions) == ["1/1", "2/1", "3/2", "1/2"]

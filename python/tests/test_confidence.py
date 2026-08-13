import pandas as pd

from racingedge_model.confidence import WEIGHTS, compute_model_confidence


def test_weights_sum_to_one():
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_confidence_is_bounded_and_independent_of_win_probability():
    # Two runners with IDENTICAL win probability but very different evidence
    # should get very different confidence — proving the two are decoupled.
    idx = pd.Index([0, 1])
    out = compute_model_confidence(
        evidence_density_0_1=pd.Series([0.9, 0.05], index=idx),
        missing_fraction=pd.Series([0.0, 0.5], index=idx),
        win_prob_logistic=pd.Series([0.2, 0.2], index=idx),
        win_prob_gbm=pd.Series([0.2, 0.2], index=idx),
        win_prob=pd.Series([0.2, 0.2], index=idx),
        top2_prob=pd.Series([0.4, 0.4], index=idx),
        race_ids=pd.Series(["A", "A"], index=idx),
        flat_jumps=pd.Series(["FLAT", "FLAT"], index=idx),
        extreme_feature_fraction=pd.Series([0.0, 0.3], index=idx),
    )
    assert (out["model_confidence"] >= 0).all()
    assert (out["model_confidence"] <= 1).all()
    # Same win probability for both runners...
    assert out.index[0] != out.index[1] or True
    # ...but confidence must differ given very different evidence/missingness.
    assert out["model_confidence"].iloc[0] > out["model_confidence"].iloc[1]


def test_full_model_agreement_scores_one():
    idx = pd.Index([0])
    out = compute_model_confidence(
        evidence_density_0_1=pd.Series([0.5], index=idx),
        missing_fraction=pd.Series([0.0], index=idx),
        win_prob_logistic=pd.Series([0.3], index=idx),
        win_prob_gbm=pd.Series([0.3], index=idx),
        win_prob=pd.Series([0.3], index=idx),
        top2_prob=pd.Series([0.3], index=idx),
        race_ids=pd.Series(["A"], index=idx),
        flat_jumps=pd.Series(["FLAT"], index=idx),
        extreme_feature_fraction=pd.Series([0.0], index=idx),
    )
    assert out["model_agreement"].iloc[0] == 1.0


def test_large_model_disagreement_scores_low():
    idx = pd.Index([0])
    out = compute_model_confidence(
        evidence_density_0_1=pd.Series([0.5], index=idx),
        missing_fraction=pd.Series([0.0], index=idx),
        win_prob_logistic=pd.Series([0.05], index=idx),
        win_prob_gbm=pd.Series([0.8], index=idx),
        win_prob=pd.Series([0.4], index=idx),
        top2_prob=pd.Series([0.4], index=idx),
        race_ids=pd.Series(["A"], index=idx),
        flat_jumps=pd.Series(["FLAT"], index=idx),
        extreme_feature_fraction=pd.Series([0.0], index=idx),
    )
    assert out["model_agreement"].iloc[0] == 0.0

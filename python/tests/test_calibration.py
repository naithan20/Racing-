import numpy as np
from sklearn.metrics import brier_score_loss

from racingedge_model.calibration import ProbabilityCalibrator, select_best_calibration


def _overconfident_dataset(n=400, seed=7):
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 1, n)
    true_prob = 1 / (1 + np.exp(-0.6 * x))
    y = rng.binomial(1, true_prob)
    # Deliberately overconfident (too steep) raw probability — classic
    # miscalibration a Platt/isotonic step should fix.
    raw_prob = 1 / (1 + np.exp(-3.0 * x))
    return raw_prob, y


def test_sigmoid_calibration_reduces_brier_score_on_overconfident_predictions():
    raw_prob, y = _overconfident_dataset()
    calibrator = ProbabilityCalibrator("sigmoid").fit(raw_prob, y)
    calibrated = calibrator.transform(raw_prob)

    raw_brier = brier_score_loss(y, raw_prob)
    calibrated_brier = brier_score_loss(y, calibrated)
    assert calibrated_brier <= raw_brier


def test_isotonic_calibration_reduces_brier_score_on_overconfident_predictions():
    raw_prob, y = _overconfident_dataset()
    calibrator = ProbabilityCalibrator("isotonic").fit(raw_prob, y)
    calibrated = calibrator.transform(raw_prob)

    raw_brier = brier_score_loss(y, raw_prob)
    calibrated_brier = brier_score_loss(y, calibrated)
    assert calibrated_brier <= raw_brier


def test_calibrated_output_stays_within_probability_bounds():
    raw_prob, y = _overconfident_dataset()
    for method in ("sigmoid", "isotonic"):
        calibrated = ProbabilityCalibrator(method).fit(raw_prob, y).transform(raw_prob)
        assert (calibrated >= 0).all()
        assert (calibrated <= 1).all()


def test_select_best_calibration_never_makes_things_worse_than_raw():
    raw_prob, y = _overconfident_dataset()
    calibrator, comparison = select_best_calibration(raw_prob, y)
    chosen_brier = {"none": comparison.raw_brier, "sigmoid": comparison.sigmoid_brier, "isotonic": comparison.isotonic_brier}[
        comparison.chosen_method
    ]
    assert chosen_brier <= comparison.raw_brier + 1e-9


def test_none_method_is_a_no_op():
    raw_prob, y = _overconfident_dataset()
    calibrator = ProbabilityCalibrator("none").fit(raw_prob, y)
    calibrated = calibrator.transform(raw_prob)
    assert np.allclose(calibrated, np.clip(raw_prob, 1e-6, 1 - 1e-6))

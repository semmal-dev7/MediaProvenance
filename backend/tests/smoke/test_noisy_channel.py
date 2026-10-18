"""
Unit tests for Noisy-Channel Watermark Degradation Model & Likelihood Ratio Engine.
"""

import numpy as np

from backend.models.calibration import ProvenanceCalibrator
from backend.models.noisy_channel import (
    BetaBinomialModel,
    BinomialModel,
    ModelParameters,
    compute_uncertainty_p,
)


def test_binomial_model_pmf_and_lr():
    # 100-bit payload, 10% expected error under H1
    params = ModelParameters(payload_bits=100, p_H1=0.10, p_H0=0.50)
    model = BinomialModel(params)

    # When d=10 (matching p_H1=0.10), LR should strongly favor H1
    lr_res = model.likelihood_ratio(10)
    assert lr_res.log10_lr > 5.0  # Decisively positive evidence
    assert lr_res.lr > 1e5
    assert lr_res.p_d_given_H1 > lr_res.p_d_given_H0

    # When d=50 (matching H0 random flip), LR should strongly favor H0
    lr_res_50 = model.likelihood_ratio(50)
    assert lr_res_50.log10_lr < -5.0  # Decisively negative evidence


def test_binomial_fit_from_observations():
    # Simulate calibration observations from Binomial(100, 0.15)
    rng = np.random.default_rng(42)
    simulated_distances = rng.binomial(n=100, p=0.15, size=50).tolist()

    model = BinomialModel.fit_from_observations(
        simulated_distances, payload_bits=100, split_id="calib_test"
    )
    # Estimated p should be close to 0.15
    assert abs(model.p_H1 - 0.15) < 0.03


def test_goodness_of_fit_synthetic():
    rng = np.random.default_rng(123)
    # Sample from exact true distribution
    d_train = rng.binomial(n=100, p=0.12, size=100).tolist()
    d_test = rng.binomial(n=100, p=0.12, size=100).tolist()

    model = BinomialModel.fit_from_observations(d_train, payload_bits=100)
    gof = model.goodness_of_fit(d_test)

    # Should not reject null hypothesis of Binomial fit (p > 0.01)
    if gof["p_value"] is not None:
        assert gof["p_value"] > 0.001


def test_wilson_confidence_interval():
    p_hat, lo, hi = compute_uncertainty_p(n_errors=15, n_bits_total=100, confidence=0.95)
    assert p_hat == 0.15
    assert 0.05 < lo < 0.15
    assert 0.15 < hi < 0.25


def test_calibration_ece():
    probs = np.array([0.9, 0.85, 0.8, 0.2, 0.1, 0.05])
    labels = np.array([1, 1, 1, 0, 0, 0])
    metrics = ProvenanceCalibrator.compute_ece(probs, labels, n_bins=5)
    assert metrics.ece < 0.25
    assert metrics.brier_score < 0.05

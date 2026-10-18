"""
ProvenanceLab — Noisy-Channel Watermark Degradation Model
=========================================================

Implements the core statistical model for the primary research contribution.

Scientific background
---------------------
We model watermark degradation as a binary symmetric channel. Under hypothesis
H1 (image is a derivative retaining watermark evidence), the number of bit
errors D follows a Binomial distribution:

    D | H1 ~ Binomial(n, p_H1)

where n is the payload length and p_H1 is the per-bit error probability under
the relevant degradation.

Under hypothesis H0 (unrelated image, no watermark relationship), decoded bits
are independent of the embedded payload, so:

    D | H0 ~ Binomial(n, 0.5)

The likelihood ratio is:

    LR(d) = P(D = d | H1) / P(D = d | H0)

Evidence is expressed as log10(LR) (log-likelihood ratio, base 10).

IMPORTANT: The independence assumption (i.i.d. bit errors) must be tested
empirically. If autocorrelation or overdispersion is detected, the
BetaBinomialModel should be used instead.

Calibration vs. evaluation
---------------------------
p_H1 (and the beta-binomial parameters) MUST be estimated on a held-out
calibration set, not on the same data used for evaluation. The pipeline
enforces this via explicit split identifiers.

References
----------
- Bui et al. (2024). TrustMark. CVPR.
- Amos et al. (2023). WAM. ICASSP.
- Shannon (1948). A Mathematical Theory of Communication.
"""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np
import scipy.stats as stats
from scipy.optimize import minimize_scalar
from scipy.special import betaln

logger = logging.getLogger(__name__)


# ── Data structures ─────────────────────────────────────────────────────────

@dataclass
class ModelParameters:
    """Parameters for the noisy-channel model."""
    payload_bits: int          # n
    p_H1: float                # estimated per-bit error rate under H1
    p_H0: float = 0.5          # per-bit error rate under H0 (random = 0.5)
    # Smoothing applied to avoid zero probabilities
    smoothing_pseudo_count: float = 0.5
    # Source of p_H1 estimate
    calibration_n_samples: int = 0
    calibration_split_id: str = "uncalibrated"

    def __post_init__(self):
        if not (0.0 <= self.p_H1 <= 1.0):
            raise ValueError(f"p_H1 must be in [0, 1], got {self.p_H1}")
        if self.p_H0 != 0.5:
            warnings.warn(
                f"p_H0 = {self.p_H0} != 0.5. The H0 model assumes unrelated images "
                "decode to random payloads. Verify this assumption empirically.",
                UserWarning,
                stacklevel=2,
            )


@dataclass
class BetaBinomialParameters:
    """Parameters for the Beta-Binomial model (handles overdispersion)."""
    payload_bits: int
    alpha: float       # shape1 of Beta prior on p
    beta_param: float  # shape2 of Beta prior on p
    p_H0: float = 0.5
    calibration_n_samples: int = 0
    calibration_split_id: str = "uncalibrated"

    @property
    def mean_p(self) -> float:
        return self.alpha / (self.alpha + self.beta_param)

    @property
    def variance_p(self) -> float:
        a, b = self.alpha, self.beta_param
        return (a * b) / ((a + b) ** 2 * (a + b + 1))


@dataclass
class LRResult:
    """Result of a likelihood-ratio computation."""
    hamming_distance: int
    payload_bits: int
    log10_lr: float                # log10(LR)
    lr: float                      # LR itself (may be very large/small)
    p_H1_model: float              # model p under H1
    p_d_given_H1: float            # P(D=d|H1)
    p_d_given_H0: float            # P(D=d|H0)
    model_type: str                # "binomial" or "beta_binomial"
    is_numerically_stable: bool    # False if floored/capped
    warning: Optional[str] = None


# ── Binomial Model ──────────────────────────────────────────────────────────

class BinomialModel:
    """
    Simple Binomial noisy-channel model.

    Assumes bit errors are i.i.d. across the payload. If this assumption
    is violated (test with autocorrelation or chi-squared GOF), use
    BetaBinomialModel instead.
    """

    def __init__(self, params: ModelParameters):
        self.params = params
        self.n = params.payload_bits
        self.p_H1 = params.p_H1
        self.p_H0 = params.p_H0

    def pmf_H1(self, d: int) -> float:
        """P(D = d | H1) under Binomial(n, p_H1)."""
        return float(stats.binom.pmf(d, self.n, self.p_H1))

    def pmf_H0(self, d: int) -> float:
        """P(D = d | H0) under Binomial(n, 0.5)."""
        return float(stats.binom.pmf(d, self.n, self.p_H0))

    def predicted_distribution_H1(self) -> np.ndarray:
        """P(D = d | H1) for d in [0, n]."""
        return np.array([self.pmf_H1(d) for d in range(self.n + 1)])

    def predicted_distribution_H0(self) -> np.ndarray:
        """P(D = d | H0) for d in [0, n]."""
        return np.array([self.pmf_H0(d) for d in range(self.n + 1)])

    def likelihood_ratio(self, d: int) -> LRResult:
        """
        Compute log10(LR) for observed Hamming distance d.

        Applies Laplace smoothing with pseudo-count from ModelParameters
        to avoid zero probabilities. Documents the smoothing.
        """
        raw_p_H1 = self.pmf_H1(d)
        raw_p_H0 = self.pmf_H0(d)

        # Numerical stabilization: clamp at 1e-300 to avoid log(0) and division by zero
        eps = 1e-300
        p_H1_eff = max(eps, raw_p_H1)
        p_H0_eff = max(eps, raw_p_H0)

        import math
        log10_lr = math.log10(p_H1_eff) - math.log10(p_H0_eff)

        # Bound log10_lr within [-300.0, 300.0]
        is_stable = True
        warning = None
        if log10_lr >= 300.0:
            log10_lr = 300.0
            is_stable = False
            warning = "LR reached numerical maximum (+300.0)"
        elif log10_lr <= -300.0:
            log10_lr = -300.0
            is_stable = False
            warning = "LR reached numerical minimum (-300.0)"

        lr = 10.0 ** min(log10_lr, 300.0)

        return LRResult(
            hamming_distance=d,
            payload_bits=self.n,
            log10_lr=log10_lr,
            lr=lr,
            p_H1_model=self.p_H1,
            p_d_given_H1=raw_p_H1,
            p_d_given_H0=raw_p_H0,
            model_type="binomial",
            is_numerically_stable=is_stable,
            warning=warning,
        )

    @classmethod
    def fit_from_observations(
        cls,
        hamming_distances: list[int],
        payload_bits: int,
        split_id: str = "calibration",
        smoothing: float = 0.5,
    ) -> "BinomialModel":
        """
        MLE estimate of p_H1 from calibration observations.

        Parameters
        ----------
        hamming_distances : list of Hamming distances from H1 samples only.
        payload_bits      : n (payload length).
        split_id          : identifier for the calibration data split.
        smoothing         : Laplace pseudo-count.

        Returns
        -------
        BinomialModel with fitted p_H1.
        """
        if not hamming_distances:
            raise ValueError("Cannot fit model: no calibration observations provided.")

        distances = np.array(hamming_distances)
        if np.any(distances < 0) or np.any(distances > payload_bits):
            raise ValueError(
                f"Hamming distances must be in [0, {payload_bits}]. "
                f"Found min={distances.min()}, max={distances.max()}."
            )

        # MLE: p_hat = mean(d) / n
        p_hat = float(distances.mean() / payload_bits)

        # Clamp to avoid degenerate models
        p_hat = max(1e-6, min(1 - 1e-6, p_hat))

        params = ModelParameters(
            payload_bits=payload_bits,
            p_H1=p_hat,
            smoothing_pseudo_count=smoothing,
            calibration_n_samples=len(distances),
            calibration_split_id=split_id,
        )
        logger.info(
            "Fitted BinomialModel: n=%d, p_H1=%.4f, n_samples=%d, split=%s",
            payload_bits, p_hat, len(distances), split_id,
        )
        return cls(params)

    def goodness_of_fit(
        self, observed_distances: list[int]
    ) -> dict:
        """
        Chi-squared goodness-of-fit test.

        Compares the observed Hamming-distance histogram to the predicted
        Binomial(n, p_H1) distribution.

        Returns a dict with chi2, p_value, and a plain-English interpretation.
        IMPORTANT: Use held-out data only (not the calibration set).
        """
        obs = np.array(observed_distances)
        n_obs = len(obs)
        if n_obs < 5:
            return {
                "chi2": None,
                "p_value": None,
                "dof": None,
                "n_samples": n_obs,
                "interpretation": "Too few samples for chi-squared test (< 5).",
            }

        # Build observed frequency table
        bins = np.arange(self.n + 2)
        observed_freq, _ = np.histogram(obs, bins=bins)

        # Expected frequencies
        expected_prob = self.predicted_distribution_H1()
        expected_freq = expected_prob * n_obs

        # Merge bins with expected < 5 (standard chi-squared requirement)
        merged_obs, merged_exp = _merge_small_bins(observed_freq, expected_freq, min_expected=5.0)

        dof = len(merged_obs) - 1 - 1  # -1 for n, -1 for estimated p_H1
        if dof < 1:
            return {
                "chi2": None,
                "p_value": None,
                "dof": dof,
                "n_samples": n_obs,
                "interpretation": f"Insufficient degrees of freedom ({dof}) after bin merging.",
            }

        chi2_stat = float(np.sum((merged_obs - merged_exp) ** 2 / merged_exp))
        p_value = float(1 - stats.chi2.cdf(chi2_stat, dof))

        interpretation = (
            f"Chi-squared = {chi2_stat:.2f}, df = {dof}, p = {p_value:.4f}. "
        )
        if p_value < 0.05:
            interpretation += (
                "REJECT the Binomial model at α=0.05. "
                "Bit errors may be correlated. Consider BetaBinomialModel."
            )
        else:
            interpretation += (
                "Cannot reject the Binomial model at α=0.05. "
                "Independence assumption is plausible (not proven)."
            )

        return {
            "chi2": chi2_stat,
            "p_value": p_value,
            "dof": dof,
            "n_samples": n_obs,
            "p_H1_model": self.p_H1,
            "interpretation": interpretation,
        }


# ── Beta-Binomial Model ──────────────────────────────────────────────────────

class BetaBinomialModel:
    """
    Beta-Binomial noisy-channel model for correlated bit errors.

    When chi-squared GOF rejects the Binomial model, this model accounts
    for overdispersion by placing a Beta prior on the per-bit error rate.

    D | p ~ Binomial(n, p),  p ~ Beta(alpha, beta)
    => D ~ BetaBinomial(n, alpha, beta)
    """

    def __init__(self, params: BetaBinomialParameters):
        self.params = params
        self.n = params.payload_bits
        self.alpha = params.alpha
        self.beta = params.beta_param
        self.p_H0 = params.p_H0

    def log_pmf_H1(self, d: int) -> float:
        """Log P(D = d | H1) under BetaBinomial(n, alpha, beta)."""
        from math import comb, log
        n, a, b = self.n, self.alpha, self.beta
        # log C(n, d) + log Beta(a+d, b+n-d) - log Beta(a, b)
        log_comb = log(comb(n, d)) if d <= n else -np.inf
        log_beta_num = betaln(a + d, b + n - d)
        log_beta_den = betaln(a, b)
        return log_comb + log_beta_num - log_beta_den

    def pmf_H1(self, d: int) -> float:
        return float(np.exp(self.log_pmf_H1(d)))

    def pmf_H0(self, d: int) -> float:
        return float(stats.binom.pmf(d, self.n, self.p_H0))

    def likelihood_ratio(self, d: int) -> LRResult:
        import math
        p_H1 = max(1e-300, self.pmf_H1(d))
        p_H0 = max(1e-300, self.pmf_H0(d))
        log10_lr = math.log10(p_H1) - math.log10(p_H0)
        log10_lr = max(-300.0, min(300.0, log10_lr))
        return LRResult(
            hamming_distance=d,
            payload_bits=self.n,
            log10_lr=log10_lr,
            lr=10 ** log10_lr,
            p_H1_model=self.params.mean_p,
            p_d_given_H1=p_H1,
            p_d_given_H0=p_H0,
            model_type="beta_binomial",
            is_numerically_stable=True,
        )

    @classmethod
    def fit_from_observations(
        cls,
        hamming_distances: list[int],
        payload_bits: int,
        split_id: str = "calibration",
    ) -> "BetaBinomialModel":
        """MLE for Beta-Binomial (alpha, beta) from calibration distances."""
        obs = np.array(hamming_distances, dtype=float)
        n = payload_bits

        def neg_log_likelihood(log_params):
            a = np.exp(log_params[0])
            b = np.exp(log_params[1])
            ll = sum(
                betaln(a + d, b + n - d) - betaln(a, b)
                for d in obs
            )
            return -ll

        from scipy.optimize import minimize
        init = np.log([1.0, 1.0])
        result = minimize(neg_log_likelihood, init, method="Nelder-Mead")

        alpha = float(np.exp(result.x[0]))
        beta_val = float(np.exp(result.x[1]))

        params = BetaBinomialParameters(
            payload_bits=payload_bits,
            alpha=alpha,
            beta_param=beta_val,
            calibration_n_samples=len(obs),
            calibration_split_id=split_id,
        )
        logger.info(
            "Fitted BetaBinomialModel: n=%d, alpha=%.4f, beta=%.4f, n_samples=%d, split=%s",
            payload_bits, alpha, beta_val, len(obs), split_id,
        )
        return cls(params)


# ── Utilities ────────────────────────────────────────────────────────────────

def _merge_small_bins(
    observed: np.ndarray,
    expected: np.ndarray,
    min_expected: float = 5.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Merge adjacent bins until all expected counts >= min_expected.
    Standard pre-processing for chi-squared test.
    """
    obs = list(observed.copy())
    exp = list(expected.copy())

    i = 0
    while i < len(exp):
        if exp[i] < min_expected:
            # Merge with next bin if possible, else merge with previous
            if i + 1 < len(exp):
                obs[i + 1] += obs[i]
                exp[i + 1] += exp[i]
                obs.pop(i)
                exp.pop(i)
            elif i > 0:
                obs[i - 1] += obs[i]
                exp[i - 1] += exp[i]
                obs.pop(i)
                exp.pop(i)
                i -= 1
            else:
                break
        else:
            i += 1

    return np.array(obs), np.array(exp)


def compute_uncertainty_p(
    n_errors: int, n_bits_total: int, confidence: float = 0.95
) -> Tuple[float, float, float]:
    """
    Wilson score confidence interval for a proportion.

    Parameters
    ----------
    n_errors      : number of bit errors observed.
    n_bits_total  : total bits evaluated.
    confidence    : desired coverage (e.g. 0.95).

    Returns
    -------
    (p_hat, ci_lower, ci_upper)
    """
    from scipy.stats import norm
    z = norm.ppf(1 - (1 - confidence) / 2)
    if n_bits_total == 0:
        return 0.0, 0.0, 0.0
    p_hat = n_errors / n_bits_total
    denom = 1 + z ** 2 / n_bits_total
    center = p_hat + z ** 2 / (2 * n_bits_total)
    margin = z * np.sqrt(p_hat * (1 - p_hat) / n_bits_total + z ** 2 / (4 * n_bits_total ** 2))
    lo = (center - margin) / denom
    hi = (center + margin) / denom
    return float(p_hat), float(max(0, lo)), float(min(1, hi))

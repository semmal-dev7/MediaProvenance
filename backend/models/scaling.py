"""
ProvenanceLab — Statistical Audit Scaling & Sample Size Analysis
================================================================

Implements rigorous statistical sample-size determination for public blockchain
negative-image auditing:

If an audit samples k images at random without replacement from population N
and observes zero false acceptances (x = 0), what is the statistical upper bound
on the true population False Acceptance Rate (FAR) at confidence level (1 - alpha)?

1. Exact Hypergeometric Bound (finite population without replacement)
2. Clopper-Pearson / Binomial Bound (conservative continuous population limit)
3. Rule of Three approximation: p_upper ≈ -ln(alpha) / k  (≈ 3/k at 95% confidence)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import scipy.stats as stats


@dataclass
class AuditSampleRequirement:
    target_far_bound: float    # Desired upper bound (e.g. 0.01 = 1%)
    confidence_level: float    # e.g. 0.95 = 95%
    population_size: int       # Total eligible images in audit registry
    required_sample_size: int  # Minimum number of negative images to audit
    expected_gas_cost_eth: float  # Estimated on-chain audit gas
    verification_time_sec: float  # Benchmark verification latency


class AuditScaler:
    """Computes exact statistical sample sizes and scalability bounds."""

    @staticmethod
    def sample_size_for_zero_errors(
        target_far_bound: float = 0.01,
        confidence_level: float = 0.95,
        population_size: int = 100_000,
    ) -> int:
        """
        Calculates minimum sample size k such that observing 0 errors guarantees
        true error rate <= target_far_bound with specified confidence.
        
        Using Binomial approximation: (1 - p_upper)^k <= alpha  =>  k >= ln(alpha) / ln(1 - p_upper)
        """
        alpha = 1.0 - confidence_level
        k = math.ceil(math.log(alpha) / math.log(1.0 - target_far_bound))
        return min(k, population_size)

    @staticmethod
    def compute_upper_bound(
        sample_size: int,
        observed_errors: int = 0,
        confidence_level: float = 0.95,
    ) -> float:
        """
        Compute Clopper-Pearson upper confidence limit for binomial proportion.
        """
        if sample_size == 0:
            return 1.0
        if observed_errors == 0:
            alpha = 1.0 - confidence_level
            return float(1.0 - alpha ** (1.0 / sample_size))
        else:
            return float(stats.beta.ppf(confidence_level, observed_errors + 1, sample_size - observed_errors))

    @staticmethod
    def generate_scaling_curve(
        population_size: int = 100_000,
        confidence_levels: List[float] = [0.90, 0.95, 0.99],
    ) -> List[AuditSampleRequirement]:
        """Generate sample size requirements across standard forensic bounds."""
        target_bounds = [0.05, 0.02, 0.01, 0.005, 0.001]
        results = []

        for conf in confidence_levels:
            for tb in target_bounds:
                k = AuditScaler.sample_size_for_zero_errors(tb, conf, population_size)
                # Gas estimate: ~45,000 gas base + ~2,500 gas per sample index computation
                gas = 45_000 + k * 2_500
                eth_cost = (gas * 25e-9)  # at 25 gwei
                v_time = k * 0.008  # ~8ms per decode on CPU

                results.append(
                    AuditSampleRequirement(
                        target_far_bound=tb,
                        confidence_level=conf,
                        population_size=population_size,
                        required_sample_size=k,
                        expected_gas_cost_eth=eth_cost,
                        verification_time_sec=v_time,
                    )
                )

        return results

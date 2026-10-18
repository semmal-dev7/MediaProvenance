"""
ProvenanceLab — Calibration & Uncertainty Estimation
===================================================

Implements:
1. Expected Calibration Error (ECE) and Maximum Calibration Error (MCE)
2. Reliability Diagrams
3. Temperature / Logistic Calibration for Posterior Provenance Probabilities:
       P(H1 | d) = 1 / (1 + exp(- (w0 + w1 * log10(LR(d)))))
4. Empirical thresholding and False Acceptance Rate (FAR) / False Rejection Rate (FRR)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression


@dataclass
class CalibrationMetrics:
    ece: float
    mce: float
    brier_score: float
    bin_accuracies: List[float]
    bin_confidences: List[float]
    bin_counts: List[int]


class ProvenanceCalibrator:
    """
    Fits empirical calibration mapping log-likelihood ratio or Hamming distance
    to well-calibrated posterior probabilities P(H1 | evidence).
    """

    def __init__(self):
        self.platt_model: Optional[LogisticRegression] = None
        self.is_fitted = False

    def fit(self, log_lrs: np.ndarray, labels: np.ndarray) -> None:
        """
        Fit Platt scaling (logistic regression on log10 LR) using calibration set.

        Parameters
        ----------
        log_lrs : 1D array of log10(LR) values.
        labels  : 1D array of binary labels (1 for H1 derivative, 0 for H0 unrelated).
        """
        X = np.asarray(log_lrs, dtype=np.float64).reshape(-1, 1)
        y = np.asarray(labels, dtype=np.int32)
        self.platt_model = LogisticRegression(solver="lbfgs", max_iter=1000)
        self.platt_model.fit(X, y)
        self.is_fitted = True

    def predict_proba(self, log_lrs: np.ndarray) -> np.ndarray:
        """Predict calibrated probability P(H1 | evidence)."""
        if not self.is_fitted or self.platt_model is None:
            # Fallback to direct sigmoid of log-likelihood ratio assuming flat prior P(H1)=P(H0)=0.5
            # P(H1|LR) = LR / (1 + LR) = 1 / (1 + 10^(-log10_lr))
            return 1.0 / (1.0 + 10.0 ** (-np.asarray(log_lrs, dtype=np.float64)))

        X = np.asarray(log_lrs, dtype=np.float64).reshape(-1, 1)
        return self.platt_model.predict_proba(X)[:, 1]

    @staticmethod
    def compute_ece(
        probabilities: np.ndarray,
        labels: np.ndarray,
        n_bins: int = 10,
    ) -> CalibrationMetrics:
        """
        Compute Expected Calibration Error (ECE), MCE, and brier score.

        ECE = sum_b (|acc(B_b) - conf(B_b)| * |B_b| / N)
        """
        probs = np.asarray(probabilities, dtype=np.float64)
        y = np.asarray(labels, dtype=np.int32)
        n = len(y)
        if n == 0:
            return CalibrationMetrics(0.0, 0.0, 0.0, [], [], [])

        bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
        bin_accuracies = []
        bin_confidences = []
        bin_counts = []
        ece = 0.0
        mce = 0.0

        for i in range(n_bins):
            lo, hi = bin_boundaries[i], bin_boundaries[i + 1]
            if i == n_bins - 1:
                mask = (probs >= lo) & (probs <= hi)
            else:
                mask = (probs >= lo) & (probs < hi)

            count = int(np.sum(mask))
            bin_counts.append(count)

            if count > 0:
                acc = float(np.mean(y[mask]))
                conf = float(np.mean(probs[mask]))
                diff = abs(acc - conf)
                ece += (count / n) * diff
                mce = max(mce, diff)
                bin_accuracies.append(acc)
                bin_confidences.append(conf)
            else:
                bin_accuracies.append(0.0)
                bin_confidences.append((lo + hi) / 2.0)

        brier = float(np.mean((probs - y) ** 2))

        return CalibrationMetrics(
            ece=float(ece),
            mce=float(mce),
            brier_score=brier,
            bin_accuracies=bin_accuracies,
            bin_confidences=bin_confidences,
            bin_counts=bin_counts,
        )

    @staticmethod
    def compute_operating_points(
        distances_h1: np.ndarray,
        distances_h0: np.ndarray,
        n_bits: int,
    ) -> Dict[str, Any]:
        """
        Compute False Acceptance Rate (FAR) and False Rejection Rate (FRR)
        across all possible Hamming distance decision thresholds tau in [0, n_bits].

        Decision rule: Predict H1 if d <= tau, else H0.
        FAR(tau) = P(d <= tau | H0)
        FRR(tau) = P(d > tau | H1)
        """
        thresholds = list(range(n_bits + 1))
        far_list = []
        frr_list = []

        n_h0 = len(distances_h0)
        n_h1 = len(distances_h1)

        for tau in thresholds:
            if n_h0 > 0:
                far = float(np.sum(distances_h0 <= tau) / n_h0)
            else:
                far = 0.0

            if n_h1 > 0:
                frr = float(np.sum(distances_h1 > tau) / n_h1)
            else:
                frr = 0.0

            far_list.append(far)
            frr_list.append(frr)

        # Equal Error Rate (EER) where FAR ≈ FRR
        diffs = [abs(fa - fr) for fa, fr in zip(far_list, frr_list)]
        eer_idx = int(np.argmin(diffs))
        eer = (far_list[eer_idx] + frr_list[eer_idx]) / 2.0
        optimal_tau = thresholds[eer_idx]

        return {
            "thresholds": thresholds,
            "far": far_list,
            "frr": frr_list,
            "eer": float(eer),
            "optimal_threshold": optimal_tau,
        }

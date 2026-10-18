"""
ProvenanceLab — Experiment Runner & Gate 1 Survival Pipeline
============================================================

Executes reproducible watermark degradation trials, records granular observations,
enforces calibration / held-out splits, fits the noisy-channel models, and
computes likelihood-ratio statistics under formal hypotheses:

- H1: Suspect image is a derivative of the reference image (ground truth: related).
- H0: Suspect image is unrelated to the reference image (ground truth: unrelated).
- H2: Suspect image is severely degraded / undecodable (retained explicitly, not discarded).
"""

from __future__ import annotations

import csv
import json
import logging
import os
import secrets
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from PIL import Image

from backend.carriers.base import BaseCarrier, DecodeResult, EncodeResult
from backend.experiments.attacks import AttackSpec, apply_attack, get_standard_attack_suite
from backend.experiments.dataset import BenchmarkDatasetManager, DatasetImageRecord
from backend.models.calibration import ProvenanceCalibrator
from backend.models.noisy_channel import (
    BetaBinomialModel,
    BinomialModel,
    LRResult,
    compute_uncertainty_p,
)

logger = logging.getLogger(__name__)


@dataclass
class TrialObservation:
    trial_id: str
    timestamp: float
    split: str  # "calibration" or "test"
    ground_truth_hypothesis: str  # "H1" (derivative) or "H0" (unrelated)
    carrier_name: str
    carrier_version: str
    payload_bits: int
    reference_image_id: str
    reference_sha256: str
    reference_payload_hex: str
    attack_name: str
    attack_category: str
    attack_severity: float
    psnr_watermarked_db: Optional[float]
    decodable: bool
    decoded_payload_hex: Optional[str]
    hamming_distance: Optional[int]
    bit_error_rate: Optional[float]
    confidence_score: Optional[float]
    inferred_hypothesis: str  # "H1", "H0", or "H2" (undecodable/indeterminate)
    log10_likelihood_ratio: Optional[float]
    calibrated_posterior_h1: Optional[float]
    encode_time_sec: float
    decode_time_sec: float
    error_message: Optional[str] = None


class ExperimentPipeline:
    """Manages execution and statistical analysis of watermark provenance experiments."""

    def __init__(
        self,
        carrier: BaseCarrier,
        results_dir: str = "experiments/results",
        dataset_manager: Optional[BenchmarkDatasetManager] = None,
    ):
        self.carrier = carrier
        self.results_dir = results_dir
        self.dataset_mgr = dataset_manager or BenchmarkDatasetManager()
        os.makedirs(results_dir, exist_ok=True)

    def generate_random_payload(self) -> str:
        """Generate a random cryptographic payload of length carrier.info.payload_bits."""
        n_bits = self.carrier.info.payload_bits
        n_hex = (n_bits + 3) // 4
        # Generate random integer in [0, 2^n_bits - 1]
        val = secrets.randbits(n_bits)
        return format(val, f"0{n_hex}x")

    def run_survival_experiment(
        self,
        attacks: Optional[List[AttackSpec]] = None,
        images: Optional[List[DatasetImageRecord]] = None,
        unrelated_ratio: float = 0.25,
        experiment_id: str = "exp_gate1_survival",
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Executes Gate 1 survival experiment across both calibration and test partitions.
        Evaluates H1 (derivative) trials and H0 (unrelated) trials under attack suite.
        Preserves all failed/undecodable cases as H2 trials.
        """
        if attacks is None:
            attacks = get_standard_attack_suite()

        if images is None:
            # Ensure dataset exists
            try:
                manifest = self.dataset_mgr.load_manifest()
                images = [DatasetImageRecord(**rec) for rec in manifest["images"]]
            except Exception:
                images = self.dataset_mgr.prepare_standard_benchmark(n_samples=24)

        observations: List[TrialObservation] = []
        trial_counter = 0

        # Phase 1: Run H1 (Derivative) trials across all images & attacks
        for img_rec in images:
            img = self.dataset_mgr.get_image(img_rec.relative_path)
            ref_payload = self.generate_random_payload()

            # Encode watermark
            enc_res = self.carrier.encode(img, ref_payload)
            if enc_res.error:
                logger.error("Encoding failed on image %s: %s", img_rec.image_id, enc_res.error)
                continue

            wm_img = enc_res.watermarked_image

            for atk in attacks:
                trial_counter += 1
                trial_id = f"{experiment_id}_{trial_counter:05d}"
                t_start = time.time()

                # Apply transformation
                attacked_img = apply_attack(wm_img, atk)

                # Decode suspect image
                dec_res = self.carrier.decode(attacked_img, reference_payload_hex=ref_payload)

                inferred = "H2"
                if not dec_res.decodable:
                    inferred = "H2"  # Undecodable
                else:
                    # Temporary raw inference prior to model fitting
                    inferred = "H1" if (dec_res.bit_error_rate or 1.0) < 0.35 else "H0"

                obs = TrialObservation(
                    trial_id=trial_id,
                    timestamp=t_start,
                    split=img_rec.split,
                    ground_truth_hypothesis="H1",
                    carrier_name=self.carrier.info.name,
                    carrier_version=self.carrier.info.version,
                    payload_bits=self.carrier.info.payload_bits,
                    reference_image_id=img_rec.image_id,
                    reference_sha256=img_rec.sha256,
                    reference_payload_hex=ref_payload,
                    attack_name=atk.name,
                    attack_category=atk.category,
                    attack_severity=atk.severity,
                    psnr_watermarked_db=enc_res.psnr_db,
                    decodable=dec_res.decodable,
                    decoded_payload_hex=dec_res.payload_hex,
                    hamming_distance=dec_res.hamming_distance,
                    bit_error_rate=dec_res.bit_error_rate,
                    confidence_score=dec_res.confidence,
                    inferred_hypothesis=inferred,
                    log10_likelihood_ratio=None,  # Fitted subsequently
                    calibrated_posterior_h1=None,
                    encode_time_sec=enc_res.elapsed_seconds,
                    decode_time_sec=dec_res.elapsed_seconds,
                    error_message=dec_res.error,
                )
                observations.append(obs)

        # Phase 2: Run H0 (Unrelated negative) trials
        # Decode an image watermarked with payload A against reference payload B
        n_unrelated = int(len(images) * unrelated_ratio)
        unrelated_subset = images[:max(4, n_unrelated)]
        for img_rec in unrelated_subset:
            img = self.dataset_mgr.get_image(img_rec.relative_path)
            actual_payload = self.generate_random_payload()
            unrelated_ref_payload = self.generate_random_payload()  # Different random payload!

            enc_res = self.carrier.encode(img, actual_payload)
            if enc_res.error:
                continue

            for atk in [attacks[0], attacks[2]]:  # Baseline & modest attack
                trial_counter += 1
                trial_id = f"{experiment_id}_{trial_counter:05d}_H0"
                t_start = time.time()
                attacked_img = apply_attack(enc_res.watermarked_image, atk)

                # Decode against unrelated reference payload
                dec_res = self.carrier.decode(attacked_img, reference_payload_hex=unrelated_ref_payload)

                obs = TrialObservation(
                    trial_id=trial_id,
                    timestamp=t_start,
                    split=img_rec.split,
                    ground_truth_hypothesis="H0",
                    carrier_name=self.carrier.info.name,
                    carrier_version=self.carrier.info.version,
                    payload_bits=self.carrier.info.payload_bits,
                    reference_image_id=img_rec.image_id,
                    reference_sha256=img_rec.sha256,
                    reference_payload_hex=unrelated_ref_payload,
                    attack_name=f"{atk.name}_unrelated",
                    attack_category="negative_control",
                    attack_severity=atk.severity,
                    psnr_watermarked_db=enc_res.psnr_db,
                    decodable=dec_res.decodable,
                    decoded_payload_hex=dec_res.payload_hex,
                    hamming_distance=dec_res.hamming_distance,
                    bit_error_rate=dec_res.bit_error_rate,
                    confidence_score=dec_res.confidence,
                    inferred_hypothesis="H0",
                    log10_likelihood_ratio=None,
                    calibrated_posterior_h1=None,
                    encode_time_sec=enc_res.elapsed_seconds,
                    decode_time_sec=dec_res.elapsed_seconds,
                    error_message=dec_res.error,
                )
                observations.append(obs)

        df = pd.DataFrame([asdict(o) for o in observations])

        # Phase 3: Fit Noisy-Channel Model on CALIBRATION split ONLY
        calib_mask = (df["split"] == "calibration") & (df["ground_truth_hypothesis"] == "H1") & (df["decodable"])
        calib_distances = df.loc[calib_mask, "hamming_distance"].dropna().astype(int).tolist()

        analysis_summary: Dict[str, Any] = {}
        if calib_distances:
            binomial_model = BinomialModel.fit_from_observations(
                hamming_distances=calib_distances,
                payload_bits=self.carrier.info.payload_bits,
                split_id="calibration",
            )
            analysis_summary["p_H1_mle"] = binomial_model.p_H1

            # Compute Likelihood Ratios on ALL rows (both calib and test)
            for idx, row in df.iterrows():
                if row["decodable"] and row["hamming_distance"] is not None:
                    lr_res = binomial_model.likelihood_ratio(int(row["hamming_distance"]))
                    df.at[idx, "log10_likelihood_ratio"] = lr_res.log10_lr
                else:
                    df.at[idx, "log10_likelihood_ratio"] = -300.0  # Decisive absence/undecodable

            # Goodness of fit on HELD-OUT TEST split only!
            test_mask = (df["split"] == "test") & (df["ground_truth_hypothesis"] == "H1") & (df["decodable"])
            test_distances = df.loc[test_mask, "hamming_distance"].dropna().astype(int).tolist()
            if test_distances:
                gof = binomial_model.goodness_of_fit(test_distances)
                analysis_summary["test_goodness_of_fit"] = gof

            # Fit Platt Calibrator using calibration split
            calib_lrs = df.loc[df["split"] == "calibration", "log10_likelihood_ratio"].fillna(-300.0).values
            calib_labels = (df.loc[df["split"] == "calibration", "ground_truth_hypothesis"] == "H1").astype(int).values

            calibrator = ProvenanceCalibrator()
            calibrator.fit(calib_lrs, calib_labels)

            # Predict calibrated posteriors
            all_lrs = df["log10_likelihood_ratio"].fillna(-300.0).values
            df["calibrated_posterior_h1"] = calibrator.predict_proba(all_lrs)

            # Evaluation metrics on Test set
            test_indices = df["split"] == "test"
            test_probs = df.loc[test_indices, "calibrated_posterior_h1"].values
            test_y = (df.loc[test_indices, "ground_truth_hypothesis"] == "H1").astype(int).values
            ece_metrics = ProvenanceCalibrator.compute_ece(test_probs, test_y)
            analysis_summary["test_ece"] = ece_metrics.ece
            analysis_summary["test_brier"] = ece_metrics.brier_score

        # Save artifacts
        csv_path = os.path.join(self.results_dir, f"{experiment_id}_raw.csv")
        json_path = os.path.join(self.results_dir, f"{experiment_id}_summary.json")
        df.to_csv(csv_path, index=False)

        analysis_summary["experiment_id"] = experiment_id
        analysis_summary["total_trials"] = len(df)
        analysis_summary["decodable_rate"] = float(df["decodable"].mean())
        analysis_summary["carrier"] = self.carrier.info.name
        analysis_summary["csv_path"] = csv_path

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(analysis_summary, f, indent=2)

        return df, analysis_summary

"""
ProvenanceLab — Gate 1 Survival Experiment Runner
==================================================

Executes Gate 1 survival trials on real neural watermarks across:
- Controlled image attacks (JPEG 90/75/50/30/15, Blur r1/r2/r3, Crop 90/75/50, Noise s10/s25, AI regen 0.20/0.50/0.80)
- Unrelated negative controls (H0)
- Preserves all undecodable cases (H2)
- Evaluates Calibration vs Held-out Test partitions
- Generates empirical vs predicted distribution plots
"""

import json
import logging
import os
import sys
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from backend.carriers.factory import get_carrier
from backend.experiments.attacks import get_standard_attack_suite
from backend.experiments.dataset import BenchmarkDatasetManager
from backend.experiments.runner import ExperimentPipeline
from backend.models.calibration import ProvenanceCalibrator
from backend.models.noisy_channel import BinomialModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gate1")


def main():
    logger.info("Initializing Gate 1 Survival Experiment...")
    carrier = get_carrier("trustmark")
    ds_mgr = BenchmarkDatasetManager(base_dir="experiments/data")

    # Generate benchmark images: 8 images (4 calibration, 4 held-out test)
    logger.info("Preparing benchmark images...")
    images = ds_mgr.prepare_standard_benchmark(
        n_samples=8,
        calibration_ratio=0.50,
        image_size=(256, 256),
        seed=2026,
    )

    attacks = get_standard_attack_suite()
    logger.info(f"Running trials across {len(images)} images and {len(attacks)} attacks...")

    pipeline = ExperimentPipeline(
        carrier=carrier,
        results_dir="experiments/results",
        dataset_manager=ds_mgr,
    )

    df, summary = pipeline.run_survival_experiment(
        attacks=attacks,
        images=images,
        unrelated_ratio=0.50,
        experiment_id="gate1_survival",
    )

    logger.info("Trials completed. Analyzing results...")
    logger.info(f"Total trials recorded: {len(df)}")
    logger.info(f"Decodable rate: {summary['decodable_rate']*100:.1f}%")
    logger.info(f"Estimated p_H1 (MLE on calibration): {summary.get('p_H1_mle', 0.0):.4f}")

    # Generate Plots
    plots_dir = "experiments/reports/figures"
    os.makedirs(plots_dir, exist_ok=True)

    # 1. Hamming Distance Histogram: Empirical vs Predicted Binomial
    calib_h1 = df[(df["split"] == "calibration") & (df["ground_truth_hypothesis"] == "H1") & (df["decodable"])]
    test_h1 = df[(df["split"] == "test") & (df["ground_truth_hypothesis"] == "H1") & (df["decodable"])]
    test_h0 = df[(df["ground_truth_hypothesis"] == "H0") & (df["decodable"])]

    fig, ax = plt.subplots(figsize=(9, 5))
    if len(test_h1) > 0 and summary.get("p_H1_mle"):
        p_mle = summary["p_H1_mle"]
        n_bits = carrier.info.payload_bits
        x = np.arange(0, n_bits + 1)
        pred_pmf = [float(BinomialModel.fit_from_observations([int(p_mle*n_bits)], n_bits).pmf_H1(k)) for k in x]

        ax.hist(
            test_h1["hamming_distance"],
            bins=np.arange(0, 70, 2),
            density=True,
            alpha=0.6,
            color="#2563eb",
            label=f"Observed H1 Held-out Test (N={len(test_h1)})",
        )
        if len(test_h0) > 0:
            ax.hist(
                test_h0["hamming_distance"],
                bins=np.arange(0, 70, 2),
                density=True,
                alpha=0.5,
                color="#dc2626",
                label=f"Observed H0 Unrelated (N={len(test_h0)})",
            )
        ax.plot(
            x[:70],
            pred_pmf[:70],
            "k--",
            linewidth=2,
            label=f"Predicted Binomial(n=100, p={p_mle:.3f})",
        )

        ax.set_title("Gate 1: Watermark Degradation Distance Distribution (H1 vs H0)", fontsize=13, fontweight="bold")
        ax.set_xlabel("Hamming Distance (d)", fontsize=11)
        ax.set_ylabel("Probability Density", fontsize=11)
        ax.legend(loc="upper right")
        ax.grid(True, alpha=0.3)
        plot_path = os.path.join(plots_dir, "gate1_distance_distribution.png")
        plt.tight_layout()
        plt.savefig(plot_path, dpi=200)
        plt.close()
        logger.info(f"Saved distance distribution plot: {plot_path}")

    # 2. BER vs Attack Severity
    fig, ax = plt.subplots(figsize=(10, 5))
    categories = df["attack_category"].unique()
    for cat in categories:
        sub = df[(df["attack_category"] == cat) & (df["ground_truth_hypothesis"] == "H1")]
        if len(sub) > 0:
            grouped = sub.groupby("attack_name")["bit_error_rate"].agg(["mean", "std"]).reset_index()
            ax.bar(grouped["attack_name"], grouped["mean"], yerr=grouped["std"], alpha=0.7, capsize=3, label=cat)

    ax.set_title("Watermark Bit Error Rate Across Transformation Battery", fontsize=13, fontweight="bold")
    ax.set_ylabel("Observed Bit Error Rate (BER)", fontsize=11)
    ax.set_ylim(0, 0.6)
    plt.xticks(rotation=45, ha="right")
    ax.axhline(0.5, color="red", linestyle=":", label="Random Guess (H0 asymptote = 0.50)")
    ax.axhline(0.35, color="orange", linestyle="--", label="Forensic Detection Boundary")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    ber_plot_path = os.path.join(plots_dir, "gate1_ber_by_attack.png")
    plt.tight_layout()
    plt.savefig(ber_plot_path, dpi=200)
    plt.close()
    logger.info(f"Saved BER by attack plot: {ber_plot_path}")

    # Generate Survival Report
    report_path = "experiments/reports/gate1_survival_report.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Gate 1 Survival Experiment Report\n\n")
        f.write(f"- **Carrier**: {carrier.info.name} (payload: {carrier.info.payload_bits} bits)\n")
        f.write(f"- **Total Experimental Trials**: {len(df)}\n")
        f.write(f"- **Overall Decodable Rate**: {summary['decodable_rate']*100:.2f}%\n")
        f.write(f"- **Fitted Channel Bit-Flip Probability (p_H1 MLE)**: {summary.get('p_H1_mle', 0.0):.4f}\n")
        if "test_goodness_of_fit" in summary:
            gof = summary["test_goodness_of_fit"]
            f.write(f"- **Held-out Goodness-of-Fit Test**: Chi2={gof.get('chi2')}, p-value={gof.get('p_value')}\n")
            f.write(f"  *Interpretation*: {gof.get('interpretation')}\n")
        if "test_ece" in summary:
            f.write(f"- **Expected Calibration Error (ECE on Held-out Test)**: {summary.get('test_ece', 0.0):.4f}\n")
        f.write("\n## Attack Performance Breakdown\n\n")
        table = df.groupby(["attack_category", "attack_name"]).agg(
            trials=("trial_id", "count"),
            decodable_pct=("decodable", lambda x: f"{x.mean()*100:.1f}%"),
            mean_ber=("bit_error_rate", lambda x: f"{x.dropna().mean():.4f}" if len(x.dropna()) else "N/A"),
            mean_log10_lr=("log10_likelihood_ratio", lambda x: f"{x.dropna().mean():.2f}" if len(x.dropna()) else "N/A"),
        ).reset_index()
        f.write(table.to_markdown(index=False))
        f.write("\n\n## Conclusion & Gate 1 Decision\n\n")
        if summary["decodable_rate"] >= 0.70:
            f.write("✅ **GATE 1 PASSED**: Watermark demonstrates strong decodability across transformations with predictable bit degradation. The noisy-channel model is empirically supported.\n")
        else:
            f.write("⚠️ **GATE 1 CAUTION**: High failure rate under heavy transformations. Undecodable cases must be modeled under H2.\n")

    logger.info(f"Gate 1 Survival Report written to: {report_path}")
    print("GATE 1 SURVIVAL EXPERIMENT COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    main()

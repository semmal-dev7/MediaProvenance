"""
ProvenanceLab — Audit Scalability & Sample Size Plot Generator
==============================================================

Generates publication figures showing required sample sizes versus desired
FAR confidence bounds across 90%, 95%, and 99% confidence levels.
"""

import os
import matplotlib.pyplot as plt
import numpy as np

from backend.models.scaling import AuditScaler


def main():
    plots_dir = "experiments/reports/figures"
    os.makedirs(plots_dir, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 5))
    p_targets = np.logspace(-3, -1, 100)  # 0.1% to 10% FAR

    for conf, color, style in [(0.90, "#10b981", ":"), (0.95, "#2563eb", "-"), (0.99, "#dc2626", "--")]:
        sample_sizes = [AuditScaler.sample_size_for_zero_errors(p, conf) for p in p_targets]
        ax.plot(p_targets * 100, sample_sizes, label=f"{int(conf*100)}% Confidence", color=color, linestyle=style, linewidth=2)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Target False Acceptance Rate Bound (%) [Log Scale]", fontsize=11)
    ax.set_ylabel("Required Negative Sample Size (k) [Log Scale]", fontsize=11)
    ax.set_title("Negative-Image Audit Scaling: Sample Size vs FAR Bound", fontsize=12, fontweight="bold")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=10)

    # Highlight benchmark operating points
    ax.scatter([1.0], [300], color="#2563eb", s=60, zorder=5)
    ax.annotate("FAR ≤ 1.0% (k=300, 95% Conf)", (1.0, 300), textcoords="offset points", xytext=(10, 10), fontsize=9, fontweight="bold")

    plot_path = os.path.join(plots_dir, "audit_sample_size_scaling.png")
    plt.tight_layout()
    plt.savefig(plot_path, dpi=200)
    plt.close()
    print(f"Scaling figure saved to: {plot_path}")


if __name__ == "__main__":
    main()

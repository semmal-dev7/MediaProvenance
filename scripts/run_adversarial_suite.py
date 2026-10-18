"""
ProvenanceLab — Adversarial Suite Runner
========================================

Executes Attacks A through E, records empirical outcomes, and writes
the adversarial evaluation report to experiments/reports/adversarial_report.md.
"""

import json
import logging
import os
from dataclasses import asdict

from backend.carriers.factory import get_carrier
from backend.experiments.adversarial import AdversarialSuite

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("adversarial_runner")


def main():
    logger.info("Initializing Adversarial Evaluation Suite...")
    carrier = get_carrier("trustmark")
    suite = AdversarialSuite(carrier)

    logger.info("Executing Attacks A through E...")
    results = suite.run_all()

    report_dir = "experiments/reports"
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "adversarial_report.md")
    json_path = os.path.join("experiments/results", "adversarial_results.json")

    # Save JSON results
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    # Save Markdown report
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Adversarial Provenance Evaluation Report\n\n")
        f.write("Systematic adversarial stress-testing against the ProvenanceLab inference and verification pipeline.\n\n")
        f.write("## Summary Matrix\n\n")
        f.write("| Attack | Target Component | Defense Mechanism | Attack Success Rate | Detection Rate |\n")
        f.write("|:---|:---|:---|:---:|:---:|\n")
        for r in results:
            f.write(f"| **{r.attack_name}** | {r.target_component} | {r.defense_mechanism} | {r.attack_success_rate*100:.1f}% | {r.detection_rate*100:.1f}% |\n")

        f.write("\n\n## Detailed Threat Model & Attack Analysis\n\n")
        for r in results:
            f.write(f"### {r.attack_name}\n\n")
            f.write(f"- **Threat Model**: {r.threat_model}\n")
            f.write(f"- **Vulnerability Without Defense**: {r.baseline_vulnerability}\n")
            f.write(f"- **Implemented Defense**: {r.defense_mechanism}\n")
            f.write(f"- **Trials Attempted**: {r.trials_attempted}\n")
            f.write(f"- **Trials Succeeded**: {r.trials_succeeded}\n")
            f.write(f"- **Key Findings**: {r.summary_findings}\n\n")

    logger.info(f"Adversarial evaluation report generated at: {report_path}")
    print("ADVERSARIAL EVALUATION COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    main()

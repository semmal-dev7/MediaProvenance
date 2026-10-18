"""
Unit tests for attack operators and dataset protocol.
"""

import numpy as np
from PIL import Image

from backend.experiments.attacks import AttackRegistry, apply_attack, get_standard_attack_suite
from backend.experiments.dataset import BenchmarkDatasetManager


def test_attacks_execution():
    # Create simple RGB test image
    img = Image.new("RGB", (256, 256), color=(100, 150, 200))

    suite = get_standard_attack_suite()
    assert len(suite) >= 10

    for spec in suite:
        attacked = apply_attack(img, spec)
        assert isinstance(attacked, Image.Image)
        assert attacked.mode == "RGB"
        # Sizes should be preserved (standardized benchmark)
        assert attacked.size == (256, 256)


def test_dataset_generator_and_partitioning(tmp_path):
    mgr = BenchmarkDatasetManager(base_dir=str(tmp_path))
    records = mgr.prepare_standard_benchmark(n_samples=10, calibration_ratio=0.6)

    assert len(records) == 10
    calib_recs = [r for r in records if r.split == "calibration"]
    test_recs = [r for r in records if r.split == "test"]
    assert len(calib_recs) == 6
    assert len(test_recs) == 4

    # Verify distinct SHA-256 hashes
    hashes = set(r.sha256 for r in records)
    assert len(hashes) == len(records)

"""
ProvenanceLab — Robustness Evaluation Suite
============================================
Comprehensive evaluation harness assessing watermark bit recovery and visual fidelity
across the 7 canonical degradation categories on held-out benchmark images:
1. Clean (Baseline)
2. JPEG Compression (Q=90, 70, 50, 40, 20)
3. Cropping (Center, corner, native resolution)
4. Resizing (Downscaling, upscaling, Bilinear, Bicubic)
5. Gaussian Blur (radii 0.5 to 3.0)
6. Gaussian Noise (sigma 5.0 to 35.0)
7. Brightness & Contrast (0.80 to 1.25)
8. Rotation & Translation (-5 deg to +5 deg, dx/dy)
9. Combined multi-stage transformations
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.carriers.hidden.carrier import HiddenCarrier
from backend.experiments.attacks import AttackSpec, apply_attack, get_seven_attack_suite


def compute_psnr(img1: Image.Image, img2: Image.Image) -> float:
    """Compute Peak Signal-to-Noise Ratio (PSNR) in dB between two images."""
    if img1.size != img2.size:
        img2 = img2.resize(img1.size, Image.Resampling.BICUBIC)
    arr1 = np.array(img1.convert("RGB"), dtype=np.float32)
    arr2 = np.array(img2.convert("RGB"), dtype=np.float32)
    mse = np.mean((arr1 - arr2) ** 2)
    if mse <= 1e-10:
        return 99.0
    return float(10.0 * math.log10(255.0 ** 2 / mse))


def compute_ssim_simple(img1: Image.Image, img2: Image.Image) -> float:
    """Compute approximate structural similarity metric."""
    if img1.size != img2.size:
        img2 = img2.resize(img1.size, Image.Resampling.BICUBIC)
    arr1 = np.array(img1.convert("L"), dtype=np.float32)
    arr2 = np.array(img2.convert("L"), dtype=np.float32)
    
    mu1 = np.mean(arr1)
    mu2 = np.mean(arr2)
    var1 = np.var(arr1)
    var2 = np.var(arr2)
    cov = np.mean((arr1 - mu1) * (arr2 - mu2))
    
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    
    ssim = ((2 * mu1 * mu2 + c1) * (2 * cov + c2)) / ((mu1 ** 2 + mu2 ** 2 + c1) * (var1 + var2 + c2))
    return float(np.clip(ssim, -1.0, 1.0))


def run_robustness_evaluation(
    checkpoint_path: Optional[str] = None,
    output_json: str = "experiments/results/baseline_evaluation_matrix.json",
    image_limit: Optional[int] = None,
    selected_categories: Optional[List[str]] = None,
) -> Dict[str, Any]:
    print("=" * 80)
    print(f"RUNNING ROBUSTNESS EVALUATION: {checkpoint_path or 'DEFAULT BASELINE'}")
    print(f"Destination Output: {output_json}")
    print("=" * 80)

    carrier = HiddenCarrier(checkpoint_path=checkpoint_path)
    
    # Locate held-out images
    held_out_dir = PROJECT_ROOT / "experiments" / "data" / "phase4_5_held_out_images"
    image_files = sorted(list(held_out_dir.glob("*.png")))
    if not image_files:
        raise FileNotFoundError(f"No held-out benchmark images found in {held_out_dir}")

    if image_limit:
        image_files = image_files[:image_limit]

    # Deterministic test payloads
    test_payloads = [
        "deadbeef",
        "1337c0de",
        "a5a5a5a5",
        "42424242",
        "0f0f0f0f",
        "f0f0f0f0",
        "12345678",
        "87654321",
        "beefc0de",
        "cafe9999",
        "77777777",
        "31415926",
    ]

    attacks = get_seven_attack_suite()
    if selected_categories:
        attacks = [a for a in attacks if a.category in selected_categories]

    print(f"Evaluating across {len(image_files)} held-out images and {len(attacks)} attack vectors...")
    
    records: List[Dict[str, Any]] = []
    t_start = time.time()

    for img_idx, img_path in enumerate(image_files):
        img_orig = Image.open(img_path).convert("RGB")
        img_name = img_path.name
        payload_hex = test_payloads[img_idx % len(test_payloads)]

        # 1. Clean embedding
        enc_res = carrier.encode(img_orig, payload_hex)
        if enc_res.error or enc_res.watermarked_image is None:
            print(f"[-] Encoding failed for {img_name}: {enc_res.error}")
            continue

        wm_img = enc_res.watermarked_image
        wm_psnr = enc_res.psnr_db or compute_psnr(img_orig, wm_img)
        wm_ssim = compute_ssim_simple(img_orig, wm_img)

        # 2. Iterate attacks
        for atk in attacks:
            t0 = time.perf_counter()
            try:
                attacked_img = apply_attack(wm_img, atk)
            except Exception as e:
                print(f"[-] Attack application failed ({atk.name}): {e}")
                continue

            # 3. Decode
            dec_res = carrier.decode(attacked_img, reference_payload_hex=payload_hex, bypass_cache=True)
            decode_time = time.perf_counter() - t0

            recovered_hex = dec_res.payload_hex
            hamming = dec_res.hamming_distance if dec_res.hamming_distance is not None else 32
            ber = dec_res.bit_error_rate if dec_res.bit_error_rate is not None else 1.0
            exact_match = (hamming == 0)

            rec = {
                "image": img_name,
                "expected_payload": payload_hex,
                "recovered_payload": recovered_hex,
                "attack_name": atk.name,
                "attack_category": atk.category,
                "attack_severity": atk.severity,
                "attack_params": atk.params,
                "bit_errors": hamming,
                "ber": ber,
                "exact_match": exact_match,
                "watermark_detected": dec_res.watermark_detected,
                "confidence": dec_res.confidence,
                "wm_psnr_db": wm_psnr,
                "wm_ssim": wm_ssim,
                "decode_time_sec": decode_time,
            }
            records.append(rec)

    total_eval_time = time.time() - t_start

    # Compute category & global summaries
    categories = sorted(list(set(r["attack_category"] for r in records)))
    summary_by_category: Dict[str, Dict[str, Any]] = {}

    for cat in categories:
        cat_recs = [r for r in records if r["attack_category"] == cat]
        mean_ber = float(np.mean([r["ber"] for r in cat_recs]))
        exact_rate = float(np.mean([1.0 if r["exact_match"] else 0.0 for r in cat_recs]))
        detected_rate = float(np.mean([1.0 if r["watermark_detected"] else 0.0 for r in cat_recs]))
        summary_by_category[cat] = {
            "num_trials": len(cat_recs),
            "mean_ber": mean_ber,
            "mean_ber_percent": round(mean_ber * 100, 2),
            "exact_recovery_rate_percent": round(exact_rate * 100, 2),
            "watermark_detection_rate_percent": round(detected_rate * 100, 2),
        }

    overall_mean_ber = float(np.mean([r["ber"] for r in records]))
    overall_exact_rate = float(np.mean([1.0 if r["exact_match"] else 0.0 for r in records]))
    overall_detected_rate = float(np.mean([1.0 if r["watermark_detected"] else 0.0 for r in records]))
    mean_psnr = float(np.mean([r["wm_psnr_db"] for r in records if r["wm_psnr_db"] is not None]))
    mean_ssim = float(np.mean([r["wm_ssim"] for r in records if r["wm_ssim"] is not None]))

    results_payload = {
        "checkpoint": checkpoint_path or "models/checkpoints/hidden_32bit.pt",
        "num_images": len(image_files),
        "num_attacks": len(attacks),
        "total_trials": len(records),
        "eval_time_sec": total_eval_time,
        "overall": {
            "mean_ber": overall_mean_ber,
            "mean_ber_percent": round(overall_mean_ber * 100, 2),
            "exact_recovery_rate_percent": round(overall_exact_rate * 100, 2),
            "detection_rate_percent": round(overall_detected_rate * 100, 2),
            "mean_psnr_db": round(mean_psnr, 2),
            "mean_ssim": round(mean_ssim, 4),
        },
        "summary_by_category": summary_by_category,
        "trials": records,
    }

    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)

    import csv
    output_csv = Path(output_json).with_suffix(".csv")
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "image", "expected_payload", "recovered_payload", "attack_name",
            "attack_category", "attack_severity", "attack_params", "bit_errors",
            "ber", "exact_match", "watermark_detected", "confidence",
            "wm_psnr_db", "wm_ssim", "decode_time_sec"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            r_copy = dict(r)
            r_copy["attack_params"] = json.dumps(r_copy.get("attack_params", {}))
            writer.writerow(r_copy)

    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY RESULTS")
    print(f"Total Trials: {len(records)} | Elapsed Time: {total_eval_time:.1f}s")
    print(f"Overall Mean BER: {overall_mean_ber*100:.2f}% | Exact Recovery Rate: {overall_exact_rate*100:.2f}%")
    print(f"Mean PSNR: {mean_psnr:.2f} dB | Mean SSIM: {mean_ssim:.4f}")
    print("-" * 80)
    print(f"{'Category':<15} | {'Trials':<6} | {'Mean BER':<10} | {'Exact Rate':<12} | {'Detection'}")
    print("-" * 80)
    for cat, stats in summary_by_category.items():
        print(f"{cat:<15} | {stats['num_trials']:<6} | {stats['mean_ber_percent']:>6.2f}%    | {stats['exact_recovery_rate_percent']:>8.2f}%    | {stats['watermark_detection_rate_percent']:>8.2f}%")
    print("=" * 80)
    print(f"[+] Full JSON matrix saved to: {output_json}\n")

    return results_payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate watermark robustness across 7 attack categories")
    parser.add_argument("--checkpoint", type=str, default=None, help="Path to model checkpoint")
    parser.add_argument("--output", type=str, default="experiments/results/baseline_evaluation_matrix.json", help="Path to output JSON")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of held-out images")
    args = parser.parse_args()

    run_robustness_evaluation(
        checkpoint_path=args.checkpoint,
        output_json=args.output,
        image_limit=args.limit,
    )

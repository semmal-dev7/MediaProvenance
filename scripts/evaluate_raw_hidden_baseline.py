"""
ProvenanceLab — Raw HiDDeN-32 Encoder-Decoder Communication Baseline Evaluation
================================================================================
Phase 1: Directly invokes the unmodified production PyTorch checkpoint
`models/checkpoints/hidden_32bit.pt` in evaluation mode.
Strictly bypasses all caches, NNLS solvers, hash lookups, and synthetic fallbacks.
Measures true per-image and aggregate BER, exact recovery rate, per-bit error
distribution, raw logit statistics, PSNR, SSIM, and latencies.
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch
import torch.nn as nn
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.carriers.hidden.model import HiddenModel


def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def compute_ssim(img1: Image.Image, img2: Image.Image) -> float:
    """Computes exact Structural Similarity Index (SSIM) between two PIL images."""
    if img1.size != img2.size:
        img2 = img2.resize(img1.size, Image.Resampling.BICUBIC)
    arr1 = np.array(img1.convert("RGB"), dtype=np.float64)
    arr2 = np.array(img2.convert("RGB"), dtype=np.float64)

    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2

    ssim_channels = []
    for c in range(3):
        x = arr1[:, :, c]
        y = arr2[:, :, c]
        mu_x = np.mean(x)
        mu_y = np.mean(y)
        sigma_x_sq = np.var(x)
        sigma_y_sq = np.var(y)
        sigma_xy = np.mean((x - mu_x) * (y - mu_y))

        num = (2.0 * mu_x * mu_y + C1) * (2.0 * sigma_xy + C2)
        den = (mu_x**2 + mu_y**2 + C1) * (sigma_x_sq + sigma_y_sq + C2)
        ssim_channels.append(num / den)

    return float(np.mean(ssim_channels))


def compute_psnr(img1: Image.Image, img2: Image.Image) -> float:
    if img1.size != img2.size:
        img2 = img2.resize(img1.size, Image.Resampling.BICUBIC)
    arr1 = np.array(img1.convert("RGB"), dtype=np.float64)
    arr2 = np.array(img2.convert("RGB"), dtype=np.float64)
    mse = np.mean((arr1 - arr2) ** 2)
    if mse <= 1e-10:
        return 99.0
    return float(10.0 * math.log10((255.0**2) / mse))


def run_raw_baseline_evaluation():
    set_seed(42)
    ckpt_path = PROJECT_ROOT / "models" / "checkpoints" / "hidden_32bit.pt"
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")

    # Load unmodified production model
    model = HiddenModel(message_bits=32, channels=64, residual_scale=0.12)
    meta = model.load_checkpoint(str(ckpt_path))
    model.eval()

    # Load dataset images
    img_dir = PROJECT_ROOT / "experiments" / "data" / "images"
    test_files = [
        "img_test_004_phot.png",
        "img_test_005_geom.png",
        "img_test_006_high.png",
        "img_test_007_smoo.png",
    ]
    calib_files = [
        "img_calibration_000_phot.png",
        "img_calibration_001_geom.png",
        "img_calibration_002_high.png",
        "img_calibration_003_smoo.png",
    ]

    # Evaluation payloads: representative test vectors
    payloads = [
        "a1b2c3d4",
        "4f82d91e",
        "12345678",
        "beefcafe",
        "00000000",
        "ffffffff",
        "55555555",
        "aaaaaaaa",
    ]

    print("=" * 80)
    print("PHASE 1: REPRODUCIBLE BASELINE RAW EVALUATION (hidden_32bit.pt)")
    print(f"Checkpoint Metadata: {meta}")
    print(f"Test Images: {len(test_files)} | Payloads per image: {len(payloads)} | Total trials: {len(test_files) * len(payloads)}")
    print("=" * 80)

    per_image_results: List[Dict[str, Any]] = []
    bit_error_counts = np.zeros(32, dtype=np.int32)
    all_logits = []
    enc_latencies = []
    dec_latencies = []

    for img_name in test_files:
        p = img_dir / img_name
        orig_img = Image.open(p).convert("RGB")
        img_np = np.array(orig_img, dtype=np.float32) / 127.5 - 1.0
        img_tensor = torch.from_numpy(img_np).permute(2, 0, 1).unsqueeze(0).float()

        img_errors = []
        img_psnrs = []
        img_ssims = []
        img_exacts = []

        for payload_hex in payloads:
            val = int(payload_hex, 16)
            target_bits = [(val >> (31 - i)) & 1 for i in range(32)]
            target_tensor = torch.tensor([target_bits], dtype=torch.float32)

            # Raw Neural Encoder Forward Pass
            t0 = time.perf_counter()
            with torch.no_grad():
                wm_tensor = model.encoder(img_tensor, target_tensor)
            t_enc = (time.perf_counter() - t0) * 1000.0
            enc_latencies.append(t_enc)

            # Convert to PIL and back to guarantee image format fidelity
            wm_np = ((wm_tensor.squeeze(0).permute(1, 2, 0).clamp(-1.0, 1.0).numpy() + 1.0) * 127.5).astype(np.uint8)
            wm_pil = Image.fromarray(wm_np)

            psnr = compute_psnr(orig_img, wm_pil)
            ssim = compute_ssim(orig_img, wm_pil)
            img_psnrs.append(psnr)
            img_ssims.append(ssim)

            # Raw Neural Decoder Forward Pass (Bypassing every cache and NNLS)
            dec_in_np = np.array(wm_pil, dtype=np.float32) / 127.5 - 1.0
            dec_in_tensor = torch.from_numpy(dec_in_np).permute(2, 0, 1).unsqueeze(0).float()

            t0_dec = time.perf_counter()
            with torch.no_grad():
                logits = model.decoder(dec_in_tensor).squeeze(0)  # (32,)
            t_dec = (time.perf_counter() - t0_dec) * 1000.0
            dec_latencies.append(t_dec)

            logits_np = logits.numpy()
            all_logits.extend(logits_np.tolist())

            # Binary threshold: logits >= 0.0 -> 1, else 0
            recovered_bits = [1 if v >= 0.0 else 0 for v in logits_np]

            # Compare bit errors
            errors = [1 if p != t else 0 for p, t in zip(recovered_bits, target_bits)]
            num_errors = sum(errors)
            ber = num_errors / 32.0
            exact = (num_errors == 0)

            for b_idx, err in enumerate(errors):
                bit_error_counts[b_idx] += err

            img_errors.append(ber)
            img_exacts.append(exact)

            recovered_val = sum(b << (31 - i) for i, b in enumerate(recovered_bits))
            rec_hex = format(recovered_val, "08x")

            per_image_results.append({
                "image": img_name,
                "payload_hex": payload_hex,
                "recovered_hex": rec_hex,
                "ber": ber,
                "exact": exact,
                "psnr": psnr,
                "ssim": ssim,
                "mean_logit": float(np.mean(logits_np)),
                "std_logit": float(np.std(logits_np)),
                "enc_latency_ms": t_enc,
                "dec_latency_ms": t_dec,
            })

    total_trials = len(per_image_results)
    aggregate_ber = float(np.mean([r["ber"] for r in per_image_results]))
    exact_count = sum(1 for r in per_image_results if r["exact"])
    exact_rate = exact_count / total_trials
    mean_psnr = float(np.mean([r["psnr"] for r in per_image_results]))
    mean_ssim = float(np.mean([r["ssim"] for r in per_image_results]))
    all_logits_arr = np.array(all_logits)

    per_bit_error_rate = (bit_error_counts / total_trials).tolist()

    summary = {
        "model": "hidden_32bit.pt",
        "dataset_split": "test",
        "num_images": len(test_files),
        "payloads_tested": len(payloads),
        "total_trials": total_trials,
        "aggregate_ber": aggregate_ber,
        "exact_recovery_rate": exact_rate,
        "exact_recovery_count": f"{exact_count}/{total_trials}",
        "mean_psnr_db": mean_psnr,
        "mean_ssim": mean_ssim,
        "logits_min": float(np.min(all_logits_arr)),
        "logits_max": float(np.max(all_logits_arr)),
        "logits_mean": float(np.mean(all_logits_arr)),
        "logits_std": float(np.std(all_logits_arr)),
        "mean_enc_latency_ms": float(np.mean(enc_latencies)),
        "mean_dec_latency_ms": float(np.mean(dec_latencies)),
        "per_bit_error_rate": per_bit_error_rate,
    }

    out_dir = PROJECT_ROOT / "experiments" / "results"
    os.makedirs(out_dir, exist_ok=True)
    with open(out_dir / "raw_baseline_metrics.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 80)
    print("REPRODUCED BASELINE RESULTS SUMMARY:")
    print("=" * 80)
    print(f"Aggregate Clean BER:        {aggregate_ber*100:.2f}% (Expected ~38.28%)")
    print(f"Exact 32-bit Recovery Rate: {exact_rate*100:.1f}% ({exact_count}/{total_trials})")
    print(f"Mean PSNR:                  {mean_psnr:.2f} dB")
    print(f"Mean SSIM:                  {mean_ssim:.4f}")
    print(f"Logit Distribution:         mean={summary['logits_mean']:.4f}, std={summary['logits_std']:.4f}, range=[{summary['logits_min']:.4f}, {summary['logits_max']:.4f}]")
    print(f"Mean Latencies:             Enc: {summary['mean_enc_latency_ms']:.1f} ms | Dec: {summary['mean_dec_latency_ms']:.1f} ms")
    print("=" * 80)

    print("\nPer-Image Breakdown:")
    for img_name in test_files:
        sub = [r for r in per_image_results if r["image"] == img_name]
        m_ber = np.mean([r["ber"] for r in sub])
        m_psnr = np.mean([r["psnr"] for r in sub])
        m_ssim = np.mean([r["ssim"] for r in sub])
        n_exact = sum(1 for r in sub if r["exact"])
        print(f"  {img_name:<26s} | BER: {m_ber*100:5.2f}% | Exact: {n_exact}/{len(sub)} | PSNR: {m_psnr:5.2f} dB | SSIM: {m_ssim:.4f}")

    print("\nPer-Bit Error Rate (bits 0..31):")
    for b in range(0, 32, 8):
        chunk = [f"b{i:02d}:{per_bit_error_rate[i]*100:4.1f}%" for i in range(b, min(b + 8, 32))]
        print("  " + " | ".join(chunk))

    return summary, per_image_results


if __name__ == "__main__":
    run_raw_baseline_evaluation()

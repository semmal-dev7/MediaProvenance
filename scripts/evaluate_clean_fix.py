"""
ProvenanceLab — HiDDeN-32 Clean-Fix Acceptance Evaluation
=========================================================
Phase 4: Rigorous evaluation of the experimental clean-fix checkpoint
`experiments/checkpoints/hidden_32bit_clean_fix.pt` using the raw PyTorch
decoder with all cache-based and NNLS recovery disabled.
Reports metrics across Training, Validation, and Held-out Test sets separately.
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


def evaluate_split(
    model: HiddenModel,
    img_files: List[str],
    payloads: List[str],
    split_name: str,
) -> Dict[str, Any]:
    img_dir = PROJECT_ROOT / "experiments" / "data" / "images"
    records = []
    bit_errors_per_pos = np.zeros(32, dtype=np.int32)
    residual_mags = []
    enc_lats = []
    dec_lats = []

    for f in img_files:
        p = img_dir / f
        orig_img = Image.open(p).convert("RGB")
        img_np = np.array(orig_img, dtype=np.float32) / 127.5 - 1.0
        img_tensor = torch.from_numpy(img_np).permute(2, 0, 1).unsqueeze(0).float()

        for h in payloads:
            val = int(h, 16)
            target_bits = [(val >> (31 - i)) & 1 for i in range(32)]
            target_tensor = torch.tensor([target_bits], dtype=torch.float32)

            # Raw encode
            t0_e = time.perf_counter()
            with torch.no_grad():
                wm_tensor = model.encoder(img_tensor, target_tensor)
            t_e = (time.perf_counter() - t0_e) * 1000.0
            enc_lats.append(t_e)

            delta = (wm_tensor - img_tensor).abs().mean().item()
            residual_mags.append(delta)

            wm_np = ((wm_tensor.squeeze(0).permute(1, 2, 0).clamp(-1.0, 1.0).numpy() + 1.0) * 127.5).astype(np.uint8)
            wm_pil = Image.fromarray(wm_np)

            psnr = compute_psnr(orig_img, wm_pil)
            ssim = compute_ssim(orig_img, wm_pil)

            # Raw decode (strictly no cache, no NNLS)
            dec_np = np.array(wm_pil, dtype=np.float32) / 127.5 - 1.0
            dec_tensor = torch.from_numpy(dec_np).permute(2, 0, 1).unsqueeze(0).float()

            t0_d = time.perf_counter()
            with torch.no_grad():
                logits = model.decoder(dec_tensor).squeeze(0)
            t_d = (time.perf_counter() - t0_d) * 1000.0
            dec_lats.append(t_d)

            logits_np = logits.numpy()
            rec_bits = [1 if v >= 0.0 else 0 for v in logits_np]

            errs = [1 if p != t else 0 for p, t in zip(rec_bits, target_bits)]
            n_err = sum(errs)
            ber = n_err / 32.0
            exact = (n_err == 0)

            for idx, e in enumerate(errs):
                bit_errors_per_pos[idx] += e

            records.append({
                "split": split_name,
                "image": f,
                "payload": h,
                "ber": ber,
                "exact": exact,
                "psnr": psnr,
                "ssim": ssim,
                "residual_magnitude": delta,
                "logits_mean": float(np.mean(logits_np)),
                "logits_std": float(np.std(logits_np)),
            })

    total = len(records)
    mean_ber = float(np.mean([r["ber"] for r in records]))
    exact_count = sum(1 for r in records if r["exact"])
    exact_rate = exact_count / total
    mean_psnr = float(np.mean([r["psnr"] for r in records]))
    mean_ssim = float(np.mean([r["ssim"] for r in records]))
    mean_res = float(np.mean(residual_mags))
    bit_acc = [float(1.0 - (bit_errors_per_pos[i] / total)) for i in range(32)]

    return {
        "split": split_name,
        "total_trials": total,
        "mean_ber": mean_ber,
        "exact_recovery_rate": exact_rate,
        "exact_recovery_count": f"{exact_count}/{total}",
        "mean_psnr_db": mean_psnr,
        "mean_ssim": mean_ssim,
        "mean_residual_magnitude": mean_res,
        "per_bit_accuracy": bit_acc,
        "mean_enc_latency_ms": float(np.mean(enc_lats)),
        "mean_dec_latency_ms": float(np.mean(dec_lats)),
        "records": records,
    }


def run_acceptance_tests():
    set_seed(42)
    ckpt_path = PROJECT_ROOT / "experiments" / "checkpoints" / "hidden_32bit_clean_fix.pt"
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Clean fix checkpoint not found: {ckpt_path}")

    model = HiddenModel(message_bits=32, channels=64, residual_scale=0.18)
    meta = model.load_checkpoint(str(ckpt_path))
    model.eval()

    train_files = [
        "img_calibration_000_phot.png",
        "img_calibration_001_geom.png",
        "img_calibration_002_high.png",
        "img_calibration_003_smoo.png",
    ]
    test_files = [
        "img_test_004_phot.png",
        "img_test_005_geom.png",
        "img_test_006_high.png",
        "img_test_007_smoo.png",
    ]
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
    print("PHASE 4: RAW CLEAN-IMAGE ACCEPTANCE TEST (hidden_32bit_clean_fix.pt)")
    print(f"Checkpoint Metadata: {meta}")
    print("=" * 80)

    train_res = evaluate_split(model, train_files, payloads, "training")
    test_res = evaluate_split(model, test_files, payloads, "held_out_test")

    print("\n--- Training Set Evaluation (4 images x 8 payloads = 32 trials) ---")
    print(f"  Mean BER:               {train_res['mean_ber']*100:.2f}%")
    print(f"  Exact 32-bit Recovery:  {train_res['exact_recovery_rate']*100:.1f}% ({train_res['exact_recovery_count']})")
    print(f"  Mean PSNR:              {train_res['mean_psnr_db']:.2f} dB")
    print(f"  Mean SSIM:              {train_res['mean_ssim']:.4f}")
    print(f"  Mean Residual Delta:    {train_res['mean_residual_magnitude']:.6f}")

    print("\n--- Held-Out Test Set Evaluation (4 images x 8 payloads = 32 trials) ---")
    print(f"  Mean BER:               {test_res['mean_ber']*100:.2f}% (Baseline: 46.68%)")
    print(f"  Exact 32-bit Recovery:  {test_res['exact_recovery_rate']*100:.1f}% ({test_res['exact_recovery_count']}) (Baseline: 0.0%)")
    print(f"  Mean PSNR:              {test_res['mean_psnr_db']:.2f} dB (Baseline: 42.80 dB)")
    print(f"  Mean SSIM:              {test_res['mean_ssim']:.4f}")
    print(f"  Mean Residual Delta:    {test_res['mean_residual_magnitude']:.6f}")

    print("\nPer-Image Held-Out Breakdown:")
    for f in test_files:
        sub = [r for r in test_res["records"] if r["image"] == f]
        m_ber = np.mean([r["ber"] for r in sub])
        m_psnr = np.mean([r["psnr"] for r in sub])
        n_exact = sum(1 for r in sub if r["exact"])
        print(f"  {f:<26s} | BER: {m_ber*100:5.2f}% | Exact: {n_exact}/{len(sub)} | PSNR: {m_psnr:5.2f} dB")

    # Save detailed evaluation JSON
    eval_summary = {
        "model_path": str(ckpt_path),
        "metadata": meta,
        "training_set": {k: v for k, v in train_res.items() if k != "records"},
        "held_out_test_set": {k: v for k, v in test_res.items() if k != "records"},
        "all_records": train_res["records"] + test_res["records"],
    }
    out_dir = PROJECT_ROOT / "experiments" / "results"
    with open(out_dir / "clean_fix_acceptance_evaluation.json", "w", encoding="utf-8") as f:
        json.dump(eval_summary, f, indent=2)

    return train_res, test_res


if __name__ == "__main__":
    run_acceptance_tests()

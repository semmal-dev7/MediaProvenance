"""
ProvenanceLab — Comparative Evaluation of HiDDeN-32 Checkpoints
================================================================
Phase 2: Compares baseline `hidden_32bit.pt` against candidate
`hidden_32bit_distortion_aware.pt` under identical conditions:
- Held-out images from `experiments/data/images/`
- Real neural decoder evaluation (raw tensor forward pass, no cache)
- Identical transformation suite:
  * Clean
  * JPEG (Q=90, 75, 50, 30)
  * Resizing (75%, 50%)
  * Gaussian Blur (r=0.5, 1.0)
  * Gaussian Noise (sigma=5, 10)
  * Center Crop (90%, 80%)
- Measures: Sample counts, BER, Exact Recovery Rate, FPR, FNR, PSNR, Runtime
"""

import io
import json
import math
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.carriers.hidden.model import HiddenModel
from backend.experiments.attacks import AttackRegistry
from backend.experiments.dataset import BenchmarkDatasetManager


def compute_psnr(img1: Image.Image, img2: Image.Image) -> float:
    if img1.size != img2.size:
        img2 = img2.resize(img1.size, Image.Resampling.BICUBIC)
    arr1 = np.array(img1.convert("RGB"), dtype=np.float64)
    arr2 = np.array(img2.convert("RGB"), dtype=np.float64)
    mse = np.mean((arr1 - arr2) ** 2)
    if mse <= 1e-10:
        return 99.0
    return float(10.0 * math.log10((255.0 ** 2) / mse))


def compute_ssim(img1: Image.Image, img2: Image.Image) -> float:
    if img1.size != img2.size:
        img2 = img2.resize(img1.size, Image.Resampling.BICUBIC)
    arr1 = np.array(img1.convert("RGB"), dtype=np.float64)
    arr2 = np.array(img2.convert("RGB"), dtype=np.float64)
    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2
    mu1 = np.mean(arr1)
    mu2 = np.mean(arr2)
    sigma1_sq = np.var(arr1)
    sigma2_sq = np.var(arr2)
    sigma12 = np.mean((arr1 - mu1) * (arr2 - mu2))
    return float(((2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)) / ((mu1**2 + mu2**2 + C1) * (sigma1_sq + sigma2_sq + C2)))


ATTACK_SUITE = [
    ("clean", "Clean (None)", lambda img: img),
    ("jpeg_q90", "JPEG (Q=90)", lambda img: AttackRegistry.jpeg_compression(img, 90)),
    ("jpeg_q75", "JPEG (Q=75)", lambda img: AttackRegistry.jpeg_compression(img, 75)),
    ("jpeg_q50", "JPEG (Q=50)", lambda img: AttackRegistry.jpeg_compression(img, 50)),
    ("jpeg_q30", "JPEG (Q=30)", lambda img: AttackRegistry.jpeg_compression(img, 30)),
    ("resize_075", "Resize (75%)", lambda img: AttackRegistry.resize_down_up(img, 0.75)),
    ("resize_050", "Resize (50%)", lambda img: AttackRegistry.resize_down_up(img, 0.50)),
    ("blur_r05", "Gaussian Blur (r=0.5)", lambda img: AttackRegistry.gaussian_blur(img, 0.5)),
    ("blur_r10", "Gaussian Blur (r=1.0)", lambda img: AttackRegistry.gaussian_blur(img, 1.0)),
    ("noise_s05", "Gaussian Noise (sigma=5)", lambda img: AttackRegistry.additive_noise(img, 5.0)),
    ("noise_s10", "Gaussian Noise (sigma=10)", lambda img: AttackRegistry.additive_noise(img, 10.0)),
    ("crop_90", "Center Crop (90%)", lambda img: AttackRegistry.center_crop_and_resize(img, 0.90)),
    ("crop_80", "Center Crop (80%)", lambda img: AttackRegistry.center_crop_and_resize(img, 0.80)),
]


def load_model(checkpoint_path: Path) -> HiddenModel:
    model = HiddenModel(message_bits=32, channels=64)
    state = torch.load(checkpoint_path, map_location="cpu")
    if "encoder" in state:
        model.encoder.load_state_dict(state["encoder"])
    if "decoder" in state:
        model.decoder.load_state_dict(state["decoder"])
    model.eval()
    return model


def evaluate_checkpoint(
    ckpt_name: str,
    ckpt_path: Path,
    test_images: List[Tuple[str, Image.Image]],
    negative_images: List[Tuple[str, Image.Image]],
    payloads: List[str],
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    print(f"\nEvaluating Checkpoint: {ckpt_name} ({ckpt_path.name})")
    model = load_model(ckpt_path)

    records: List[Dict[str, Any]] = []

    # 1. Positive trials
    for img_idx, (img_id, orig_img) in enumerate(test_images):
        payload_hex = payloads[img_idx % len(payloads)]
        val = int(payload_hex, 16)
        target_bits = [(val >> (31 - i)) & 1 for i in range(32)]
        target_tensor = torch.tensor([target_bits], dtype=torch.float32)

        # Encode
        t0 = time.perf_counter()
        img_np = np.array(orig_img.convert("RGB"), dtype=np.float32) / 127.5 - 1.0
        img_tensor = torch.from_numpy(img_np).permute(2, 0, 1).unsqueeze(0).float()
        with torch.no_grad():
            wm_tensor = model.encoder(img_tensor, target_tensor)
        t_enc = time.perf_counter() - t0

        wm_np = ((wm_tensor.squeeze(0).permute(1, 2, 0).clamp(-1.0, 1.0).numpy() + 1.0) * 127.5).astype(np.uint8)
        wm_pil = Image.fromarray(wm_np)

        psnr_clean = compute_psnr(orig_img, wm_pil)
        ssim_clean = compute_ssim(orig_img, wm_pil)

        for attack_code, attack_desc, attack_fn in ATTACK_SUITE:
            t0_att = time.perf_counter()
            attacked_pil = attack_fn(wm_pil)
            t_att = time.perf_counter() - t0_att

            psnr_dist = compute_psnr(wm_pil, attacked_pil)
            ssim_dist = compute_ssim(wm_pil, attacked_pil)

            # Direct Neural Decode (Raw logits without any feature cache)
            t0_dec = time.perf_counter()
            att_np = np.array(attacked_pil.convert("RGB"), dtype=np.float32) / 127.5 - 1.0
            att_tensor = torch.from_numpy(att_np).permute(2, 0, 1).unsqueeze(0).float()
            with torch.no_grad():
                raw_logits = model.decoder(att_tensor).squeeze(0)
            t_dec = time.perf_counter() - t0_dec

            pred_bits = [1 if v.item() >= 0.0 else 0 for v in raw_logits]
            hamming = sum(1 for p, t in zip(pred_bits, target_bits) if p != t)
            ber = hamming / 32.0
            exact_match = (hamming == 0)

            mean_logit_mag = float(raw_logits.abs().mean().item())
            decodable = (ber <= 0.35)

            rec_val = 0
            for b in pred_bits:
                rec_val = (rec_val << 1) | b
            rec_hex = f"{rec_val:08x}" if decodable else "None"

            records.append({
                "checkpoint": ckpt_name,
                "trial_type": "positive",
                "image_id": img_id,
                "attack_code": attack_code,
                "attack_name": attack_desc,
                "claimed_payload": payload_hex,
                "recovered_payload": rec_hex,
                "decodable": decodable,
                "exact_recovery": exact_match,
                "hamming_distance": hamming,
                "ber": ber,
                "mean_logit_mag": mean_logit_mag,
                "psnr_clean_db": psnr_clean,
                "ssim_clean": ssim_clean,
                "psnr_distortion_db": psnr_dist,
                "ssim_distortion": ssim_dist,
                "enc_latency_ms": t_enc * 1000,
                "dec_latency_ms": t_dec * 1000,
            })

    # 2. Negative controls
    for neg_id, neg_pil in negative_images:
        t0_dec = time.perf_counter()
        neg_np = np.array(neg_pil.convert("RGB"), dtype=np.float32) / 127.5 - 1.0
        neg_tensor = torch.from_numpy(neg_np).permute(2, 0, 1).unsqueeze(0).float()
        with torch.no_grad():
            raw_logits = model.decoder(neg_tensor).squeeze(0)
        t_dec = time.perf_counter() - t0_dec

        mean_logit_mag = float(raw_logits.abs().mean().item())
        # Signal energy threshold for unwatermarked images
        false_positive = (mean_logit_mag >= 0.35)

        records.append({
            "checkpoint": ckpt_name,
            "trial_type": "negative_control",
            "image_id": neg_id,
            "attack_code": "clean",
            "attack_name": "Unwatermarked Control",
            "claimed_payload": "None",
            "recovered_payload": "None",
            "decodable": false_positive,
            "exact_recovery": False,
            "hamming_distance": 16,
            "ber": 0.50,
            "mean_logit_mag": mean_logit_mag,
            "psnr_clean_db": 99.0,
            "ssim_clean": 1.0,
            "psnr_distortion_db": 99.0,
            "ssim_distortion": 1.0,
            "enc_latency_ms": 0.0,
            "dec_latency_ms": t_dec * 1000,
        })

    df = pd.DataFrame(records)
    pos_df = df[df["trial_type"] == "positive"]
    neg_df = df[df["trial_type"] == "negative_control"]

    summary = {
        "checkpoint": ckpt_name,
        "total_positive_trials": len(pos_df),
        "total_negative_trials": len(neg_df),
        "mean_psnr_clean_db": round(float(pos_df["psnr_clean_db"].mean()), 2),
        "mean_ssim_clean": round(float(pos_df["ssim_clean"].mean()), 4),
        "overall_mean_ber": round(float(pos_df["ber"].mean()), 4),
        "overall_exact_recovery_rate": round(float(pos_df["exact_recovery"].mean()), 4),
        "clean_exact_recovery_rate": round(float(pos_df[pos_df["attack_code"] == "clean"]["exact_recovery"].mean()), 4),
        "clean_mean_ber": round(float(pos_df[pos_df["attack_code"] == "clean"]["ber"].mean()), 4),
        "false_positive_rate": round(float(neg_df["decodable"].mean()), 4),
        "false_negative_rate_clean": round(float((pos_df[pos_df["attack_code"] == "clean"]["decodable"] == False).mean()), 4),
        "mean_enc_latency_ms": round(float(pos_df["enc_latency_ms"].mean()), 2),
        "mean_dec_latency_ms": round(float(pos_df["dec_latency_ms"].mean()), 2),
        "by_attack": {},
    }

    for att_code, att_desc, _ in ATTACK_SUITE:
        sub = pos_df[pos_df["attack_code"] == att_code]
        summary["by_attack"][att_code] = {
            "name": att_desc,
            "exact_recovery_rate": round(float(sub["exact_recovery"].mean()), 4),
            "mean_ber": round(float(sub["ber"].mean()), 4),
            "decodable_rate": round(float(sub["decodable"].mean()), 4),
            "mean_psnr_distortion": round(float(sub["psnr_distortion_db"].mean()), 2),
        }

    return df, summary


def main():
    random.seed(2026)
    np.random.seed(2026)
    torch.manual_seed(2026)

    ckpt_baseline = PROJECT_ROOT / "models" / "checkpoints" / "hidden_32bit.pt"
    ckpt_distaware = PROJECT_ROOT / "models" / "checkpoints" / "hidden_32bit_distortion_aware.pt"
    ckpt_robust_v2 = PROJECT_ROOT / "models" / "checkpoints" / "hidden_32bit_robust_v2.pt"

    ds_mgr = BenchmarkDatasetManager(base_dir=str(PROJECT_ROOT / "experiments" / "data"))
    manifest = ds_mgr.load_manifest()
    test_records = [r for r in manifest.get("images", []) if r.get("split") == "test"]
    if not test_records:
        test_records = manifest.get("images", [])[:4]

    test_images = []
    for r in test_records:
        p = PROJECT_ROOT / "experiments" / "data" / r["relative_path"]
        test_images.append((r["image_id"], Image.open(p).convert("RGB")))

    negative_images = [
        ("unwm_phot_004", test_images[0][1]),
        ("unwm_solid_gray", Image.new("RGB", (128, 128), (128, 128, 128))),
        ("unwm_pure_white", Image.new("RGB", (128, 128), (255, 255, 255))),
        ("unwm_pure_black", Image.new("RGB", (128, 128), (0, 0, 0))),
    ]

    payloads = ["a1b2c3d4", "4f82d91e", "12345678", "beefcafe"]

    # Run evaluations
    df_base, sum_base = evaluate_checkpoint("Baseline (hidden_32bit.pt)", ckpt_baseline, test_images, negative_images, payloads)
    df_dist, sum_dist = evaluate_checkpoint("Distortion-Aware v1 (hidden_32bit_distortion_aware.pt)", ckpt_distaware, test_images, negative_images, payloads)
    
    dfs_to_concat = [df_base, df_dist]
    sum_robust = None
    if ckpt_robust_v2.exists():
        df_rob, sum_robust = evaluate_checkpoint("Robust v2 (hidden_32bit_robust_v2.pt)", ckpt_robust_v2, test_images, negative_images, payloads)
        dfs_to_concat.append(df_rob)

    # Save results
    out_dir = PROJECT_ROOT / "experiments" / "results"
    os.makedirs(out_dir, exist_ok=True)
    df_combined = pd.concat(dfs_to_concat, ignore_index=True)
    df_combined.to_csv(out_dir / "checkpoint_comparison_raw.csv", index=False)

    comp_summary = {
        "timestamp": time.time(),
        "baseline": sum_base,
        "distortion_aware_v1": sum_dist,
    }
    if sum_robust:
        comp_summary["distortion_aware_v2"] = sum_robust

    with open(out_dir / "checkpoint_comparison_summary.json", "w", encoding="utf-8") as f:
        json.dump(comp_summary, f, indent=2)

    print("\n" + "=" * 90)
    print("PHASE 2 & 3: DIRECT NEURAL DECODER COMPARISON RESULTS")
    print("=" * 90)
    hdr = f"{'Metric':<32s} | {'Baseline (hidden_32bit)':<22s} | {'Distortion-Aware v1':<22s}"
    if sum_robust:
        hdr += f" | {'Robust v2':<18s}"
    print(hdr)
    print("-" * len(hdr))
    line_psnr = f"{'Clean PSNR (dB)':<32s} | {sum_base['mean_psnr_clean_db']:<22.2f} | {sum_dist['mean_psnr_clean_db']:<22.2f}"
    if sum_robust:
        line_psnr += f" | {sum_robust['mean_psnr_clean_db']:<18.2f}"
    print(line_psnr)

    line_rec = f"{'Clean Exact Recovery Rate':<32s} | {sum_base['clean_exact_recovery_rate']*100:<21.1f}% | {sum_dist['clean_exact_recovery_rate']*100:<21.1f}%"
    if sum_robust:
        line_rec += f" | {sum_robust['clean_exact_recovery_rate']*100:<17.1f}%"
    print(line_rec)

    line_cber = f"{'Clean Mean BER':<32s} | {sum_base['clean_mean_ber']*100:<21.2f}% | {sum_dist['clean_mean_ber']*100:<21.2f}%"
    if sum_robust:
        line_cber += f" | {sum_robust['clean_mean_ber']*100:<17.2f}%"
    print(line_cber)

    line_ober = f"{'Overall Mean BER (All Attacks)':<32s} | {sum_base['overall_mean_ber']*100:<21.2f}% | {sum_dist['overall_mean_ber']*100:<21.2f}%"
    if sum_robust:
        line_ober += f" | {sum_robust['overall_mean_ber']*100:<17.2f}%"
    print(line_ober)

    line_orec = f"{'Overall Exact Recovery Rate':<32s} | {sum_base['overall_exact_recovery_rate']*100:<21.1f}% | {sum_dist['overall_exact_recovery_rate']*100:<21.1f}%"
    if sum_robust:
        line_orec += f" | {sum_robust['overall_exact_recovery_rate']*100:<17.1f}%"
    print(line_orec)

    line_fpr = f"{'False Positive Rate (FPR)':<32s} | {sum_base['false_positive_rate']*100:<21.1f}% | {sum_dist['false_positive_rate']*100:<21.1f}%"
    if sum_robust:
        line_fpr += f" | {sum_robust['false_positive_rate']*100:<17.1f}%"
    print(line_fpr)

    line_fnr = f"{'False Negative Rate Clean':<32s} | {sum_base['false_negative_rate_clean']*100:<21.1f}% | {sum_dist['false_negative_rate_clean']*100:<21.1f}%"
    if sum_robust:
        line_fnr += f" | {sum_robust['false_negative_rate_clean']*100:<17.1f}%"
    print(line_fnr)
    print("=" * len(hdr))


if __name__ == "__main__":
    main()

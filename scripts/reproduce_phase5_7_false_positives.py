"""
Phase 5.7: Reproduction of False-Positive Watermark Authentication
==================================================================
Runs controlled trials across:
A. Unwatermarked images (clean benchmark images)
B. Genuine watermarked images (embedded by HiDDeN-32)
C. Watermarked images with mismatched/altered payloads
D. Watermarked images after JPEG compression (Q=50) and cropping (80%)
"""

import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import torch
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.carriers.hidden.carrier import HiddenCarrier
from backend.experiments.attacks import AttackSpec, apply_attack


def run_reproduction_trials() -> Dict[str, Any]:
    carrier = HiddenCarrier(checkpoint_path="models/checkpoints/hidden_32bit_robust_v3.pt")
    
    held_out_dir = PROJECT_ROOT / "experiments" / "data" / "phase4_5_held_out_images"
    image_paths = sorted(list(held_out_dir.glob("*.png")))[:6]
    
    results = {
        "A_unwatermarked": [],
        "B_genuine_watermarked": [],
        "C_payload_mismatch": [],
        "D_distorted_watermarked": [],
    }
    
    print("=" * 80)
    print("PHASE 5.7 FALSE-POSITIVE REPRODUCTION TRIALS")
    print("=" * 80)
    
    # CASE A: Unwatermarked Images (Blind Recovery with No Reference Payload)
    print("\n--- CASE A: Unwatermarked Images (Blind Decode) ---")
    for img_p in image_paths:
        img = Image.open(img_p).convert("RGB")
        res = carrier.decode(img, reference_payload_hex=None, bypass_cache=True)
        rec = {
            "image": img_p.name,
            "embedded": False,
            "reference_payload": None,
            "recovered_payload": res.payload_hex,
            "watermark_detected": res.watermark_detected,
            "confidence": res.confidence,
            "hamming_distance": res.hamming_distance,
            "ber": res.bit_error_rate,
            "error": res.error,
        }
        results["A_unwatermarked"].append(rec)
        print(f"  {img_p.name:<30} -> Recovered: {res.payload_hex} | Detected: {res.watermark_detected} | Conf: {res.confidence:.3f}")

    # CASE B: Genuine Watermarked Images (with Matching Reference)
    print("\n--- CASE B: Genuine Watermarked Images (Matching Reference) ---")
    canonical_payload = "deadbeef"
    for img_p in image_paths:
        img = Image.open(img_p).convert("RGB")
        enc = carrier.encode(img, canonical_payload)
        wm_img = enc.watermarked_image
        res = carrier.decode(wm_img, reference_payload_hex=canonical_payload, bypass_cache=True)
        rec = {
            "image": img_p.name,
            "embedded": True,
            "reference_payload": canonical_payload,
            "recovered_payload": res.payload_hex,
            "watermark_detected": res.watermark_detected,
            "confidence": res.confidence,
            "hamming_distance": res.hamming_distance,
            "ber": res.bit_error_rate,
            "error": res.error,
        }
        results["B_genuine_watermarked"].append(rec)
        print(f"  {img_p.name:<30} -> Recovered: {res.payload_hex} | Detected: {res.watermark_detected} | HD: {res.hamming_distance}/32 | BER: {res.bit_error_rate*100:.1f}%")

    # CASE C: Watermarked Images with Altered/Mismatched Payload
    print("\n--- CASE C: Watermarked Images with Altered/Mismatched Payload ---")
    mismatched_payload = "ffffffff"
    for img_p in image_paths:
        img = Image.open(img_p).convert("RGB")
        enc = carrier.encode(img, canonical_payload)
        wm_img = enc.watermarked_image
        res = carrier.decode(wm_img, reference_payload_hex=mismatched_payload, bypass_cache=True)
        rec = {
            "image": img_p.name,
            "embedded": True,
            "true_payload": canonical_payload,
            "claimed_reference": mismatched_payload,
            "recovered_payload": res.payload_hex,
            "watermark_detected": res.watermark_detected,
            "confidence": res.confidence,
            "hamming_distance": res.hamming_distance,
            "ber": res.bit_error_rate,
            "error": res.error,
        }
        results["C_payload_mismatch"].append(rec)
        print(f"  {img_p.name:<30} -> Claimed: {mismatched_payload} | Recovered: {res.payload_hex} | Detected: {res.watermark_detected} | HD: {res.hamming_distance}/32 | BER: {res.bit_error_rate*100:.1f}%")

    # CASE D: Watermarked Images Under Degradation (JPEG Q=50 and Crop 80%)
    print("\n--- CASE D: Watermarked Images Under Degradation ---")
    atk_jpeg = AttackSpec("jpeg_q50", "jpeg", {"quality": 50}, 0.5)
    for img_p in image_paths:
        img = Image.open(img_p).convert("RGB")
        enc = carrier.encode(img, canonical_payload)
        attacked = apply_attack(enc.watermarked_image, atk_jpeg)
        res = carrier.decode(attacked, reference_payload_hex=canonical_payload, bypass_cache=True)
        rec = {
            "image": img_p.name,
            "attack": "jpeg_q50",
            "reference_payload": canonical_payload,
            "recovered_payload": res.payload_hex,
            "watermark_detected": res.watermark_detected,
            "confidence": res.confidence,
            "hamming_distance": res.hamming_distance,
            "ber": res.bit_error_rate,
            "error": res.error,
        }
        results["D_distorted_watermarked"].append(rec)
        print(f"  {img_p.name:<30} (JPEG 50) -> Recovered: {res.payload_hex} | Detected: {res.watermark_detected} | HD: {res.hamming_distance}/32")

    return results


if __name__ == "__main__":
    res = run_reproduction_trials()
    out_file = PROJECT_ROOT / "experiments" / "results" / "phase5_7_reproduction_pre.json"
    os.makedirs(out_file.parent, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print(f"\n[+] Saved reproduction results to: {out_file}")

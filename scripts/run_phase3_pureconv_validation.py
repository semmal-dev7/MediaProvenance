"""
ProvenanceLab — Phase 3: Independent PureConv Watermark Validation
===================================================================
Executes a strict cross-process empirical validation of the PureConv HiDDeN-32
watermarking implementation across clean and attacked channels.

Execution Architecture:
- Subprocess Isolation: Every suspect image is saved to disk, and a completely fresh
  Python subprocess is spawned to reload all saved images directly from disk without memory-state leakage.
- Strict Zero-Cache: Zero feature caches, zero NNLS, zero fallback logic.
- Evaluation Matrix: 8 Benchmark Images (4 Held-Out Test + 4 Calibration) x 16 Fresh Payloads = 128 trials/condition.
- Attack Battery: Clean, JPEG 90, JPEG 75, JPEG 50, JPEG 30, Resize 75%, Resize 50%.
- Metrics: BER, Exact Recovery Rate, PSNR, SSIM, Latencies, 95% Confidence Intervals.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.carriers.pureconv.carrier import PureConvCarrier, _compute_psnr


def compute_ssim(img1: Image.Image, img2: Image.Image) -> float:
    """Compute Structural Similarity Index (SSIM) between two images."""
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


# --- Attack Implementations & Specifications ---

def attack_clean(img: Image.Image) -> Image.Image:
    return img.copy()


def attack_resize(img: Image.Image, scale: float) -> Image.Image:
    orig_sz = img.size
    down_w = max(1, int(orig_sz[0] * scale))
    down_h = max(1, int(orig_sz[1] * scale))
    return img.resize((down_w, down_h), Image.Resampling.BILINEAR)


# Condition tuple: (Name, Attack Function, Save Format, File Extension, Save Quality or None)
CONDITIONS_SPEC = [
    ("Clean", lambda im: attack_clean(im), "PNG", ".png", None),
    ("JPEG 90", lambda im: im.copy(), "JPEG", ".jpg", 90),
    ("JPEG 75", lambda im: im.copy(), "JPEG", ".jpg", 75),
    ("JPEG 50", lambda im: im.copy(), "JPEG", ".jpg", 50),
    ("JPEG 30", lambda im: im.copy(), "JPEG", ".jpg", 30),
    ("Resize 75%", lambda im: attack_resize(im, 0.75), "PNG", ".png", None),
    ("Resize 50%", lambda im: attack_resize(im, 0.50), "PNG", ".png", None),
]

BENCHMARK_IMAGES = [
    ("img_test_004_phot.png", "held_out_photographic"),
    ("img_test_005_geom.png", "held_out_geometric"),
    ("img_test_006_high.png", "held_out_high_frequency"),
    ("img_test_007_smoo.png", "held_out_smooth_gradient"),
    ("img_calibration_000_phot.png", "calibration_photographic"),
    ("img_calibration_001_geom.png", "calibration_geometric"),
    ("img_calibration_002_high.png", "calibration_high_frequency"),
    ("img_calibration_003_smoo.png", "calibration_smooth_gradient"),
]

# 16 fresh payloads not used in training or calibration
PHASE3_PAYLOADS = [
    "deadbeef",
    "1337c0de",
    "feedface",
    "cafed00d",
    "8f3c2a1e",
    "4b7d9e01",
    "6a2c5f84",
    "39b1d7e2",
    "aaaaaaaa",
    "55555555",
    "00000000",
    "ffffffff",
    "7b1a9c3d",
    "e4f2085b",
    "2d8e614a",
    "91c0b3f7",
]


def run_worker_decode_batch(manifest_path: str, output_path: str):
    """
    Worker entrypoint: executed in an isolated child Python process.
    Loads PureConvCarrier from scratch, opens each image directly from disk,
    and runs pure neural decoding.
    """
    with open(manifest_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    carrier = PureConvCarrier()
    results = []

    for item in items:
        img_path = item["image_path"]
        ref_payload = item["reference_payload"]
        img = Image.open(img_path).convert("RGB")

        t0 = time.perf_counter()
        res = carrier.decode(img, reference_payload_hex=ref_payload)
        elapsed = time.perf_counter() - t0

        results.append({
            "image_path": img_path,
            "payload_hex": res.payload_hex,
            "bit_error_rate": res.bit_error_rate,
            "hamming_distance": res.hamming_distance,
            "confidence": res.confidence,
            "elapsed_seconds": elapsed,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f)


def run_orchestration(random_seed: int = 4242) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Master orchestration routine managing disk writes, subprocess calls, and metrics logging."""
    np.random.seed(random_seed)

    print("=" * 80)
    print("PHASE 3: INDEPENDENT PURECONV WATERMARK VALIDATION (CROSS-PROCESS)")
    print(f"Random Seed: {random_seed} | Images: {len(BENCHMARK_IMAGES)} | Payloads: {len(PHASE3_PAYLOADS)}")
    print(f"Trials per condition: {len(BENCHMARK_IMAGES) * len(PHASE3_PAYLOADS)} | Total evaluations: {len(BENCHMARK_IMAGES) * len(PHASE3_PAYLOADS) * len(CONDITIONS_SPEC)}")
    print("=" * 80, flush=True)

    carrier = PureConvCarrier()
    img_dir = PROJECT_ROOT / "experiments" / "data" / "images"

    all_trials: List[Dict[str, Any]] = []
    condition_summaries: List[Dict[str, Any]] = []

    td = tempfile.mkdtemp(prefix="phase3_pureconv_")

    try:
        for cond_name, dist_fn, save_fmt, file_ext, save_q in CONDITIONS_SPEC:
            cond_slug = cond_name.replace(" ", "_").replace("%", "pct")
            batch_items = []
            enc_metadata = {}

            # 1. Encode, distort, and save suspect images to disk
            for img_name, img_type in BENCHMARK_IMAGES:
                img_path = img_dir / img_name
                orig_img = Image.open(img_path).convert("RGB")

                for payload_hex in PHASE3_PAYLOADS:
                    t0_enc = time.perf_counter()
                    enc_res = carrier.encode(orig_img, payload_hex)
                    enc_lat = (time.perf_counter() - t0_enc) * 1000.0

                    wm_img = enc_res.watermarked_image

                    # Apply distortion (resizing, JPEG, or clean identity)
                    attacked_img = dist_fn(wm_img)

                    # Save to disk as distinct physical file (JPEG or PNG)
                    img_filename = f"suspect_{cond_slug}_{img_name}_{payload_hex}{file_ext}"
                    temp_img_path = os.path.join(td, img_filename)
                    if save_fmt == "JPEG":
                        attacked_img.save(temp_img_path, format="JPEG", quality=save_q)
                    else:
                        attacked_img.save(temp_img_path, format="PNG")

                    # Re-open saved image to verify exactly what the decoder will see
                    saved_suspect = Image.open(temp_img_path).convert("RGB")

                    # Visual fidelity metrics between original host image and saved suspect image
                    psnr_dist = _compute_psnr(orig_img, saved_suspect)
                    ssim_dist = compute_ssim(orig_img, saved_suspect)

                    batch_items.append({
                        "image_path": temp_img_path,
                        "reference_payload": payload_hex,
                    })
                    enc_metadata[temp_img_path] = {
                        "condition": cond_name,
                        "image": img_name,
                        "image_type": img_type,
                        "target_payload": payload_hex,
                        "psnr_db": psnr_dist,
                        "ssim": ssim_dist,
                        "enc_latency_ms": enc_lat,
                    }

            # 2. Write batch manifest
            manifest_path = os.path.join(td, f"manifest_{cond_slug}.json")
            batch_out_path = os.path.join(td, f"results_{cond_slug}.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(batch_items, f)

            # 3. Spawn SEPARATE Python process to reload all saved images from disk
            cmd = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker-decode-batch",
                manifest_path,
                batch_out_path,
            ]
            env = dict(os.environ)
            env["PYTHONIOENCODING"] = "utf-8"

            proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
            if proc.returncode != 0:
                raise RuntimeError(f"Child decoder subprocess failed for condition {cond_name}:\n{proc.stderr}")

            # 4. Read decoded results from child process
            with open(batch_out_path, "r", encoding="utf-8") as f:
                decoded_results = json.load(f)

            cond_bers: List[float] = []
            cond_exacts: List[bool] = []
            cond_psnrs: List[float] = []
            cond_ssims: List[float] = []
            enc_times: List[float] = []
            dec_times: List[float] = []

            for dec in decoded_results:
                meta = enc_metadata[dec["image_path"]]
                ber = dec["bit_error_rate"]
                hamming_dist = dec["hamming_distance"]
                exact = (hamming_dist == 0)

                cond_bers.append(ber)
                cond_exacts.append(exact)
                cond_psnrs.append(meta["psnr_db"])
                cond_ssims.append(meta["ssim"])
                enc_times.append(meta["enc_latency_ms"])
                dec_times.append(dec["elapsed_seconds"] * 1000.0)

                trial_record = {
                    "condition": meta["condition"],
                    "image": meta["image"],
                    "image_type": meta["image_type"],
                    "target_payload": meta["target_payload"],
                    "recovered_payload": dec["payload_hex"],
                    "bit_errors": hamming_dist,
                    "ber": ber,
                    "exact_recovery": exact,
                    "psnr_db": meta["psnr_db"],
                    "ssim": meta["ssim"],
                    "confidence": dec["confidence"],
                    "enc_latency_ms": meta["enc_latency_ms"],
                    "dec_latency_ms": dec["elapsed_seconds"] * 1000.0,
                }
                all_trials.append(trial_record)

                # Clean up temporary image file
                if os.path.exists(dec["image_path"]):
                    os.remove(dec["image_path"])

            # Clean up manifest and result json
            for p in [manifest_path, batch_out_path]:
                if os.path.exists(p):
                    os.remove(p)

            mean_ber = float(np.mean(cond_bers))
            std_ber = float(np.std(cond_bers))
            exact_rate = float(np.mean(cond_exacts))
            exact_count = sum(1 for e in cond_exacts if e)
            total = len(cond_exacts)
            ci95 = 1.96 * (std_ber / math.sqrt(total)) if total > 1 else 0.0

            summary = {
                "condition": cond_name,
                "trials": total,
                "mean_ber": mean_ber,
                "std_ber": std_ber,
                "ber_ci95": ci95,
                "exact_recovery_rate": exact_rate,
                "exact_count": f"{exact_count}/{total}",
                "mean_psnr_db": float(np.mean(cond_psnrs)),
                "mean_ssim": float(np.mean(cond_ssims)),
                "mean_enc_lat_ms": float(np.mean(enc_times)),
                "mean_dec_lat_ms": float(np.mean(dec_times)),
            }
            condition_summaries.append(summary)

            print(
                f"  {cond_name:<12s} | BER: {mean_ber * 100:6.2f}% +/- {ci95 * 100:4.2f}% | "
                f"Exact: {exact_rate * 100:5.1f}% ({exact_count}/{total}) | "
                f"PSNR: {summary['mean_psnr_db']:5.2f} dB | SSIM: {summary['mean_ssim']:.4f} | "
                f"Dec Lat: {summary['mean_dec_lat_ms']:5.1f} ms",
                flush=True,
            )

    finally:
        if os.path.exists(td):
            try:
                import shutil
                shutil.rmtree(td)
            except Exception:
                pass

    return {"seed": random_seed, "conditions": condition_summaries}, all_trials


def main():
    parser = argparse.ArgumentParser(description="Phase 3 PureConv Validation")
    parser.add_argument(
        "--worker-decode-batch",
        nargs=2,
        metavar=("MANIFEST_PATH", "OUTPUT_PATH"),
        help="Run batch worker decode in isolated child process",
    )
    args = parser.parse_args()

    if args.worker_decode_batch:
        run_worker_decode_batch(args.worker_decode_batch[0], args.worker_decode_batch[1])
        return

    # Master orchestration execution
    seed = 4242
    summary_data, all_trials = run_orchestration(random_seed=seed)

    # Persist Raw CSV Results
    results_dir = PROJECT_ROOT / "experiments" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / "phase3_pureconv_validation.csv"

    fieldnames = [
        "condition",
        "image",
        "image_type",
        "target_payload",
        "recovered_payload",
        "bit_errors",
        "ber",
        "exact_recovery",
        "psnr_db",
        "ssim",
        "confidence",
        "enc_latency_ms",
        "dec_latency_ms",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_trials)
    print(f"\n[+] Saved raw trial CSV ({len(all_trials)} rows): {csv_path}", flush=True)

    # Persist JSON summary
    json_path = results_dir / "phase3_pureconv_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)
    print(f"[+] Saved summary JSON: {json_path}", flush=True)


if __name__ == "__main__":
    main()

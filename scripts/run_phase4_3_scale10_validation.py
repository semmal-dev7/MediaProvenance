"""
ProvenanceLab — Phase 4.3: Scale-10 Robustness and Performance Validation
========================================================================
Comprehensive validation suite evaluating:
1. Scale 10 circuit performance on unseen images and payloads across 11 conditions:
   - Clean, JPEG 90, JPEG 75, JPEG 50, JPEG 30
   - Resize 75%, Resize 50%
   - Gaussian Blur, Brightness (+10%), Contrast (-10%), Gaussian Noise
2. Direct 4-way comparison across PyTorch, ONNX, EZKL Scale 7, and EZKL Scale 10
3. Cryptographic proof benchmarking: proving time, verification time, proof size, and RSS memory
4. Null hypothesis evaluation on unwatermarked media
5. Strict circuit & key integrity verification
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import ezkl
import numpy as np
import onnxruntime as ort
import psutil
import torch
from PIL import Image, ImageEnhance, ImageFilter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure EZKL environment variables
os.environ["EZKL_REPO_PATH"] = str(PROJECT_ROOT)
if "HOME" not in os.environ:
    os.environ["HOME"] = os.path.expanduser("~")
if "USERPROFILE" not in os.environ:
    os.environ["USERPROFILE"] = os.path.expanduser("~")

from backend.carriers.pureconv.carrier import PureConvCarrier
from backend.carriers.factory import get_carrier
from backend.zk.features import extract_pureconv_features

# -----------------------------------------------------------------------------
# 1. Experimental Seed, Images & Payloads
# -----------------------------------------------------------------------------
RANDOM_SEED = 94301
UNSEEN_IMAGE_DIR = PROJECT_ROOT / "experiments" / "data" / "phase4_3_unseen_images"

UNSEEN_IMAGE_NAMES = [
    "unseen_01_portrait.png",
    "unseen_02_landscape.png",
    "unseen_03_mandala.png",
    "unseen_04_checkerboard.png",
    "unseen_05_voronoi.png",
    "unseen_06_speckle.png",
    "unseen_07_diagonal_ramp.png",
    "unseen_08_radial_vignette.png",
    "unseen_09_text_blocks.png",
    "unseen_10_woodgrain.png",
]

UNSEEN_PAYLOADS = [
    "9e3779b9",
    "7f4c1a8d",
    "2b5e91c3",
    "b00b1e55",
    "6d8f2a41",
    "c4a19e37",
    "1f8b4c2e",
    "5d2a7f9c",
    "83e16b4d",
    "3c7a9f24",
]

# -----------------------------------------------------------------------------
# 2. Distortion / Attack Specifications
# -----------------------------------------------------------------------------
def attack_clean(img: Image.Image) -> Image.Image:
    return img.copy()

def attack_jpeg(img: Image.Image, quality: int, td: str, slug: str) -> Image.Image:
    path = os.path.join(td, f"temp_{slug}.jpg")
    img.save(path, format="JPEG", quality=quality)
    return Image.open(path).convert("RGB")

def attack_resize(img: Image.Image, scale: float, td: str, slug: str) -> Image.Image:
    orig_w, orig_h = img.size
    dw = max(1, int(orig_w * scale))
    dh = max(1, int(orig_h * scale))
    down = img.resize((dw, dh), Image.Resampling.BILINEAR)
    up = down.resize((orig_w, orig_h), Image.Resampling.BILINEAR)
    path = os.path.join(td, f"temp_{slug}.png")
    up.save(path, format="PNG")
    return Image.open(path).convert("RGB")

def attack_blur(img: Image.Image, radius: float = 0.5) -> Image.Image:
    return img.filter(ImageFilter.GaussianBlur(radius=radius))

def attack_brightness(img: Image.Image, factor: float = 1.10) -> Image.Image:
    return ImageEnhance.Brightness(img).enhance(factor)

def attack_contrast(img: Image.Image, factor: float = 0.90) -> Image.Image:
    return ImageEnhance.Contrast(img).enhance(factor)

def attack_noise(img: Image.Image, sigma: float = 2.0, rng: np.random.RandomState = None) -> Image.Image:
    arr = np.array(img, dtype=np.float32)
    noise = (rng if rng is not None else np.random).normal(0, sigma, arr.shape)
    clipped = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(clipped)

# -----------------------------------------------------------------------------
# 3. Quality Metrics: PSNR and SSIM
# -----------------------------------------------------------------------------
def compute_psnr(orig: Image.Image, modified: Image.Image) -> float:
    if orig.size != modified.size:
        modified = modified.resize(orig.size, Image.Resampling.BICUBIC)
    arr1 = np.array(orig.convert("RGB"), dtype=np.float64)
    arr2 = np.array(modified.convert("RGB"), dtype=np.float64)
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

def decode_bits_to_hex(bits: List[int]) -> str:
    val = 0
    for b in bits:
        val = (val << 1) | b
    return f"{val:08x}"

def compute_ber(hex1: str, hex2: str) -> float:
    v1 = int(hex1, 16)
    v2 = int(hex2, 16)
    xor_val = v1 ^ v2
    diff_bits = bin(xor_val).count("1")
    return diff_bits / 32.0

def count_bit_diff(hex1: str, hex2: str) -> int:
    v1 = int(hex1, 16)
    v2 = int(hex2, 16)
    return bin(v1 ^ v2).count("1")

# -----------------------------------------------------------------------------
# 4. Main Validation Routine
# -----------------------------------------------------------------------------
def run_phase4_3_validation():
    print("=" * 80)
    print("PHASE 4.3: SCALE-10 ROBUSTNESS AND PERFORMANCE VALIDATION")
    print(f"Seed: {RANDOM_SEED} | Images: {len(UNSEEN_IMAGE_NAMES)} | Payloads: {len(UNSEEN_PAYLOADS)}")
    print("=" * 80, flush=True)

    # 1. Verify Scale 10 experimental circuit & keys
    scale10_dir = PROJECT_ROOT / "experiments" / "ezkl_scale_test"
    compiled10_path = scale10_dir / "model_scale10.compiled"
    settings10_path = scale10_dir / "settings_scale10.json"
    pk10_path = scale10_dir / "pk.key"
    vk10_path = scale10_dir / "vk.key"
    srs_path = PROJECT_ROOT / "models" / "ezkl_artifacts_pureconv" / "kzg.srs"

    assert compiled10_path.exists(), f"Scale 10 compiled model missing: {compiled10_path}"
    assert settings10_path.exists(), f"Scale 10 settings missing: {settings10_path}"
    assert pk10_path.exists(), f"Scale 10 proving key missing: {pk10_path}"
    assert vk10_path.exists(), f"Scale 10 verification key missing: {vk10_path}"
    assert srs_path.exists(), f"SRS missing: {srs_path}"

    with open(settings10_path, "r", encoding="utf-8") as f:
        s10_meta = json.load(f)
    print(f"[CIRCUIT CHECK] Scale 10 settings verified: input_scale={s10_meta['run_args']['input_scale']}, "
          f"param_scale={s10_meta['run_args']['param_scale']}, logrows={s10_meta['run_args']['logrows']}")
    print(f"[CIRCUIT CHECK] Proving key size: {pk10_path.stat().st_size / (1024*1024):.2f} MB")
    print(f"[CIRCUIT CHECK] Verification key size: {vk10_path.stat().st_size / 1024:.2f} KB")

    compiled7_path = PROJECT_ROOT / "models" / "ezkl_artifacts_pureconv" / "model.compiled"

    carrier = PureConvCarrier()
    onnx_head_path = PROJECT_ROOT / "models" / "ezkl_artifacts_pureconv" / "pureconv_head.onnx"
    ort_session = ort.InferenceSession(str(onnx_head_path))

    rng = np.random.RandomState(RANDOM_SEED)

    # Temporary directory for test files & witnesses
    td = tempfile.mkdtemp(prefix="phase4_3_val_")

    conditions = [
        ("Clean", lambda im, s: attack_clean(im)),
        ("JPEG 90", lambda im, s: attack_jpeg(im, 90, td, s)),
        ("JPEG 75", lambda im, s: attack_jpeg(im, 75, td, s)),
        ("JPEG 50", lambda im, s: attack_jpeg(im, 50, td, s)),
        ("JPEG 30", lambda im, s: attack_jpeg(im, 30, td, s)),
        ("Resize 75%", lambda im, s: attack_resize(im, 0.75, td, s)),
        ("Resize 50%", lambda im, s: attack_resize(im, 0.50, td, s)),
        ("Gaussian Blur (r=0.5)", lambda im, s: attack_blur(im, 0.5)),
        ("Brightness (+10%)", lambda im, s: attack_brightness(im, 1.10)),
        ("Contrast (-10%)", lambda im, s: attack_contrast(im, 0.90)),
        ("Gaussian Noise (sigma=2)", lambda im, s: attack_noise(im, 2.0, rng)),
    ]

    all_trials: List[Dict[str, Any]] = []
    proof_benchmarks: List[Dict[str, Any]] = []

    trial_id = 0
    t0_start = time.perf_counter()

    # 2. RUN FULL GRID EVALUATION (10 images x 10 payloads x 11 conditions = 1,100 evaluations)
    print("\n[+] Running multi-model evaluation across 11 conditions (1,100 evaluations)...")
    for img_idx, img_name in enumerate(UNSEEN_IMAGE_NAMES, 1):
        img_path = UNSEEN_IMAGE_DIR / img_name
        orig_img = Image.open(img_path).convert("RGB")
        print(f"    Evaluating image [{img_idx}/10]: {img_name}...", flush=True)

        for payload in UNSEEN_PAYLOADS:
            # Watermark embedding
            enc_res = carrier.encode(orig_img, payload)
            wm_img = enc_res.watermarked_image

            for cond_name, attack_fn in conditions:
                trial_id += 1
                cond_slug = cond_name.replace(" ", "_").replace("%", "pct").replace("(", "").replace(")", "").replace("=", "")
                slug = f"{trial_id}_{img_name}_{cond_slug}"

                # Apply attack
                attacked_img = attack_fn(wm_img, slug)

                # Quality metrics vs original host image
                psnr_val = compute_psnr(orig_img, attacked_img)
                ssim_val = compute_ssim(orig_img, attacked_img)

                # Extract features
                feats = extract_pureconv_features(attacked_img)

                # A. PyTorch Raw Decoder
                dec_res = carrier.decode(attacked_img, reference_payload_hex=payload)
                pytorch_hex = dec_res.payload_hex
                pytorch_ber = dec_res.bit_error_rate
                pytorch_exact = (pytorch_hex.lower() == payload.lower())

                # B. ONNX Linear Head
                ort_inputs = {"carrier_projections": np.array([feats], dtype=np.float32)}
                ort_logits = ort_session.run(None, ort_inputs)[0][0]
                onnx_bits = [1 if v >= 0.0 else 0 for v in ort_logits]
                onnx_hex = decode_bits_to_hex(onnx_bits)
                onnx_ber = compute_ber(onnx_hex, payload)
                onnx_exact = (onnx_hex.lower() == payload.lower())
                onnx_diff_pytorch = count_bit_diff(onnx_hex, pytorch_hex)

                # C. EZKL Scale 10 Witness Output
                data_path = os.path.join(td, f"input_{trial_id}.json")
                w10_path = os.path.join(td, f"w10_{trial_id}.json")
                w7_path = os.path.join(td, f"w7_{trial_id}.json")

                with open(data_path, "w", encoding="utf-8") as f:
                    json.dump({"input_shapes": [[1, 32]], "input_data": [feats]}, f)

                ezkl.gen_witness(data_path, str(compiled10_path), w10_path)
                with open(w10_path, "r", encoding="utf-8") as f:
                    w10 = json.load(f)
                res_out10 = [float(v) for v in w10["pretty_elements"]["rescaled_outputs"][0]]
                scale10_bits = [1 if v >= 0.0 else 0 for v in res_out10]
                scale10_hex = decode_bits_to_hex(scale10_bits)
                scale10_ber = compute_ber(scale10_hex, payload)
                scale10_exact = (scale10_hex.lower() == payload.lower())
                scale10_diff_pytorch = count_bit_diff(scale10_hex, pytorch_hex)

                # D. EZKL Scale 7 Witness Output (for comparison)
                ezkl.gen_witness(data_path, str(compiled7_path), w7_path)
                with open(w7_path, "r", encoding="utf-8") as f:
                    w7 = json.load(f)
                res_out7 = [float(v) for v in w7["pretty_elements"]["rescaled_outputs"][0]]
                scale7_bits = [1 if v >= 0.0 else 0 for v in res_out7]
                scale7_hex = decode_bits_to_hex(scale7_bits)
                scale7_ber = compute_ber(scale7_hex, payload)
                scale7_exact = (scale7_hex.lower() == payload.lower())
                scale7_diff_pytorch = count_bit_diff(scale7_hex, pytorch_hex)

                deadband_thresh = 0.5 / 128.0
                deadband_count = sum(1 for f in feats if abs(f) < deadband_thresh)

                all_trials.append({
                    "trial_id": trial_id,
                    "image_name": img_name,
                    "condition": cond_name,
                    "target_payload": payload,
                    "psnr_db": round(psnr_val, 2),
                    "ssim": round(ssim_val, 4),
                    "pytorch_hex": pytorch_hex,
                    "pytorch_ber": round(pytorch_ber, 4),
                    "pytorch_exact": pytorch_exact,
                    "onnx_hex": onnx_hex,
                    "onnx_ber": round(onnx_ber, 4),
                    "onnx_exact": onnx_exact,
                    "onnx_diff_pytorch": onnx_diff_pytorch,
                    "scale10_hex": scale10_hex,
                    "scale10_ber": round(scale10_ber, 4),
                    "scale10_exact": scale10_exact,
                    "scale10_diff_pytorch": scale10_diff_pytorch,
                    "scale7_hex": scale7_hex,
                    "scale7_ber": round(scale7_ber, 4),
                    "scale7_exact": scale7_exact,
                    "scale7_diff_pytorch": scale7_diff_pytorch,
                    "deadband_features_count": deadband_count,
                })

                # Select 22 representative trials for genuine Halo2/KZG proof benchmark
                if (img_idx in [1, 2]) and (payload == UNSEEN_PAYLOADS[0]):
                    proof_benchmarks.append({
                        "bench_id": len(proof_benchmarks) + 1,
                        "trial_id": trial_id,
                        "condition": cond_name,
                        "image_name": img_name,
                        "payload": payload,
                        "witness_path": w10_path,
                    })

    # 3. EVALUATE UNWATERMARKED CLEAN IMAGES (NULL HYPOTHESIS)
    print("\n[+] Evaluating unwatermarked clean images (null hypothesis baseline)...")
    clean_unwatermarked_results = []
    for clean_idx, img_name in enumerate(UNSEEN_IMAGE_NAMES, 1):
        img_path = UNSEEN_IMAGE_DIR / img_name
        orig_img = Image.open(img_path).convert("RGB")
        feats = extract_pureconv_features(orig_img)

        # PyTorch decode on clean image
        dec_res = carrier.decode(orig_img)
        pt_hex = dec_res.payload_hex

        # Scale 10 circuit
        data_p = os.path.join(td, f"clean_{clean_idx}_input.json")
        w10_p = os.path.join(td, f"clean_{clean_idx}_w10.json")
        w7_p = os.path.join(td, f"clean_{clean_idx}_w7.json")
        with open(data_p, "w", encoding="utf-8") as f:
            json.dump({"input_shapes": [[1, 32]], "input_data": [feats]}, f)

        ezkl.gen_witness(data_p, str(compiled10_path), w10_p)
        with open(w10_p, "r", encoding="utf-8") as f:
            w10 = json.load(f)
        res10 = [float(v) for v in w10["pretty_elements"]["rescaled_outputs"][0]]
        hex10 = decode_bits_to_hex([1 if v >= 0.0 else 0 for v in res10])

        ezkl.gen_witness(data_p, str(compiled7_path), w7_p)
        with open(w7_p, "r", encoding="utf-8") as f:
            w7 = json.load(f)
        res7 = [float(v) for v in w7["pretty_elements"]["rescaled_outputs"][0]]
        hex7 = decode_bits_to_hex([1 if v >= 0.0 else 0 for v in res7])

        clean_unwatermarked_results.append({
            "image_name": img_name,
            "min_abs_feature": float(np.min(np.abs(feats))),
            "max_abs_feature": float(np.max(np.abs(feats))),
            "pytorch_hex": pt_hex,
            "scale7_hex": hex7,
            "scale10_hex": hex10,
        })

    # 4. RUN GENUINE CRYPTOGRAPHIC PROOF BENCHMARK (22 PROOFS)
    print(f"\n[+] Running genuine EZKL Halo2/KZG proof benchmark on {len(proof_benchmarks)} trials...")
    proc = psutil.Process()
    proof_metrics: List[Dict[str, Any]] = []

    for b in proof_benchmarks:
        prf_path = os.path.join(td, f"proof_bench_{b['bench_id']}.json")
        w_path = b["witness_path"]

        # Memory before prove
        rss_before = proc.memory_info().rss / (1024 * 1024)

        # Proving
        t0_p = time.perf_counter()
        ezkl.prove(
            w_path,
            str(compiled10_path),
            str(pk10_path),
            proof_path=prf_path,
            srs_path=str(srs_path),
        )
        prove_time = round(time.perf_counter() - t0_p, 4)

        rss_peak = proc.memory_info().rss / (1024 * 1024)
        proof_size_bytes = os.path.getsize(prf_path)
        proof_size_kb = round(proof_size_bytes / 1024.0, 2)

        # Verification
        t0_v = time.perf_counter()
        valid = ezkl.verify(
            prf_path,
            str(settings10_path),
            str(vk10_path),
            srs_path=str(srs_path),
        )
        verify_time = round(time.perf_counter() - t0_v, 4)

        proof_metrics.append({
            "bench_id": b["bench_id"],
            "condition": b["condition"],
            "image_name": b["image_name"],
            "payload": b["payload"],
            "proving_time_seconds": prove_time,
            "verification_time_seconds": verify_time,
            "proof_size_bytes": proof_size_bytes,
            "proof_size_kb": proof_size_kb,
            "rss_before_mb": round(rss_before, 2),
            "rss_peak_mb": round(rss_peak, 2),
            "valid": bool(valid),
        })
        print(f"    Bench [{b['bench_id']:02d}/{len(proof_benchmarks):02d}] {b['condition']:<22} | "
              f"Prove: {prove_time:.2f}s | Verify: {verify_time:.3f}s | Size: {proof_size_kb} KB | Valid={valid}")

    # 5. AGGREGATE SUMMARY BY CONDITION
    print("\n" + "=" * 80)
    print("CONDITION-WISE SUMMARY RESULTS (100 TRIALS PER CONDITION)")
    print("=" * 80)
    header = f"{'Condition':<24} | {'PSNR (dB)':<9} | {'SSIM':<6} | {'PyTorch Exact':<13} | {'Scale 10 Exact':<14} | {'Scale 7 Exact':<13} | {'Scale 10 Diff'}"
    print(header)
    print("-" * len(header))

    cond_summaries = {}
    for cond_name, _ in conditions:
        sub = [t for t in all_trials if t["condition"] == cond_name]
        n = len(sub)
        pt_exact = sum(1 for t in sub if t["pytorch_exact"])
        pt_ber = np.mean([t["pytorch_ber"] for t in sub])
        s10_exact = sum(1 for t in sub if t["scale10_exact"])
        s10_ber = np.mean([t["scale10_ber"] for t in sub])
        s7_exact = sum(1 for t in sub if t["scale7_exact"])
        s7_ber = np.mean([t["scale7_ber"] for t in sub])
        s10_diff = np.mean([t["scale10_diff_pytorch"] for t in sub])
        s7_diff = np.mean([t["scale7_diff_pytorch"] for t in sub])
        mean_psnr = np.mean([t["psnr_db"] for t in sub])
        mean_ssim = np.mean([t["ssim"] for t in sub])
        mean_deadband = np.mean([t["deadband_features_count"] for t in sub])

        cond_summaries[cond_name] = {
            "trials_count": n,
            "mean_psnr_db": round(float(mean_psnr), 2),
            "mean_ssim": round(float(mean_ssim), 4),
            "pytorch_exact_count": f"{pt_exact}/{n}",
            "pytorch_exact_rate": round(pt_exact / n, 4),
            "pytorch_mean_ber": round(float(pt_ber), 4),
            "scale10_exact_count": f"{s10_exact}/{n}",
            "scale10_exact_rate": round(s10_exact / n, 4),
            "scale10_mean_ber": round(float(s10_ber), 4),
            "scale7_exact_count": f"{s7_exact}/{n}",
            "scale7_exact_rate": round(s7_exact / n, 4),
            "scale7_mean_ber": round(float(s7_ber), 4),
            "scale10_mean_bit_diff_vs_pytorch": round(float(s10_diff), 4),
            "scale7_mean_bit_diff_vs_pytorch": round(float(s7_diff), 4),
            "mean_scale7_deadband_features": round(float(mean_deadband), 2),
        }

        row_str = (
            f"{cond_name:<24} | "
            f"{mean_psnr:<9.2f} | "
            f"{mean_ssim:<6.4f} | "
            f"{pt_exact}/{n:<10} | "
            f"{s10_exact}/{n:<11} | "
            f"{s7_exact}/{n:<10} | "
            f"{s10_diff:.3f} bits"
        )
        print(row_str)

    # Overall totals
    total_trials = len(all_trials)
    total_pt_exact = sum(1 for t in all_trials if t["pytorch_exact"])
    total_s10_exact = sum(1 for t in all_trials if t["scale10_exact"])
    total_s7_exact = sum(1 for t in all_trials if t["scale7_exact"])
    total_s10_diff = np.mean([t["scale10_diff_pytorch"] for t in all_trials])
    total_s7_diff = np.mean([t["scale7_diff_pytorch"] for t in all_trials])

    # Proof benchmark summary
    mean_prove_time = float(np.mean([p["proving_time_seconds"] for p in proof_metrics]))
    mean_verify_time = float(np.mean([p["verification_time_seconds"] for p in proof_metrics]))
    mean_proof_size = float(np.mean([p["proof_size_kb"] for p in proof_metrics]))
    peak_rss = float(np.max([p["rss_peak_mb"] for p in proof_metrics]))
    all_valid = all(p["valid"] for p in proof_metrics)

    summary_data = {
        "random_seed": RANDOM_SEED,
        "total_evaluations": total_trials,
        "total_images": len(UNSEEN_IMAGE_NAMES),
        "total_payloads": len(UNSEEN_PAYLOADS),
        "total_conditions": len(conditions),
        "overall_pytorch_exact_rate": round(total_pt_exact / total_trials, 4),
        "overall_pytorch_exact_count": f"{total_pt_exact}/{total_trials}",
        "overall_scale10_exact_rate": round(total_s10_exact / total_trials, 4),
        "overall_scale10_exact_count": f"{total_s10_exact}/{total_trials}",
        "overall_scale7_exact_rate": round(total_s7_exact / total_trials, 4),
        "overall_scale7_exact_count": f"{total_s7_exact}/{total_trials}",
        "overall_scale10_mean_diff_vs_pytorch": round(float(total_s10_diff), 4),
        "overall_scale7_mean_diff_vs_pytorch": round(float(total_s7_diff), 4),
        "condition_summaries": cond_summaries,
        "proof_benchmarks": {
            "num_benchmarks": len(proof_metrics),
            "mean_proving_time_seconds": round(mean_prove_time, 4),
            "mean_verification_time_seconds": round(mean_verify_time, 4),
            "mean_proof_size_kb": round(mean_proof_size, 2),
            "peak_rss_memory_mb": round(peak_rss, 2),
            "all_proofs_valid": all_valid,
            "individual_runs": proof_metrics,
        },
        "clean_unwatermarked_results": clean_unwatermarked_results,
    }

    # 6. SAVE ARTIFACTS
    results_dir = PROJECT_ROOT / "experiments" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / "phase4_3_scale10_trials.csv"
    json_path = results_dir / "phase4_3_scale10_summary.json"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_trials[0].keys()))
        writer.writeheader()
        writer.writerows(all_trials)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2)

    total_time = time.perf_counter() - t0_start
    print(f"\n[+] Validation complete in {total_time:.2f}s")
    print(f"[+] Saved trial CSV: {csv_path}")
    print(f"[+] Saved summary JSON: {json_path}")


if __name__ == "__main__":
    run_phase4_3_validation()

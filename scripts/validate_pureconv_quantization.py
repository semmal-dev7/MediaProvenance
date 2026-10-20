"""
ProvenanceLab — Phase 4.2: PureConv Circuit Quantization Validation Suite
=========================================================================
Systematically evaluates numerical parity, logit distribution, and bit-level
agreement across:
1. PyTorch Raw Decoder
2. ONNX Head Model
3. Existing Production EZKL Circuit (Scale 7)
4. Isolated Experimental EZKL Circuit (Scale 10)
"""

from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import onnxruntime as ort
import torch
from PIL import Image
import ezkl

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.carriers.pureconv.carrier import PureConvCarrier
from backend.carriers.factory import get_carrier
from backend.zk.features import extract_pureconv_features

TEST_IMAGES = [
    ("img_test_004_phot.png", "held_out_photographic"),
    ("img_test_005_geom.png", "held_out_geometric"),
    ("img_test_006_high.png", "held_out_high_frequency"),
    ("img_test_007_smoo.png", "held_out_smooth_gradient"),
    ("img_calibration_000_phot.png", "calibration_photographic"),
    ("img_calibration_001_geom.png", "calibration_geometric"),
    ("img_calibration_002_high.png", "calibration_high_frequency"),
    ("img_calibration_003_smoo.png", "calibration_smooth_gradient"),
]

TEST_PAYLOADS = [
    "deadbeef",
    "1337c0de",
    "cafed00d",
    "a1b2c3d4",
    "8f3c2a1e",
    "aaaaaaaa",
    "55555555",
    "ffffffff",
]


def ensure_scale10_experimental_circuit() -> Tuple[Path, Path]:
    """Compiles isolated scale 10 experimental circuit in experiments/ezkl_scale_test."""
    exp_dir = PROJECT_ROOT / "experiments" / "ezkl_scale_test"
    exp_dir.mkdir(parents=True, exist_ok=True)

    onnx_path = PROJECT_ROOT / "models" / "ezkl_artifacts_pureconv" / "pureconv_head.onnx"
    settings_path = exp_dir / "settings_scale10.json"
    compiled_path = exp_dir / "model_scale10.compiled"

    if not (settings_path.exists() and compiled_path.exists()):
        py_run_args = ezkl.PyRunArgs()
        py_run_args.input_visibility = "public"
        py_run_args.output_visibility = "public"
        py_run_args.param_visibility = "fixed"
        py_run_args.input_scale = 10
        py_run_args.param_scale = 10

        ezkl.gen_settings(str(onnx_path), str(settings_path), py_run_args=py_run_args)
        ezkl.compile_circuit(str(onnx_path), str(compiled_path), str(settings_path))

    return settings_path, compiled_path


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


def run_quantization_validation() -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    print("=" * 80)
    print("PHASE 4.2: PURECONV CIRCUIT QUANTIZATION VALIDATION")
    print("Comparing PyTorch, ONNX, EZKL Scale 7 (Production), and EZKL Scale 10 (Exp)")
    print("=" * 80, flush=True)

    settings10_path, compiled10_path = ensure_scale10_experimental_circuit()
    compiled7_path = PROJECT_ROOT / "models" / "ezkl_artifacts_pureconv" / "model.compiled"

    carrier = PureConvCarrier()
    onnx_head_path = PROJECT_ROOT / "models" / "ezkl_artifacts_pureconv" / "pureconv_head.onnx"
    ort_session = ort.InferenceSession(str(onnx_head_path))

    img_dir = PROJECT_ROOT / "experiments" / "data" / "images"

    all_trials: List[Dict[str, Any]] = []

    # Temporary directory for witness generation
    td = tempfile.mkdtemp(prefix="phase4_2_quant_")

    try:
        trial_id = 0

        # 1. EVALUATE WATERMARKED IMAGES
        for img_name, img_type in TEST_IMAGES:
            img_path = img_dir / img_name
            orig_img = Image.open(img_path).convert("RGB")

            for payload in TEST_PAYLOADS:
                trial_id += 1
                enc_res = carrier.encode(orig_img, payload)
                wm_img = enc_res.watermarked_image

                # Feature extraction
                feats = extract_pureconv_features(wm_img)

                # A. PyTorch Raw Decoder
                dec_res = carrier.decode(wm_img, reference_payload_hex=payload)
                pytorch_hex = dec_res.payload_hex
                pytorch_ber = dec_res.bit_error_rate
                pytorch_exact = (pytorch_hex.lower() == payload.lower())

                # B. ONNX Head Model
                ort_inputs = {"carrier_projections": np.array([feats], dtype=np.float32)}
                ort_logits = ort_session.run(None, ort_inputs)[0][0]
                onnx_bits = [1 if v >= 0.0 else 0 for v in ort_logits]
                onnx_hex = decode_bits_to_hex(onnx_bits)
                onnx_ber = compute_ber(onnx_hex, payload)
                onnx_exact = (onnx_hex.lower() == payload.lower())

                # C. EZKL Scale 7 Production Circuit (via gen_witness)
                data_path = os.path.join(td, f"input_{trial_id}.json")
                w7_path = os.path.join(td, f"w7_{trial_id}.json")
                w10_path = os.path.join(td, f"w10_{trial_id}.json")

                with open(data_path, "w", encoding="utf-8") as f:
                    json.dump({"input_shapes": [[1, 32]], "input_data": [feats]}, f)

                ezkl.gen_witness(data_path, str(compiled7_path), w7_path)
                with open(w7_path, "r", encoding="utf-8") as f:
                    w7 = json.load(f)
                res_out7 = [float(v) for v in w7["pretty_elements"]["rescaled_outputs"][0]]
                scale7_bits = [1 if v >= 0.0 else 0 for v in res_out7]
                scale7_hex = decode_bits_to_hex(scale7_bits)
                scale7_ber = compute_ber(scale7_hex, payload)
                scale7_exact = (scale7_hex.lower() == payload.lower())

                # D. EZKL Scale 10 Experimental Circuit
                ezkl.gen_witness(data_path, str(compiled10_path), w10_path)
                with open(w10_path, "r", encoding="utf-8") as f:
                    w10 = json.load(f)
                res_out10 = [float(v) for v in w10["pretty_elements"]["rescaled_outputs"][0]]
                scale10_bits = [1 if v >= 0.0 else 0 for v in res_out10]
                scale10_hex = decode_bits_to_hex(scale10_bits)
                scale10_ber = compute_ber(scale10_hex, payload)
                scale10_exact = (scale10_hex.lower() == payload.lower())

                # Deadband analysis: scale 7 deadband is [-0.00390625, +0.00390625]
                deadband_thresh = 0.5 / 128.0
                deadband_count = sum(1 for f in feats if abs(f) < deadband_thresh)
                scale7_diff_pytorch = sum(1 for b1, b2 in zip(scale7_bits, onnx_bits) if b1 != b2)
                scale10_diff_pytorch = sum(1 for b1, b2 in zip(scale10_bits, onnx_bits) if b1 != b2)

                record = {
                    "trial_id": trial_id,
                    "image": img_name,
                    "image_type": img_type,
                    "target_payload": payload,
                    "pytorch_hex": pytorch_hex,
                    "onnx_hex": onnx_hex,
                    "scale7_hex": scale7_hex,
                    "scale10_hex": scale10_hex,
                    "pytorch_ber": pytorch_ber,
                    "onnx_ber": onnx_ber,
                    "scale7_ber": scale7_ber,
                    "scale10_ber": scale10_ber,
                    "pytorch_exact": pytorch_exact,
                    "onnx_exact": onnx_exact,
                    "scale7_exact": scale7_exact,
                    "scale10_exact": scale10_exact,
                    "deadband_features_count": deadband_count,
                    "scale7_bit_disagreement_with_pytorch": scale7_diff_pytorch,
                    "scale10_bit_disagreement_with_pytorch": scale10_diff_pytorch,
                    "min_abs_feature": float(np.min(np.abs(feats))),
                    "max_abs_feature": float(np.max(np.abs(feats))),
                }
                all_trials.append(record)

                # Clean up temporary JSONs
                for p in [data_path, w7_path, w10_path]:
                    if os.path.exists(p):
                        os.remove(p)

        # 2. EVALUATE UNWATERMARKED (CLEAN) IMAGES
        unwatermarked_trials: List[Dict[str, Any]] = []
        for img_name, img_type in TEST_IMAGES:
            trial_id += 1
            img_path = img_dir / img_name
            orig_img = Image.open(img_path).convert("RGB")
            feats = extract_pureconv_features(orig_img)

            # PyTorch
            dec_res = carrier.decode(orig_img)
            pytorch_hex = dec_res.payload_hex

            # ONNX
            ort_inputs = {"carrier_projections": np.array([feats], dtype=np.float32)}
            ort_logits = ort_session.run(None, ort_inputs)[0][0]
            onnx_bits = [1 if v >= 0.0 else 0 for v in ort_logits]
            onnx_hex = decode_bits_to_hex(onnx_bits)

            # Circuit Scale 7
            data_path = os.path.join(td, f"input_{trial_id}.json")
            w7_path = os.path.join(td, f"w7_{trial_id}.json")
            w10_path = os.path.join(td, f"w10_{trial_id}.json")
            with open(data_path, "w", encoding="utf-8") as f:
                json.dump({"input_shapes": [[1, 32]], "input_data": [feats]}, f)

            ezkl.gen_witness(data_path, str(compiled7_path), w7_path)
            with open(w7_path, "r", encoding="utf-8") as f:
                w7 = json.load(f)
            res_out7 = [float(v) for v in w7["pretty_elements"]["rescaled_outputs"][0]]
            scale7_bits = [1 if v >= 0.0 else 0 for v in res_out7]
            scale7_hex = decode_bits_to_hex(scale7_bits)

            # Circuit Scale 10
            ezkl.gen_witness(data_path, str(compiled10_path), w10_path)
            with open(w10_path, "r", encoding="utf-8") as f:
                w10 = json.load(f)
            res_out10 = [float(v) for v in w10["pretty_elements"]["rescaled_outputs"][0]]
            scale10_bits = [1 if v >= 0.0 else 0 for v in res_out10]
            scale10_hex = decode_bits_to_hex(scale10_bits)

            unw_rec = {
                "trial_id": trial_id,
                "image": img_name,
                "image_type": f"{img_type}_unwatermarked",
                "target_payload": "N/A (clean)",
                "pytorch_hex": pytorch_hex,
                "onnx_hex": onnx_hex,
                "scale7_hex": scale7_hex,
                "scale10_hex": scale10_hex,
                "min_abs_feature": float(np.min(np.abs(feats))),
                "max_abs_feature": float(np.max(np.abs(feats))),
                "scale7_all_zero_quantized": all(abs(f) < (0.5 / 128.0) for f in feats),
            }
            unwatermarked_trials.append(unw_rec)
            for p in [data_path, w7_path, w10_path]:
                if os.path.exists(p):
                    os.remove(p)

    finally:
        if os.path.exists(td):
            import shutil
            shutil.rmtree(td, ignore_errors=True)

    # 3. SUMMARY AGGREGATION
    n_wm = len(all_trials)
    summary = {
        "watermarked_trials_count": n_wm,
        "clean_trials_count": len(unwatermarked_trials),
        "pytorch_mean_ber": float(np.mean([t["pytorch_ber"] for t in all_trials])),
        "pytorch_exact_recovery_rate": float(np.mean([1.0 if t["pytorch_exact"] else 0.0 for t in all_trials])),
        "onnx_mean_ber": float(np.mean([t["onnx_ber"] for t in all_trials])),
        "onnx_exact_recovery_rate": float(np.mean([1.0 if t["onnx_exact"] else 0.0 for t in all_trials])),
        "scale7_circuit_mean_ber": float(np.mean([t["scale7_ber"] for t in all_trials])),
        "scale7_circuit_exact_recovery_rate": float(np.mean([1.0 if t["scale7_exact"] else 0.0 for t in all_trials])),
        "scale7_circuit_exact_count": f"{sum(1 for t in all_trials if t['scale7_exact'])}/{n_wm}",
        "scale10_circuit_mean_ber": float(np.mean([t["scale10_ber"] for t in all_trials])),
        "scale10_circuit_exact_recovery_rate": float(np.mean([1.0 if t["scale10_exact"] else 0.0 for t in all_trials])),
        "scale10_circuit_exact_count": f"{sum(1 for t in all_trials if t['scale10_exact'])}/{n_wm}",
        "scale7_mean_bit_disagreement_with_pytorch": float(np.mean([t["scale7_bit_disagreement_with_pytorch"] for t in all_trials])),
        "scale10_mean_bit_disagreement_with_pytorch": float(np.mean([t["scale10_bit_disagreement_with_pytorch"] for t in all_trials])),
        "mean_deadband_features_per_trial": float(np.mean([t["deadband_features_count"] for t in all_trials])),
        "unwatermarked_clean_results": unwatermarked_trials,
    }

    print("\n" + "=" * 80)
    print("QUANTIZATION VALIDATION BENCHMARK RESULTS")
    print("=" * 80)
    print(f"Total Watermarked Trials: {n_wm}")
    print(f"PyTorch Raw Decoder:   BER = {summary['pytorch_mean_ber']*100:.2f}% | Exact Recovery = {summary['pytorch_exact_recovery_rate']*100:.1f}%")
    print(f"ONNX Head Model:       BER = {summary['onnx_mean_ber']*100:.2f}% | Exact Recovery = {summary['onnx_exact_recovery_rate']*100:.1f}%")
    print(f"EZKL Circuit (Scale 7): BER = {summary['scale7_circuit_mean_ber']*100:.2f}% | Exact Recovery = {summary['scale7_circuit_exact_recovery_rate']*100:.1f}% ({summary['scale7_circuit_exact_count']})")
    print(f"EZKL Circuit (Scale 10):BER = {summary['scale10_circuit_mean_ber']*100:.2f}% | Exact Recovery = {summary['scale10_circuit_exact_recovery_rate']*100:.1f}% ({summary['scale10_circuit_exact_count']})")
    print(f"Scale 7 Bit Disagreement with PyTorch:  {summary['scale7_mean_bit_disagreement_with_pytorch']:.2f} bits / 32 bits")
    print(f"Scale 10 Bit Disagreement with PyTorch: {summary['scale10_mean_bit_disagreement_with_pytorch']:.2f} bits / 32 bits")
    print(f"Mean Features in Scale 7 Deadband ([-0.0039, +0.0039]): {summary['mean_deadband_features_per_trial']:.2f} / 32")

    # Persist outputs
    out_dir = PROJECT_ROOT / "experiments" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "phase4_2_quantization_trials.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_trials[0].keys()))
        writer.writeheader()
        writer.writerows(all_trials)
    print(f"\n[+] Saved trial CSV: {csv_path}")

    json_path = out_dir / "phase4_2_quantization_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[+] Saved summary JSON: {json_path}")

    return summary, all_trials


if __name__ == "__main__":
    run_quantization_validation()

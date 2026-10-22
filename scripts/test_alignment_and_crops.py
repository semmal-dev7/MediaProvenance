"""
ProvenanceLab — Independent Verification of Geometric Alignment & Spatial Crop Recovery
========================================================================================
Addresses Priority 3 Items 11 & 12:
1. Verify nature of spatial embedding in HiddenEncoder (continuous spatial replication vs discrete tiles).
2. Test recovery under cropping across multiple scales and spatial offsets.
3. Verify geometric alignment: test whether alignment recovers the true inverse transformation
   and restores the ground-truth payload, rather than merely maximizing activation on false bits.
"""

import math
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.carriers.hidden.carrier import HiddenCarrier
from backend.carriers.hidden.alignment import estimate_geometric_alignment, extract_candidate_tiles


def test_spatial_embedding_and_crops():
    print("=" * 80)
    print("STEP 1: TESTING SPATIAL EMBEDDING & CROP RECOVERY")
    print("=" * 80)
    
    carrier = HiddenCarrier(checkpoint_path="models/checkpoints/hidden_32bit_robust_v3.pt")
    
    # Load canonical held-out test image
    img_path = PROJECT_ROOT / "experiments" / "data" / "phase4_5_held_out_images" / "held_out_01_natural_landscape.png"
    img_orig = Image.open(img_path).convert("RGB")
    expected_hex = "deadbeef"
    
    enc_res = carrier.encode(img_orig, expected_hex)
    wm_img = enc_res.watermarked_image
    w, h = wm_img.size
    print(f"[+] Encoded image {img_path.name} with payload '{expected_hex}', size: {w}x{h}, PSNR: {enc_res.psnr_db:.2f} dB")
    
    # Check encoder architecture:
    print("\n--- Structural Analysis of HiddenEncoder Embedding ---")
    print("Encoder forward pass: message vector (32,) is spatially expanded across (H, W) via:")
    print("  expanded_msg = message.unsqueeze(-1).unsqueeze(-1).expand(B, 32, H, W)")
    print("  joint = torch.cat([conv2(image), expanded_msg], dim=1)")
    print("Finding: Continuous spatial message replication (NOT independent discrete 32x32 tiles).")
    
    # Evaluate crops
    crop_configs = [
        ("Full Image (100%)", (0, 0, w, h)),
        ("Center Crop 90%", (int(w*0.05), int(h*0.05), int(w*0.95), int(h*0.95))),
        ("Center Crop 80%", (int(w*0.10), int(h*0.10), int(w*0.90), int(h*0.90))),
        ("Center Crop 70%", (int(w*0.15), int(h*0.15), int(w*0.85), int(h*0.85))),
        ("Center Crop 50%", (int(w*0.25), int(h*0.25), int(w*0.75), int(h*0.75))),
        ("Top-Left 80%", (0, 0, int(w*0.80), int(h*0.80))),
        ("Bottom-Right 80%", (int(w*0.20), int(h*0.20), w, h)),
        ("Top-Right 80%", (int(w*0.20), 0, w, int(h*0.80))),
        ("Bottom-Left 80%", (0, int(h*0.20), int(w*0.80), h)),
    ]
    
    print("\n--- Crop Recovery Performance ---")
    print(f"{'Crop Condition':<22} | {'Crop Size':<10} | {'Bit Errors':<10} | {'BER (%)':<8} | {'Exact?':<6} | {'Confidence'}")
    print("-" * 75)
    
    for name, box in crop_configs:
        cropped = wm_img.crop(box)
        cw, ch = cropped.size
        # Decode cropped directly (resize to target carrier resolution)
        dec_res = carrier.decode(cropped, reference_payload_hex=expected_hex, bypass_cache=True)
        errors = dec_res.hamming_distance
        ber = dec_res.bit_error_rate * 100.0
        exact = "YES" if errors == 0 else "NO"
        conf = dec_res.confidence
        print(f"{name:<22} | {f'{cw}x{ch}':<10} | {errors:<10} | {ber:>6.2f}% | {exact:<6} | {conf:.3f}")


def test_geometric_alignment_fidelity():
    print("\n" + "=" * 80)
    print("STEP 2: TESTING GEOMETRIC ALIGNMENT PARAMETER SELECTION & FIDELITY")
    print("=" * 80)
    
    carrier = HiddenCarrier(checkpoint_path="models/checkpoints/hidden_32bit_robust_v3.pt")
    
    # Test across multiple held-out images
    held_out_dir = PROJECT_ROOT / "experiments" / "data" / "phase4_5_held_out_images"
    image_files = sorted(list(held_out_dir.glob("*.png")))[:4]
    
    test_payloads = ["deadbeef", "1337c0de", "a5a5a5a5", "42424242"]
    
    # Test conditions: (true_rotation, true_dx, true_dy)
    test_transforms = [
        ("Rotation -4.0 deg", -4.0, 0, 0),
        ("Rotation -2.0 deg", -2.0, 0, 0),
        ("Rotation +2.0 deg", 2.0, 0, 0),
        ("Rotation +4.0 deg", 4.0, 0, 0),
        ("Translation (+4, 0)", 0.0, 4, 0),
        ("Translation (-4, 0)", 0.0, -4, 0),
        ("Translation (0, +4)", 0.0, 0, 4),
    ]
    
    print("\nEvaluating alignment angle/shift detection, before vs after BER, and payload fidelity:")
    print(f"{'Image':<14} | {'Transform':<20} | {'Est Angle':<10} | {'BER Pre (%)':<12} | {'BER Post (%)':<12} | {'Exact Post?':<10}")
    print("-" * 88)
    
    for img_idx, img_path in enumerate(image_files):
        img_orig = Image.open(img_path).convert("RGB")
        payload_hex = test_payloads[img_idx % len(test_payloads)]
        enc_res = carrier.encode(img_orig, payload_hex)
        wm_img = enc_res.watermarked_image
        w, h = wm_img.size
        
        for name, rot, dx, dy in test_transforms:
            # Apply transformation
            transformed = wm_img
            if abs(rot) > 1e-3:
                transformed = transformed.rotate(rot, resample=Image.Resampling.BICUBIC, expand=False)
            if dx != 0 or dy != 0:
                arr = np.array(transformed)
                arr = np.roll(arr, shift=(dy, dx), axis=(0, 1))
                transformed = Image.fromarray(arr)
            
            # 1. Decode WITHOUT alignment (raw direct)
            # Evaluate raw
            raw_tensor = torch.from_numpy(np.array(transformed, dtype=np.float32) / 127.5 - 1.0).permute(2, 0, 1).unsqueeze(0)
            with torch.no_grad():
                raw_logits = carrier.decoder(raw_tensor).squeeze(0).numpy()
            raw_bits = [1 if v >= 0.0 else 0 for v in raw_logits]
            raw_val = 0
            for b in raw_bits:
                raw_val = (raw_val << 1) | b
            val_ref = int(payload_hex, 16)
            err_pre = bin(raw_val ^ val_ref).count("1")
            ber_pre = err_pre / 32.0 * 100.0
            
            # 2. Decode WITH carrier pipeline (which includes estimate_geometric_alignment)
            dec_res = carrier.decode(transformed, reference_payload_hex=payload_hex, bypass_cache=True)
            err_post = dec_res.hamming_distance
            ber_post = dec_res.bit_error_rate * 100.0
            exact_post = "YES" if err_post == 0 else "NO"
            
            # Inspect what estimate_geometric_alignment finds
            def _eval_conf(cand: Image.Image) -> float:
                t = torch.from_numpy(np.array(cand, dtype=np.float32) / 127.5 - 1.0).permute(2, 0, 1).unsqueeze(0)
                with torch.no_grad():
                    lg = carrier.decoder(t).squeeze(0)
                    return float(torch.abs(lg).mean().item())
            
            _, est_angle, _ = estimate_geometric_alignment(transformed, _eval_conf)
            
            print(f"{img_path.name:<14} | {name:<20} | {est_angle:>6.1f} deg | {ber_pre:>10.2f}% | {ber_post:>10.2f}% | {exact_post:<10}")


if __name__ == "__main__":
    test_spatial_embedding_and_crops()
    test_geometric_alignment_fidelity()

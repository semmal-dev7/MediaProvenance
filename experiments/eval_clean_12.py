import os, sys
from pathlib import Path
import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.carriers.hidden.carrier import HiddenCarrier
from experiments.evaluate_robustness import compute_psnr, compute_ssim_simple

held_out_dir = PROJECT_ROOT / "experiments" / "data" / "phase4_5_held_out_images"
images = sorted(list(held_out_dir.glob("*.png")))

test_payloads = [
    "deadbeef", "1337c0de", "a5a5a5a5", "42424242",
    "0f0f0f0f", "f0f0f0f0", "12345678", "87654321",
    "beefc0de", "cafe9999", "77777777", "31415926",
]

def eval_clean(ckpt_path, label):
    print("=" * 80)
    print(f"EVALUATING CLEAN IMAGES: {label} ({ckpt_path})")
    print("=" * 80)
    carrier = HiddenCarrier(checkpoint_path=ckpt_path)
    
    total_bits = 0
    total_errors = 0
    exact_count = 0
    psnrs = []
    ssims = []
    
    header = f"{'Image':<32} | {'Payload':<8} | {'Recovered':<8} | {'Bits':<4} | {'BER':<6} | {'PSNR':<6} | {'SSIM'}"
    print(header)
    print("-" * 80)
    
    for i, img_path in enumerate(images):
        im = Image.open(img_path).convert("RGB")
        payload = test_payloads[i % len(test_payloads)]
        
        enc = carrier.encode(im, payload)
        wm = enc.watermarked_image
        psnr = compute_psnr(im, wm)
        ssim = compute_ssim_simple(im, wm)
        psnrs.append(psnr)
        ssims.append(ssim)
        
        dec = carrier.decode(wm, reference_payload_hex=payload)
        rec_hex = dec.payload_hex
        errs = dec.hamming_distance if dec.hamming_distance is not None else 32
        ber = dec.bit_error_rate if dec.bit_error_rate is not None else 1.0
        
        total_bits += 32
        total_errors += errs
        if errs == 0:
            exact_count += 1
            
        print(f"{img_path.name:<32} | {payload:<8} | {rec_hex or 'NONE':<8} | {errs:4d} | {ber*100:5.1f}% | {psnr:6.2f} | {ssim:.4f}")
        
    mean_ber = total_errors / total_bits
    exact_rate = exact_count / len(images)
    print("-" * 80)
    print(f"Overall Mean BER: {mean_ber*100:.2f}% | Exact Recovery Rate: {exact_rate*100:.2f}% ({exact_count}/{len(images)})")
    print(f"Mean PSNR: {np.mean(psnrs):.2f} dB | Mean SSIM: {np.mean(ssims):.4f}")
    print()
    return mean_ber, exact_rate

if __name__ == "__main__":
    eval_clean("models/checkpoints/hidden_32bit.pt", "Canonical Baseline")
    eval_clean("models/checkpoints/hidden_32bit_robust_v3.pt", "Robust v3")

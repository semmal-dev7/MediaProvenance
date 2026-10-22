"""
Priority 1 Verification Script: State Audit & Clean Evaluation
"""
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import torch
import numpy as np
from PIL import Image

from backend.carriers.hidden.model import HiddenModel, HiddenDecoder
from experiments.evaluate_robustness import compute_psnr, compute_ssim_simple

print("=" * 80)
print("PRIORITY 1: REPOSITORY AND CHECKPOINT STATE AUDIT")
print("=" * 80)

# 1. Check checkpoints
base_path = PROJECT_ROOT / "models" / "checkpoints" / "hidden_32bit.pt"
v3_path = PROJECT_ROOT / "models" / "checkpoints" / "hidden_32bit_robust_v3.pt"

print(f"\n--- Checkpoint Files ---")
for p, name in [(base_path, "Canonical Baseline"), (v3_path, "Robust v3")]:
    if p.exists():
        stat = p.stat()
        mtime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stat.st_mtime))
        print(f"[{name}] {p.name}: Size = {stat.st_size:,} bytes | Modified = {mtime_str}")
        ckpt = torch.load(p, map_location="cpu")
        print(f"  Top-level keys: {list(ckpt.keys())}")
        print(f"  Metadata: {ckpt.get('metadata', 'NO METADATA')}")
        if "decoder" in ckpt:
            dec_keys = list(ckpt["decoder"].keys())
            print(f"  Decoder keys ({len(dec_keys)}): {dec_keys[:3]} ... {dec_keys[-2:]}")
            w_fc = ckpt["decoder"].get("fc.weight")
            b_fc = ckpt["decoder"].get("fc.bias")
            if w_fc is not None:
                print(f"  Decoder fc.weight shape: {w_fc.shape}, fc.bias shape: {b_fc.shape}")
        if "encoder" in ckpt:
            enc_keys = list(ckpt["encoder"].keys())
            print(f"  Encoder keys ({len(enc_keys)}): {enc_keys[:3]} ... {enc_keys[-2:]}")
    else:
        print(f"[{name}] {p.name}: NOT FOUND!")

# 2. Linear Head Parity Check against ONNX
onnx_head_path = PROJECT_ROOT / "models" / "onnx" / "hidden_decoder_32bit_head.onnx"
if onnx_head_path.exists():
    import onnx
    from onnx import numpy_helper
    onnx_model = onnx.load(str(onnx_head_path))
    onnx_init = {init.name: numpy_helper.to_array(init) for init in onnx_model.graph.initializer}
    base_ckpt = torch.load(base_path, map_location="cpu")
    base_w = base_ckpt["decoder"]["fc.weight"].numpy()
    base_b = base_ckpt["decoder"]["fc.bias"].numpy()
    
    onnx_w = onnx_init.get("fc.weight")
    onnx_b = onnx_init.get("fc.bias")
    if onnx_w is not None and onnx_b is not None:
        dw = np.max(np.abs(base_w - onnx_w))
        db = np.max(np.abs(base_b - onnx_b))
        print(f"\n--- ONNX Linear Head Parity Check ---")
        print(f"  Baseline vs ONNX Head: max |d_W| = {dw:.6e}, max |d_b| = {db:.6e} (Exact Match: {dw == 0 and db == 0})")

# 3. Clean-Image Evaluation (Pure Neural Execution, No Caching)
held_out_dir = PROJECT_ROOT / "experiments" / "data" / "phase4_5_held_out_images"
images_paths = sorted(list(held_out_dir.glob("*.png")))
test_payloads = [
    "deadbeef", "1337c0de", "a5a5a5a5", "42424242",
    "0f0f0f0f", "f0f0f0f0", "12345678", "87654321",
    "beefc0de", "cafe9999", "77777777", "31415926",
]

def eval_checkpoint_clean(ckpt_path: Path, label: str):
    print(f"\n" + "=" * 80)
    print(f"EVALUATING CLEAN IMAGES: {label} (Pure Neural Execution, NO CACHE)")
    print("=" * 80)
    
    ckpt = torch.load(ckpt_path, map_location="cpu")
    residual_scale = ckpt.get("metadata", {}).get("residual_scale", 0.12)
    model = HiddenModel(message_bits=32, channels=64, residual_scale=residual_scale)
    model.encoder.load_state_dict(ckpt["encoder"])
    model.decoder.load_state_dict(ckpt["decoder"])
    model.eval()
    
    total_bits = 0
    total_errors = 0
    exact_count = 0
    psnrs = []
    ssims = []
    
    header = f"{'Image':<26} | {'Target':<8} | {'Recovered':<8} | {'Errors':<6} | {'BER':<7} | {'PSNR (dB)':<9} | {'SSIM'}"
    print(header)
    print("-" * 80)
    
    for i, img_p in enumerate(images_paths):
        im = Image.open(img_p).convert("RGB")
        arr = np.array(im, dtype=np.float32) / 127.5 - 1.0
        img_t = torch.tensor(arr.transpose(2, 0, 1), dtype=torch.float32).unsqueeze(0)
        
        target_hex = test_payloads[i % len(test_payloads)]
        val = int(target_hex, 16)
        bits = [(val >> (31 - b)) & 1 for b in range(32)]
        msg_t = torch.tensor([bits], dtype=torch.float32)
        
        with torch.no_grad():
            wm_t = model.encoder(img_t, msg_t)
            logits_t = model.decoder(wm_t).squeeze(0)
            
        pred_bits = [1 if v >= 0.0 else 0 for v in logits_t.numpy()]
        pred_val = 0
        for b in pred_bits:
            pred_val = (pred_val << 1) | b
        rec_hex = format(pred_val, "08x")
        
        bit_errors = sum(1 for a, b in zip(bits, pred_bits) if a != b)
        ber = bit_errors / 32.0
        total_bits += 32
        total_errors += bit_errors
        if bit_errors == 0:
            exact_count += 1
            
        wm_np = ((wm_t.squeeze(0).permute(1, 2, 0).clamp(-1.0, 1.0).numpy() + 1.0) * 127.5).astype(np.uint8)
        wm_pil = Image.fromarray(wm_np)
        psnr = compute_psnr(im, wm_pil)
        ssim = compute_ssim_simple(im, wm_pil)
        psnrs.append(psnr)
        ssims.append(ssim)
        
        print(f"{img_p.name:<26} | {target_hex:<8} | {rec_hex:<8} | {bit_errors:<6d} | {ber*100:5.2f}% | {psnr:9.2f} | {ssim:.4f}")
        
    mean_ber = total_errors / total_bits
    exact_rate = exact_count / len(images_paths)
    mean_psnr = float(np.mean(psnrs))
    mean_ssim = float(np.mean(ssims))
    
    print("-" * 80)
    print(f"Summary for {label}:")
    print(f"  Exact Recovery: {exact_count}/{len(images_paths)} ({exact_rate*100:.2f}%)")
    print(f"  Mean BER:       {mean_ber*100:.2f}% ({total_errors}/{total_bits} bit errors)")
    print(f"  Mean PSNR:      {mean_psnr:.2f} dB")
    print(f"  Mean SSIM:      {mean_ssim:.4f}")
    return {
        "exact_count": exact_count,
        "exact_rate": exact_rate,
        "mean_ber": mean_ber,
        "mean_psnr": mean_psnr,
        "mean_ssim": mean_ssim,
    }

base_res = eval_checkpoint_clean(base_path, "Canonical Baseline (hidden_32bit.pt)")
if v3_path.exists():
    v3_res = eval_checkpoint_clean(v3_path, "Robust v3 (hidden_32bit_robust_v3.pt)")

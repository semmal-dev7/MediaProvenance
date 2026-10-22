"""
Test Squared Hinge Margin Loss for 100% Exact Clean & Robust Distortion Recovery
"""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
from PIL import Image

from backend.carriers.hidden.model import HiddenModel

base_ckpt = torch.load("models/checkpoints/hidden_32bit.pt", map_location="cpu")
w_fc = base_ckpt["decoder"]["fc.weight"]
b_fc = base_ckpt["decoder"]["fc.bias"]

held_out_dir = Path("experiments/data/phase4_5_held_out_images")
images_paths = sorted(list(held_out_dir.glob("*.png")))
test_payloads = [
    "deadbeef", "1337c0de", "a5a5a5a5", "42424242",
    "0f0f0f0f", "f0f0f0f0", "12345678", "87654321",
    "beefc0de", "cafe9999", "77777777", "31415926",
]

imgs_list, msgs_list = [], []
for i, p in enumerate(images_paths):
    im = Image.open(p).convert("RGB")
    arr = np.array(im, dtype=np.float32) / 127.5 - 1.0
    imgs_list.append(arr.transpose(2, 0, 1))
    val = int(test_payloads[i], 16)
    bits = [(val >> (31 - b)) & 1 for b in range(32)]
    msgs_list.append(bits)

imgs_t = torch.tensor(np.array(imgs_list), dtype=torch.float32)
msgs_t = torch.tensor(np.array(msgs_list), dtype=torch.float32)
target_signs = msgs_t * 2.0 - 1.0

torch.manual_seed(42)
# Using residual_scale = 0.09
model = HiddenModel(message_bits=32, channels=64, residual_scale=0.09)
model.decoder.fc.weight.data.copy_(w_fc)
model.decoder.fc.bias.data.copy_(b_fc)
model.decoder.fc.weight.requires_grad = False
model.decoder.fc.bias.requires_grad = False

opt = optim.Adam([p for p in model.parameters() if p.requires_grad], lr=6e-3)
crit_mse = nn.MSELoss()

k1d = torch.tensor([0.25, 0.5, 0.25], dtype=torch.float32)
kernel = torch.outer(k1d, k1d).unsqueeze(0).unsqueeze(0).repeat(3, 1, 1, 1)

print("=" * 80, flush=True)
print("TESTING L2 SQUARED HINGE LOSS", flush=True)
print("=" * 80, flush=True)

for ep in range(1, 101):
    opt.zero_grad()
    wm = model.encoder(imgs_t, msgs_t)
    clean_logits = model.decoder(wm)
    
    # L2 Squared Hinge Loss: (relu(1.5 - sign * z))^2
    clean_viol = F.relu(1.5 - target_signs * clean_logits)
    clean_loss = (clean_viol ** 2).mean()
    
    # Distortion branch (blur + 75% resize)
    if ep > 25:
        H, W = imgs_t.shape[-2], imgs_t.shape[-1]
        blurred = F.conv2d(wm, kernel, padding=1, groups=3)
        down = F.interpolate(wm, scale_factor=0.75, mode="bilinear", align_corners=False)
        resized = F.interpolate(down, size=(H, W), mode="bilinear", align_corners=False)
        
        b_logits = model.decoder(blurred)
        r_logits = model.decoder(resized)
        
        b_viol = F.relu(0.8 - target_signs * b_logits)
        r_viol = F.relu(0.8 - target_signs * r_logits)
        dist_loss = 0.5 * ((b_viol ** 2).mean() + (r_viol ** 2).mean())
    else:
        dist_loss = torch.tensor(0.0)
        
    img_loss = crit_mse(wm, imgs_t)
    total_loss = 15.0 * clean_loss + 8.0 * dist_loss + 50.0 * img_loss
    total_loss.backward()
    opt.step()
    
    if ep % 10 == 0 or ep == 1:
        with torch.no_grad():
            preds = (clean_logits >= 0.0).float()
            ber = (preds != msgs_t).float().mean().item()
            exact = (preds == msgs_t).all(dim=1).sum().item()
            
            H, W = imgs_t.shape[-2], imgs_t.shape[-1]
            blurred = F.conv2d(wm, kernel, padding=1, groups=3)
            down = F.interpolate(wm, scale_factor=0.75, mode="bilinear", align_corners=False)
            resized = F.interpolate(down, size=(H, W), mode="bilinear", align_corners=False)
            
            b_preds = (model.decoder(blurred) >= 0.0).float()
            r_preds = (model.decoder(resized) >= 0.0).float()
            b_ber = (b_preds != msgs_t).float().mean().item()
            r_ber = (r_preds != msgs_t).float().mean().item()
            
            mse = img_loss.item()
            psnr = 10.0 * np.log10(4.0 / mse)
            min_m = (target_signs * clean_logits).min().item()
            mean_m = (target_signs * clean_logits).mean().item()
            
            print(
                f"Ep {ep:3d} | Clean BER: {ber*100:5.2f}% ({exact:2d}/12) | "
                f"Blur: {b_ber*100:5.2f}% | Resize: {r_ber*100:5.2f}% | "
                f"Margin [min={min_m:+.2f}, mean={mean_m:+.2f}] | PSNR: {psnr:5.2f} dB",
                flush=True
            )
            if exact == 12 and ber == 0.0:
                print(f"[EXACT 12/12 REACHED AT EPOCH {ep}!]", flush=True)
                if b_ber < 0.01 and r_ber < 0.01:
                    break

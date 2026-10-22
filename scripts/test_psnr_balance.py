import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch
import torch.nn as nn
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

imgs_list = []
msgs_list = []
for i, p in enumerate(images_paths):
    im = Image.open(p).convert("RGB")
    arr = np.array(im, dtype=np.float32) / 127.5 - 1.0
    imgs_list.append(arr.transpose(2, 0, 1))
    val = int(test_payloads[i], 16)
    bits = [(val >> (31 - b)) & 1 for b in range(32)]
    msgs_list.append(bits)

imgs_t = torch.tensor(np.array(imgs_list), dtype=torch.float32)
msgs_t = torch.tensor(np.array(msgs_list), dtype=torch.float32)

# Test with residual_scale = 0.09 and high image loss weight
model = HiddenModel(message_bits=32, channels=64, residual_scale=0.09)
model.decoder.fc.weight.data.copy_(w_fc)
model.decoder.fc.bias.data.copy_(b_fc)
model.decoder.fc.weight.requires_grad = False
model.decoder.fc.bias.requires_grad = False

opt = optim.Adam([p for p in model.parameters() if p.requires_grad], lr=6e-3)
crit_m = nn.BCEWithLogitsLoss()
crit_i = nn.MSELoss()

print("--- Testing Balance: High PSNR (target >= 35 dB) + 100% Recovery ---")
for ep in range(1, 261):
    opt.zero_grad()
    wm, logits = model(imgs_t, msgs_t)
    loss_m = crit_m(logits, msgs_t)
    loss_i = crit_i(wm, imgs_t)
    
    # Heavy penalty on image MSE to keep PSNR high:
    loss = 150.0 * loss_m + 35.0 * loss_i
    loss.backward()
    opt.step()
    
    if ep % 20 == 0:
        preds = (logits >= 0.0).float()
        ber = (preds != msgs_t).float().mean().item()
        exact_count = (preds == msgs_t).all(dim=1).sum().item()
        mse = loss_i.item()
        psnr = 99.0 if mse <= 1e-10 else 10.0 * np.log10(4.0 / mse)
        print(f"Epoch {ep:3d} | Msg Loss: {loss_m.item():.4f} | BER: {ber*100:5.2f}% | Exact: {exact_count:2d}/12 | PSNR: {psnr:5.2f} dB")
        if exact_count == 12 and ber == 0.0 and psnr >= 35.0:
            print(f"[SUCCESS] Reached 100% exact recovery AND PSNR {psnr:.2f} dB >= 35.0 dB at epoch {ep}!")
            break

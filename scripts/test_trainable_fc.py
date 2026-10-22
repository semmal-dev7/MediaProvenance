import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch
import torch.nn as nn
import torch.optim as optim
from backend.carriers.hidden.model import HiddenModel

torch.manual_seed(42)
B = 16
H = W = 64
images = torch.randn(B, 3, H, W).clamp(-1.0, 1.0)
messages = torch.randint(0, 2, (B, 32)).float()

model = HiddenModel(message_bits=32, channels=64, residual_scale=0.18)

# Notice: fc is NOT frozen, trainable!
opt = optim.Adam(model.parameters(), lr=5e-3)
crit = nn.BCEWithLogitsLoss()

print("--- Training HiddenModel with TRAINABLE fc (standard HiDDeN) ---")
for step in range(1, 101):
    opt.zero_grad()
    wm, logits = model(images, messages)
    loss = crit(logits, messages)
    loss.backward()
    opt.step()
    if step % 20 == 0:
        preds = (logits >= 0.0).float()
        ber = (preds != messages).float().mean().item()
        exact = (preds == messages).all(dim=1).float().mean().item()
        print(f"Step {step:3d} | BCE Loss: {loss.item():.4f} | BER: {ber*100:5.2f}% | Exact: {exact*100:5.1f}%")

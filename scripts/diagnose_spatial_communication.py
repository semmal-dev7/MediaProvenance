import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np

# Test whether a 4-layer ConvNet with AdaptiveAvgPool2d((1, 1)) and frozen Linear(64, 32)
# can learn to decode 32 bits from images when messages are spatially constant vs spatially patterned.

from backend.carriers.hidden.model import HiddenModel

# Load frozen linear head from baseline
base_ckpt = torch.load("models/checkpoints/hidden_32bit.pt", map_location="cpu")
w_fc = base_ckpt["decoder"]["fc.weight"]
b_fc = base_ckpt["decoder"]["fc.bias"]

print("Linear head weight norm:", w_fc.norm().item())
print("Linear head bias norm:", b_fc.norm().item())

# Test 1: Can we overfit 16 diverse image-payload pairs with standard flat expansion?
torch.manual_seed(42)
B = 16
H = W = 64
images = torch.randn(B, 3, H, W).clamp(-1.0, 1.0)
messages = torch.randint(0, 2, (B, 32)).float()

model = HiddenModel(message_bits=32, channels=64, residual_scale=0.18)
model.decoder.fc.weight.data.copy_(w_fc)
model.decoder.fc.bias.data.copy_(b_fc)
model.decoder.fc.weight.requires_grad = False
model.decoder.fc.bias.requires_grad = False

opt = optim.Adam([p for p in model.parameters() if p.requires_grad], lr=2e-3)
crit = nn.BCEWithLogitsLoss()

print("\n--- Training on 16 samples with standard flat expansion ---")
for step in range(1, 201):
    opt.zero_grad()
    wm, logits = model(images, messages)
    loss = crit(logits, messages)
    loss.backward()
    opt.step()
    if step % 40 == 0 or step == 200:
        preds = (logits >= 0.0).float()
        ber = (preds != messages).float().mean().item()
        exact = (preds == messages).all(dim=1).float().mean().item()
        print(f"Step {step:3d} | BCE Loss: {loss.item():.4f} | BER: {ber*100:5.2f}% | Exact: {exact*100:5.1f}%")

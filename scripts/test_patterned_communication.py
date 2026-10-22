import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np

# Load frozen linear head from baseline
base_ckpt = torch.load("models/checkpoints/hidden_32bit.pt", map_location="cpu")
w_fc = base_ckpt["decoder"]["fc.weight"]
b_fc = base_ckpt["decoder"]["fc.bias"]

torch.manual_seed(42)
B = 16
H = W = 64
N_BITS = 32

# Generate 32 orthogonal 2D DCT spatial basis patterns (zero mean, unit norm)
patterns = []
y, x = torch.meshgrid(torch.linspace(0, np.pi, H), torch.linspace(0, np.pi, W), indexing="ij")
idx = 0
for u in range(1, 8):
    for v in range(1, 8):
        if idx >= N_BITS:
            break
        pat = torch.cos(u * y) * torch.cos(v * x)
        pat = pat - pat.mean()
        pat = pat / pat.norm()
        patterns.append(pat)
        idx += 1
patterns = torch.stack(patterns) # (32, H, W)
print("Generated 32 patterns, max mean:", patterns.mean(dim=(1, 2)).abs().max().item())

from backend.carriers.hidden.model import HiddenModel

class PatternedHiddenModel(HiddenModel):
    def __init__(self, message_bits=32, channels=64, residual_scale=0.18):
        super().__init__(message_bits=message_bits, channels=channels, residual_scale=residual_scale)
        self.register_buffer("patterns", patterns)

    def forward(self, image, message):
        B, _, H, W = image.shape
        # Modulate message bits (0, 1 -> -1, 1) onto spatial patterns
        bipolar = message * 2.0 - 1.0 # (B, 32)
        modulated = bipolar.unsqueeze(-1).unsqueeze(-1) * self.patterns.unsqueeze(0) # (B, 32, H, W)
        
        # Image features
        x = self.encoder.conv1(image)
        x = self.encoder.conv2(x)
        joint = torch.cat([x, modulated], dim=1)
        x = self.encoder.conv3(joint)
        x = self.encoder.conv4(x)
        delta = torch.tanh(self.encoder.residual_conv(x)) * self.encoder.residual_scale
        watermarked = torch.clamp(image + delta, -1.0, 1.0)
        
        logits = self.decoder(watermarked)
        return watermarked, logits

model = PatternedHiddenModel(residual_scale=0.18)
model.decoder.fc.weight.data.copy_(w_fc)
model.decoder.fc.bias.data.copy_(b_fc)
model.decoder.fc.weight.requires_grad = False
model.decoder.fc.bias.requires_grad = False

images = torch.randn(B, 3, H, W).clamp(-1.0, 1.0)
messages = torch.randint(0, 2, (B, 32)).float()

opt = optim.Adam([p for p in model.parameters() if p.requires_grad], lr=5e-3)
crit = nn.BCEWithLogitsLoss()

print("\n--- Training on 16 samples with orthogonal spatial pattern modulation ---")
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

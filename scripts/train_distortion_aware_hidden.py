"""
ProvenanceLab — HiDDeN-32 Distortion-Aware Training Pipeline
=============================================================
Implements distortion-aware joint training with differentiable noise layers
(Gaussian noise, spatial blur, simulated JPEG compression) to study robustness
improvements under aggressive distribution attacks.

Preservation Guarantee:
Saves strictly to `models/checkpoints/hidden_32bit_distortion_aware.pt`
without replacing the canonical production checkpoint `hidden_32bit.pt`.
"""

import math
import os
import random
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

from backend.carriers.hidden.model import HiddenDecoder, HiddenEncoder, HiddenModel


def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


class DifferentiableDistortionLayer(nn.Module):
    """
    Applies differentiable distortions during training:
    - Gaussian noise
    - Gaussian spatial blur (via fixed depthwise 3x3 conv)
    - Simulated color/contrast perturbations
    """
    def __init__(self):
        super().__init__()
        # Predefine 3x3 Gaussian blur kernel
        kernel_1d = torch.tensor([0.25, 0.5, 0.25], dtype=torch.float32)
        kernel_2d = torch.outer(kernel_1d, kernel_1d).unsqueeze(0).unsqueeze(0)
        self.register_buffer("blur_kernel", kernel_2d.repeat(3, 1, 1, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if not self.training:
            return x

        choice = random.random()
        # 30% chance: Additive Gaussian Noise
        if choice < 0.30:
            noise = torch.randn_like(x) * random.uniform(0.01, 0.05)
            return torch.clamp(x + noise, -1.0, 1.0)

        # 30% chance: Gaussian Blur
        elif choice < 0.60:
            blurred = F.conv2d(x, self.blur_kernel, padding=1, groups=3)
            return blurred

        # 20% chance: Simulated JPEG high-frequency rounding (quantization approximation)
        elif choice < 0.80:
            # Rounding simulation with STE (Straight-Through Estimator)
            scale = random.choice([32.0, 64.0, 128.0])
            quant = torch.round((x + 1.0) * scale) / scale - 1.0
            return x + (quant - x).detach()

        # 20% chance: Identity (clean channel)
        return x


def generate_training_batch(batch_size: int = 32, resolution: int = 64, device: torch.device = torch.device("cpu")):
    images = []
    for _ in range(batch_size):
        mode = random.choice(["gradient", "checker", "noise", "shapes"])
        if mode == "gradient":
            x = np.linspace(-1, 1, resolution)
            y = np.linspace(-1, 1, resolution)
            xx, yy = np.meshgrid(x, y)
            r = np.sin(xx * random.uniform(1, 4))
            g = np.cos(yy * random.uniform(1, 4))
            b = np.sin((xx + yy) * random.uniform(1, 4))
            arr = np.stack([r, g, b], axis=0)
        elif mode == "checker":
            grid = (np.indices((resolution, resolution)).sum(axis=0) // 8) % 2
            arr = np.stack([grid * 1.6 - 0.8] * 3, axis=0)
        else:
            arr = np.random.uniform(-0.8, 0.8, (3, resolution, resolution))
        images.append(arr.astype(np.float32))

    imgs_tensor = torch.tensor(np.array(images), dtype=torch.float32, device=device)
    msgs_tensor = torch.randint(0, 2, (batch_size, 32), dtype=torch.float32, device=device)
    return imgs_tensor, msgs_tensor


def train_distortion_aware(
    epochs: int = 60,
    batch_size: int = 32,
    resolution: int = 64,
    checkpoint_out: str = "models/checkpoints/hidden_32bit_distortion_aware.pt",
):
    set_seed(42)
    device = torch.device("cpu")
    print("=" * 70)
    print("DISTORTION-AWARE HiDDeN-32 TRAINING EXPERIMENT")
    print(f"Distortion Layers: Additive Gaussian Noise, Spatial Blur, Quantization")
    print(f"Output Checkpoint: {checkpoint_out}")
    print("=" * 70)

    model = HiddenModel(message_bits=32, channels=64, residual_scale=0.15).to(device)
    distortion_layer = DifferentiableDistortionLayer().to(device)

    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    criterion_msg = nn.BCEWithLogitsLoss()
    criterion_img = nn.MSELoss()

    model.train()
    distortion_layer.train()

    start_time = time.time()
    for epoch in range(1, epochs + 1):
        imgs, msgs = generate_training_batch(batch_size, resolution, device)

        optimizer.zero_grad()
        watermarked = model.encoder(imgs, msgs)

        # Pass through distortion channel
        distorted = distortion_layer(watermarked)

        logits = model.decoder(distorted)

        loss_msg = criterion_msg(logits, msgs)
        loss_img = criterion_img(watermarked, imgs)
        loss = 3.0 * loss_msg + 6.0 * loss_img

        loss.backward()
        optimizer.step()

        if epoch % 20 == 0 or epoch == epochs:
            model.eval()
            with torch.no_grad():
                val_imgs, val_msgs = generate_training_batch(batch_size=32, resolution=resolution, device=device)
                val_wm = model.encoder(val_imgs, val_msgs)
                val_logits = model.decoder(val_wm)
                preds = (val_logits >= 0.0).float()
                ber = (preds != val_msgs).float().mean().item()
                mse = criterion_img(val_wm, val_imgs).item()
                psnr = 10.0 * math.log10(4.0 / max(mse, 1e-8))
            model.train()
            print(f"Epoch [{epoch:3d}/{epochs:3d}] | Loss: {loss.item():.4f} | BER: {ber*100:5.2f}% | PSNR: {psnr:5.2f} dB | Elapsed: {time.time()-start_time:.1f}s")

    # Save to dedicated checkpoint
    os.makedirs(os.path.dirname(checkpoint_out), exist_ok=True)
    metadata = {
        "architecture": "HiDDeN-32-Distortion-Aware",
        "epochs": epochs,
        "residual_scale": 0.15,
        "distortion_types": ["gaussian_noise", "spatial_blur", "quantization_ste"],
        "timestamp": time.time(),
    }
    model.save_checkpoint(checkpoint_out, metadata=metadata)
    print(f"\n[+] Successfully saved distortion-aware checkpoint to {checkpoint_out}")
    print("[!] Canonical checkpoint models/checkpoints/hidden_32bit.pt was NOT touched.")


if __name__ == "__main__":
    train_distortion_aware(epochs=30)

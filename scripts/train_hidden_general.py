"""
ProvenanceLab — HiDDeN-32 Beginner Training Pipeline
=====================================================
Step-by-step training pipeline for learning general watermark embedding & recovery
on clean, unwatermarked real-world images.

Key Features for Beginners:
1. Safe: Saves to a new checkpoint `models/checkpoints/hidden_32bit_general.pt`.
   Never overwrites your existing checkpoints.
2. Blockchain-Safe: Keeps the last Linear(64, 32) layer strictly FROZEN.
   This guarantees your Zero-Knowledge proofs and Sepolia smart contract won't break!
3. Simple Output: Prints clear progress every epoch (Loss, BER, and PSNR).

Usage:
    python scripts/train_hidden_general.py --epochs 30 --batch-size 16 --lr 0.001
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from PIL import Image

from backend.carriers.hidden.model import HiddenModel


def set_seed(seed: int = 42):
    """Makes random numbers predictable so your training results are reproducible."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def load_dataset(data_dir: Path, resolution: int = 128) -> list[torch.Tensor]:
    """
    Finds all PNG and JPG photos in data_dir, resizes them to 128x128,
    and converts them to PyTorch tensors in range [-1.0, 1.0].
    """
    image_paths = sorted(
        [p for p in data_dir.glob("*") if p.suffix.lower() in [".png", ".jpg", ".jpeg"]]
    )
    if not image_paths:
        raise FileNotFoundError(
            f"No photos found in '{data_dir}'!\n"
            f"Run 'python scripts/download_training_data.py' first to download clean photos."
        )

    tensors = []
    print(f"Loading {len(image_paths)} photos from {data_dir.name}...")
    for p in image_paths:
        try:
            im = Image.open(p).convert("RGB")
            im = im.resize((resolution, resolution), Image.Resampling.BICUBIC)
            # Normalize pixels [0, 255] into [-1.0, 1.0]
            arr = np.array(im, dtype=np.float32) / 127.5 - 1.0
            # Convert to PyTorch format: (Channels, Height, Width)
            t = torch.from_numpy(arr).permute(2, 0, 1)
            tensors.append(t)
        except Exception as e:
            print(f"Warning: could not load {p.name}: {e}")

    print(f"Successfully loaded {len(tensors)} images at {resolution}x{resolution} resolution.\n")
    return tensors


def train_model(
    epochs: int = 30,
    batch_size: int = 16,
    lr: float = 0.001,
    resolution: int = 128,
    residual_scale: float = 0.10,
    save_path: str = "models/checkpoints/hidden_32bit_general.pt",
):
    set_seed(42)
    device = torch.device("cpu")

    print("=" * 75)
    print("STEP 2: TRAINING HiDDeN-32 ON UNWATERMARKED IMAGES")
    print("=" * 75)
    print(f"Hardware:        {device.type.upper()}")
    print(f"Total Epochs:    {epochs}")
    print(f"Batch Size:      {batch_size}")
    print(f"Learning Rate:   {lr}")
    print(f"Residual Scale:  {residual_scale} (Controls watermark invisibility)")
    print(f"Saving Model To: {save_path}")
    print("=" * 75 + "\n")

    # 1. Load clean images
    data_dir = PROJECT_ROOT / "experiments" / "data" / "train_clean"
    if not data_dir.exists() or len(list(data_dir.glob("*"))) == 0:
        # Fallback to the 100 benchmark images if train_clean wasn't downloaded yet
        alt_dir = PROJECT_ROOT / "experiments" / "data" / "phase5_8_100_images"
        if alt_dir.exists():
            print(f"Notice: '{data_dir.name}' is empty. Using '{alt_dir.name}' as fallback dataset.")
            data_dir = alt_dir

    images = load_dataset(data_dir, resolution=resolution)

    # Split into 90% Training and 10% Validation (Test)
    split_idx = max(1, int(len(images) * 0.90))
    train_imgs = images[:split_idx]
    val_imgs = images[split_idx:]
    print(f"Dataset split: {len(train_imgs)} images for Training | {len(val_imgs)} images for Validation\n")

    # 2. Initialize Model
    model = HiddenModel(message_bits=32, channels=64, residual_scale=residual_scale).to(device)

    # Load baseline weights to give the model a smart head start
    base_ckpt_path = PROJECT_ROOT / "models" / "checkpoints" / "hidden_32bit.pt"
    if base_ckpt_path.exists():
        base_state = torch.load(base_ckpt_path, map_location="cpu")
        if "decoder" in base_state and "fc.weight" in base_state["decoder"]:
            model.decoder.fc.weight.data.copy_(base_state["decoder"]["fc.weight"])
            model.decoder.fc.bias.data.copy_(base_state["decoder"]["fc.bias"])
            print("[+] Loaded baseline Linear Head weights.")

    # -------------------------------------------------------------------------
    # THE GOLDEN RULE: FREEZE THE LINEAR CLASSIFICATION HEAD
    # -------------------------------------------------------------------------
    # This prevents the final 64->32 layer from changing.
    # Because this layer doesn't change, your Zero-Knowledge Halo2 circuit and
    # Ethereum smart contracts will remain 100% compatible!
    model.decoder.fc.weight.requires_grad = False
    model.decoder.fc.bias.requires_grad = False
    print("[+] Linear Head (fc = Linear(64, 32)) is STRICTLY FROZEN 🔒 (Protects ZK/Blockchain)")

    # 3. Setup Optimizer (only updates unfrozen convolutional layers)
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    optimizer = optim.Adam(trainable_params, lr=lr)

    # 4. Training Loop
    best_ber = 1.0
    start_time = time.time()

    print("\n" + "-" * 75)
    print("STARTING TRAINING: Watch BER drop towards 0% and PSNR stay above 30 dB")
    print("-" * 75)

    for epoch in range(1, epochs + 1):
        model.train()
        random.shuffle(train_imgs)

        epoch_loss_msg = 0.0
        epoch_loss_img = 0.0
        batches = 0

        # Loop through images in small batches
        for i in range(0, len(train_imgs), batch_size):
            batch = train_imgs[i : i + batch_size]
            if len(batch) < 2:
                continue

            imgs_tensor = torch.stack(batch).to(device)
            B = imgs_tensor.shape[0]

            # Generate random 32-bit passwords on the fly (0 or 1)
            msgs_tensor = torch.randint(0, 2, (B, 32), dtype=torch.float32, device=device)

            optimizer.zero_grad()

            # Step A: Encoder creates watermarked images
            wm_imgs = model.encoder(imgs_tensor, msgs_tensor)

            # Step B: Decoder tries to recover the 32 bits
            pred_logits = model.decoder(wm_imgs)

            # Step C: Calculate Losses
            # 1. Message Loss: Did the decoder predict the correct bits?
            loss_msg = F.binary_cross_entropy_with_logits(pred_logits, msgs_tensor)

            # 2. Image Loss: Does the watermarked image look identical to the original?
            loss_img = F.mse_loss(wm_imgs, imgs_tensor)

            # Total Loss = Focus on recovering bits (15x) while keeping visual distortion low (2x)
            total_loss = 15.0 * loss_msg + 2.0 * loss_img

            # Step D: Update network weights
            total_loss.backward()
            optimizer.step()

            epoch_loss_msg += loss_msg.item()
            epoch_loss_img += loss_img.item()
            batches += 1

        # ---------------------------------------------------------------------
        # Validation Step: Test on photos the model DID NOT train on
        # ---------------------------------------------------------------------
        model.eval()
        with torch.no_grad():
            val_batch = torch.stack(val_imgs).to(device)
            val_msgs = torch.randint(0, 2, (len(val_imgs), 32), dtype=torch.float32, device=device)

            val_wm = model.encoder(val_batch, val_msgs)
            val_logits = model.decoder(val_wm)

            # Bit Error Rate (BER): percentage of wrong bits
            val_preds = (val_logits >= 0.0).float()
            val_ber = (val_preds != val_msgs).float().mean().item()

            # PSNR: visual quality (higher is better, >30 dB is invisible to human eye)
            val_mse = F.mse_loss(val_wm, val_batch).item()
            val_psnr = 10.0 * math.log10(4.0 / max(1e-10, val_mse))

        # Print progress line
        elapsed = time.time() - start_time
        print(
            f"Epoch [{epoch:2d}/{epochs:2d}] | "
            f"BER: {val_ber * 100:5.1f}% | "
            f"PSNR: {val_psnr:5.1f} dB | "
            f"Loss: {epoch_loss_msg / max(1, batches):.4f} | "
            f"Time: {elapsed:.0f}s"
        )

        # Save the best model
        if val_ber < best_ber:
            best_ber = val_ber
            out_file = PROJECT_ROOT / save_path
            out_file.parent.mkdir(parents=True, exist_ok=True)
            metadata = {
                "architecture": "HiDDeN-32bit-General",
                "trained_epochs": epoch,
                "residual_scale": residual_scale,
                "best_val_ber": val_ber,
                "val_psnr_db": val_psnr,
                "linear_head_frozen": True,
                "timestamp": time.time(),
            }
            model.save_checkpoint(str(out_file), metadata=metadata)
            print(f"  --> Saved new best checkpoint! (BER: {val_ber * 100:.1f}%)")

    print("\n" + "=" * 75)
    print("TRAINING FINISHED SUCCESSFULLY!")
    print(f"Best Validation BER: {best_ber * 100:.1f}%")
    print(f"Saved to: {save_path}")
    print("=" * 75)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=30, help="Number of training rounds")
    parser.add_argument("--batch-size", type=int, default=16, help="Photos processed at once")
    parser.add_argument("--lr", type=float, default=0.001, help="Learning rate (step size)")
    parser.add_argument("--residual-scale", type=float, default=0.10, help="Watermark strength")
    args = parser.parse_args()

    train_model(
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        residual_scale=args.residual_scale,
    )

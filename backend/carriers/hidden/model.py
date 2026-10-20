"""
ProvenanceLab — HiDDeN-Style 32-Bit Neural Watermark Model
===========================================================

Implementation of the HiDDeN architecture (Zhu et al., 2018) for 32-bit payloads:
- Encoder: Takes image (3, H, W) and 32-bit message, embeds via residual conv layers.
- Decoder: Takes watermarked image (3, H, W) and extracts 32-bit logits.

Can be exported cleanly to ONNX for EZKL / Halo2 zero-knowledge circuit compilation.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F


class ConvBNRelu(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.conv(x))


class HiddenEncoder(nn.Module):
    """
    HiDDeN Encoder: Spatially replicates 32-bit message, concatenates with image
    convolutions, and outputs watermarked image via residual addition.
    """
    def __init__(self, message_bits: int = 32, channels: int = 64, residual_scale: float = 0.12):
        super().__init__()
        self.message_bits = message_bits
        self.residual_scale = residual_scale

        # Image feature extractor
        self.conv1 = ConvBNRelu(3, channels)
        self.conv2 = ConvBNRelu(channels, channels)

        # Message expansion layer (concatenated with image features)
        self.conv3 = ConvBNRelu(channels + message_bits, channels)
        self.conv4 = ConvBNRelu(channels, channels)

        # Output residual delta
        self.residual_conv = nn.Conv2d(channels, 3, kernel_size=1)

    def forward(self, image: torch.Tensor, message: torch.Tensor) -> torch.Tensor:
        """
        image: (B, 3, H, W) in range [-1, 1]
        message: (B, 32) binary {0, 1}
        """
        B, _, H, W = image.shape

        # Replicate 32-bit message across H x W spatial dimensions
        expanded_msg = message.unsqueeze(-1).unsqueeze(-1).expand(B, self.message_bits, H, W)

        # Image features
        x = self.conv1(image)
        x = self.conv2(x)

        # Joint features
        joint = torch.cat([x, expanded_msg], dim=1)
        x = self.conv3(joint)
        x = self.conv4(x)

        # Residual perturbation scaled by configurable factor
        delta = torch.tanh(self.residual_conv(x)) * self.residual_scale
        watermarked = torch.clamp(image + delta, -1.0, 1.0)
        return watermarked


class HiddenDecoder(nn.Module):
    """
    HiDDeN Decoder: Convolutional feature extractor with adaptive spatial pooling
    producing 32 linear logits for payload extraction.
    Designed for ONNX and EZKL / Halo2 ZK circuit compilation.
    """
    def __init__(self, message_bits: int = 32, channels: int = 64):
        super().__init__()
        self.message_bits = message_bits

        self.conv1 = ConvBNRelu(3, channels)
        self.conv2 = ConvBNRelu(channels, channels)
        self.conv3 = ConvBNRelu(channels, channels)
        self.conv4 = ConvBNRelu(channels, channels)

        # Spatial average pooling
        self.pool = nn.AdaptiveAvgPool2d((1, 1))

        # Linear classifier for 32 bits
        self.fc = nn.Linear(channels, message_bits)

    def extract_features(self, image: torch.Tensor) -> torch.Tensor:
        """
        Extract 64-dimensional pooled latent feature vector from image tensor.
        image: (B, 3, H, W) in range [-1, 1]
        returns: (B, 64) latent embedding
        """
        x = self.conv1(image)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)
        pooled = self.pool(x).flatten(1)
        return pooled

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        """
        image: (B, 3, H, W) in range [-1, 1]
        returns: (B, 32) logits
        """
        pooled = self.extract_features(image)
        logits = self.fc(pooled)
        return logits

    def load_onnx_weights(self, onnx_path: str) -> None:
        """Load trained weights directly from the exported HiDDeN ONNX model."""
        import onnx
        import onnx.numpy_helper as nh
        m = onnx.load(str(onnx_path))
        inits = {i.name: torch.from_numpy(nh.to_array(i).copy()) for i in m.graph.initializer}
        for i, block in enumerate([self.conv1, self.conv2, self.conv3, self.conv4], start=1):
            w_key = f"conv{i}.conv.weight"
            b_key = f"conv{i}.conv.weight_bias"
            if w_key in inits:
                block.conv.weight.data = inits[w_key]
            if b_key in inits and block.conv.bias is not None:
                block.conv.bias.data = inits[b_key]
        if "fc.weight" in inits:
            self.fc.weight.data = inits["fc.weight"]
        if "fc.bias" in inits:
            self.fc.bias.data = inits["fc.bias"]


class HiddenModel(nn.Module):
    """
    Unified HiDDeN Neural Architecture combining Encoder and Decoder.
    Supports end-to-end joint training, evaluation, and checkpoint persistence.
    """
    def __init__(self, message_bits: int = 32, channels: int = 64, residual_scale: float = 0.12):
        super().__init__()
        self.encoder = HiddenEncoder(message_bits=message_bits, channels=channels, residual_scale=residual_scale)
        self.decoder = HiddenDecoder(message_bits=message_bits, channels=channels)

    def forward(self, image: torch.Tensor, message: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Runs joint forward pass:
        image: (B, 3, H, W) normalized to [-1, 1]
        message: (B, 32) binary tensor {0, 1}
        returns: (watermarked_image, recovered_logits)
        """
        watermarked = self.encoder(image, message)
        logits = self.decoder(watermarked)
        return watermarked, logits

    def save_checkpoint(self, checkpoint_path: str, metadata: Optional[dict] = None) -> None:
        """Save full model weights and training metadata."""
        import os
        os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
        state = {
            "encoder": self.encoder.state_dict(),
            "decoder": self.decoder.state_dict(),
            "metadata": metadata or {},
        }
        torch.save(state, checkpoint_path)

    def load_checkpoint(self, checkpoint_path: str) -> dict:
        """Load full model weights from checkpoint."""
        state = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        self.encoder.load_state_dict(state["encoder"])
        self.decoder.load_state_dict(state["decoder"])
        return state.get("metadata", {})

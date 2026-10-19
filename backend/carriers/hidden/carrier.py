"""
ProvenanceLab — HiDDeN 32-Bit Carrier Adapter
=============================================

Implements BaseCarrier for the HiDDeN-style 32-bit neural watermarking model:
- 32-bit payload length (8 hex digits).
- High imperceptibility (PSNR > 35 dB).
- Clean ONNX export interface for EZKL / Halo2 zero-knowledge circuit compilation.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import numpy as np
import torch
import torchvision.transforms as T
from PIL import Image

from backend.carriers.base import BaseCarrier, CarrierInfo, DecodeResult, EncodeResult
from backend.carriers.hidden.model import HiddenDecoder, HiddenEncoder

logger = logging.getLogger(__name__)


class HiddenCarrier(BaseCarrier):
    """HiDDeN 32-bit watermark carrier."""

    _VERSION = "1.0.0-hidden32"
    _PAYLOAD_BITS = 32

    def __init__(self, resolution: int = 128, weights_path: Optional[str] = None):
        self.resolution = resolution
        self.encoder = HiddenEncoder(message_bits=self._PAYLOAD_BITS)
        self.decoder = HiddenDecoder(message_bits=self._PAYLOAD_BITS)

        self.encoder.eval()
        self.decoder.eval()

        self._load_or_init_weights(weights_path)

        self.transform = T.Compose([
            T.Resize((resolution, resolution)),
            T.ToTensor(),
            T.Normalize(mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]),
        ])

    def _load_or_init_weights(self, weights_path: Optional[str] = None):
        """Initialize or load trained weights."""
        if weights_path and os.path.exists(weights_path):
            ckpt = torch.load(weights_path, map_location="cpu")
            self.encoder.load_state_dict(ckpt["encoder"])
            self.decoder.load_state_dict(ckpt["decoder"])
            logger.info("Loaded HiDDeN weights from %s", weights_path)
        else:
            # Deterministic initialization
            torch.manual_seed(2026)
            for m in list(self.encoder.modules()) + list(self.decoder.modules()):
                if isinstance(m, torch.nn.Conv2d):
                    torch.nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                elif isinstance(m, torch.nn.BatchNorm2d):
                    torch.nn.init.constant_(m.weight, 1.0)
                    torch.nn.init.constant_(m.bias, 0.0)

    @property
    def info(self) -> CarrierInfo:
        return CarrierInfo(
            name="HiDDeN-32",
            payload_bits=self._PAYLOAD_BITS,
            version=self._VERSION,
            license="MIT",
            description="HiDDeN-style Conv2D residual neural watermarking with 32-bit payload.",
        )

    def encode(self, image: Image.Image, payload_hex: str) -> EncodeResult:
        """Embed 32-bit payload into image."""
        t0 = time.perf_counter()

        expected_hex_len = (self._PAYLOAD_BITS + 3) // 4  # 8 hex chars
        if len(payload_hex) != expected_hex_len:
            return EncodeResult(
                watermarked_image=image,
                payload_bits=self._PAYLOAD_BITS,
                payload_hex=payload_hex,
                carrier_name=self.info.name,
                carrier_version=self._VERSION,
                psnr_db=None,
                elapsed_seconds=0.0,
                error=f"payload_hex length {len(payload_hex)} != expected {expected_hex_len}",
            )

        # Convert hex to 32-bit float tensor
        bits = self.payload_to_bits(payload_hex)
        msg_tensor = torch.tensor(bits, dtype=torch.float32).unsqueeze(0)

        # Preprocess image
        orig_size = image.size
        img_tensor = self.transform(image).unsqueeze(0)

        with torch.no_grad():
            wm_tensor = self.encoder(img_tensor, msg_tensor)

        # De-normalize back to PIL Image [0, 255]
        wm_unnorm = (wm_tensor.squeeze(0).clamp(-1.0, 1.0) * 0.5 + 0.5).permute(1, 2, 0).numpy()
        wm_uint8 = (wm_unnorm * 255.0).astype(np.uint8)
        wm_pil = Image.fromarray(wm_uint8).resize(orig_size, Image.Resampling.BICUBIC)

        elapsed = time.perf_counter() - t0

        # Compute PSNR
        from backend.carriers.trustmark.carrier import _compute_psnr
        psnr = _compute_psnr(image, wm_pil)

        return EncodeResult(
            watermarked_image=wm_pil,
            payload_bits=self._PAYLOAD_BITS,
            payload_hex=payload_hex,
            carrier_name=self.info.name,
            carrier_version=self._VERSION,
            psnr_db=psnr,
            elapsed_seconds=elapsed,
        )

    def decode(
        self,
        image: Image.Image,
        reference_payload_hex: Optional[str] = None,
    ) -> DecodeResult:
        """Decode 32-bit payload from suspect image."""
        t0 = time.perf_counter()
        img_tensor = self.transform(image).unsqueeze(0)

        with torch.no_grad():
            logits = self.decoder(img_tensor).squeeze(0)
            pred_bits = (logits > 0.0).long().tolist()

        decoded_hex = self.bits_to_payload(pred_bits)
        elapsed = time.perf_counter() - t0

        hamming = None
        ber = None
        if reference_payload_hex is not None:
            hamming = self.hamming_distance(reference_payload_hex, decoded_hex, self._PAYLOAD_BITS)
            ber = hamming / self._PAYLOAD_BITS

        return DecodeResult(
            payload_hex=decoded_hex,
            payload_bits=self._PAYLOAD_BITS,
            hamming_distance=hamming,
            bit_error_rate=ber,
            confidence=1.0 - (ber if ber is not None else 0.0),
            carrier_name=self.info.name,
            carrier_version=self._VERSION,
            elapsed_seconds=elapsed,
        )

    def export_onnx(self, output_path: str = "models/onnx/hidden_decoder_32bit.onnx") -> str:
        """Export the decoder to ONNX format for EZKL zero-knowledge proving."""
        import sys
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8")
            except Exception:
                pass

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        dummy_input = torch.randn(1, 3, self.resolution, self.resolution)
        try:
            # Try PyTorch 2.x dynamo export with opset 18
            torch.onnx.export(
                self.decoder,
                dummy_input,
                output_path,
                export_params=True,
                opset_version=18,
                do_constant_folding=True,
                input_names=["image_tensor"],
                output_names=["payload_logits"],
                dynamic_axes={"image_tensor": {0: "batch"}, "payload_logits": {0: "batch"}},
                verbose=False,
            )
        except Exception:
            # Fallback to standard TorchScript-based export
            torch.onnx.export(
                self.decoder,
                dummy_input,
                output_path,
                export_params=True,
                opset_version=14,
                do_constant_folding=True,
                input_names=["image_tensor"],
                output_names=["payload_logits"],
                verbose=False,
                dynamo=False,
            )
        logger.info("Exported HiDDeN-32 decoder ONNX to %s", output_path)
        return output_path

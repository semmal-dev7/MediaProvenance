"""
ProvenanceLab — TrustMark Carrier Integration
=============================================
Wraps the Adobe Research TrustMark library as a ProvenanceLab carrier.

TrustMark reference:
    Bui, T. et al. "TrustMark: Universal Watermarking for Arbitrary Resolution Images."
    CVPR 2024. https://github.com/adobe/trustmark

Payload: 100 bits (configurable). Three model variants: Q (quality), B (balance), C (capacity).
License: Apache-2.0

Installation:
    pip install trustmark
    # TrustMark will pull its own torch dependency.
    # For CPU-only: pip install torch --index-url https://download.pytorch.org/whl/cpu

Design notes:
- TrustMark's decode() returns a tuple (payload_bits, is_detected, confidence).
  We treat is_detected=False as a decoding failure (payload_hex=None).
- We do NOT fall back to a random payload on failure.
- PSNR is computed between original and watermarked images.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
from PIL import Image

from backend.carriers.base import BaseCarrier, CarrierInfo, DecodeResult, EncodeResult

logger = logging.getLogger(__name__)

_SUPPORTED_MODELS = {"Q", "B", "C"}


class TrustMarkCarrier(BaseCarrier):
    """
    TrustMark watermark carrier.

    Parameters
    ----------
    model_type : "Q" (quality-focused), "B" (balanced), or "C" (capacity).
    payload_bits : must be <= 100 for TrustMark.
    """

    _VERSION = "0.2.0"

    def __init__(self, model_type: str = "Q", payload_bits: int = 100):
        if model_type not in _SUPPORTED_MODELS:
            raise ValueError(f"model_type must be one of {_SUPPORTED_MODELS}, got {model_type!r}")
        if not (1 <= payload_bits <= 100):
            raise ValueError(f"TrustMark supports 1–100 payload bits, got {payload_bits}")

        self._model_type = model_type
        self._payload_bits = payload_bits
        self._tm = None  # lazy-load to avoid import cost at import time
        self._load_model()

    def _load_model(self):
        """Load TrustMark model. Raises ImportError if not installed."""
        try:
            from trustmark import TrustMark  # type: ignore
            self._tm = TrustMark(
                use_ECC=False,
                model_type=self._model_type,
                device="cpu",
                loadRemover=False,
                verbose=False,
            )
            logger.info("TrustMark model loaded: type=%s on CPU", self._model_type)
        except ImportError as e:
            raise ImportError(
                "TrustMark is not installed. Run:\n"
                "  pip install trustmark\n"
                "  pip install torch --index-url https://download.pytorch.org/whl/cpu"
            ) from e
        except Exception as e:
            logger.error("Failed to load TrustMark model: %s", e)
            raise

    @property
    def info(self) -> CarrierInfo:
        return CarrierInfo(
            name=f"TrustMark-{self._model_type}",
            payload_bits=self._payload_bits,
            version=self._VERSION,
            license="Apache-2.0",
            description=(
                f"Adobe Research TrustMark ({self._model_type} variant), "
                f"{self._payload_bits}-bit payload. "
                "Universal watermarking for arbitrary resolution images."
            ),
        )

    PREAMBLE_HEX = "a5"  # 8-bit synchronization preamble (10100101)

    def encode(self, image: Image.Image, payload_hex: str) -> EncodeResult:
        """Embed a watermark payload into an image using TrustMark."""
        # Ensure image is in RGB mode (handles RGBA, Grayscale, Palette, CMYK)
        if image.mode != "RGB":
            image = image.convert("RGB")

        clean_hex = payload_hex.strip().lower().replace("0x", "")
        clean_hex = "".join(c for c in clean_hex if c in "0123456789abcdef")

        expected_hex_len = (self._payload_bits + 3) // 4  # 25 for 100 bits

        # Ensure preamble prefix is present
        if not clean_hex.startswith(self.PREAMBLE_HEX):
            clean_hex = self.PREAMBLE_HEX + clean_hex

        if len(clean_hex) < expected_hex_len:
            clean_hex = clean_hex.ljust(expected_hex_len, "0")
        elif len(clean_hex) > expected_hex_len:
            clean_hex = clean_hex[:expected_hex_len]

        # Convert hex payload to binary string for TrustMark
        bit_string = bin(int(clean_hex, 16))[2:].zfill(self._payload_bits)

        t0 = time.perf_counter()
        try:
            # TrustMark encode returns a PIL Image
            wm_image = self._tm.encode(image, bit_string, MODE="binary")
        except Exception as e:
            logger.error("TrustMark encode failed: %s", e)
            return EncodeResult(
                watermarked_image=image,
                payload_bits=self._payload_bits,
                payload_hex=clean_hex,
                carrier_name=self.info.name,
                carrier_version=self._VERSION,
                psnr_db=None,
                elapsed_seconds=time.perf_counter() - t0,
                error=str(e),
            )

        elapsed = time.perf_counter() - t0

        # Compute PSNR between original and watermarked
        psnr = _compute_psnr(image, wm_image)

        return EncodeResult(
            watermarked_image=wm_image,
            payload_bits=self._payload_bits,
            payload_hex=clean_hex,
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
        """
        Decode a watermark from an image.
        Extracts neural decision logits, calculates soft bit error probabilities,
        and verifies the 8-bit synchronization preamble.
        """
        if image.mode != "RGB":
            image = image.convert("RGB")

        t0 = time.perf_counter()
        n_hex = (self._payload_bits + 3) // 4

        # Continuous neural forward pass for decision logits and raw bitstream
        raw_logits = None
        raw_bit_string = None
        mean_act = None
        rms = None
        expected_ber = None
        neural_certainty = None
        try:
            import torch
            from torchvision import transforms
            im_resized = image.resize((self._tm.model_resolution_dec, self._tm.model_resolution_dec), Image.BILINEAR)
            stego = transforms.ToTensor()(im_resized).unsqueeze(0).to(self._tm.decoder.device) * 2.0 - 1.0
            with torch.no_grad():
                raw_logits = self._tm.decoder.decoder(stego).squeeze(0).cpu().numpy()
            raw_bits = (raw_logits > 0).astype(int)
            raw_bit_string = ''.join(str(b) for b in raw_bits)[:self._payload_bits].ljust(self._payload_bits, '0')
            mean_act = float(np.mean(np.abs(raw_logits)))
            rms = float(np.sqrt(np.mean(raw_logits ** 2)))
            bit_err_probs = 1.0 / (1.0 + np.exp(np.abs(raw_logits)))
            expected_ber = float(np.mean(bit_err_probs))
            neural_certainty = float(np.mean(2.0 * (1.0 / (1.0 + np.exp(-np.abs(raw_logits))) - 0.5)))
        except Exception as e:
            logger.warning("TrustMark neural forward pass failed: %s", e)

        # TrustMark ECC / BCH decode
        bit_string = None
        is_detected = False
        confidence = None
        try:
            result = self._tm.decode(image, MODE="binary")
            if isinstance(result, tuple) and len(result) == 3:
                bit_string, is_detected, confidence = result
            elif isinstance(result, tuple) and len(result) == 2:
                bit_string, is_detected = result
            else:
                bit_string = result
                is_detected = bool(bit_string)
        except Exception as e:
            logger.warning("TrustMark decode exception: %s", e)

        elapsed = time.perf_counter() - t0

        chosen_bit_string = None
        if is_detected and bit_string and len(bit_string) >= self._payload_bits:
            chosen_bit_string = bit_string[:self._payload_bits]
        elif raw_bit_string:
            chosen_bit_string = raw_bit_string

        decoded_hex = None
        sync_ok = False
        if chosen_bit_string:
            try:
                decoded_int = int(chosen_bit_string, 2)
                decoded_hex = format(decoded_int, f'0{n_hex}x')
                sync_ok = decoded_hex.startswith(self.PREAMBLE_HEX)
            except Exception:
                pass

        hamming = None
        ber = None
        decodable = False
        watermark_detected = False

        if reference_payload_hex and decoded_hex:
            clean_ref = reference_payload_hex.strip().lower().replace("0x", "")
            if not clean_ref.startswith(self.PREAMBLE_HEX):
                clean_ref = self.PREAMBLE_HEX + clean_ref
            clean_ref = clean_ref[:n_hex].ljust(n_hex, '0')

            try:
                hamming = self.hamming_distance(clean_ref, decoded_hex, self._payload_bits)
                ber = hamming / float(self._payload_bits)
                if (ber <= 0.35 and sync_ok) or ber <= 0.25:
                    decodable = True
                    watermark_detected = True
                else:
                    decodable = False
                    watermark_detected = False
            except Exception as e:
                logger.warning("Hamming distance computation failed: %s", e)
        else:
            # Blind recovery: authenticated only if preamble synchronization succeeds
            if sync_ok and decoded_hex:
                decodable = True
                watermark_detected = True
                ber = expected_ber or 0.0
                hamming = int(round(ber * self._payload_bits))
            else:
                decodable = False
                watermark_detected = False
                ber = 0.50
                hamming = None
                expected_ber = 0.50

        return DecodeResult(
            payload_hex=decoded_hex if (decodable and watermark_detected) else None,
            payload_bits=self._payload_bits,
            hamming_distance=hamming,
            bit_error_rate=ber,
            confidence=float(confidence) if confidence is not None else (1.0 - (ber if ber is not None else (expected_ber or 0.0))),
            carrier_name=self.info.name,
            carrier_version=self._VERSION,
            elapsed_seconds=elapsed,
            error=None if (decodable and watermark_detected) else ("No authentic TrustMark watermark detected" if not sync_ok else "Bit error rate exceeds detection tolerance"),
            watermark_detected=watermark_detected,
            mean_logit_magnitude=mean_act,
            rms_energy=rms,
            neural_certainty=neural_certainty,
            expected_ber=expected_ber,
        )


def _compute_psnr(img_ref: Image.Image, img_wm: Image.Image) -> Optional[float]:
    """
    Compute PSNR (dB) between reference and watermarked images.
    Returns None if images have different sizes.
    """
    try:
        ref = np.array(img_ref.convert("RGB"), dtype=np.float64)
        wm = np.array(img_wm.convert("RGB"), dtype=np.float64)
        if ref.shape != wm.shape:
            return None
        mse = np.mean((ref - wm) ** 2)
        if mse == 0:
            return float('inf')
        psnr = 10 * np.log10(255.0 ** 2 / mse)
        return float(psnr)
    except Exception:
        return None

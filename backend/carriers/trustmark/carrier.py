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
        Detects 8-bit synchronization preamble to reject unwatermarked / clean media.
        """
        # Ensure image is in RGB mode
        if image.mode != "RGB":
            image = image.convert("RGB")

        t0 = time.perf_counter()
        try:
            # TrustMark decode returns (bit_string, is_detected, confidence)
            result = self._tm.decode(image, MODE="binary")
            if isinstance(result, tuple) and len(result) == 3:
                bit_string, is_detected, confidence = result
            elif isinstance(result, tuple) and len(result) == 2:
                bit_string, is_detected = result
                confidence = None
            else:
                bit_string = result
                is_detected = bool(bit_string)
                confidence = None
        except Exception as e:
            logger.warning("TrustMark decode exception: %s", e)
            return DecodeResult(
                payload_hex=None,
                payload_bits=self._payload_bits,
                hamming_distance=None,
                bit_error_rate=None,
                confidence=None,
                carrier_name=self.info.name,
                carrier_version=self._VERSION,
                elapsed_seconds=time.perf_counter() - t0,
                error=str(e),
            )

        elapsed = time.perf_counter() - t0

        if not is_detected or not bit_string:
            return DecodeResult(
                payload_hex=None,
                payload_bits=self._payload_bits,
                hamming_distance=None,
                bit_error_rate=None,
                confidence=float(confidence) if confidence is not None else None,
                carrier_name=self.info.name,
                carrier_version=self._VERSION,
                elapsed_seconds=elapsed,
                error="No watermark detected in candidate image",
            )

        # Truncate or pad bit_string to payload_bits
        bit_string = bit_string[:self._payload_bits].ljust(self._payload_bits, '0')

        # Convert to hex
        try:
            decoded_int = int(bit_string, 2)
            n_hex = (self._payload_bits + 3) // 4
            decoded_hex = format(decoded_int, f'0{n_hex}x')
        except ValueError as e:
            return DecodeResult(
                payload_hex=None,
                payload_bits=self._payload_bits,
                hamming_distance=None,
                bit_error_rate=None,
                confidence=None,
                carrier_name=self.info.name,
                carrier_version=self._VERSION,
                elapsed_seconds=elapsed,
                error=f"Bit string conversion failed: {e}",
            )

        # Preamble synchronization check
        sync_ok = decoded_hex.startswith(self.PREAMBLE_HEX)

        # Compute Hamming distance if reference is provided
        hamming = None
        ber = None
        decodable = False

        if reference_payload_hex:
            clean_ref = reference_payload_hex.strip().lower().replace("0x", "")
            if not clean_ref.startswith(self.PREAMBLE_HEX):
                clean_ref = self.PREAMBLE_HEX + clean_ref
            clean_ref = clean_ref[:n_hex].ljust(n_hex, '0')

            try:
                hamming = self.hamming_distance(clean_ref, decoded_hex, self._payload_bits)
                ber = hamming / self._payload_bits
                if ber <= 0.35 and sync_ok:
                    decodable = True
                elif ber <= 0.25:
                    decodable = True
            except Exception as e:
                logger.warning("Hamming distance computation failed: %s", e)
        else:
            # Blind decoding requires valid synchronization preamble
            if sync_ok:
                decodable = True
                ber = None
                hamming = None

        return DecodeResult(
            payload_hex=decoded_hex if decodable else None,
            payload_bits=self._payload_bits,
            hamming_distance=hamming,
            bit_error_rate=ber,
            confidence=float(confidence) if confidence is not None else (1.0 - (ber if ber is not None else 0.0)),
            carrier_name=self.info.name,
            carrier_version=self._VERSION,
            elapsed_seconds=elapsed,
            error=None if decodable else "No authentic TrustMark watermark detected (preamble sync failed)",
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

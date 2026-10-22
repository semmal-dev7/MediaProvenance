"""
ProvenanceLab — Abstract Watermark Carrier Interface
=====================================================
All watermark carriers must implement this interface so that the experiment
pipeline, benchmark, and API can treat them uniformly.

Design principles:
- encode() and decode() operate on PIL Images, not file paths.
- Carriers are responsible for their own model loading and caching.
- Carriers must report their payload_bits and a descriptive name.
- decode() returns None when the decoder cannot produce a valid payload
  (e.g. no watermark detected, confidence too low). Callers must handle None.
- Carriers must NOT silently substitute random payloads for failed decodes.
"""

from __future__ import annotations

import abc
import hashlib
import time
from dataclasses import dataclass, field
from typing import Optional

from PIL import Image


@dataclass
class CarrierInfo:
    """Metadata describing a watermark carrier."""
    name: str
    payload_bits: int
    version: str
    license: str
    description: str


@dataclass
class EncodeResult:
    """Result of a watermark encoding operation."""
    watermarked_image: Image.Image
    payload_bits: int          # number of bits in the payload
    payload_hex: str           # hex encoding of the payload bytes
    carrier_name: str
    carrier_version: str
    psnr_db: Optional[float]   # None if not computed
    elapsed_seconds: float
    error: Optional[str] = None  # non-None means encoding failed


@dataclass
class DecodeResult:
    """
    Result of a watermark decoding operation.

    If decoding fails or the decoder judges no watermark is present,
    payload_hex is None and error describes the reason.
    Callers MUST check for None payload_hex before using the value.
    """
    payload_hex: Optional[str]   # None = decoding failed / no watermark
    payload_bits: int            # expected bit length of the payload
    hamming_distance: Optional[int]   # vs reference payload, if provided
    bit_error_rate: Optional[float]   # hamming_distance / payload_bits
    confidence: Optional[float]       # carrier-specific confidence score [0,1]
    carrier_name: str
    carrier_version: str
    elapsed_seconds: float
    error: Optional[str] = None
    watermark_detected: bool = True
    mean_logit_magnitude: Optional[float] = None
    rms_energy: Optional[float] = None
    neural_certainty: Optional[float] = None
    expected_ber: Optional[float] = None

    @property
    def decodable(self) -> bool:
        """True iff the decoder produced a valid payload and detected watermark signal."""
        return self.payload_hex is not None and self.watermark_detected


class BaseCarrier(abc.ABC):
    """Abstract base class for all watermark carriers."""

    @property
    @abc.abstractmethod
    def info(self) -> CarrierInfo:
        """Return static metadata about this carrier."""
        ...

    @abc.abstractmethod
    def encode(self, image: Image.Image, payload_hex: str) -> EncodeResult:
        """
        Embed a watermark payload into an image.

        Parameters
        ----------
        image       : input PIL Image (RGB).
        payload_hex : hex string representing the payload bits.
                      Must have length == ceil(info.payload_bits / 4).

        Returns
        -------
        EncodeResult with watermarked_image and metadata.
        If encoding fails, returns EncodeResult with error set.
        """
        ...

    @abc.abstractmethod
    def decode(
        self,
        image: Image.Image,
        reference_payload_hex: Optional[str] = None,
    ) -> DecodeResult:
        """
        Attempt to decode a watermark from an image.

        Parameters
        ----------
        image                  : suspect PIL Image (RGB).
        reference_payload_hex  : if provided, compute Hamming distance vs this.

        Returns
        -------
        DecodeResult. payload_hex is None if decoding failed.
        """
        ...

    # ── Shared utilities ─────────────────────────────────────────────────────

    def payload_to_bits(self, payload_hex: str) -> list[int]:
        """Convert hex payload to list of bits (MSB first)."""
        n_bytes = (self.info.payload_bits + 7) // 8
        value = int(payload_hex, 16)
        bits = [(value >> (self.info.payload_bits - 1 - i)) & 1
                for i in range(self.info.payload_bits)]
        return bits

    def bits_to_payload(self, bits: list[int]) -> str:
        """Convert list of bits (MSB first) to hex payload."""
        value = 0
        for b in bits:
            value = (value << 1) | b
        n_hex = (self.info.payload_bits + 3) // 4
        return format(value, f'0{n_hex}x')

    @staticmethod
    def hamming_distance(a_hex: str, b_hex: str, n_bits: int) -> int:
        """Compute bit-level Hamming distance between two hex payloads."""
        a = int(a_hex, 16)
        b = int(b_hex, 16)
        xor = a ^ b
        distance = bin(xor).count('1')
        return distance

    @staticmethod
    def image_sha256(image: Image.Image) -> str:
        """Compute SHA-256 of raw image bytes for record-keeping."""
        raw = image.tobytes()
        return hashlib.sha256(raw).hexdigest()

    def _timed(self, fn, *args, **kwargs):
        """Run fn(*args, **kwargs) and return (result, elapsed_seconds)."""
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        return result, time.perf_counter() - t0

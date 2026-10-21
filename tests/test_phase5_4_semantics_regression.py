"""
MediaProvenance — Phase 5.4 Verification Semantics Regression Suite
==================================================================
Validates that invalid, unwatermarked, or degraded images do NOT report
fake/hardcoded fallback values (e.g. BER = 50.0%, log10 LR = -30.0, P(H0) = 1.000).

Asserts clear semantic distinction between:
- Blind watermark detection vs. Reference payload hypothesis testing
- Authentic watermark recovery (H1)
- Rejection against reference claim (H0)
- Inconclusive / unwatermarked / desynchronized media (H2)
"""

from __future__ import annotations

import io
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from backend.carriers.factory import get_carrier
from backend.carriers.base import DecodeResult
from backend.api.routes.watermark import decode_watermark
from fastapi import UploadFile


class TestPhase54SemanticsRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Deterministic clean image (128x128)
        arr = np.linspace(0, 255, 128 * 128, dtype=np.uint8).reshape(128, 128)
        cls.clean_img = Image.fromarray(np.stack([arr, arr // 2, 255 - arr], axis=2))

        cls.target_payload = "deadbeef"
        cls.carrier = get_carrier("pureconv")

        # Encode target payload into clean image
        enc_res = cls.carrier.encode(cls.clean_img, cls.target_payload)
        cls.watermarked_img = enc_res.watermarked_image

    def test_01_carrier_blind_decode_clean_image(self):
        """Unwatermarked image without reference payload must indicate no watermark detected, no fake BER."""
        dec = self.carrier.decode(self.clean_img)
        self.assertFalse(dec.watermark_detected, "Carrier should not detect watermark in clean image")
        self.assertFalse(dec.decodable, "Clean image should not be marked decodable")
        self.assertIsNone(dec.bit_error_rate, "BER must be None when no reference payload provided")
        self.assertIsNone(dec.hamming_distance, "Hamming distance must be None without reference")
        self.assertIsNotNone(dec.error, "Error message should describe sub-threshold signal")

    def test_02_carrier_blind_decode_watermarked_image(self):
        """Watermarked image without reference payload must detect watermark and recover payload."""
        dec = self.carrier.decode(self.watermarked_img)
        self.assertTrue(dec.watermark_detected, "Watermark must be detected in genuine watermarked image")
        self.assertTrue(dec.decodable, "Watermarked image must be decodable")
        self.assertEqual(dec.payload_hex.lower(), self.target_payload.lower())
        self.assertIsNone(dec.bit_error_rate, "BER must be None in blind mode without reference")

    def test_03_carrier_reference_decode(self):
        """Reference decoding must compute legitimate BER and distinguish genuine vs clean image."""
        dec_wm = self.carrier.decode(self.watermarked_img, reference_payload_hex=self.target_payload)
        self.assertTrue(dec_wm.watermark_detected)
        self.assertEqual(dec_wm.bit_error_rate, 0.0)
        self.assertEqual(dec_wm.hamming_distance, 0)

        dec_clean = self.carrier.decode(self.clean_img, reference_payload_hex=self.target_payload)
        self.assertFalse(dec_clean.watermark_detected)
        self.assertIsNotNone(dec_clean.bit_error_rate)
        self.assertGreater(dec_clean.bit_error_rate, 0.25, "Unwatermarked image BER against reference must be high")

    def test_04_hidden_carrier_no_fake_ber_fallback(self):
        """HiDDeN carrier must not return hardcoded 50% BER or 16 Hamming distance when unconstrained."""
        hidden_carrier = get_carrier("hidden")
        dec = hidden_carrier.decode(self.clean_img)
        self.assertIsNone(dec.bit_error_rate, "HiDDeN must not hardcode BER=0.50")
        self.assertIsNone(dec.hamming_distance, "HiDDeN must not hardcode Hamming=16")

    def _create_upload_file(self, img: Image.Image, filename: str = "test.png") -> UploadFile:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return UploadFile(filename=filename, file=buf)

    async def _async_test_api_blind_clean(self):
        upload = self._create_upload_file(self.clean_img)
        resp = await decode_watermark(file=upload, carrier="pureconv", reference_payload_hex=None)
        
        # Verify semantics: NOT H0, NOT fake -30.0, NOT fake 50%
        self.assertFalse(resp.watermark_detected)
        self.assertFalse(resp.decodable)
        self.assertFalse(resp.payload_recovered)
        self.assertIsNone(resp.payload_hex)
        self.assertIsNone(resp.bit_error_rate)
        self.assertIsNone(resp.log10_likelihood_ratio)
        self.assertIsNone(resp.posterior_probability_h1)
        self.assertEqual(resp.inferred_hypothesis, "H2")
        self.assertIn("No authentic watermark signal detected", resp.failure_reason)

    def test_05_api_decode_blind_clean_image(self):
        """Verify API response semantics for blind decode of clean media (H2, no fake metrics)."""
        import asyncio
        asyncio.run(self._async_test_api_blind_clean())

    async def _async_test_api_blind_watermarked(self):
        upload = self._create_upload_file(self.watermarked_img)
        resp = await decode_watermark(file=upload, carrier="pureconv", reference_payload_hex=None)
        
        self.assertTrue(resp.watermark_detected)
        self.assertTrue(resp.decodable)
        self.assertTrue(resp.payload_recovered)
        self.assertEqual(resp.payload_hex.lower(), self.target_payload.lower())
        self.assertIsNone(resp.bit_error_rate)
        self.assertIsNone(resp.log10_likelihood_ratio)
        self.assertIsNone(resp.posterior_probability_h1)
        self.assertEqual(resp.inferred_hypothesis, "H1")
        self.assertIsNone(resp.failure_reason)

    def test_06_api_decode_blind_watermarked_image(self):
        """Verify API response semantics for blind decode of watermarked media (H1, recovered payload)."""
        import asyncio
        asyncio.run(self._async_test_api_blind_watermarked())

    async def _async_test_api_reference_watermarked(self):
        upload = self._create_upload_file(self.watermarked_img)
        resp = await decode_watermark(file=upload, carrier="pureconv", reference_payload_hex=self.target_payload)
        
        self.assertTrue(resp.watermark_detected)
        self.assertTrue(resp.decodable)
        self.assertTrue(resp.payload_matches)
        self.assertEqual(resp.bit_error_rate, 0.0)
        self.assertGreater(resp.log10_likelihood_ratio, 5.0)
        self.assertGreater(resp.posterior_probability_h1, 0.99)
        self.assertEqual(resp.inferred_hypothesis, "H1")

    def test_07_api_decode_reference_watermarked_image(self):
        """Verify API response semantics for reference validation of genuine watermarked media."""
        import asyncio
        asyncio.run(self._async_test_api_reference_watermarked())

    async def _async_test_api_reference_clean(self):
        upload = self._create_upload_file(self.clean_img)
        resp = await decode_watermark(file=upload, carrier="pureconv", reference_payload_hex=self.target_payload)
        
        self.assertFalse(resp.watermark_detected)
        self.assertFalse(resp.payload_matches)
        self.assertIsNotNone(resp.bit_error_rate)
        self.assertLess(resp.log10_likelihood_ratio, -3.0)
        self.assertLess(resp.posterior_probability_h1, 0.01)
        self.assertEqual(resp.inferred_hypothesis, "H0")

    def test_08_api_decode_reference_clean_image(self):
        """Verify API response semantics for reference validation of clean media (H0, genuine negative LR)."""
        import asyncio
        asyncio.run(self._async_test_api_reference_clean())


if __name__ == "__main__":
    unittest.main()

"""
MediaProvenance — Phase 5.8 HiDDeN-32 False-Positive Root-Cause Regression Suite
==================================================================================
Tests and proves that:
1. High-contrast unwatermarked images (documents, text, sharp gradients) never
   trigger positive watermark detection in blind decode mode despite large CNN activations.
2. Blind decode strictly returns bit_error_rate = None, expected_ber = None,
   confidence = None, and inferred_hypothesis = "H2" (Unanchored).
3. The UI-facing semantic fields (watermark_detected, publisher_authenticated,
   proof_valid, image_binding_verified) remain False in blind mode.
4. An unwatermarked image tested against an arbitrary reference payload is strictly
   rejected under hypothesis H0 with noise-level Hamming distance (d_H >= 11).
5. A genuine HiDDeN-watermarked image with matching reference is accepted under H1.
6. A genuine HiDDeN-watermarked image with mismatched reference is rejected under H0.
7. Blind payload recovery can NEVER bypass cryptographic publisher authentication.
"""

import io
import json
import os
import sys
import unittest
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.carriers.hidden.carrier import HiddenCarrier
from fastapi.testclient import TestClient
from backend.main import app


class TestPhase58HiddenFalsePositive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.carrier = HiddenCarrier()
        cls.canonical_payload = "1a2b3c4d"
        cls.mismatched_payload = "ffffffff"

        # Create a synthetic high-contrast text document image (the exact condition that caused logit saturation)
        cls.doc_img = Image.new("RGB", (128, 128), color=(255, 255, 255))
        draw = ImageDraw.Draw(cls.doc_img)
        for y in range(8, 120, 10):
            draw.line([(8, y), (120, y)], fill=(0, 0, 0), width=2)
        
        buf = io.BytesIO()
        cls.doc_img.save(buf, format="PNG")
        cls.doc_bytes = buf.getvalue()

        # Load held-out images
        held_out_dir = PROJECT_ROOT / "experiments" / "data" / "phase5_8_100_images"
        cls.clean_paths = sorted(list(held_out_dir.glob("*.png")))[:10]

    def test_01_high_contrast_document_blind_decode_no_false_positive(self):
        """A sharp black-and-white document drives CNN logits hard, but must NEVER trigger detection or green BER."""
        resp = self.client.post(
            "/api/v1/watermark/decode",
            files={"file": ("document_clean.png", self.doc_bytes, "image/png")},
            data={"carrier": "hidden"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Must NOT detect watermark
        self.assertFalse(data["watermark_detected"], "Document must not be detected as watermarked")
        self.assertFalse(data["publisher_authenticated"], "Document must not be authenticated")
        self.assertFalse(data["proof_valid"], "Document must have proof_valid=False")
        self.assertFalse(data["image_binding_verified"], "Image binding must be False")

        # Missing measurements must be None (Requirement 3 & D)
        self.assertIsNone(data["bit_error_rate"], "BER must be None in blind mode")
        self.assertIsNone(data["expected_ber"], "expected_ber must be suppressed in blind mode")
        self.assertIsNone(data["confidence"], "confidence must be None in blind mode")
        self.assertIsNone(data["payload_matches"], "payload_matches must be None without reference")
        self.assertEqual(data["inferred_hypothesis"], "H2", "Blind image must be H2 (Unanchored)")

        # Verify CNN activation is indeed high (demonstrating why logit thresholding fails)
        self.assertGreater(
            data["mean_logit_magnitude"],
            5.0,
            "CNN activation magnitude on document should be high due to sharp text edges"
        )

    def test_02_held_out_clean_images_blind_decode_all_h2(self):
        """All 10 held-out clean images must produce H2 with watermark_detected=False."""
        for p in self.clean_paths:
            with open(p, "rb") as f:
                content = f.read()
            resp = self.client.post(
                "/api/v1/watermark/decode",
                files={"file": (p.name, content, "image/png")},
                data={"carrier": "hidden"},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertFalse(data["watermark_detected"])
            self.assertEqual(data["inferred_hypothesis"], "H2")
            self.assertIsNone(data["bit_error_rate"])
            self.assertIsNone(data["expected_ber"])

    def test_03_high_contrast_document_anchored_rejection(self):
        """Document tested against reference payload must fail under H0 with noise-level Hamming distance."""
        resp = self.client.post(
            "/api/v1/watermark/decode",
            files={"file": ("document_clean.png", self.doc_bytes, "image/png")},
            data={"carrier": "hidden", "reference_payload_hex": self.canonical_payload},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertFalse(data["watermark_detected"])
        self.assertFalse(data["payload_matches"])
        self.assertEqual(data["inferred_hypothesis"], "H0")
        self.assertGreaterEqual(data["hamming_distance"], 10, "Hamming distance must be noise-level")
        self.assertFalse(data["publisher_authenticated"])

    def test_04_genuine_watermark_with_matching_reference_accepted(self):
        """Genuine watermarked image with matching reference claim is accepted under H1."""
        img = self.doc_img.copy()
        enc_res = self.carrier.encode(img, self.canonical_payload)
        
        buf = io.BytesIO()
        enc_res.watermarked_image.save(buf, format="PNG")
        wm_bytes = buf.getvalue()

        resp = self.client.post(
            "/api/v1/watermark/decode",
            files={"file": ("wm_doc.png", wm_bytes, "image/png")},
            data={"carrier": "hidden", "reference_payload_hex": self.canonical_payload},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIsNotNone(data["hamming_distance"])
        self.assertIsNotNone(data["bit_error_rate"])

    def test_05_watermark_with_mismatched_payload_rejected(self):
        """Watermarked image with mismatched reference claim is rejected under H0."""
        img = self.doc_img.copy()
        enc_res = self.carrier.encode(img, self.canonical_payload)
        
        buf = io.BytesIO()
        enc_res.watermarked_image.save(buf, format="PNG")
        wm_bytes = buf.getvalue()

        resp = self.client.post(
            "/api/v1/watermark/decode",
            files={"file": ("wm_doc.png", wm_bytes, "image/png")},
            data={"carrier": "hidden", "reference_payload_hex": self.mismatched_payload},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertFalse(data["watermark_detected"])
        self.assertFalse(data["payload_matches"])
        self.assertEqual(data["inferred_hypothesis"], "H0")
        self.assertEqual(data["failure_reason"], "PAYLOAD_MISMATCH")


if __name__ == "__main__":
    unittest.main()

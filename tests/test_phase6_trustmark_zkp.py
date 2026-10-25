"""
Test Phase 6: TrustMark-Q Zero-Knowledge Proving and Soundness Suite
====================================================================
Tests end-to-end 100-bit witness proof generation, KZG verification,
and Negative Claim Verification Test (Soundness / Model Substitution rejection).
"""

import unittest
from PIL import Image

from backend.carriers.trustmark.carrier import TrustMarkCarrier
from backend.carriers.base import BaseCarrier
from backend.zk.engine import zk_engine
from backend.zk.features import cache_image_features, extract_trustmark_features


class TestTrustMarkZKP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.carrier = TrustMarkCarrier(model_type="Q", payload_bits=100)
        cls.test_image = Image.new("RGB", (256, 256), color=(80, 140, 200))
        cls.test_payload = "a5" + "9876543210fedcba98765432"  # 25 hex chars

        # Embed watermark
        cls.enc_res = cls.carrier.encode(cls.test_image, cls.test_payload)
        cls.wm_image = cls.enc_res.watermarked_image
        cls.image_sha = BaseCarrier.image_sha256(cls.wm_image)

        # Cache features
        cache_image_features(cls.image_sha, cls.wm_image, carrier="trustmark")

    def test_01_feature_extraction(self):
        """Verify 2048-dimensional intermediate feature extraction from TrustMark ResNet backbone."""
        features = extract_trustmark_features(self.wm_image)
        self.assertEqual(len(features), 2048)
        self.assertTrue(any(abs(f) > 1e-4 for f in features))

    def test_02_proof_generation_and_positive_verification(self):
        """Verify Halo2 KZG proof generation and positive verification."""
        proof_res = zk_engine.generate_proof(
            payload_hex=self.test_payload,
            image_sha256=self.image_sha,
            prover_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
            image_input=self.wm_image,
            carrier="trustmark",
        )
        self.assertTrue(proof_res["success"])
        self.assertEqual(proof_res["circuit_version"], "ezkl_halo2_trustmark_decoder_v1")
        self.assertEqual(proof_res["public_inputs"]["model_digest"], zk_engine.trustmark_model_digest)

        # Positive verification
        ver_res = zk_engine.verify_proof(proof_res["proof"], proof_res["public_inputs"], image_input=self.wm_image)
        self.assertTrue(ver_res["valid"], f"Verification failed: {ver_res.get('error')}")

    def test_03_negative_claim_tampered_model_digest(self):
        """Verify that tampered model digest is strictly REJECTED (Soundness)."""
        proof_res = zk_engine.generate_proof(
            payload_hex=self.test_payload,
            image_sha256=self.image_sha,
            carrier="trustmark",
        )
        tampered_inputs = dict(proof_res["public_inputs"])
        tampered_inputs["model_digest"] = "0x" + "0" * 64

        ver_res = zk_engine.verify_proof(proof_res["proof"], tampered_inputs)
        self.assertFalse(ver_res["valid"])
        self.assertIn("TrustMark-Q decoder", ver_res.get("error", ""))
        self.assertIn("Model digest mismatch", ver_res.get("error", ""))

    def test_04_negative_claim_tampered_payload_commitment(self):
        """Verify that a tampered payload commitment is strictly REJECTED."""
        proof_res = zk_engine.generate_proof(
            payload_hex=self.test_payload,
            image_sha256=self.image_sha,
            carrier="trustmark",
        )
        tampered_inputs = dict(proof_res["public_inputs"])
        tampered_inputs["payload_commitment"] = "0x" + "f" * 64

        ver_res = zk_engine.verify_proof(proof_res["proof"], tampered_inputs)
        self.assertFalse(ver_res["valid"])
        self.assertIn("commitment mismatch", ver_res.get("error", "").lower())


if __name__ == "__main__":
    unittest.main()

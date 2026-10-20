"""
ProvenanceLab — Comprehensive Test Suite for PureConv Carrier & Dual-Circuit ZK Routing
========================================================================================
Validates Phase 2 Deliverables:
1. PureConv Carrier Initialization & Factory Registry.
2. PureConv Raw Embedding & Decoding (PSNR > 30 dB, BER = 0.0, zero NNLS / caches).
3. PureConv Feature Extractor (strictly 32 dimensions vs 64 for legacy).
4. PureConv ONNX & Circuit Artifact Integrity.
5. Genuine EZKL Halo2/KZG Proof Generation & Cryptographic Verification for PureConv.
6. Dual Circuit Dimension-Aware Routing (32-dim PureConv vs 64-dim Legacy).
7. Negative Security & Adversarial Rejection Tests for PureConv.
"""

from __future__ import annotations

import hashlib
import json
import os
import unittest
from pathlib import Path

import numpy as np
import onnxruntime as ort
import torch
from PIL import Image

from backend.carriers.base import BaseCarrier
from backend.carriers.factory import get_carrier
from backend.carriers.pureconv.carrier import PureConvCarrier
from backend.zk.engine import EZKLProvingEngine, zk_engine
from backend.zk.features import extract_hidden_features, extract_pureconv_features


class TestPureConvIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Configure HOME, USERPROFILE, and EZKL_REPO_PATH
        os.environ["HOME"] = os.path.expanduser("~")
        os.environ["USERPROFILE"] = os.path.expanduser("~")
        cls.project_root = Path(__file__).resolve().parents[1]
        os.environ["EZKL_REPO_PATH"] = str(cls.project_root)

        cls.pureconv_dir = cls.project_root / "models" / "ezkl_artifacts_pureconv"
        cls.pureconv_head_onnx = cls.pureconv_dir / "pureconv_head.onnx"

        # Deterministic test image (128x128)
        arr = np.arange(128 * 128, dtype=np.uint8).reshape(128, 128)
        cls.test_img = Image.fromarray(np.stack([arr, arr // 2, 255 - arr], axis=2))

    def test_01_carrier_initialization_and_factory(self):
        """Verify PureConv carrier initializes and registers in factory alongside legacy carriers."""
        carrier = get_carrier("pureconv")
        self.assertIsInstance(carrier, BaseCarrier)
        self.assertEqual(carrier.info.name, "PureConv-32")
        self.assertEqual(carrier.info.payload_bits, 32)
        self.assertEqual(carrier.info.version, "1.0.0-pureconv32")

        # Verify legacy carriers remain intact
        carrier_hidden = get_carrier("hidden")
        self.assertEqual(carrier_hidden.info.payload_bits, 32)
        carrier_tm = get_carrier("trustmark")
        self.assertEqual(carrier_tm.info.payload_bits, 100)
        print("\n[PASS] PureConv registered in factory; legacy carriers preserved.")

    def test_02_pureconv_embedding_and_decoding(self):
        """Verify PureConv embeds and decodes payload with zero errors and PSNR > 30 dB."""
        carrier = get_carrier("pureconv")
        target_payload = "a1b2c3d4"

        # Encode
        enc_res = carrier.encode(self.test_img, target_payload)
        self.assertIsNone(enc_res.error)
        self.assertEqual(enc_res.payload_hex, target_payload)
        self.assertIsNotNone(enc_res.psnr_db)
        self.assertGreater(enc_res.psnr_db, 30.0, f"PSNR {enc_res.psnr_db} dB is below 30 dB threshold")

        # Decode directly without cache
        dec_res = carrier.decode(enc_res.watermarked_image, reference_payload_hex=target_payload)
        self.assertIsNone(dec_res.error)
        self.assertEqual(dec_res.payload_hex, target_payload)
        self.assertEqual(dec_res.bit_error_rate, 0.0)
        self.assertEqual(dec_res.hamming_distance, 0)
        self.assertGreaterEqual(dec_res.confidence, 0.5)

        # Negative test: invalid payload hex length
        bad_res = carrier.encode(self.test_img, "short")
        self.assertIsNotNone(bad_res.error)
        print(f"\n[PASS] PureConv Encode/Decode Verified: PSNR={enc_res.psnr_db:.2f} dB, BER=0.00%")

    def test_03_feature_dimensions(self):
        """Verify PureConv feature extraction produces exactly 32 dimensions while legacy produces 64."""
        pureconv_feats = extract_pureconv_features(self.test_img)
        self.assertEqual(len(pureconv_feats), 32)

        hidden_feats = extract_hidden_features(self.test_img)
        self.assertEqual(len(hidden_feats), 64)
        print("\n[PASS] Feature dimensions confirmed: PureConv=32, Legacy HiDDeN=64.")

    def test_04_circuit_artifacts_and_onnx_parity(self):
        """Verify PureConv circuit artifacts exist and evaluate ONNX numerical parity."""
        self.assertTrue(self.pureconv_head_onnx.exists(), "pureconv_head.onnx missing")
        self.assertTrue((self.pureconv_dir / "settings.json").exists(), "settings.json missing")
        self.assertTrue((self.pureconv_dir / "model.compiled").exists(), "model.compiled missing")
        self.assertTrue((self.pureconv_dir / "pk.key").exists(), "pk.key missing")
        self.assertTrue((self.pureconv_dir / "vk.key").exists(), "vk.key missing")

        # PyTorch vs ONNX parity for pureconv_head
        ort_sess = ort.InferenceSession(str(self.pureconv_head_onnx))
        dummy_feat = np.random.randn(1, 32).astype(np.float32)
        ort_out = ort_sess.run(None, {"carrier_projections": dummy_feat})[0]

        head = torch.nn.Linear(32, 32)
        head.eval()
        with torch.no_grad():
            head.weight.data = torch.eye(32) * 100.0
            head.bias.data = torch.zeros(32)
            pt_out = head(torch.from_numpy(dummy_feat)).numpy()

        diff = float(np.max(np.abs(ort_out - pt_out)))
        self.assertLess(diff, 1e-5, f"PureConv head ONNX parity diff {diff} exceeds 1e-5")
        print(f"\n[PASS] PureConv ONNX numerical parity verified: max diff = {diff:.2e}")

    def test_05_pureconv_proof_generation_and_verification(self):
        """Verify genuine EZKL Halo2/KZG proof generation and independent verification for PureConv."""
        features = extract_pureconv_features(self.test_img)
        self.assertEqual(len(features), 32)

        carrier = get_carrier("pureconv")
        dec_res = carrier.decode(self.test_img)
        recovered_hex = dec_res.payload_hex
        image_sha256 = "0x" + hashlib.sha256(self.test_img.tobytes()).hexdigest()

        # Generate genuine PureConv proof
        proof_res = zk_engine.generate_proof(
            payload_hex=recovered_hex,
            image_sha256=image_sha256,
            prover_address="0x36bBE99D2bBA981bEBB08f8a0BC40b15021e6791",
            image_features=features,
            carrier="pureconv",
        )

        self.assertTrue(proof_res["success"])
        self.assertEqual(proof_res["proof_system"], "EZKL-Halo2-KZG")
        self.assertEqual(proof_res["circuit_version"], "ezkl_halo2_pureconv_decoder_v1")
        self.assertFalse(proof_res["is_synthetic"])

        # Cryptographically verify proof
        verif_res = zk_engine.verify_proof(proof_res["proof"], proof_res["public_inputs"])
        self.assertTrue(verif_res["valid"], f"PureConv verification failed: {verif_res.get('error')}")
        self.assertEqual(verif_res["circuit_identifier"], "ezkl_halo2_pureconv_decoder_v1")
        print(f"\n[PASS] PureConv Proof generated in {proof_res['proving_time_seconds']}s")
        print(f"       Verified in {verif_res['verification_time_seconds']}s | Valid={verif_res['valid']}")

    def test_06_dimension_aware_dual_circuit_routing(self):
        """Verify engine selects correct circuit (32-dim PureConv vs 64-dim Legacy) based on input dimensions."""
        pureconv_feats = [0.1] * 32
        hidden_feats = [0.1] * 64
        image_sha256 = "0x" + hashlib.sha256(b"routing_test_image").hexdigest()

        # 32 dimensions -> PureConv
        res_pure = zk_engine.generate_proof(
            payload_hex="a1b2c3d4",
            image_sha256=image_sha256,
            image_features=pureconv_feats,
        )
        self.assertEqual(res_pure["circuit_version"], "ezkl_halo2_pureconv_decoder_v1")

        # 64 dimensions -> Legacy HiDDeN
        res_hidden = zk_engine.generate_proof(
            payload_hex="a1b2c3d4",
            image_sha256=image_sha256,
            image_features=hidden_feats,
        )
        self.assertEqual(res_hidden["circuit_version"], "ezkl_halo2_hidden_decoder_v1")
        print("\n[PASS] Dual-circuit routing verified: 32-dim -> PureConv, 64-dim -> Legacy HiDDeN.")

    def test_07_tampered_proof_and_digest_rejected(self):
        """Adversarial test: tampered model digest or payload in PureConv proof must be rejected."""
        features = extract_pureconv_features(self.test_img)
        image_sha256 = "0x" + hashlib.sha256(self.test_img.tobytes()).hexdigest()

        proof_res = zk_engine.generate_proof(
            payload_hex="a1b2c3d4",
            image_sha256=image_sha256,
            image_features=features,
            carrier="pureconv",
        )

        # 1. Tampered model digest
        tampered_public = dict(proof_res["public_inputs"])
        tampered_public["model_digest"] = "0x0000000000000000000000000000000000000000000000000000000000000000"
        rej_res = zk_engine.verify_proof(proof_res["proof"], tampered_public)
        self.assertFalse(rej_res["valid"])
        self.assertIn("mismatch", rej_res["error"].lower())

        # 2. Tampered payload
        tampered_payload_public = dict(proof_res["public_inputs"])
        tampered_payload_public["payload_hex"] = "ffffffff"
        rej_res2 = zk_engine.verify_proof(proof_res["proof"], tampered_payload_public)
        self.assertFalse(rej_res2["valid"])
        self.assertIn("mismatch", rej_res2["error"].lower())
        print("\n[PASS] Adversarial rejection confirmed: tampered digests and payloads successfully blocked.")


if __name__ == "__main__":
    unittest.main()

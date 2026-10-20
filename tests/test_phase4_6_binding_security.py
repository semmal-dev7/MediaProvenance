"""
ProvenanceLab — Phase 4.6: Image-to-Proof Binding Security Audit Test Suite
=============================================================================
Evaluates the 8 canonical security attacks identified in Phase 4.6:
1. Submitting Image A with features derived from Image B.
2. Replacing the image digest while reusing a proof.
3. Supplying handcrafted feature vectors (Direct engine vs REST API).
4. Changing the claimed payload.
5. Recomputing a commitment after changing the claim.
6. Reusing a proof with a different model digest or verification key.
7. Reusing a valid proof for a different asset ID or publisher identity.
8. Submitting a blockchain commitment without a valid corresponding proof.

Separates cryptographic circuit constraints from application-level checks.
Exports empirical results to experiments/results/phase4_6_attack_matrix.json.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.carriers.pureconv.carrier import PureConvCarrier
from backend.zk.engine import zk_engine, compute_claim_commitment
from backend.zk.features import extract_pureconv_features


class TestPhase46BindingSecurity(unittest.TestCase):
    """Phase 4.6 Security Audit and Attack Reproduction Test Suite."""

    @classmethod
    def setUpClass(cls):
        os.environ["HOME"] = os.path.expanduser("~")
        os.environ["USERPROFILE"] = os.path.expanduser("~")
        cls.carrier = PureConvCarrier()

        # Image B (legitimate watermarked source)
        img_b_path = PROJECT_ROOT / "experiments" / "data" / "images" / "img_test_004_phot.png"
        cls.img_b_orig = Image.open(img_b_path).convert("RGB")
        cls.payload_b = "deadbeef"
        cls.enc_b = cls.carrier.encode(cls.img_b_orig, cls.payload_b)
        cls.img_b_wm = cls.enc_b.watermarked_image
        cls.sha_b = "0x" + cls.carrier.image_sha256(cls.img_b_wm)

        # Image A (victim/unrelated target image, unwatermarked)
        img_a_path = PROJECT_ROOT / "experiments" / "data" / "images" / "img_test_005_geom.png"
        cls.img_a = Image.open(img_a_path).convert("RGB")
        cls.sha_a = "0x" + cls.carrier.image_sha256(cls.img_a)

        # Generate genuine reference proof for Image B
        print("\n[*] Generating baseline reference proof for Image B...", flush=True)
        t0 = time.perf_counter()
        cls.base_proof_res = zk_engine.generate_proof(
            payload_hex=cls.payload_b,
            image_sha256=cls.sha_b,
            image_input=cls.img_b_wm,
            carrier="pureconv",
        )
        cls.base_gen_time = round(time.perf_counter() - t0, 4)
        cls.base_proof = cls.base_proof_res["proof"]
        cls.base_pi = cls.base_proof_res["public_inputs"]
        print(f"[+] Baseline proof ready in {cls.base_gen_time}s", flush=True)

        cls.attack_matrix: List[Dict[str, Any]] = []

    @classmethod
    def tearDownClass(cls):
        # Save attack matrix to JSON
        out_dir = PROJECT_ROOT / "experiments" / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "phase4_6_attack_matrix.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "audit_phase": "Phase 4.6",
                    "timestamp": time.time(),
                    "total_tests": len(cls.attack_matrix),
                    "attack_matrix": cls.attack_matrix,
                },
                f,
                indent=2,
            )
        print(f"\n[+] Saved attack matrix ({len(cls.attack_matrix)} tests) to {out_path}", flush=True)

    def _record_test(
        self,
        test_id: str,
        name: str,
        category: str,
        attack_description: str,
        expected_secure_outcome: str,
        actual_outcome: str,
        decision_layer: str,
        is_vulnerable: bool,
        error_message: str = "",
        details: str = "",
    ):
        record = {
            "test_id": test_id,
            "name": name,
            "category": category,
            "attack_description": attack_description,
            "expected_secure_outcome": expected_secure_outcome,
            "actual_outcome": actual_outcome,
            "decision_layer": decision_layer,
            "vulnerability_confirmed": is_vulnerable,
            "error_message": error_message or "None",
            "details": details,
        }
        self.attack_matrix.append(record)
        print(f"  [{test_id}] {name}: Actual={actual_outcome} (Layer: {decision_layer}) -> {'VULNERABLE!' if is_vulnerable else 'SECURE'}")

    def test_01_baseline_verification(self):
        """Baseline check: genuine proof on Image B passes all checks."""
        v = zk_engine.verify_proof(self.base_proof, self.base_pi, image_input=self.img_b_wm)
        self.assertTrue(v["valid"])
        self._record_test(
            test_id="ATTACK-00",
            name="Baseline Verification",
            category="Baseline",
            attack_description="Untampered proof, matching image B, matching public inputs",
            expected_secure_outcome="ACCEPTED",
            actual_outcome="ACCEPTED" if v["valid"] else "REJECTED",
            decision_layer="Cryptographic (Halo2) + Application",
            is_vulnerable=False,
            error_message=v.get("error") or "",
            details="Untampered baseline verified successfully.",
        )

    def test_02_image_a_with_features_of_image_b(self):
        """
        Attack 1: Submitting Image A with features derived from Image B.
        Attacker proves features of B, but sets suspect_image_sha256 to Image A
        and recomputes claim commitment. Verifier receives Image A.
        """
        pi = copy.deepcopy(self.base_pi)
        pi["suspect_image_sha256"] = self.sha_a
        pi["claim_commitment"] = compute_claim_commitment(
            image_sha256=self.sha_a,
            payload_commitment=pi["payload_commitment"],
            model_digest=pi["model_digest"],
            prover_address=pi["prover_address"],
        )

        # Attacker supplies Image A to the verifier
        v = zk_engine.verify_proof(self.base_proof, pi, image_input=self.img_a)

        # Record whether current system accepts or rejects
        is_vuln = v["valid"]
        self._record_test(
            test_id="ATTACK-01",
            name="Image A with features from Image B",
            category="Cross-Image Feature Substitution",
            attack_description="Proof generated from Image B submitted to verify unwatermarked Image A with recomputed claim commitment",
            expected_secure_outcome="REJECTED",
            actual_outcome="ACCEPTED" if v["valid"] else "REJECTED",
            decision_layer="None (Accepted!)" if is_vuln else "Application Verifier",
            is_vulnerable=is_vuln,
            error_message=v.get("error") or "",
            details="Verifier checked Image A hash against suspect_image_sha256, but circuit did not constrain that features were derived from Image A.",
        )

    def test_03_replace_image_digest_naive(self):
        """
        Attack 2a: Replacing image digest without recomputing claim commitment.
        """
        pi = copy.deepcopy(self.base_pi)
        pi["suspect_image_sha256"] = self.sha_a  # Changed digest, claim_commitment unchanged

        v = zk_engine.verify_proof(self.base_proof, pi)
        self.assertFalse(v["valid"])
        self._record_test(
            test_id="ATTACK-02A",
            name="Replacing image digest (naive)",
            category="Image Digest Replay",
            attack_description="Altering suspect_image_sha256 while leaving claim_commitment untouched",
            expected_secure_outcome="REJECTED",
            actual_outcome="ACCEPTED" if v["valid"] else "REJECTED",
            decision_layer="Application Verifier (Claim Commitment Check)",
            is_vulnerable=v["valid"],
            error_message=v.get("error") or "",
            details="Rejected because C_claim = H(sha_a || ...) does not match claimed C_claim.",
        )

    def test_04_replace_image_digest_with_recomputed_commitment(self):
        """
        Attack 2b: Replacing image digest WITH recomputed claim commitment (no raw image passed).
        """
        pi = copy.deepcopy(self.base_pi)
        pi["suspect_image_sha256"] = self.sha_a
        pi["claim_commitment"] = compute_claim_commitment(
            image_sha256=self.sha_a,
            payload_commitment=pi["payload_commitment"],
            model_digest=pi["model_digest"],
            prover_address=pi["prover_address"],
        )

        v = zk_engine.verify_proof(self.base_proof, pi)  # No raw image provided (API verifier style)
        is_vuln = v["valid"]
        self._record_test(
            test_id="ATTACK-02B",
            name="Replacing image digest (recomputed commitment, no raw media)",
            category="Image Digest Replay",
            attack_description="Proof reused for different image digest by recomputing claim commitment off-chain",
            expected_secure_outcome="REJECTED",
            actual_outcome="ACCEPTED" if v["valid"] else "REJECTED",
            decision_layer="None (Accepted!)" if is_vuln else "Application Verifier",
            is_vulnerable=is_vuln,
            error_message=v.get("error") or "",
            details="Accepted because the circuit does not constrain the image digest and no raw image was supplied for re-extraction.",
        )

    def test_05_handcrafted_features_direct_zk(self):
        """
        Attack 3a: Supplying handcrafted feature vector directly to ZK proof engine.
        Attacker supplies artificial features [0.05]*32 to force positive logits.
        """
        handcrafted = [0.05] * 32
        proof_crafted = zk_engine.generate_proof(
            payload_hex="ffffffff",
            image_sha256=self.sha_b,
            image_features=handcrafted,
            allow_synthetic=True,
            carrier="pureconv",
        )
        v = zk_engine.verify_proof(proof_crafted["proof"], proof_crafted["public_inputs"])
        is_vuln = v["valid"]
        self._record_test(
            test_id="ATTACK-03A",
            name="Handcrafted features (direct ZK proving)",
            category="Feature Forgery",
            attack_description="Attacker generates proof using handcrafted feature vector without an image",
            expected_secure_outcome="REJECTED",
            actual_outcome="ACCEPTED" if v["valid"] else "REJECTED",
            decision_layer="None (Accepted!)" if is_vuln else "Cryptographic / Circuit",
            is_vulnerable=is_vuln,
            error_message=v.get("error") or "",
            details="Circuit successfully proves y = W*x + b for handcrafted x. Circuit does not know x is synthetic.",
        )

    def test_06_handcrafted_features_api_boundary(self):
        """
        Attack 3b: Supplying handcrafted feature vector to REST API endpoint.
        """
        from backend.api.routes.proofs import CreateProofRequest, generate_proof_direct
        from fastapi import HTTPException

        req = CreateProofRequest(
            payload_hex="ffffffff",
            image_sha256=self.sha_b,
            image_features=[0.05] * 32,
            allow_synthetic=False,
        )

        try:
            asyncio.run(generate_proof_direct(req))
            api_rejected = False
            err_msg = ""
        except HTTPException as e:
            api_rejected = True
            err_msg = str(e.detail)

        self.assertTrue(api_rejected)
        self._record_test(
            test_id="ATTACK-03B",
            name="Handcrafted features via REST API",
            category="Feature Forgery",
            attack_description="Untrusted client submits custom feature array to /proofs/generate endpoint",
            expected_secure_outcome="REJECTED",
            actual_outcome="REJECTED" if api_rejected else "ACCEPTED",
            decision_layer="Application / API Boundary Guard",
            is_vulnerable=not api_rejected,
            error_message=err_msg,
            details="API rejects client features because they are not present in server feature cache.",
        )

    def test_07_changing_claimed_payload(self):
        """
        Attack 4: Changing claimed payload while keeping proof and commitment unchanged.
        """
        pi = copy.deepcopy(self.base_pi)
        pi["payload_hex"] = "1337c0de"  # Claim fake payload

        v = zk_engine.verify_proof(self.base_proof, pi)
        self.assertFalse(v["valid"])
        self._record_test(
            test_id="ATTACK-04",
            name="Changing claimed payload",
            category="Payload Tampering",
            attack_description="Claiming payload 1337c0de on proof that constrained deadbeef",
            expected_secure_outcome="REJECTED",
            actual_outcome="ACCEPTED" if v["valid"] else "REJECTED",
            decision_layer="Application Verifier (Circuit Output Match Check)",
            is_vulnerable=v["valid"],
            error_message=v.get("error") or "",
            details="Verifier extracted constrained circuit outputs from proof and caught mismatch with claimed payload.",
        )

    def test_08_recomputing_commitment_after_changing_claim(self):
        """
        Attack 5: Recomputing payload and claim commitments after changing claimed payload.
        """
        pi = copy.deepcopy(self.base_pi)
        fake_payload = "1337c0de"
        pi["payload_hex"] = fake_payload
        ch = hashlib.sha256()
        ch.update(fake_payload.encode("utf-8"))
        ch.update(zk_engine.pureconv_model_digest.lower().encode("utf-8"))
        fake_pc = "0x" + ch.hexdigest()
        pi["payload_commitment"] = fake_pc
        pi["claim_commitment"] = compute_claim_commitment(
            image_sha256=pi["suspect_image_sha256"],
            payload_commitment=fake_pc,
            model_digest=zk_engine.pureconv_model_digest,
            prover_address=pi["prover_address"],
        )

        v = zk_engine.verify_proof(self.base_proof, pi)
        self.assertFalse(v["valid"])
        self._record_test(
            test_id="ATTACK-05",
            name="Recomputing commitment after payload change",
            category="Payload Commitment Forgery",
            attack_description="Recomputing C_payload and C_claim to match fake payload 1337c0de while keeping proof instances",
            expected_secure_outcome="REJECTED",
            actual_outcome="ACCEPTED" if v["valid"] else "REJECTED",
            decision_layer="Application Verifier (Circuit Output Consistency)",
            is_vulnerable=v["valid"],
            error_message=v.get("error") or "",
            details="Even though commitments match 1337c0de, proof's constrained outputs still evaluate to deadbeff, triggering rejection.",
        )

    def test_09_mismatched_model_digest_and_vk(self):
        """
        Attack 6: Reusing proof with different model digest or verification key.
        """
        # 6a: Altered model digest
        pi = copy.deepcopy(self.base_pi)
        pi["model_digest"] = "0x" + "0" * 64
        v_model = zk_engine.verify_proof(self.base_proof, pi)
        self.assertFalse(v_model["valid"])

        # 6b: Wrong VK (verify PureConv proof against legacy HiDDeN VK)
        pi_vk = copy.deepcopy(self.base_pi)
        pi_vk["circuit_version"] = zk_engine.CIRCUIT_VERSION  # Force HiDDeN VK path
        pi_vk["model_digest"] = zk_engine.model_digest.lower()
        v_vk = zk_engine.verify_proof(self.base_proof, pi_vk)
        self.assertFalse(v_vk["valid"])

        self._record_test(
            test_id="ATTACK-06",
            name="Mismatched model digest and verification key",
            category="Model & Circuit Integrity",
            attack_description="6a: Altered model digest in public inputs. 6b: Verifying PureConv proof with HiDDeN vk.key",
            expected_secure_outcome="REJECTED",
            actual_outcome="REJECTED",
            decision_layer="Application Check (Model Digest) + Cryptographic Halo2 VK Pairing",
            is_vulnerable=False,
            error_message=f"Model: {v_model.get('error')}; VK: {v_vk.get('error')}",
            details="Altered model digest caught by application; mismatched VK fails Halo2 transcript verification.",
        )

    def test_10_proof_replay_different_asset_or_publisher(self):
        """
        Attack 7: Reusing a valid proof for a different asset ID or publisher address.
        Attacker intercepts valid proof, sets prover_address to attacker address,
        and recomputes claim commitment.
        """
        attacker_address = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
        pi = copy.deepcopy(self.base_pi)
        pi["prover_address"] = attacker_address
        pi["claim_commitment"] = compute_claim_commitment(
            image_sha256=pi["suspect_image_sha256"],
            payload_commitment=pi["payload_commitment"],
            model_digest=pi["model_digest"],
            prover_address=attacker_address,
        )

        v = zk_engine.verify_proof(self.base_proof, pi)
        is_vuln = v["valid"]
        self._record_test(
            test_id="ATTACK-07",
            name="Proof replay across publisher addresses",
            category="Publisher / Asset Identity Binding",
            attack_description="Attacker takes valid proof and re-submits with attacker prover_address and recomputed claim commitment",
            expected_secure_outcome="REJECTED",
            actual_outcome="ACCEPTED" if v["valid"] else "REJECTED",
            decision_layer="None (Accepted!)" if is_vuln else "Application Verifier",
            is_vulnerable=is_vuln,
            error_message=v.get("error") or "",
            details="Accepted because the proof contains no cryptographic signature from the prover, and claim commitment can be recomputed by anyone.",
        )

    def test_11_unconstrained_blockchain_anchoring(self):
        """
        Attack 8: Submitting a blockchain commitment without a valid proof.
        Evaluates ProvenanceAnchor.sol contract logic (mocked/simulated local invocation).
        """
        # Inspect ProvenanceAnchor.sol logic
        # anchor(bytes32 assetId, bytes32 commitment) only checks:
        # require(assetId != 0), require(commitment != 0), require(!records[assetId].exists)
        # It does NOT verify any proof or signature!
        fake_asset_id = "0x" + "11" * 32
        fake_commitment = "0x" + "22" * 32

        # In job_manager: anchor_commitment simply stores the record
        from backend.services.job_manager import job_manager
        record = job_manager.anchor_commitment(
            asset_id=fake_asset_id,
            commitment=fake_commitment,
            submitter="0xAttacker00000000000000000000000000000000",
        )

        stored = job_manager.get_anchor(fake_asset_id)
        is_vuln = stored is not None and stored.commitment.lower() == fake_commitment.lower()

        self._record_test(
            test_id="ATTACK-08",
            name="Unconstrained blockchain commitment anchoring",
            category="Smart Contract Soundness",
            attack_description="Attacker calls anchor(assetId, commitment) with arbitrary fake data and zero proof",
            expected_secure_outcome="REJECTED",
            actual_outcome="ACCEPTED" if is_vuln else "REJECTED",
            decision_layer="None (Accepted on contract!)",
            is_vulnerable=is_vuln,
            error_message="None (Contract accepted arbitrary commitment)",
            details="ProvenanceAnchor.sol is merely a key-value registry; it does not invoke an EVM verifier or check proof calldata.",
        )


if __name__ == "__main__":
    unittest.main()

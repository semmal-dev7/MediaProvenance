"""
Step 2 Verification: Genuine Groth16 Zero-Knowledge Proving and Pairing Verification
===================================================================================
Tests:
1. Genuine proof generation over BN254 / bn128 curve with 537 Poseidon circuit constraints.
2. Honest proof verification (pairing check).
3. Rejection of tampered model weights (model substitution defense).
4. Rejection of tampered image digest (cross-image replay defense).
5. Rejection of altered proof points (cryptographic soundness).
6. Rejection of forged commitment.
"""

import sys
import time
from backend.zk.engine import zk_engine


def run_zk_tests():
    print("=" * 75)
    print("STEP 2: GENUINE ZERO-KNOWLEDGE PROOF & PAIRING VERIFICATION TEST")
    print("=" * 75)

    payload_hex = "a1b2c3d4"
    image_sha256 = "3036c3933c3413a7b63f533a1e4c029471131ef5e1428359be24419ad2231bfa"

    # 1. Genuine Proof Generation
    print("\n1. Generating Genuine Groth16 zk-SNARK Proof...")
    t0 = time.time()
    proof_result = zk_engine.generate_proof(payload_hex, image_sha256)
    t_gen = time.time() - t0

    proof = proof_result["proof"]
    pub_inputs = proof_result["public_inputs"]
    pub_signals = proof_result.get("publicSignals")

    print(f"  [+] Proof Generated in {t_gen*1000:.1f} ms (prover core: {proof_result['proving_time_seconds']*1000:.1f} ms)")
    print(f"      Protocol:       {proof['protocol']}")
    print(f"      Curve:          {proof['curve']}")
    print(f"      Constraints:    {proof_result['witness_constraints']}")
    print(f"      Commitment:     {pub_inputs['payload_commitment'][:20]}...")
    print(f"      Nullifier:      {pub_inputs['public_nullifier'][:20]}...")
    print(f"      pi_a[0]:        {proof['pi_a'][0][:20]}...")

    # 2. Honest Verification
    print("\n2. Executing Cryptographic Pairing Verification on Honest Proof...")
    v_honest = zk_engine.verify_proof(proof, pub_inputs, pub_signals)
    print(f"  [+] Verification Result: {v_honest['valid']} (took {v_honest['verification_time_seconds']*1000:.2f} ms)")
    assert v_honest["valid"] is True, f"Honest proof verification failed: {v_honest}"
    print("      -> PASS: Honest cryptographic proof verified via elliptic curve pairing!")

    # 3. Negative Test: Tampered Model Digest
    print("\n3. Testing Negative Case 1: Tampered Model Weights (Substitution Attack)...")
    bad_model_inputs = dict(pub_inputs)
    bad_model_inputs["model_digest"] = "0x" + "0" * 64
    v_bad_model = zk_engine.verify_proof(proof, bad_model_inputs)
    print(f"  [+] Tampered Model Verification Result: {v_bad_model['valid']}")
    assert v_bad_model["valid"] is False, "Security failure: Tampered model accepted!"
    print(f"      -> PASS: Unauthorized model weights strictly rejected: {v_bad_model.get('error')}")

    # 4. Negative Test: Tampered Image Digest (Cross-Image Replay)
    print("\n4. Testing Negative Case 2: Tampered Image Hash (Cross-Image Replay Attack)...")
    bad_image_inputs = dict(pub_inputs)
    bad_image_inputs["suspect_image_sha256"] = "1111111122222222333333334444444455555555666666667777777788888888"
    v_bad_image = zk_engine.verify_proof(proof, bad_image_inputs)
    print(f"  [+] Tampered Image Verification Result: {v_bad_image['valid']}")
    assert v_bad_image["valid"] is False, "Security failure: Replay to different image accepted!"
    print("      -> PASS: Replay on unauthorized image strictly rejected by pairing equations!")

    # 5. Negative Test: Altered Proof Points
    print("\n5. Testing Negative Case 3: Altered Proof Element (Cryptographic Forgery)...")
    bad_proof = dict(proof)
    bad_proof["pi_a"] = ["0x1234567890abcdef", proof["pi_a"][1]]
    v_bad_proof = zk_engine.verify_proof(bad_proof, pub_inputs, pub_signals)
    print(f"  [+] Altered Proof Point Result: {v_bad_proof['valid']}")
    assert v_bad_proof["valid"] is False, "Security failure: Altered proof point accepted!"
    print("      -> PASS: Forged elliptic curve proof point strictly rejected by pairing equations!")

    # 6. Negative Test: Altered Commitment
    print("\n6. Testing Negative Case 4: Altered Payload Commitment...")
    bad_commit_inputs = dict(pub_inputs)
    bad_commit_inputs["payload_commitment"] = "0x" + "deadbeef" * 8
    v_bad_commit = zk_engine.verify_proof(proof, bad_commit_inputs)
    print(f"  [+] Altered Commitment Result: {v_bad_commit['valid']}")
    assert v_bad_commit["valid"] is False, "Security failure: Altered commitment accepted!"
    print("      -> PASS: Altered commitment strictly rejected!")

    print("\n" + "=" * 75)
    print(">>> STEP 2: ALL GENUINE ZERO-KNOWLEDGE PROOF & SECURITY TESTS PASSED! <<<")
    print("=" * 75)


if __name__ == "__main__":
    run_zk_tests()

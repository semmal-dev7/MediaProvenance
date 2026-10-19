"""
ProvenanceLab — Neural ZK Circuit Acceptance & Privacy Verification Test
========================================================================
Validates all acceptance criteria:
1. Proof generated from genuine image pixels (features extracted dynamically).
2. Privacy: Zero private witness values or secret_key_hex returned in proof dictionary.
3. Soundness: Valid proof accepted by pairing equations over BN254.
4. Negative Test 1: Tampered proof coordinate rejected (pi_a altered).
5. Negative Test 2: Tampered suspect image commitment rejected.
6. Negative Test 3: Tampered model digest rejected.
7. Negative Test 4: Tampered session nonce (replay attack) rejected.
8. Negative Test 5: Inconsistent witness weights rejected during proving.
"""

import sys
import copy
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.zk.engine import zk_engine
from backend.zk.features import extract_latent_features_from_image, get_quantized_decoder_parameters


def run_acceptance_suite():
    print("=" * 80)
    print("PROVENANCELAB: NEURAL ZK CIRCUIT ACCEPTANCE & PRIVACY TEST SUITE")
    print("=" * 80)

    # 1. Create two visually distinct images
    print("\n[1/6] Creating Real Test Images & Extracting Latent Representations...")
    img_a = Image.new("RGB", (128, 128), color=(180, 70, 40))
    img_b = Image.new("RGB", (128, 128), color=(30, 150, 220))

    feat_a = extract_latent_features_from_image(img_a)
    feat_b = extract_latent_features_from_image(img_b)

    print(f"  > Image A extracted features: {feat_a}")
    print(f"  > Image B extracted features: {feat_b}")
    assert feat_a != feat_b, "Features must differ across distinct images!"

    # 2. Generate Genuine Neural Proof from Image A
    print("\n[2/6] Generating Genuine Neural Groth16 Proof for Image A...")
    proof_bundle = zk_engine.generate_neural_proof(image=img_a)

    print(f"  > Circuit:              {proof_bundle.get('circuit_version')}")
    print(f"  > Constraints:          {proof_bundle.get('witness_constraints')}")
    print(f"  > Proving Time:         {proof_bundle.get('proving_time_seconds'):.3f}s")
    print(f"  > Proof Digest:         {proof_bundle.get('proof_digest')[:24]}...")

    # 3. Privacy Test: Ensure no secret keys or private witness leaked
    print("\n[3/6] Verifying Privacy & Zero Witness Leakage...")
    assert "secret_key_hex" not in proof_bundle, "SECURITY FAILURE: secret_key_hex leaked in proof_bundle!"
    assert "secretKey" not in proof_bundle, "SECURITY FAILURE: secretKey leaked!"
    assert "is_valid" not in proof_bundle, "Prover must not assert is_valid!"
    assert "weights" not in proof_bundle.get("public_inputs", {}), "Private weights must not be public!"
    print("  [PASS] Zero private witness fields exposed! secret_key_hex strictly kept confidential.")

    # 4. Positive Verification Test
    print("\n[4/6] Executing Pairing Verification on Honest Proof...")
    v_res = zk_engine.verify_proof(
        proof=proof_bundle["proof"],
        public_inputs=proof_bundle["public_inputs"],
        public_signals=proof_bundle["publicSignals"],
        is_neural=True,
    )
    print(f"  > Verification Valid:   {v_res['valid']}")
    print(f"  > Verification Latency: {v_res['verification_time_seconds'] * 1000:.2f} ms")
    assert v_res["valid"] is True, "Honest proof must verify successfully!"
    print("  [PASS] Honest neural proof mathematically verified over BN254.")

    # 5. Rigorous Negative Test Battery
    print("\n[5/6] Executing Negative Claim Rejection Battery...")

    # Negative 1: Tampered Proof Coordinates
    print("  --- Test 5a: Altered Proof Coordinate (pi_a[0])")
    bad_proof = copy.deepcopy(proof_bundle["proof"])
    # alter last digit
    last_char = bad_proof["pi_a"][0][-1]
    new_char = "2" if last_char == "1" else "1"
    bad_proof["pi_a"][0] = bad_proof["pi_a"][0][:-1] + new_char
    v_bad_proof = zk_engine.verify_proof(
        proof=bad_proof,
        public_inputs=proof_bundle["public_inputs"],
        public_signals=proof_bundle["publicSignals"],
        is_neural=True,
    )
    assert v_bad_proof["valid"] is False, "Altered proof coordinate MUST be rejected!"
    print("  [PASS] Altered proof coordinate strictly rejected by elliptic curve pairing!")

    # Negative 2: Tampered Suspect Image Commitment (claiming proof for Image B with Image A's proof)
    print("  --- Test 5b: Cross-Image Substitution (Tampered Image Commitment)")
    bad_signals_img = copy.deepcopy(proof_bundle["publicSignals"])
    # publicSignals[1] is suspectImageCommitment
    bad_signals_img[1] = "123456789012345678901234567890"
    v_bad_img = zk_engine.verify_proof(
        proof=proof_bundle["proof"],
        public_inputs=proof_bundle["public_inputs"],
        public_signals=bad_signals_img,
        is_neural=True,
    )
    assert v_bad_img["valid"] is False, "Mismatched image commitment MUST be rejected!"
    print("  [PASS] Mismatched suspect image commitment strictly rejected!")

    # Negative 3: Tampered Model Weights Digest
    print("  --- Test 5c: Model Substitution (Tampered Model Digest)")
    bad_signals_model = copy.deepcopy(proof_bundle["publicSignals"])
    # publicSignals[2] is modelDigest
    bad_signals_model[2] = "998877665544332211"
    v_bad_model = zk_engine.verify_proof(
        proof=proof_bundle["proof"],
        public_inputs=proof_bundle["public_inputs"],
        public_signals=bad_signals_model,
        is_neural=True,
    )
    assert v_bad_model["valid"] is False, "Tampered model digest MUST be rejected!"
    print("  [PASS] Tampered model weights digest strictly rejected!")

    # Negative 4: Replay Attack with Altered Session Nonce
    print("  --- Test 5d: Replay Attack (Altered Session Nonce)")
    bad_signals_nonce = copy.deepcopy(proof_bundle["publicSignals"])
    # publicSignals[3] is sessionNonce
    bad_signals_nonce[3] = "7777777"
    v_bad_nonce = zk_engine.verify_proof(
        proof=proof_bundle["proof"],
        public_inputs=proof_bundle["public_inputs"],
        public_signals=bad_signals_nonce,
        is_neural=True,
    )
    assert v_bad_nonce["valid"] is False, "Replayed proof with different nonce MUST be rejected!"
    print("  [PASS] Replay attack with altered nonce strictly rejected!")

    # Negative 5: Prover Constraint Failure on Mismatched Weights
    print("  --- Test 5e: Inconsistent Model Weights during Proving")
    weights, biases = get_quantized_decoder_parameters()
    # maliciously tamper 1 weight
    weights[0][0] = 99999
    try:
        zk_engine.generate_neural_proof(image=img_a, weights=weights, biases=biases)
        witness_caught = False
    except Exception as e:
        witness_caught = True
        print(f"  > Prover rejected inconsistent witness weights: {str(e)[:60]}...")
    assert witness_caught is True, "Prover MUST refuse to prove inconsistent witness!"
    print("  [PASS] Prover strictly failed to generate proof for inconsistent witness weights!")

    print("\n" + "=" * 80)
    print(">>> ACCEPTANCE SUITE COMPLETED: 100% OF SECURITY & PRIVACY TESTS PASSED <<<")
    print("=" * 80)


if __name__ == "__main__":
    run_acceptance_suite()

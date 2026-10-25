import sys
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.carriers.trustmark.carrier import TrustMarkCarrier
from backend.zk.engine import zk_engine
from backend.zk.features import cache_image_features

def test_pipeline():
    print("=" * 70)
    print("Testing Complete TrustMark-Q Zero-Knowledge Proving Pipeline")
    print("=" * 70)

    # 1. Create candidate test image
    img = Image.new("RGB", (256, 256), color=(120, 150, 180))
    carrier = TrustMarkCarrier(model_type="Q", payload_bits=100)

    test_payload = "a5" + "1234567890abcdef12345678"  # 25 hex chars (100 bits) with preamble
    print(f"[*] Original Payload: {test_payload}")

    # 2. Encode
    enc_res = carrier.encode(img, test_payload)
    print(f"[+] Encoded image successfully. PSNR: {enc_res.psnr_db:.2f} dB")

    # 3. Decode
    dec_res = carrier.decode(enc_res.watermarked_image, reference_payload_hex=test_payload)
    print(f"[+] Decoded payload: {dec_res.payload_hex}")
    print(f"[+] Watermark detected: {dec_res.watermark_detected}, BER: {dec_res.bit_error_rate}")

    # 4. Cache features for suspect image
    from backend.carriers.base import BaseCarrier
    img_sha = BaseCarrier.image_sha256(enc_res.watermarked_image)
    cache_image_features(img_sha, enc_res.watermarked_image, carrier="trustmark")
    print(f"[+] Cached 2048-dim features for SHA: {img_sha[:16]}...")

    # 5. Generate ZK Proof
    print("[*] Generating EZKL Halo2 ZK Proof...")
    proof_result = zk_engine.generate_proof(
        payload_hex=dec_res.payload_hex,
        image_sha256=img_sha,
        prover_address="0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        image_input=enc_res.watermarked_image,
        carrier="trustmark",
    )
    print(f"[+] Proof generated successfully in {proof_result['proving_time_seconds']}s")
    print(f"[+] Circuit Version: {proof_result['circuit_version']}")
    print(f"[+] Model Digest: {proof_result['public_inputs']['model_digest']}")
    print(f"[+] Payload Commitment: {proof_result['public_inputs']['payload_commitment']}")

    # 6. Verify ZK Proof (Positive Verification)
    print("[*] Verifying ZK Proof with zk_engine.verify_proof()...")
    ver_res = zk_engine.verify_proof(proof_result["proof"], proof_result["public_inputs"], image_input=enc_res.watermarked_image)
    print(f"[+] Verification Result: {ver_res['valid']}")
    assert ver_res["valid"] is True, f"Positive verification failed: {ver_res.get('error')}"

    # 7. Test Negative Claim Verification (Soundness Check)
    print("[*] Testing Negative Claim Verification with tampered model digest...")
    tampered_inputs = dict(proof_result["public_inputs"])
    tampered_inputs["model_digest"] = "0x" + "0" * 64
    neg_res = zk_engine.verify_proof(proof_result["proof"], tampered_inputs, image_input=enc_res.watermarked_image)
    print(f"[+] Negative Test Valid: {neg_res['valid']} (Expected: False)")
    print(f"[+] Negative Test Error: {neg_res.get('error')}")
    assert neg_res["valid"] is False, "Negative test failed: tampered digest was accepted!"
    assert "TrustMark-Q decoder" in neg_res["error"], f"Expected TrustMark-Q decoder in error, got {neg_res['error']}"

    print("=" * 70)
    print("ALL TESTS PASSED! TrustMark-Q ZKP PIPELINE IS 100% OPERATIONAL!")
    print("=" * 70)

if __name__ == "__main__":
    test_pipeline()

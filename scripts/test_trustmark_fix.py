"""
ProvenanceLab — TrustMark Robustness & Preamble Verification Test
"""

import io
import requests
from PIL import Image

BASE_URL = "http://127.0.0.1:8080/api/v1"

def test_trustmark_pipeline():
    print("=== Testing TrustMark Embedding & Verification Fixes ===\n")

    # 1. Test embedding with an RGBA PNG image (verifying channel fix)
    print("1. Testing RGBA Image Embedding with TrustMark-Q...")
    rgba_img = Image.new("RGBA", (256, 256), color=(80, 120, 180, 255))
    buf = io.BytesIO()
    rgba_img.save(buf, format="PNG")
    buf.seek(0)

    payload_input = "a5123456789abcdef01234567"  # 100-bit payload with preamble
    files = {"file": ("test_rgba.png", buf.getvalue(), "image/png")}
    data = {"carrier": "trustmark", "payload_hex": payload_input}

    res = requests.post(f"{BASE_URL}/watermarks/embed", files=files, data=data)
    assert res.status_code == 200, f"Embed failed: {res.text}"
    enc_data = res.json()
    print("  Success:", enc_data["success"])
    print("  Embedded Payload:", enc_data["payload_hex"])
    print(f"  PSNR: {enc_data['psnr_db']:.2f} dB")
    assert enc_data["success"] is True, "Embed returned False"
    assert enc_data["psnr_db"] > 40.0, "PSNR too low"
    print("  [PASS] RGBA image embedded with high fidelity (no channel crash)!\n")

    # Extract watermarked image bytes
    import base64
    b64_str = enc_data["watermarked_image_base64"].split(",")[1]
    wm_bytes = base64.b64decode(b64_str)

    # 2. Test blind decoding of watermarked image (no reference payload)
    print("2. Testing Blind Verification of Watermarked Image...")
    files_wm = {"file": ("watermarked.png", wm_bytes, "image/png")}
    data_wm = {"carrier": "trustmark"}
    res_dec = requests.post(f"{BASE_URL}/watermarks/decode", files=files_wm, data=data_wm)
    assert res_dec.status_code == 200, f"Decode failed: {res_dec.text}"
    dec_data = res_dec.json()
    print("  Decodable:", dec_data["decodable"])
    print("  Recovered Payload:", dec_data["payload_hex"])
    print("  Hypothesis:", dec_data["inferred_hypothesis"])
    print("  Evidence Log10 LR:", dec_data["log10_likelihood_ratio"])
    assert dec_data["decodable"] is True, "Authentic watermarked image failed to decode"
    assert dec_data["inferred_hypothesis"] == "H1", f"Expected H1, got {dec_data['inferred_hypothesis']}"
    assert dec_data["payload_hex"] == enc_data["payload_hex"], "Payload mismatch"
    print("  [PASS] Correctly recovered payload with preamble sync and assigned H1!\n")

    # 3. Test verification with reference payload
    print("3. Testing Verification with Reference Payload...")
    files_ref = {"file": ("watermarked.png", wm_bytes, "image/png")}
    data_ref = {"carrier": "trustmark", "reference_payload_hex": enc_data["payload_hex"]}
    res_ref = requests.post(f"{BASE_URL}/watermarks/decode", files=files_ref, data=data_ref)
    ref_data = res_ref.json()
    print("  Decodable:", ref_data["decodable"])
    print(f"  Bit Error Rate: {ref_data['bit_error_rate']}")
    print("  Hypothesis:", ref_data["inferred_hypothesis"])
    assert ref_data["decodable"] is True
    assert ref_data["bit_error_rate"] == 0.0
    print("  [PASS] Exactly 0.0 BER verified!\n")

    # 4. Test clean / unwatermarked image rejection
    print("4. Testing Clean / Unwatermarked Image Rejection (False Positive Check)...")
    clean_img = Image.new("RGB", (256, 256), color=(220, 220, 220))
    clean_buf = io.BytesIO()
    clean_img.save(clean_buf, format="PNG")
    clean_buf.seek(0)
    files_clean = {"file": ("clean.png", clean_buf.getvalue(), "image/png")}
    data_clean = {"carrier": "trustmark"}
    res_clean = requests.post(f"{BASE_URL}/watermarks/decode", files=files_clean, data=data_clean)
    clean_data = res_clean.json()
    print("  Decodable:", clean_data["decodable"])
    print("  Hypothesis:", clean_data["inferred_hypothesis"])
    print("  Error:", clean_data["error"])
    assert clean_data["decodable"] is False, "False positive! Clean image was marked decodable"
    assert clean_data["inferred_hypothesis"] == "H0", f"Expected H0, got {clean_data['inferred_hypothesis']}"
    print("  [PASS] Clean image correctly rejected under H0 (no false positive)!\n")

    print(">>> ALL TRUSTMARK EMBEDDING & VERIFICATION TESTS PASSED! <<<")

if __name__ == "__main__":
    test_trustmark_pipeline()

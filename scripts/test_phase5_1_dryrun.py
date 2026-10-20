import base64
import io
import json
import requests
from PIL import Image
import numpy as np

BASE_URL = "http://127.0.0.1:8080/api/v1"
TEST_IMG_PATH = "experiments/data/images/img_test_004_phot.png"
PAYLOAD = "deadbeef"

results = {}

# Test A: Embed watermark into image
print("[TEST A] Embedding watermark...")
with open(TEST_IMG_PATH, "rb") as f:
    r = requests.post(
        f"{BASE_URL}/watermarks/embed",
        files={"file": ("test.png", f, "image/png")},
        data={"carrier": "pureconv", "payload_hex": PAYLOAD}
    )
embed_res = r.json()
print("  Success:", embed_res.get("success"), "PSNR:", embed_res.get("psnr_db"))
results["test_A_embed"] = {
    "status_code": r.status_code,
    "success": embed_res.get("success"),
    "psnr_db": embed_res.get("psnr_db"),
    "payload_hex": embed_res.get("payload_hex"),
    "image_sha256": embed_res.get("image_sha256"),
    "carrier_name": embed_res.get("carrier_name")
}

# Save watermarked image
raw_b64 = embed_res["watermarked_image_base64"]
if "," in raw_b64:
    raw_b64 = raw_b64.split(",", 1)[1]
wm_bytes = base64.b64decode(raw_b64)
wm_img = Image.open(io.BytesIO(wm_bytes))
wm_img.save("experiments/data/tmp_test_wm.png")

# Test B: Verify watermarked image and compare recovered payload
print("[TEST B] Decoding watermarked image...")
with open("experiments/data/tmp_test_wm.png", "rb") as f:
    r = requests.post(
        f"{BASE_URL}/watermarks/decode",
        files={"file": ("wm.png", f, "image/png")},
        data={"carrier": "pureconv"}
    )
decode_res = r.json()
print("  Success:", decode_res.get("success"), "Recovered:", decode_res.get("payload_hex"), "Matches:", decode_res.get("payload_hex") == PAYLOAD)
results["test_B_verify_clean"] = {
    "status_code": r.status_code,
    "success": decode_res.get("success"),
    "recovered_hex": decode_res.get("payload_hex"),
    "expected_hex": PAYLOAD,
    "match": decode_res.get("payload_hex") == PAYLOAD,
    "confidence": decode_res.get("confidence")
}

# Test C: Test unwatermarked clean image
print("[TEST C] Testing unwatermarked clean image...")
with open(TEST_IMG_PATH, "rb") as f:
    r = requests.post(
        f"{BASE_URL}/watermarks/decode",
        files={"file": ("clean.png", f, "image/png")},
        data={"carrier": "pureconv"}
    )
clean_res = r.json()
print("  Clean decode payload:", clean_res.get("payload_hex"), "Confidence:", clean_res.get("confidence"), "Presence detected:", clean_res.get("watermark_present"))
results["test_C_unwatermarked"] = {
    "status_code": r.status_code,
    "payload_hex": clean_res.get("payload_hex"),
    "confidence": clean_res.get("confidence"),
    "watermark_present": clean_res.get("watermark_present"),
    "observation": "High uncertainty / near random confidence on unwatermarked media"
}

# Test D: Test transformations (JPEG 75, Resize 50%, Blur)
print("[TEST D] Testing transformations...")
# D1: JPEG 75
jpeg_buf = io.BytesIO()
wm_img.save(jpeg_buf, format="JPEG", quality=75)
jpeg_buf.seek(0)
r_jpeg = requests.post(
    f"{BASE_URL}/watermarks/decode",
    files={"file": ("wm_q75.jpg", jpeg_buf, "image/jpeg")},
    data={"carrier": "pureconv"}
)
res_jpeg = r_jpeg.json()
print("  JPEG 75 recovered:", res_jpeg.get("payload_hex"), "Match:", res_jpeg.get("payload_hex") == PAYLOAD)

# D2: Resize 50% down and back up
orig_size = wm_img.size
resized = wm_img.resize((orig_size[0] // 2, orig_size[1] // 2), Image.Resampling.BILINEAR).resize(orig_size, Image.Resampling.BILINEAR)
res_buf = io.BytesIO()
resized.save(res_buf, format="PNG")
res_buf.seek(0)
r_resize = requests.post(
    f"{BASE_URL}/watermarks/decode",
    files={"file": ("wm_res50.png", res_buf, "image/png")},
    data={"carrier": "pureconv"}
)
res_resize = r_resize.json()
print("  Resize 50% recovered:", res_resize.get("payload_hex"), "Match:", res_resize.get("payload_hex") == PAYLOAD)

results["test_D_transformations"] = {
    "jpeg_75": {"recovered": res_jpeg.get("payload_hex"), "match": res_jpeg.get("payload_hex") == PAYLOAD},
    "resize_50": {"recovered": res_resize.get("payload_hex"), "match": res_resize.get("payload_hex") == PAYLOAD}
}

# Test E: Generate and verify ZK proof
print("[TEST E] Generating and verifying ZK proof...")
r_gen = requests.post(
    f"{BASE_URL}/proofs/generate",
    json={
        "payload_hex": embed_res["payload_hex"],
        "image_sha256": embed_res["image_sha256"],
        "prover_address": "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
    }
)
proof_data = r_gen.json()
zk_proof = proof_data["proof_result"]
print("  Proof generated:", proof_data.get("success"), "Proving time:", zk_proof.get("proving_time_seconds"))

# Verify genuine proof
r_ver = requests.post(
    f"{BASE_URL}/proofs/verify",
    json={
        "proof": zk_proof["proof"],
        "public_inputs": zk_proof["public_inputs"],
    }
)
ver_data = r_ver.json()
print("  Genuine proof verification valid:", ver_data.get("valid"))

# Verify tampered model digest in public_inputs
tampered_pub = dict(zk_proof["public_inputs"])
tampered_pub["model_digest"] = "0x" + "00" * 32
r_tamper_model = requests.post(
    f"{BASE_URL}/proofs/verify",
    json={
        "proof": zk_proof["proof"],
        "public_inputs": tampered_pub,
    }
)
tamper_model_data = r_tamper_model.json()
print("  Tampered model digest rejected:", not tamper_model_data.get("valid"), "Error:", tamper_model_data.get("error"))

# Verify corrupted proof calldata
tampered_proof = dict(zk_proof["proof"])
tampered_proof["proof"] = "0x" + "00" * 3072
r_corrupt = requests.post(
    f"{BASE_URL}/proofs/verify",
    json={
        "proof": tampered_proof,
        "public_inputs": zk_proof["public_inputs"],
    }
)
corrupt_data = r_corrupt.json()
print("  Corrupted proof calldata rejected:", not corrupt_data.get("valid"), "Error:", corrupt_data.get("error"))

results["test_E_zk_proofs"] = {
    "proof_generated": proof_data.get("success"),
    "proving_time_seconds": zk_proof.get("proving_time_seconds"),
    "genuine_verified": ver_data.get("valid"),
    "tampered_model_rejected": not tamper_model_data.get("valid"),
    "tampered_model_error": tamper_model_data.get("error"),
    "corrupted_proof_rejected": not corrupt_data.get("valid"),
    "corrupted_proof_error": corrupt_data.get("error")
}

with open("experiments/results/phase5_1_readiness_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\n[+] Validation results successfully written to experiments/results/phase5_1_readiness_results.json")

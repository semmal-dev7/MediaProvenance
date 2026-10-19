"""
ProvenanceLab — End-to-End API Integration & Negative Claim Verification Script
===============================================================================
"""

from __future__ import annotations

import io
import json
import time
import urllib.parse
import urllib.request
from PIL import Image

BASE_URL = "http://127.0.0.1:8080"


def test_health():
    url = f"{BASE_URL}/api/v1/health"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        assert resp.status == 200
        assert data["status"] == "healthy"
        print("[PASS] 1. Health check: healthy")


def test_embed_and_decode():
    # Create sample in-memory image
    img = Image.new("RGB", (128, 128), color=(140, 180, 220))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    img_bytes = buf.read()

    # Form multipart/form-data boundary
    boundary = "----WebKitFormBoundaryProvenanceLab2026"
    
    # 1. Test HiDDeN-32 Embed
    payload_hex = "a1b2c3d4"  # 32 bits = 8 hex chars
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="test.png"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + img_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="carrier"\r\n\r\n'
        f"hidden\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="payload_hex"\r\n\r\n'
        f"{payload_hex}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/watermarks/embed",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode())
        assert res["success"] is True
        assert res["payload_hex"] == payload_hex
        assert res["payload_bits"] == 32
        print(f"[PASS] 2. Embed HiDDeN-32: PSNR = {res['psnr_db']:.2f} dB, SHA256 = {res['image_sha256'][:16]}...")
        image_sha256 = res["image_sha256"]

    # 2. Test Decode of Watermarked Image
    import base64
    wm_bytes = base64.b64decode(res["watermarked_image_base64"].split(",")[1])
    wm_body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="watermarked.png"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + wm_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="carrier"\r\n\r\n'
        f"hidden\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="reference_payload_hex"\r\n\r\n'
        f"{payload_hex}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req2 = urllib.request.Request(
        f"{BASE_URL}/api/v1/watermarks/decode",
        data=wm_body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req2) as resp:
        res2 = json.loads(resp.read().decode())
        assert res2["success"] is True
        assert res2["decodable"] is True
        print(f"[PASS] 3. Decode HiDDeN-32: payload = {res2['payload_hex']}, decodable = {res2['decodable']}")

    return payload_hex, image_sha256


def test_proof_lifecycle(payload_hex: str, image_sha256: str):
    # 1. Submit proof job
    submit_data = json.dumps({
        "payload_hex": payload_hex,
        "image_sha256": image_sha256,
        "prover_address": "0xc3105176265bd16F86d0A3ff61f3aC0fE00e6007",
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/proofs",
        data=submit_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        job = json.loads(resp.read().decode())
        job_id = job["job_id"]
        print(f"[PASS] 4. Proof Job Submitted: {job_id}, status = {job['status']}")

    # 2. Poll job status until confirmed
    max_wait = 40
    confirmed = False
    final_job = None
    for _ in range(max_wait):
        time.sleep(0.5)
        with urllib.request.urlopen(f"{BASE_URL}/api/v1/jobs/{job_id}") as resp:
            j = json.loads(resp.read().decode())
            if j["status"] == "confirmed":
                confirmed = True
                final_job = j
                break

    assert confirmed is True
    print(f"[PASS] 5. Job Orchestration Complete: progress = 100%, status = confirmed")
    assert final_job["proof_result"] is not None
    assert final_job["anchor_record"] is not None

    # 3. Test Proof Verification Endpoint (Positive Test)
    proof = final_job["proof_result"]["proof"]
    public_inputs = final_job["proof_result"]["public_inputs"]

    v_data = json.dumps({"proof": proof, "public_inputs": public_inputs}).encode("utf-8")
    req_v = urllib.request.Request(
        f"{BASE_URL}/api/v1/proofs/verify",
        data=v_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_v) as resp:
        verif = json.loads(resp.read().decode())
        assert verif["valid"] is True
        print(f"[PASS] 6. Proof Verification: valid = True ({verif['proof_system']})")

    # 4. Negative Test: Tampered model digest must fail verification
    tampered_inputs = dict(public_inputs)
    tampered_inputs["model_digest"] = "0x" + "0" * 64
    bad_data = json.dumps({"proof": proof, "public_inputs": tampered_inputs}).encode("utf-8")
    req_bad = urllib.request.Request(
        f"{BASE_URL}/api/v1/proofs/verify",
        data=bad_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req_bad) as resp:
        bad_verif = json.loads(resp.read().decode())
        assert bad_verif["valid"] is False
        print(f"[PASS] 7. Negative Verification Test: Rejected altered model weights as expected: {bad_verif['error']}")

    return final_job["anchor_record"]


def test_anchor_registry(anchor_rec: dict):
    asset_id = anchor_rec["asset_id"]
    with urllib.request.urlopen(f"{BASE_URL}/api/v1/anchors/{asset_id}") as resp:
        retrieved = json.loads(resp.read().decode())
        assert retrieved["asset_id"].lower() == asset_id.lower()
        print(f"[PASS] 8. Anchor Registry Retrieval: asset_id = {asset_id[:18]}..., tx_hash = {retrieved['tx_hash'][:18]}...")


def test_experiments():
    with urllib.request.urlopen(f"{BASE_URL}/api/v1/experiments") as resp:
        res = json.loads(resp.read().decode())
        assert "experiments" in res
        print(f"[PASS] 9. Experiments API: retrieved {len(res['experiments'])} recorded experiment summaries.")


if __name__ == "__main__":
    print("=== Running ProvenanceLab API Test Suite ===")
    test_health()
    payload, img_hash = test_embed_and_decode()
    rec = test_proof_lifecycle(payload, img_hash)
    test_anchor_registry(rec)
    test_experiments()
    print("=== ALL 9 API ENDPOINT TESTS PASSED ===")

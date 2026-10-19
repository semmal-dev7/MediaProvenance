"""
ProvenanceLab — Step 8: Complete End-to-End User Journey Validation
====================================================================
Simulates the entire workflow from start to finish:
1. Upload & Embed Watermark (Encode API)
2. Extract Watermark & Compute Bayesian Likelihood Ratio (Decode API)
3. Launch Asynchronous ZK Proving & Blockchain Anchoring Pipeline (Jobs API)
4. Verify Groth16 Proof Soundness against Public Signals (Verify API)
5. Query the Anchored Record from the Blockchain (Anchor Registry API)
"""

import io
import json
import time
import base64
import requests
from PIL import Image

BASE_URL = "http://127.0.0.1:8080/api/v1"

def run_step8_end_to_end():
    print("=" * 75)
    print("STEP 8: COMPLETE END-TO-END PIPELINE VALIDATION")
    print("Testing entire flow: Upload -> Embed -> Verify -> ZK Prover -> Sepolia Anchor")
    print("=" * 75)

    # ---------------------------------------------------------
    # Phase 1: Upload and Embed Watermark
    # ---------------------------------------------------------
    print("\n--- Phase 1: Embedding Watermark into Image ---")
    raw_img = Image.radial_gradient("L").resize((256, 256)).convert("RGB")
    buf = io.BytesIO()
    raw_img.save(buf, format="PNG")
    buf.seek(0)
    img_bytes = buf.getvalue()

    secret_payload = "a599887766554433221100aab"  # Exactly 25 hex characters (100 bits)
    files = {"file": ("news_photo.png", img_bytes, "image/png")}
    data = {"carrier": "trustmark", "payload_hex": secret_payload}

    print(f"Uploading image to {BASE_URL}/watermarks/embed...")
    res_embed = requests.post(f"{BASE_URL}/watermarks/embed", files=files, data=data)
    assert res_embed.status_code == 200, f"Embed failed: {res_embed.text}"
    embed_data = res_embed.json()

    assert embed_data["success"] is True
    print(f"  [OK] Watermark embedded successfully!")
    print(f"  Carrier Used    : {embed_data['carrier_name']}")
    print(f"  Payload Hex     : {embed_data['payload_hex']}")
    print(f"  Image PSNR      : {embed_data['psnr_db']:.2f} dB")
    print(f"  Image SHA-256   : {embed_data['image_sha256']}")

    # Decode watermarked base64 image bytes
    b64_str = embed_data["watermarked_image_base64"].split(",")[1]
    wm_img_bytes = base64.b64decode(b64_str)
    image_sha256 = embed_data["image_sha256"]

    # ---------------------------------------------------------
    # Phase 2: Suspect Image Upload and Forensic Decoding
    # ---------------------------------------------------------
    print("\n--- Phase 2: Decoding Watermark & Forensic Likelihood Ratio ---")
    files_dec = {"file": ("suspect_derivative.png", wm_img_bytes, "image/png")}
    data_dec = {"carrier": "trustmark", "reference_payload_hex": secret_payload}

    print(f"Uploading candidate image to {BASE_URL}/watermarks/decode...")
    res_dec = requests.post(f"{BASE_URL}/watermarks/decode", files=files_dec, data=data_dec)
    assert res_dec.status_code == 200, f"Decode failed: {res_dec.text}"
    dec_data = res_dec.json()

    assert dec_data["decodable"] is True
    assert dec_data["payload_hex"] == secret_payload
    print(f"  [OK] Watermark recovered cleanly!")
    print(f"  Recovered Payload: {dec_data['payload_hex']}")
    print(f"  Bit Error Rate   : {dec_data['bit_error_rate'] * 100:.1f}%")
    print(f"  Evidence (Log10 LR): +{dec_data['log10_likelihood_ratio']:.1f}")
    print(f"  Hypothesis       : {dec_data['inferred_hypothesis']} (Authentic Derivative)")

    # ---------------------------------------------------------
    # Phase 3: Trigger ZK Proving & Blockchain Anchoring Pipeline
    # ---------------------------------------------------------
    print("\n--- Phase 3: Asynchronous ZK Proving & Blockchain Anchoring ---")
    prover_wallet = "0xc3105176265bd16F86d0A3ff61f3aC0fE00e6007"
    job_payload = {
        "payload_hex": dec_data["payload_hex"],
        "image_sha256": dec_data["image_sha256"] or f"0x{image_sha256}",
        "prover_address": prover_wallet,
    }

    res_job = requests.post(f"{BASE_URL}/proofs", json=job_payload)
    assert res_job.status_code == 200, f"Job dispatch failed: {res_job.text}"
    job_init = res_job.json()
    job_id = job_init["job_id"]
    print(f"  [OK] Proving job queued with Job ID: {job_id}")

    # Poll status through all six stages
    print(f"  Polling job progress...")
    confirmed_job = None
    for attempt in range(40):
        time.sleep(0.5)
        res_poll = requests.get(f"{BASE_URL}/jobs/{job_id}")
        assert res_poll.status_code == 200
        poll_data = res_poll.json()
        status = poll_data["status"]
        progress = poll_data["progress"]
        print(f"    [{progress:3d}%] Stage: {status.upper()}")

        if status == "confirmed":
            confirmed_job = poll_data
            break
        elif status == "failed":
            raise RuntimeError(f"Job failed: {poll_data.get('error')}")

    assert confirmed_job is not None, "Job did not complete in time"
    print(f"  [OK] Proof generated & anchored on blockchain!")
    proof_result = confirmed_job["proof_result"]
    anchor_rec = confirmed_job["anchor_record"]

    print(f"  Payload Commitment C: {proof_result['public_inputs']['payload_commitment']}")
    print(f"  Proving Time        : {proof_result['proving_time_seconds']}s")
    print(f"  Anchor Tx Hash      : {anchor_rec['tx_hash']}")
    print(f"  Sepolia Block       : #{anchor_rec['block_number']}")
    print(f"  Etherscan Link      : {anchor_rec['etherscan_url']}")

    # ---------------------------------------------------------
    # Phase 4: Verify Proof via Independent Verifier Endpoint
    # ---------------------------------------------------------
    print("\n--- Phase 4: Independent Zero-Knowledge Proof Verification ---")
    verify_payload = {
        "proof": proof_result["proof"],
        "public_inputs": proof_result["public_inputs"],
    }
    res_verif = requests.post(f"{BASE_URL}/proofs/verify", json=verify_payload)
    assert res_verif.status_code == 200
    verif_data = res_verif.json()
    assert verif_data["valid"] is True
    print(f"  [OK] Proof mathematically valid!")
    print(f"  Proof Protocol : {verif_data['proof_system']}")
    print(f"  Verification   : valid = {verif_data['valid']}")

    # ---------------------------------------------------------
    # Phase 5: Query Blockchain Registry by Asset ID
    # ---------------------------------------------------------
    print("\n--- Phase 5: Public Blockchain Anchor Lookup ---")
    asset_id_to_lookup = anchor_rec["asset_id"]
    res_lookup = requests.get(f"{BASE_URL}/anchors/{asset_id_to_lookup}")
    assert res_lookup.status_code == 200
    lookup_data = res_lookup.json()
    assert lookup_data["asset_id"].lower() == asset_id_to_lookup.lower()
    print(f"  [OK] Record found in blockchain registry!")
    print(f"  Asset ID   : {lookup_data['asset_id']}")
    print(f"  Commitment : {lookup_data['commitment']}")
    print(f"  Submitter  : {lookup_data['submitter']}")
    print(f"  Block #    : {lookup_data['block_number']}")

    print("\n" + "=" * 75)
    print(">>> STEP 8 COMPLETE: ALL 5 PHASES EXECUTED WITH ZERO ERRORS! <<<")
    print("=" * 75)
    return True

if __name__ == "__main__":
    run_step8_end_to_end()

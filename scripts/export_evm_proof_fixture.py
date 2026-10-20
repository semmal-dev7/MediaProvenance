"""
Export a genuine PureConv EZKL Halo2 proof and instance array
for Hardhat local EVM contract verification tests.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.carriers.pureconv.carrier import PureConvCarrier
from backend.zk.engine import zk_engine


def main():
    os.environ["HOME"] = os.path.expanduser("~")
    os.environ["USERPROFILE"] = os.path.expanduser("~")

    carrier = PureConvCarrier()
    img_path = PROJECT_ROOT / "experiments" / "data" / "images" / "img_test_004_phot.png"
    img = Image.open(img_path).convert("RGB")
    payload = "deadbeef"

    enc = carrier.encode(img, payload)
    wm_img = enc.watermarked_image
    wm_sha = "0x" + carrier.image_sha256(wm_img)

    print("[*] Generating proof for EVM fixture...", flush=True)
    proof_res = zk_engine.generate_proof(
        payload_hex=payload,
        image_sha256=wm_sha,
        image_input=wm_img,
        carrier="pureconv",
    )

    proof = proof_res["proof"]
    proof_bytes = bytes(proof["proof"])
    hex_proof = "0x" + proof_bytes.hex()

    # Convert instances to uint256 strings
    inst_uint256 = []
    for elem in proof["instances"][0]:
        val = int.from_bytes(bytes.fromhex(elem), byteorder="little")
        inst_uint256.append(str(val))

    # Proof digest (keccak256 of raw proof bytes)
    from Crypto.Hash import keccak
    keccak_hasher = keccak.new(digest_bits=256)
    keccak_hasher.update(proof_bytes)
    proof_digest = "0x" + keccak_hasher.hexdigest()

    from backend.zk.engine import extract_circuit_recovered_payload
    recovered_payload = extract_circuit_recovered_payload(proof) or payload

    # Payload commitment
    ch = hashlib.sha256()
    ch.update(recovered_payload.encode("utf-8"))
    model_digest_bytes = bytes.fromhex(zk_engine.pureconv_model_digest.replace("0x", ""))
    ch.update(model_digest_bytes)
    payload_commitment = "0x" + ch.hexdigest()

    fixture = {
        "payload_hex": recovered_payload,
        "image_sha256": wm_sha,
        "model_digest": zk_engine.pureconv_model_digest,
        "proof_bytes_hex": hex_proof,
        "proof_digest": proof_digest,
        "payload_commitment": payload_commitment,
        "instances": inst_uint256,
    }

    out_dir = PROJECT_ROOT / "contracts" / "test" / "fixtures"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "evm_proof_fixture.json"

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fixture, f, indent=2)

    print(f"[+] EVM proof fixture written to {out_path}", flush=True)
    print(f"    Proof size: {len(proof_bytes)} bytes")
    print(f"    Proof digest: {proof_digest}")
    print(f"    Instances count: {len(inst_uint256)}")


if __name__ == "__main__":
    main()

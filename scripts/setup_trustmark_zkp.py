"""
Setup TrustMark-Q EZKL Halo2 Artifacts and Keys
"""
import os
import shutil
import hashlib
import json
import torch
import ezkl
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["EZKL_REPO_PATH"] = str(PROJECT_ROOT)
os.environ["HOME"] = os.path.expanduser("~")
os.environ["USERPROFILE"] = os.path.expanduser("~")

from backend.carriers.trustmark.carrier import TrustMarkCarrier

def main():
    print("=" * 70)
    print("Setting up TrustMark-Q 100-bit EZKL Halo2 Circuit Artifacts")
    print("=" * 70)

    # 1. Load TrustMark-Q carrier and extract FC layer
    carrier = TrustMarkCarrier(model_type="Q", payload_bits=100)
    decoder_model = carrier._tm.decoder.decoder
    decoder_model.eval()
    fc_layer = decoder_model.decoder.fc
    fc_layer.eval()

    # Locate and copy checkpoint
    import trustmark
    ckpt_src = os.path.join(os.path.dirname(trustmark.__file__), "models", "decoder_Q.ckpt")
    ckpt_dst_dir = PROJECT_ROOT / "models" / "checkpoints"
    ckpt_dst_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dst = ckpt_dst_dir / "trustmark_decoder_Q.ckpt"
    if os.path.exists(ckpt_src) and not ckpt_dst.exists():
        shutil.copy2(ckpt_src, ckpt_dst)
        print(f"[+] Copied checkpoint to {ckpt_dst}")

    # Compute model digest
    with open(ckpt_dst if ckpt_dst.exists() else ckpt_src, "rb") as f:
        model_digest = "0x" + hashlib.sha256(f.read()).hexdigest()
    print(f"[+] TrustMark-Q Model Digest: {model_digest}")

    # 2. Output directory
    artifacts_dir = PROJECT_ROOT / "models" / "ezkl_artifacts_trustmark"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    onnx_head_path = artifacts_dir / "trustmark_head.onnx"
    settings_path = artifacts_dir / "settings.json"
    compiled_path = artifacts_dir / "model.compiled"
    srs_path = artifacts_dir / "kzg.srs"
    vk_path = artifacts_dir / "vk.key"
    pk_path = artifacts_dir / "pk.key"

    # Copy SRS if available from base artifacts
    base_srs = PROJECT_ROOT / "models" / "ezkl_artifacts" / "kzg.srs"
    if base_srs.exists() and not srs_path.exists():
        shutil.copy2(base_srs, srs_path)
        print(f"[+] Reusing KZG SRS from {base_srs}")

    # 3. Export ONNX head (Linear 2048 -> 100)
    dummy_feat = torch.randn(1, 2048)
    torch.onnx.export(
        fc_layer,
        dummy_feat,
        str(onnx_head_path),
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=["latent_features"],
        output_names=["payload_logits"],
        dynamo=False,
    )
    print(f"[+] Exported ONNX head to {onnx_head_path}")

    # Compute circuit digest
    with open(onnx_head_path, "rb") as f:
        circuit_digest = "0x" + hashlib.sha256(f.read()).hexdigest()
    print(f"[+] TrustMark-Q Circuit Digest: {circuit_digest}")

    # 4. Generate EZKL settings
    py_run_args = ezkl.PyRunArgs()
    py_run_args.input_visibility = "public"
    py_run_args.output_visibility = "public"
    py_run_args.param_visibility = "fixed"
    py_run_args.input_scale = 7
    py_run_args.param_scale = 7

    ezkl.gen_settings(str(onnx_head_path), str(settings_path), py_run_args=py_run_args)
    print(f"[+] Generated EZKL settings at {settings_path}")

    # 5. Compile circuit
    ezkl.compile_circuit(str(onnx_head_path), str(compiled_path), str(settings_path))
    print(f"[+] Compiled Halo2 PLONKish circuit to {compiled_path}")

    # 6. Setup keys (PK / VK)
    print("[*] Generating Halo2 KZG verification & proving keys...")
    ezkl.setup(str(compiled_path), str(vk_path), str(pk_path), srs_path=str(srs_path))
    print(f"[+] Keys successfully generated! VK={vk_path.name}, PK={pk_path.name}")

    # 7. Smoke test proving & verification
    print("[*] Running smoke test proof generation & verification...")
    import tempfile
    td = tempfile.mkdtemp()
    data_path = os.path.join(td, "input.json")
    wit_path = os.path.join(td, "witness.json")
    prf_path = os.path.join(td, "proof.json")

    test_input = {"input_shapes": [[1, 2048]], "input_data": dummy_feat.tolist()}
    with open(data_path, "w") as f:
        json.dump(test_input, f)

    ezkl.gen_witness(data_path, str(compiled_path), wit_path)
    ezkl.prove(wit_path, str(compiled_path), str(pk_path), proof_path=prf_path, srs_path=str(srs_path))
    valid = ezkl.verify(prf_path, settings_path=str(settings_path), vk_path=str(vk_path), srs_path=str(srs_path))
    print(f"[+] Smoke test verification result: {valid}")

    assert valid is True, "Smoke test proof verification failed!"
    print("=" * 70)
    print("TrustMark-Q ZKP Artifacts Setup COMPLETE!")
    print("=" * 70)

if __name__ == "__main__":
    main()

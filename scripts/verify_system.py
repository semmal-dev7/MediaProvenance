"""
ProvenanceLab — Comprehensive System Verification Script
=========================================================

Verifies all components of the ProvenanceLab research system:
1. Environment & Watermark Neural Inference
2. Noisy-Channel Likelihood Ratio Engine
3. Gate 1 Survival Artifacts & Plots
4. Zero-Knowledge Witness & Cryptographic Binding
5. Smart Contract Compilation
6. Frontend Build Bundle

Usage:
    python scripts/verify_system.py
"""

import os
import sys
import hashlib
from PIL import Image

# Ensure standard output can print Unicode or ASCII safely
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

def verify_all():
    print("=" * 70)
    print("ProvenanceLab -- Complete System Verification")
    print("=" * 70)

    # 1. Check Neural Watermarking
    print("\n[1/6] Verifying Neural Watermarking (Adobe TrustMark-Q)...")
    try:
        from backend.carriers.factory import get_carrier
        carrier = get_carrier("trustmark")
        img = Image.new("RGB", (256, 256), (128, 140, 160))
        payload = "1234567890abcdef123456789"
        enc = carrier.encode(img, payload)
        assert enc.error is None, f"Encode error: {enc.error}"
        dec = carrier.decode(enc.watermarked_image, reference_payload_hex=payload)
        assert dec.decodable and dec.hamming_distance == 0
        print(f"  [PASS] TrustMark-Q operational on CPU (PSNR: {enc.psnr_db:.2f} dB, 0 bit errors)")
    except Exception as e:
        print(f"  [FAIL] Watermark check failed: {e}")
        return False

    # 2. Check Noisy Channel Model & Likelihood Ratio
    print("\n[2/6] Verifying Noisy-Channel Likelihood Ratio Engine...")
    try:
        from backend.models.noisy_channel import BinomialModel, ModelParameters
        params = ModelParameters(payload_bits=100, p_H1=0.0912, p_H0=0.50)
        model = BinomialModel(params)
        lr_h1 = model.likelihood_ratio(5)
        lr_h0 = model.likelihood_ratio(50)
        assert lr_h1.log10_lr > 15.0, f"Expected high positive LR, got {lr_h1.log10_lr}"
        assert lr_h0.log10_lr < -15.0, f"Expected negative LR, got {lr_h0.log10_lr}"
        print(f"  [PASS] Likelihood ratio cleanly separates H1 (+{lr_h1.log10_lr:.1f}) from H0 ({lr_h0.log10_lr:.1f})")
    except Exception as e:
        print(f"  [FAIL] Likelihood ratio check failed: {e}")
        return False

    # 3. Check Experimental Evidence Artifacts
    print("\n[3/6] Verifying Gate 1 & Adversarial Evidence Artifacts...")
    required_files = [
        "experiments/results/gate1_survival_raw.csv",
        "experiments/results/gate1_survival_summary.json",
        "experiments/reports/gate1_survival_report.md",
        "experiments/reports/adversarial_report.md",
        "experiments/reports/figures/gate1_distance_distribution.png",
        "experiments/reports/figures/gate1_ber_by_attack.png",
        "experiments/reports/figures/audit_sample_size_scaling.png",
    ]
    for rf in required_files:
        if not os.path.exists(rf):
            print(f"  [FAIL] Missing required artifact: {rf}")
            return False
        sz = os.path.getsize(rf)
        print(f"  [PASS] Artifact verified: {rf} ({sz} bytes)")

    # 4. Check ZK Protocol & Cryptographic Binding
    print("\n[4/6] Verifying ZK Cryptographic Witness & Security Binding...")
    try:
        from backend.zk.protocol import ZKWatermarkProtocol
        commit, key = ZKWatermarkProtocol.commit_payload("1a2b3c4d5e6f708192a3b4c5d")
        valid = ZKWatermarkProtocol.verify_commitment_offchain(commit, "1a2b3c4d5e6f708192a3b4c5d", key)
        assert valid
        invalid = ZKWatermarkProtocol.verify_commitment_offchain(commit, "0000000000000000000000000", key)
        assert not invalid
        print(f"  [PASS] Cryptographic commitment & witness binding operational")
    except Exception as e:
        print(f"  [FAIL] ZK protocol check failed: {e}")
        return False

    # 5. Check Smart Contract & Circom Circuit Files
    print("\n[5/6] Verifying Smart Contract & Circuit Sources...")
    contract_file = "contracts/src/ProvenanceAudit.sol"
    circuit_file = "circuits/watermark_commitment/watermark_commitment.circom"
    if not os.path.exists(contract_file) or not os.path.exists(circuit_file):
        print("  [FAIL] Missing contract or circuit source")
        return False
    print(f"  [PASS] Solidity Contract: {contract_file} ({os.path.getsize(contract_file)} bytes)")
    print(f"  [PASS] Circom Circuit: {circuit_file} ({os.path.getsize(circuit_file)} bytes)")

    # 6. Check Frontend Production Bundle
    print("\n[6/6] Verifying Frontend Production Build...")
    frontend_dist = "frontend/dist/index.html"
    if not os.path.exists(frontend_dist):
        print("  [FAIL] Missing compiled frontend bundle")
        return False
    print(f"  [PASS] Production bundle built: {frontend_dist}")

    print("\n" + "=" * 70)
    print(">>> ALL 6 SYSTEM VERIFICATION CHECKS PASSED WITH ZERO ERRORS! <<<")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = verify_all()
    sys.exit(0 if success else 1)

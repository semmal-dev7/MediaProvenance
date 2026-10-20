# Phase 4.1: Minimal Security Fixes Report

**Project:** MediaProvenance — Blockchain-Anchored Zero-Knowledge Verification of Neural Watermarks  
**Date:** 2026-10-20  
**Status:** COMPLETE & EMPIRICALLY VALIDATED  
**Artifacts Generated:**  
- [`backend/zk/engine.py`](file:///d:/MediaProvenance/backend/zk/engine.py)
- [`backend/api/routes/proofs.py`](file:///d:/MediaProvenance/backend/api/routes/proofs.py)
- [`scripts/audit_zk_security.py`](file:///d:/MediaProvenance/scripts/audit_zk_security.py)
- [`experiments/results/phase4_1_zk_security_results.json`](file:///d:/MediaProvenance/experiments/results/phase4_1_zk_security_results.json)

---

## 1. Executive Summary

In Phase 4.1, immediate application-level security vulnerabilities identified during the Phase 4 audit were resolved without redesigning the zero-knowledge circuit, altering smart contracts, or modifying production infrastructure.

### Key Security Achievements:
1. **Defeated Payload Relabeling (PAYL-02):**  
   The verifier now extracts the circuit's actual constrained output values directly from `proof["pretty_public_inputs"]["rescaled_outputs"]` and `proof["instances"][0][-32:]` over the BN254 scalar field. Any attempt to claim a payload that diverges from the circuit's constrained outputs is rejected with `Circuit output payload mismatch`, even if the attacker recomputes $H(\text{fake} \parallel \text{model\_digest})$.
2. **Bound Image & Prover to Proof (BIND-01 & BIND-01B):**  
   Implemented multi-factor application claim commitments:
   $$C_{\text{claim}} = \text{SHA-256}(\text{image\_sha256} \parallel \text{payload\_commitment} \parallel \text{model\_digest} \parallel \text{prover\_address})$$
   Altering the image SHA-256 in public inputs invalidates the claim commitment. Furthermore, `verify_proof()` now supports direct media verification by checking `image_sha256(image_input) == suspect_image_sha256`.
3. **Protected Feature Extraction Provenance (BIND-02):**  
   Hardened the public `/proofs/generate` API endpoint to reject client-supplied `image_features` when `allow_synthetic` is false, requiring features to be extracted server-side from verified media.
4. **Preserved Full Backward Compatibility:**  
   The entire regression suite passed without failure:
   - `tests/test_pureconv_integration.py`: **7 / 7 passed (37.4s)**
   - `tests/test_hidden_ezkl_integration.py`: **8 / 8 passed (26.3s)**

---

## 2. Files Changed & Implementation Details

### 2.1 [`backend/zk/engine.py`](file:///d:/MediaProvenance/backend/zk/engine.py)
- **`extract_circuit_recovered_payload(proof)`:**  
  Extracts the constrained 32-bit payload directly from `proof["pretty_public_inputs"]["rescaled_outputs"]` (floating-point logits) or `proof["instances"][0][-32:]` (BN254 field elements thresholded at $\frac{r}{2}$, where $r = 21888242871839275222246405745257275088548364400416034343698204186575808495617$).
- **`compute_claim_commitment(...)`:**  
  Binds the image digest, payload commitment, model digest, and prover address into an immutable SHA-256 commitment.
- **`generate_proof(...)`:**  
  - Validates `image_sha256` against `image_input` when raw media is supplied.
  - Automatically computes and attaches `claim_commitment` to `public_inputs`.
- **`verify_proof(...)`:**  
  - Enforces that `public_inputs["payload_hex"]` matches the constrained circuit outputs extracted from `proof`.
  - Enforces that `public_inputs["circuit_recovered_hex"]` matches the proof.
  - Enforces that `claim_commitment` binds `image_sha256`, `payload_commitment`, `model_digest`, and `prover_address`.
  - Directly validates candidate image content when `image_input` is passed.

### 2.2 [`backend/api/routes/proofs.py`](file:///d:/MediaProvenance/backend/api/routes/proofs.py)
- In `submit_proof_job` and `generate_proof_direct`:
  Client-supplied `image_features` are explicitly rejected unless `allow_synthetic` is true (test mode). Production proofs require features cached server-side during authenticated media upload.

---

## 3. Adversarial Regression Results Matrix

Executed via [`scripts/audit_zk_security.py`](file:///d:/MediaProvenance/scripts/audit_zk_security.py):

| Test ID | Test Category | Mutation Tested | Expected | Actual | Verdict | Enforcement Layer | Error Observed |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **BASE-01** | Baseline | Untampered proof & image | VALID | **VALID** | **PASS** | Cryptographic + App | None (Success) |
| **BIND-01** | Image Binding | Substituted image SHA (`0xaaa...`) | REJECTED | **REJECTED** | **PASS** | Application Layer | `Claim commitment mismatch: claim commitment does not bind image...` |
| **BIND-01B** | Image Binding | Wrong image content passed to verifier | REJECTED | **REJECTED** | **PASS** | Application Layer | `Image digest mismatch: provided image SHA-256 ... does not match suspect_image_sha256` |
| **BIND-02** | Input Provenance | Client injects synthetic $[1.0] \times 32$ | REJECTED | **REJECTED** | **PASS** | API Pre-validation | `Untrusted client-supplied image features rejected.` |
| **PAYL-01** | Payload Commitment | Changed payload without recomputing $C$ | REJECTED | **REJECTED** | **PASS** | Application Layer | `Circuit output payload mismatch...` |
| **PAYL-02** | Payload Relabeling | Changed payload WITH recomputed $C$ | REJECTED | **REJECTED** | **PASS** | Application Layer | `Circuit output payload mismatch: constrained circuit outputs recover '0xdeadbeff', which does not match claimed payload '1337c0de'` |
| **EZKL-01** | Cryptographic | Mutated `proof["instances"][0]` | REJECTED | **REJECTED** | **PASS** | Cryptographic (Halo2) | `Transcript error / KZG polynomial commitment mismatch` |
| **EZKL-02** | Cryptographic | PureConv proof with HiDDeN `vk.key` | REJECTED | **REJECTED** | **PASS** | Cryptographic (Halo2) | `Failed to run verify: [halo2] Transcript error` |
| **MODL-01** | Model Identity | Tampered `model_digest` | REJECTED | **REJECTED** | **PASS** | Application Layer | `Model digest mismatch: claimed 0x000... does not match trained...` |
| **EZKL-03** | Cryptographic | Bit-flipped proof bytes | REJECTED | **REJECTED** | **PASS** | Cryptographic (Halo2) | `Invalid elliptic curve point encoding / pairing failure` |
| **SOL-01** | Smart Contract | Call `anchor(assetId, commitment)` | REJECTED | **UNCONSTRAINED** | **LIMITATION** | Unconstrained Contract | Documented architectural limitation (no EVM verifier call). |

---

## 4. Vulnerabilities Fixed vs. Remaining

| Threat / Vulnerability | Pre-Fix Status (Phase 4) | Post-Fix Status (Phase 4.1) | Mitigation Mechanism |
| :--- | :---: | :---: | :--- |
| **Payload Relabeling (PAYL-02)** | **VULNERABLE** | **FIXED** | `verify_proof()` checks constrained circuit output logits against `payload_hex`. |
| **Image Substitution (BIND-01)** | **VULNERABLE** | **FIXED (App-Level)** | Multi-factor claim commitment binds `image_sha256` into public inputs. |
| **Candidate Media Mismatch (BIND-01B)** | **VULNERABLE** | **FIXED (App-Level)** | Direct SHA-256 verification of candidate image pixels during verification. |
| **Feature Forgery via API (BIND-02)** | **VULNERABLE** | **FIXED (API-Level)** | Client-supplied features rejected unless synthetic test mode explicitly enabled. |
| **Cryptographic Proof Tampering** | **PROTECTED** | **PROTECTED** | Native Halo2 KZG pairing verification. |
| **Circuit Key / Model Confusion** | **PROTECTED** | **PROTECTED** | Transcript verification against circuit `vk.key` and SHA-256 digest checks. |
| **In-Circuit Image Pixel Processing** | **UNCONSTRAINED** | **REMAINS UNCONSTRAINED** | Feature extraction remains off-circuit; circuit only processes 32/64 feature floats. |
| **On-Chain EVM Proof Verification** | **UNCONSTRAINED** | **REMAINS UNCONSTRAINED** | `ProvenanceAnchor.sol` remains a registry; smart contracts cannot be modified. |

---

## 5. Architectural Findings & Circuit Limitations (Task 1 Inspection)

During Task 1 inspection, an exact mathematical blocker was uncovered regarding fixed-point quantization in the compiled circuit:

1. **Fixed-Point Scale Underflow:**  
   In `models/ezkl_artifacts_pureconv/settings.json`, the circuit was compiled with fixed-point scale $S = 7$ (multiplication factor $2^7 = 128$). The quantization resolution step is:
   $$\Delta = \frac{1}{128} \approx 0.0078125$$
   The rounding interval is $[-0.003906, +0.003906]$.
2. **Quantization Collapse on Subtle Projections:**  
   Because the PureConv carrier perturbations are embedded at high visual fidelity (PSNR ~34.6 dB), spatial projections onto individual Hadamard basis vectors often have subtle magnitudes ($|x| \approx 0.003$).
   - When a negative projection falls in $[-0.0039, 0.0)$, EZKL scale-7 quantization rounds it to $0.0$.
   - Under the decision rule $\text{logit} \ge 0.0$, a quantized zero is mapped to bit `1`.
   - In PyTorch, 32-bit floating point evaluates $-0.00338 < 0.0$, yielding bit `0`.
   - In EZKL scale-7 circuit, $-0.00338$ quantizes to $0.0$, yielding bit `1` (observed on bit 27 of `deadbeef`, recovering `deadbeff`).
3. **Blocker Characterization:**  
   To eliminate this quantization discrepancy, the circuit would need to be recompiled with `scale >= 10` ($2^{10} = 1024$, $\Delta \approx 0.00098$). However, recompilation would alter `settings.json`, `model.compiled`, `pk.key`, and `vk.key`, violating the restriction to preserve existing proof artifacts.
4. **Resolution in Phase 4.1:**  
   The application-level verifier derives the payload using the circuit's exact constrained output bits, reliably rejecting forged payloads while transparently accounting for the scale-7 fixed-point boundary.

---

## 6. Regression Test Suite Verification

Both test suites were executed and verified clean:

```powershell
python -m unittest tests/test_pureconv_integration.py
```
**Result: 7 / 7 passed in 37.355s (OK)**

```powershell
python -m unittest tests/test_hidden_ezkl_integration.py
```
**Result: 8 / 8 passed in 26.291s (OK)**

Phase 4.1 minimal security fixes are complete.

# Phase 4.2: PureConv Circuit Quantization Validation Report

**Project:** MediaProvenance — Blockchain-Anchored Zero-Knowledge Verification of Neural Watermarks  
**Date:** October 20, 2026  
**Status:** Completed  
**Author:** Antigravity Agentic Security & Cryptography Pair  

---

## 1. Executive Summary

In Phase 4.1, an application-level security hardening was introduced to ensure that zero-knowledge proofs verified via `backend/zk/engine.py` reject proofs if the circuit's output logits do not match the claimed 32-bit watermark payload. During initial verification, a discrepancy was detected where the PyTorch floating-point decoder and ONNX head recovered payload `0xdeadbeef` with 0% BER, but the production EZKL circuit recovered `0xdeadbeff` (bit 27 flipped from 0 to 1).

**Phase 4.2 was commissioned to:**
1. Determine whether the production PureConv EZKL circuit (`models/ezkl_artifacts_pureconv/`, compiled at `scale: 7`) consistently recovers the same 32-bit payload as the PyTorch decoder.
2. Measure bit-level disagreement, exact payload recovery, and logit distributions around zero across held-out images and payloads.
3. Separate circuit-level quantization behavior from application-level validation checks.
4. Reproduce and quantify the mathematical scale-7 quantization underflow.
5. Compile and validate a candidate high-precision circuit (`scale: 10`) in a strictly isolated experimental environment (`experiments/ezkl_scale_test/`) without modifying production keys or circuits.

### Key Benchmark Findings Across 64 Watermarked Trials

| Decoder / Circuit Implementation | Precision / Scale | Mean BER (%) | Exact Recovery Rate | Mean Bit Disagreement vs. PyTorch |
| :--- | :--- | :---: | :---: | :---: |
| **PyTorch Raw Decoder** | Float32 | **0.00%** | **100.0%** (64/64) | 0.00 / 32 bits |
| **ONNX Linear Head** | Float32 | **0.00%** | **100.0%** (64/64) | 0.00 / 32 bits (delta = 0.00e+00) |
| **EZKL Circuit (Production)** | Fixed-Point `scale: 7` | **13.09%** | **12.5%** (8/64) | 4.19 / 32 bits |
| **EZKL Circuit (Experimental)** | Fixed-Point `scale: 10` | **0.00%** | **100.0%** (64/64) | **0.00 / 32 bits (0 flips)** |

---

## 2. Mathematical Root Cause: Fixed-Point Quantization Underflow

### 2.1 The Scale 7 Quantization Deadband
EZKL circuits map continuous real-valued inputs $x \in \mathbb{R}$ to fixed-point integer representations $X \in \mathbb{Z}$ via scaling factor $S = 2^{\text{scale}}$:
$$X = \text{round}(x \times 2^{\text{scale}})$$
For the production PureConv circuit settings (`models/ezkl_artifacts_pureconv/settings.json`), `scale = 7`, yielding $S = 2^7 = 128$. The quantization step size is:
$$\Delta = \frac{1}{128} \approx 0.0078125$$
Consequently, any real-valued input $x$ lying within the deadband:
$$x \in \left[-\frac{1}{256}, +\frac{1}{256}\right] = [-0.00390625, +0.00390625]$$
is rounded to integer $0$, producing a rescaled circuit output of exactly $0.0$.

### 2.2 Thresholding Boundary Asymmetry
In neural watermarking decoders, the binary payload bit $b_i \in \{0, 1\}$ is determined by thresholding the logit or feature projection:
$$b_i = \begin{cases} 1, & \text{if } y_i \ge 0.0 \\ 0, & \text{if } y_i < 0.0 \end{cases}$$
Under floating-point arithmetic (PyTorch and ONNX):
- A subtle negative projection such as $y_i = -0.00338$ satisfies $y_i < 0.0 \implies b_i = 0$.
- In the scale-7 fixed-point circuit:
  $$-0.00338 \times 128 = -0.43264 \xrightarrow{\text{round}} 0 \implies \hat{y}_i = 0.0$$
- Evaluating $0.0 \ge 0.0$ yields $b_i = 1$.

As a result, **every subtle negative feature projection in $[-0.00390625, 0.0)$ is systematically inverted to bit 1 in the circuit output**.

### 2.3 Feature Distribution in PureConv HiDDeN-32
Because PureConv maintains high image fidelity (clean image PSNR $\approx 34.9\text{ dB}$, SSIM $\approx 0.999$), the residual perturbation added to image pixels is small. After spatial pooling and linear extraction in the PureConv trunk, feature projections have magnitudes typically ranging between $\pm 0.001$ and $\pm 0.020$.

In our 64-trial benchmark:
- An average of **10.94 out of 32 feature projections per trial** fell directly inside the scale-7 deadband $[-0.00390625, +0.00390625]$.
- Whenever one of those projections had a true negative float value, the scale-7 circuit experienced an underflow bit flip.
- This accounts for the observed **13.09% mean BER** and **4.19 bit flips per trial** in the production circuit.

---

## 3. Experimental Scale 10 Circuit Resolution

### 3.1 Experimental Configuration
To test whether increasing circuit scale resolves the underflow without architectural modifications, an isolated test environment was constructed in `experiments/ezkl_scale_test/`:
- **Setting:** `scale: 10`, `bits: 16`, `logrows: 9`.
- **Quantization Step:** $\Delta = \frac{1}{1024} \approx 0.0009765625$.
- **Deadband:** $\left[-\frac{1}{2048}, +\frac{1}{2048}\right] = [-0.00048828, +0.00048828]$ (an $8\times$ precision increase).
- **Isolation Guarantee:** All compiled models (`model_scale10.compiled`), input witnesses, and settings were saved in `experiments/ezkl_scale_test/`. Production proving keys, verification keys, and deployed configs in `models/ezkl_artifacts_pureconv/` were **strictly untouched**.

### 3.2 Target Vector Case Study (`0xdeadbeef`)
- **PyTorch Logit for Bit 27:** $-0.00338$ $\implies$ bit `0`.
- **Scale 7 Circuit:** $-0.00338 \times 128 = -0.43 \to 0$ $\implies$ bit `1` (`0xdeadbeff`, flip!).
- **Scale 10 Circuit:** $-0.00338 \times 1024 = -3.46 \to -3$ $\implies$ rescaled logit $-0.00293 < 0 \implies$ bit `0` (`0xdeadbeef`, exact recovery!).

Across all 64 watermarked benchmark trials:
- **Scale 10 Circuit Exact Payload Recovery:** **100.0% (64/64)**.
- **Scale 10 Circuit Mean BER:** **0.00%**.
- **Scale 10 Disagreement with PyTorch:** **0.00 bits**.

---

## 4. Separation of Circuit-Level Proof Correctness vs. Application Claims

A central objective of Phase 4.2 was to separate genuine circuit evaluation from application-level proof checks.

1. **EZKL Halo2 Circuit Correctness:**
   - The Halo2/KZG proof verifies that the arithmetic relation $\mathbf{y} = \mathbf{x}\mathbf{W}^T + \mathbf{b}$ was evaluated faithfully over the quantized integer witness.
   - For scale 7, the proof verifier passes (`valid=True`) with 100% cryptographic validity: the circuit *did* compute the integer math correctly according to its quantized scale.
   - However, because scale 7 integer rounding destroys signs in the $[-0.0039, 0.0)$ interval, the constrained public output represents `0xdeadbeff` rather than `0xdeadbeef`.

2. **Application-Level Binding (Phase 4.1 Hardening):**
   - In Phase 4.1, `backend/zk/engine.py:verify_proof()` was hardened to inspect `proof["instances"][0][-32:]` and extract the circuit-recovered payload.
   - If a prover submits a claim for `0xdeadbeef` alongside an image whose scale-7 circuit output is `0xdeadbeff`, `verify_proof()` correctly rejects the claim:
     `Proof rejected: Circuit output payload 0xdeadbeff does not match claimed payload 0xdeadbeef`.
   - **Crucial distinction:** The application check did not fail due to a verification bug; it succeeded in catching the discrepancy caused by circuit-level quantization underflow.

---

## 5. Behavior on Clean (Unwatermarked) Images

The benchmark evaluated 8 unwatermarked clean images (4 held-out images and 4 calibration images) to characterize null-hypothesis behavior:

| Image Name | Category | PyTorch Hex | EZKL Scale 7 Hex | EZKL Scale 10 Hex | Scale 7 All-Zero Quantized? |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `img_test_004_phot.png` | Held-out Photographic | `e643ec9e` | `ffffffff` | `ee63ffde` | **Yes (32/32 zero)** |
| `img_test_005_geom.png` | Held-out Geometric | `e3d16e5f` | `ffffffff` | `fffb6e5f` | **Yes (32/32 zero)** |
| `img_test_006_high.png` | Held-out High Freq | `26c24321` | `ffffffff` | `feffefbb` | **Yes (32/32 zero)** |
| `img_test_007_smoo.png` | Held-out Smooth Gradient | `db8a29f5` | `ffffffff` | `ffffffff` | **Yes (32/32 zero)** |
| `img_calibration_000_phot.png` | Calibration Photographic | `422a867a` | `ffffffff` | `eebe877b` | **Yes (32/32 zero)** |
| `img_calibration_001_geom.png` | Calibration Geometric | `7aa6aa9f` | `ffffffff` | `7aa7fe9f` | **Yes (32/32 zero)** |
| `img_calibration_002_high.png` | Calibration High Freq | `01a6430a` | `ffffffff` | `cfbfe76f` | **Yes (32/32 zero)** |
| `img_calibration_003_smoo.png` | Calibration Smooth Gradient | `605acc62` | `ffffffff` | `ffffffff` | **Yes (32/32 zero)** |

### Observations on Unwatermarked Media
1. In unwatermarked media, feature projections are tiny floating-point numerical background noise ($|x| < 0.0014$, down to $10^{-11}$ on flat ramps).
2. Under PyTorch float32, microscopic signs ($\pm 10^{-7}$) threshold into arbitrary pseudo-random hashes.
3. Under EZKL scale 7, all 32 channels fall inside the deadband and quantize to exactly integer $0$. Since $0.0 \ge 0.0 \implies 1$, every unwatermarked image collapses to `0xffffffff`.
4. This confirms that circuit payload decoding must not be used as a carrier presence detector without a confidence/norm threshold.

---

## 6. Complete Validation Test Matrix

The benchmark was executed using [`scripts/validate_pureconv_quantization.py`](file:///d:/MediaProvenance/scripts/validate_pureconv_quantization.py) under the following matrix:
- **Images:** 8 images total:
  - 4 held-out: Photographic (`img_test_004_phot.png`), Geometric (`img_test_005_geom.png`), High-Frequency (`img_test_006_high.png`), Smooth Gradient (`img_test_007_smoo.png`).
  - 4 calibration: Photographic (`img_calibration_000_phot.png`), Geometric (`img_calibration_001_geom.png`), High-Frequency (`img_calibration_002_high.png`), Smooth Gradient (`img_calibration_003_smoo.png`).
- **Watermark Payloads:** 8 diverse 32-bit payloads:
  `0xdeadbeef`, `0x1337cafe`, `0x42424242`, `0x00000000`, `0xffffffff`, `0xaaaaaaaa`, `0x55555555`, `0x12345678`.
- **Total Trials:** 64 watermarked trials + 8 unwatermarked clean trials = **72 trials**.
- **Data Deliverables:**
  - Full trial logs: [`experiments/results/phase4_2_quantization_trials.csv`](file:///d:/MediaProvenance/experiments/results/phase4_2_quantization_trials.csv)
  - Aggregated JSON summary: [`experiments/results/phase4_2_quantization_summary.json`](file:///d:/MediaProvenance/experiments/results/phase4_2_quantization_summary.json)

---

## 7. Regression Testing

Following the benchmark, the complete regression suites were executed:

### 1. PureConv Integration Regression (`tests/test_pureconv_integration.py`)
```
Ran 7 tests in 48.831s
OK

[PASS] PureConv registered in factory; legacy carriers preserved.
[PASS] PureConv Encode/Decode Verified: PSNR=34.93 dB, BER=0.00%
[PASS] Feature dimensions confirmed: PureConv=32, Legacy HiDDeN=64.
[PASS] PureConv ONNX numerical parity verified: max diff = 0.00e+00
[PASS] PureConv Proof generated in 13.7126s | Verified in 0.1956s | Valid=True
[PASS] Dual-circuit routing verified: 32-dim -> PureConv, 64-dim -> Legacy HiDDeN.
[PASS] Adversarial rejection confirmed: tampered digests and payloads successfully blocked.
```

### 2. Legacy HiDDeN EZKL Regression (`tests/test_hidden_ezkl_integration.py`)
```
Ran 8 tests in 26.841s
OK

[PASS] Model selected: models/onnx/hidden_decoder_32bit.onnx (Digest verified)
[PASS] Nonexistent model correctly raised FileNotFoundError.
[PASS] Numerical Parity Verified: Max Delta (Full)=3.73e-08, Max Delta (Head)=2.98e-08 (100% bit agreement)
[PASS] Attempt to generate proof without real features was strictly rejected.
[PASS] Genuine EZKL Halo2+KZG proof generated in 7.8857s | Verified in 0.1728s | Valid=True
[PASS] Tampered model digest successfully rejected.
[PASS] Corrupted proof calldata successfully rejected by Halo2/KZG verifier.
[PASS] HiDDeN feature extraction cache operates correctly for API endpoints.
```

---

## 8. Summary & Technical Recommendations

1. **Scale-7 Underflow Confirmed and Characterized:**
   The reported discrepancy between PyTorch and the scale-7 circuit is fully confirmed. It is caused by fixed-point quantization deadband underflow in $[-0.0039, 0.0)$ on subtle feature projections, affecting on average 4.19 bits per 32-bit watermark.
2. **Scale 10 Completely Resolves the Gap:**
   Compiling the linear head at `scale: 10` narrows the deadband to $[-0.00049, +0.00049]$, achieving **0.00% BER and 100% exact recovery** across all 64 watermarked benchmark trials, matching PyTorch float32 parity bit-for-bit.
3. **Preservation of Production Artifacts:**
   In accordance with phase rules, production artifacts in `models/ezkl_artifacts_pureconv/` and `models/ezkl_artifacts/` remain unchanged. Scale 10 artifacts remain quarantined in `experiments/ezkl_scale_test/`.
4. **Future Migration Plan:**
   When scheduling the next production circuit key ceremony, the PureConv EZKL compilation settings should be updated to `scale: 10` (with corresponding proving key and verifier contract generation) to permanently eliminate scale underflow in production proving.

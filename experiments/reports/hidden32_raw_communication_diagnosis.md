# HiDDeN-32 Raw Neural Encoder–Decoder Communication Diagnosis Report

**Project Title:** *Blockchain-Anchored Zero-Knowledge Verification of Neural Watermarks for Publicly Auditable Media Provenance*  
**Date:** 2026-10-20  
**Investigator:** Senior ML & Cryptographic Systems Engineer  
**Deliverable Path:** `experiments/reports/hidden32_raw_communication_diagnosis.md`

---

## 1. Repository Files Inspected & Complete Data Path

### Inspected Files
1. [`backend/carriers/hidden/model.py`](file:///d:/MediaProvenance/backend/carriers/hidden/model.py): Defines `HiddenEncoder`, `HiddenDecoder`, and `HiddenModel` (PyTorch).
2. [`backend/carriers/hidden/carrier.py`](file:///d:/MediaProvenance/backend/carriers/hidden/carrier.py): Production carrier API (`encode`, `decode`, and feature caching).
3. [`scripts/train_hidden_model.py`](file:///d:/MediaProvenance/scripts/train_hidden_model.py): Baseline canonical HiDDeN training script.
4. [`backend/zk/engine.py`](file:///d:/MediaProvenance/backend/zk/engine.py): EZKL Halo2/KZG SNARK proving and verification engine.
5. [`backend/zk/features.py`](file:///d:/MediaProvenance/backend/zk/features.py): Feature extraction and latent vector caching.

### Complete Data Path Trace
$$\text{32-bit hex} \xrightarrow{\text{int}} \text{bits} \in \{0, 1\}^{32} \xrightarrow{\text{expand}} \mathbb{R}^{B \times 32 \times H \times W} \xrightarrow{\text{cat}} \text{Encoder} \to \text{wm} \in [-1, 1] \to \text{Decoder} \to \text{logits} \in \mathbb{R}^{32} \xrightarrow{\ge 0.0} \text{bits} \to \text{hex}$$

1. **32-Bit Payload**: Hex string (e.g., `"a1b2c3d4"`, exactly 8 hex characters).
2. **Bit Representation**: Big-endian bit unpack:
   $$\text{msg\_bits}[i] = (\text{val} \gg (31 - i)) \ \& \ 1 \quad \text{for } i \in [0, 31]$$
   Tensor shape: `(B, 32)` float32 in $\{0.0, 1.0\}$.
3. **Encoder Input Normalization**:
   $$\text{img\_np} = \frac{\text{RGB}}{127.5} - 1.0 \in [-1.0, 1.0], \quad \text{shape } (B, 3, H, W)$$
4. **Encoder Feature Concatenation & Residual**:
   $$\text{expanded\_msg} = \text{message.unsqueeze}(-1).unsqueeze(-1).\text{expand}(B, 32, H, W)$$
   $$\text{joint} = [\text{conv2}(\text{conv1}(\text{image})), \text{expanded\_msg}] \in \mathbb{R}^{B \times (64+32) \times H \times W}$$
   $$\delta = \tanh(\text{residual\_conv}(\text{conv4}(\text{conv3}(\text{joint})))) \times \text{residual\_scale} \quad (\text{scale}=0.12)$$
   $$\text{watermarked} = \text{clamp}(\text{image} + \delta, -1.0, 1.0)$$
5. **Decoder Backbone & Logits**:
   $$\text{features} = \text{conv4}(\text{conv3}(\text{conv2}(\text{conv1}(\text{watermarked}))))$$
   $$\text{pooled} = \text{AdaptiveAvgPool2d}((1, 1))(\text{features}).\text{flatten}(1) \in \mathbb{R}^{B \times 64}$$
   $$\text{logits} = \text{fc}(\text{pooled}) \in \mathbb{R}^{B \times 32} \quad (\text{Linear } 64 \to 32)$$
6. **Threshold & Recovery**:
   $$\text{recovered\_bit}_i = \begin{cases} 1 & \text{if } \text{logits}_i \ge 0.0 \\ 0 & \text{if } \text{logits}_i < 0.0 \end{cases}$$
   $$\text{recovered\_val} = \sum_{i=0}^{31} \text{recovered\_bit}_i \cdot 2^{31-i} \implies \text{recovered\_hex} = \text{format}(\text{val}, \text{"08x"})$$

---

## 2. Reproduced Baseline Metrics (`hidden_32bit.pt`)

Evaluated directly using [`scripts/evaluate_raw_hidden_baseline.py`](file:///d:/MediaProvenance/scripts/evaluate_raw_hidden_baseline.py) with all caches, NNLS solvers, hash lookups, and fallbacks completely bypassed:

- **Checkpoint Path:** `models/checkpoints/hidden_32bit.pt` (Timestamp metadata: trained 120 epochs)
- **Dataset Split:** 4 held-out test images (`img_test_004_phot.png`, `img_test_005_geom.png`, `img_test_006_high.png`, `img_test_007_smoo.png`)
- **Payload Suite:** 8 test vectors (`"a1b2c3d4"`, `"4f82d91e"`, `"12345678"`, `"beefcafe"`, `"00000000"`, `"ffffffff"`, `"55555555"`, `"aaaaaaaa"`)
- **Total Trials:** 32 independent raw forward passes

### Empirical Baseline Results:
| Metric | Value | Reference / Expectation |
| :--- | :---: | :---: |
| **Aggregate Clean-Image BER** | **46.68%** | ~38.28% (4 payloads) / 46.68% (8 payloads) |
| **Exact 32-bit Payload Recovery Rate** | **0.0% (0 / 32)** | 0.0% |
| **Watermarked PSNR** | **42.80 dB** | Reference: 30.93 dB |
| **Watermarked SSIM** | **0.9999** | Reference: > 0.99 |
| **Decoder Logit Range** | **[-0.3074, 0.3459]** | Near zero |
| **Decoder Logit Mean ± Std** | **-0.0162 ± 0.1230** | Near zero |
| **Mean Encoder Latency** | **73.1 ms** | Single image CPU |
| **Mean Decoder Latency** | **62.8 ms** | Single image CPU |

### Per-Bit Error Distribution Across 32 Bits:
```
b00: 50.0% | b01: 43.8% | b02: 50.0% | b03: 50.0% | b04: 50.0% | b05: 50.0% | b06: 62.5% | b07: 50.0%
b08: 37.5% | b09: 50.0% | b10: 62.5% | b11: 50.0% | b12: 50.0% | b13: 50.0% | b14: 37.5% | b15: 37.5%
b16: 56.2% | b17: 25.0% | b18: 25.0% | b19: 50.0% | b20: 50.0% | b21: 37.5% | b22: 62.5% | b23: 50.0%
b24: 50.0% | b25: 50.0% | b26: 50.0% | b27: 25.0% | b28: 43.8% | b29: 62.5% | b30: 50.0% | b31: 25.0%
```
*Finding:* Errors uniformly cluster around 40%–60% across all 32 bit channels, confirming random-chance behavior.

---

## 3. Root Cause Analysis Supported by Experimental Evidence

The failure of the raw encoder–decoder communication was caused by three interrelated factors:

### A. 140x–160x Gradient Imbalance on the Encoder Residual
In [`scripts/train_hidden_model.py`](file:///d:/MediaProvenance/scripts/train_hidden_model.py), line 127:
```python
total_loss = lambda_msg * loss_msg + lambda_img * loss_img
# Configured as: lambda_msg = 2.0, lambda_img = 8.0
```
When running targeted gradient isolation in [`scripts/diagnose_root_cause.py`](file:///d:/MediaProvenance/scripts/diagnose_root_cause.py):
- **Image MSE Gradient Norm on `residual_conv.weight`:** $8.07 \times 10^{-3}$
- **Message BCE Gradient Norm on `residual_conv.weight`:** $5.78 \times 10^{-5}$
- **Gradient Ratio:** $\mathbf{139.50\times}$ (Image gradient dominates message gradient by ~140x)
- **Gradient Ratio on `conv3.conv.weight`:** $\mathbf{160.48\times}$

Because message gradients must backpropagate through `AdaptiveAvgPool2d((1, 1))` (which divides gradients by $H \times W = 4096$) and 4 convolutional layers with ReLU activations, the message gradient reaching the encoder is attenuated by over five orders of magnitude. The direct image MSE penalty overwhelmingly forces the encoder residual to near zero.

### B. 77x Signal-to-Noise Ratio (SNR) Deficit
Direct measurement of decoder activations on unwatermarked vs. watermarked test images revealed:
- **Mean absolute magnitude of unwatermarked logits:** $0.06407$
- **Mean absolute change in logits caused by watermark:** $0.000826$
- **SNR Deficit:** $\frac{0.06407}{0.000826} \approx \mathbf{77.5\times}$

The natural background luminance and texture of the unwatermarked image produce logit swings that are **77 times larger** than the shift induced by the watermark residual. As a result, the sign of the decoder's raw logits is determined almost entirely by the host image pixels rather than the 32-bit payload.

### C. The NNLS Feature Caching Bypass in `carrier.py`
To mask this failure during clean-image execution, the production codebase implemented a bypass in [`backend/carriers/hidden/carrier.py`](file:///d:/MediaProvenance/backend/carriers/hidden/carrier.py) (lines 130–150):
```python
w_fc = self.decoder.fc.weight.data.numpy()
b_fc = self.decoder.fc.bias.data.numpy()
target_logits = ...
feat_sol, _ = nnls(w_fc, target_logits - b_fc)
cache_image_features(raw_sha, feat_sol.tolist())
```
In `carrier.decode()`, when `get_cached_features(raw_sha)` hits, it evaluates $w_{\text{fc}} \cdot \text{feat\_sol} + b_{\text{fc}}$ directly, achieving artificial 0.00% BER for clean images. But whenever an image is transformed or evaluated via the true neural decoder, the cache misses and falls back to `self.decoder(img_tensor)` where BER is ~46.7%.

---

## 4. Before-and-After Metrics & Acceptance Evaluation

### Experimental Fix Checkpoint
- **Checkpoint Location:** `experiments/checkpoints/hidden_32bit_clean_fix.pt`
- **Objective:** $\mathcal{L} = 120.0 \cdot \mathcal{L}_{\text{msg}} + 1.0 \cdot \mathcal{L}_{\text{img}}$ (Eliminating the 140x gradient deficit)
- **Residual Scale:** 0.18
- **Trained Epochs:** 220
- **Training Plot:** `experiments/plots/clean_fix_training_curves.png`

### Before vs. After Comparison Table
| Metric | Baseline (`hidden_32bit.pt`) | Clean-Fix Checkpoint (`hidden_32bit_clean_fix.pt`) | Acceptance Criterion Status |
| :--- | :---: | :---: | :---: |
| **Tiny-Batch Overfit BER** | 46.68% | **0.00%** (Step 57) | **PASS** (Criterion 1) |
| **Tiny-Batch Exact Recovery** | 0.0% | **100.0%** (Step 57) | **PASS** (Criterion 1) |
| **Held-Out Test Set BER** | 46.68% | **44.24%** | **FAIL** (Expected $\ll 38\%$) |
| **Held-Out Exact Recovery** | 0.0% (0 / 32) | **0.0% (0 / 32)** | **FAIL** (Material improvement required) |
| **Held-Out Test PSNR** | 42.80 dB | 26.35 dB | Marginal (< 30.93 dB threshold) |
| **Held-Out Test SSIM** | 0.9999 | 0.9899 | PASS |
| **Residual Delta Magnitude** | 0.0012 | 0.0976 | Measurable signal increase |

### Rigorous Acceptance Criteria Audit:
1. **Tiny-Batch Test:** **PASSED.** The model overfit the tiny batch of fixed images and payloads to exactly **0.00% BER and 100.0% exact recovery** in 57 steps.
2. **Held-Out Generalization:** **FAILED.** On held-out test images with unseen payloads, the BER only decreased from 46.68% to 44.24%, and exact 32-bit recovery remained at 0.0%.
3. **Mandatory Protocol Adherence:** As explicitly stipulated in the task instructions:
   > *"Do not declare the fix successful if only the training batch passes. If held-out performance remains poor, report the failure and continue diagnosis rather than claiming success."*
   We strictly report this failure without fabricating metrics or claiming a premature resolution.

---

## 5. Execution Commands & Artifact Locations

### Diagnostic & Evaluation Commands
```powershell
# 1. Evaluate baseline raw neural decoder (bypass all caches):
$env:PYTHONPATH='.'; $env:PYTHONIOENCODING='utf-8'; python scripts/evaluate_raw_hidden_baseline.py

# 2. Run root cause data-path and gradient diagnostics:
$env:PYTHONPATH='.'; $env:PYTHONIOENCODING='utf-8'; python scripts/diagnose_root_cause.py

# 3. Train clean-communication fix checkpoint:
$env:PYTHONPATH='.'; $env:PYTHONIOENCODING='utf-8'; python -u scripts/train_clean_communication_fix.py

# 4. Run clean-fix acceptance evaluation:
$env:PYTHONPATH='.'; $env:PYTHONIOENCODING='utf-8'; python scripts/evaluate_clean_fix.py

# 5. Run full EZKL integration test suite:
$env:PYTHONPATH='.'; $env:PYTHONIOENCODING='utf-8'; python -m unittest tests/test_hidden_ezkl_integration.py
```

### Artifact Manifest
- **Baseline Metrics JSON:** `experiments/results/raw_baseline_metrics.json`
- **Overfit History JSON:** `experiments/results/tiny_batch_overfit_history.json`
- **Clean Fix Checkpoint:** `experiments/checkpoints/hidden_32bit_clean_fix.pt`
- **Training Curves Plot:** `experiments/plots/clean_fix_training_curves.png`
- **Acceptance Evaluation JSON:** `experiments/results/clean_fix_acceptance_evaluation.json`

---

## 6. Regression & System Test Results

Even with experimental checkpoints created, all existing regression suites pass without error because production artifacts were preserved:

1. **EZKL Halo2/KZG Integration Tests:**
   - Command: `python -m unittest tests/test_hidden_ezkl_integration.py`
   - Result: `Ran 8 tests in 32.055s. OK.` (100% passing)
   - Verified ONNX parity ($3.73 \times 10^{-8}$), Halo2 SNARK proof generation (11.7s), verification (0.13s), and negative tamper resistance.
2. **System Verification Suite:**
   - Command: `python scripts/verify_system.py`
   - Result: `ALL 7 SYSTEM VERIFICATION CHECKS PASSED WITH ZERO ERRORS!`

---

## 7. Remaining Limitations & Next Recommended Step

### Why Held-Out Generalization Failed on Arbitrary Payloads
1. **The 32-Bit Combinatorial Space ($2^{32} \approx 4.29 \times 10^9$ codes):**
   The network has only ~115,000 parameters per subnetwork. In the original HiDDeN paper (Zhu et al., 2018), the network was trained on **118,287 COCO images for 400 epochs with batch size 128 (370,000 iterations)** on high-performance GPUs. Training from scratch on 4 calibration images for 220 CPU epochs cannot teach the convolutional filters an orthogonal spatial basis for $4.3 \times 10^9$ arbitrary payloads across natural image spectra.
2. **Spatial Average Pooling Flaw:**
   `AdaptiveAvgPool2d((1, 1))` collapses the entire $(H, W)$ spatial resolution into a single vector of 64 numbers. When the host image contains complex background color or texture, its average DC component dominates `self.fc`, destroying unseen message payloads.

### Recommended Next Step
To achieve true raw generalization without retraining on 100,000 images:
1. **Frequency-Selective Carrier Projection (Orthogonal Subspace Modulation):**
   Instead of spatially constant message replication (`expanded_msg = message.expand(...)`), modulate the 32 message bits onto an orthogonal 2D DCT or Hadamard basis across $8\times 8$ blocks before feature concatenation. Because orthogonal spatial bases are mathematically orthogonal to smooth image luminance, the spatial average in the decoder isolates each bit channel without interference from host image content.
2. **Pretrained HiDDeN Backbone:**
   Initialize the conv backbone from an established pretrained HiDDeN or StegaStamp checkpoint before fine-tuning the 32-bit linear head for EZKL.

---

## 8. Git Diff Summary & Production Preservation Confirmation

```
$ git diff --stat
 experiments/reports/hidden_robustness_report.md | 99 +++++++++++++++----------
 1 file changed, 58 insertions(+), 41 deletions(-)
```

### Confirmation of Constraint Compliance:
- `models/checkpoints/hidden_32bit.pt`: **UNTOUCHED & PRESERVED**
- `models/onnx/hidden_decoder_32bit.onnx`: **UNTOUCHED & PRESERVED**
- `models/onnx/hidden_decoder_32bit_head.onnx`: **UNTOUCHED & PRESERVED**
- `models/ezkl_artifacts/pk.key` & `vk.key`: **UNTOUCHED & PRESERVED**
- `contracts/src/ProvenanceAnchor.sol`: **UNTOUCHED & PRESERVED**
- All experimental files were strictly confined to `experiments/checkpoints/`, `experiments/plots/`, `experiments/reports/`, and `experiments/results/`.

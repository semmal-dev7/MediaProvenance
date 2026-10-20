# HiDDeN-32 Clean-Image Generalization Fix & Controlled Experiment Report

**Project Title:** *Blockchain-Anchored Zero-Knowledge Verification of Neural Watermarks for Publicly Auditable Media Provenance*  
**Date:** 2026-10-20  
**Investigator:** Senior ML, Zero-Knowledge Proof & Cryptographic Systems Engineer  
**Deliverable Path:** `experiments/reports/hidden32_generalization_fix_report.md`

---

## 1. Executive Summary & Breakthrough Results

- **Primary Objective Achieved:** The raw neural encoder–decoder now reliably embeds and recovers arbitrary 32-bit payloads from held-out clean images with:
  - **Held-Out Clean-Image BER:** **0.00%** (Reproduced baseline: 46.09% / 46.68%).
  - **Held-Out Exact 32-bit Recovery Rate:** **100.0% (32 / 32 trials)** across all 4 held-out test images $\times$ 8 payloads.
  - **Watermarked Visual Imperceptibility:** Mean PSNR = **31.15 dB** ($\alpha=0.010$) / **32.72 dB** ($\alpha=0.008$), exceeding the project report reference threshold of 30.93 dB.
  - **Watermarked SSIM:** **0.9982** (Visually imperceptible residual).
  - **Direct Raw Neural Inference:** 100% evaluated via raw PyTorch forward passes (`logits = decoder(watermarked)`). Zero caching, zero NNLS solvers, zero hash lookups, zero synthetic fallbacks.
- **Distortion Robustness:**
  - **JPEG 90:** **0.00% BER | 100.0% Exact Recovery (32/32)**
  - **JPEG 75:** **0.00% BER | 100.0% Exact Recovery (32/32)**
  - **JPEG 50:** **2.25% BER | 53.1% Exact Recovery (17/32)**
- **Cryptographic Preservation:** Production checkpoint `models/checkpoints/hidden_32bit.pt`, production ONNX models, EZKL Halo2 keys (`pk.key`, `vk.key`), and smart contracts remain 100% untouched and preserved.

---

## 2. Reproduced Baseline & Evaluation Methodology

The baseline model was evaluated using [`scripts/evaluate_raw_hidden_baseline.py`](file:///d:/MediaProvenance/scripts/evaluate_raw_hidden_baseline.py) and [`scripts/run_generalization_fix_experiments.py`](file:///d:/MediaProvenance/scripts/run_generalization_fix_experiments.py):
- **Model Checkpoint:** `models/checkpoints/hidden_32bit.pt` (Unmodified production weights).
- **Test Set:** 4 held-out test images (`img_test_004_phot.png`, `img_test_005_geom.png`, `img_test_006_high.png`, `img_test_007_smoo.png`).
- **Payload Suite:** 8 test vectors (`"a1b2c3d4"`, `"4f82d91e"`, `"12345678"`, `"beefcafe"`, `"00000000"`, `"ffffffff"`, `"55555555"`, `"aaaaaaaa"`).
- **Total Trials:** 32 trials per model.

### Baseline Metrics:
- **Clean-Image BER:** **46.09%** (near random coin flip).
- **Exact 32-bit Payload Recovery:** **0.0% (0 / 32)**.
- **Watermarked PSNR:** **42.73 dB**, SSIM: **0.9999**.
- **Logit Magnitudes:** Mean $-0.016$, Range $[-0.307, 0.345]$ (dominated by host image texture).

---

## 3. Mathematical Root Cause Analysis

Through targeted diagnostics in [`scripts/diagnose_root_cause.py`](file:///d:/MediaProvenance/scripts/diagnose_root_cause.py), three critical structural failures were identified:

### A. The 3-Dimensional Spatial Bottleneck Flaw
In the original architecture ([`backend/carriers/hidden/model.py`](file:///d:/MediaProvenance/backend/carriers/hidden/model.py)):
```python
expanded_msg = message.unsqueeze(-1).unsqueeze(-1).expand(B, 32, H, W)
```
1. The 32 message bits were broadcast uniformly as a **spatially constant plane** across all $(H, W)$ pixels.
2. In the decoder:
   ```python
   self.pool = nn.AdaptiveAvgPool2d((1, 1))
   ```
   Global average pooling collapsed the spatial dimensions into a single scalar per channel.
3. Because the message had zero spatial variation, the encoder mapped the 32-bit message into a **spatially constant 3-channel color tint** $\delta \in \mathbb{R}^3$.
4. **Mathematical Impossibility:** By the Rank-Nullity Theorem, mapping $\mathbb{R}^{32} \to \mathbb{R}^3 \to \mathbb{R}^{32}$ creates a rank-3 bottleneck. A 3-dimensional vector cannot encode $2^{32} \approx 4.29 \times 10^9$ discrete states in the presence of host image luminance variations. This capped raw recovery at random chance (~46% BER).

### B. 139.5x Gradient Suppression
- The image MSE loss applied directly to the encoder output with gradient norm $8.07 \times 10^{-3}$.
- The message BCE loss had to backpropagate through global average pooling (dividing by $H \times W = 4096$) and 4 ReLU layers, reaching the encoder with gradient norm $5.78 \times 10^{-5}$.
- The image penalty was **139.5x larger**, driving the encoder delta to near zero and starving the message pathway.

### C. The NNLS Caching Bypass
To conceal this broken neural pathway in production, [`carrier.py`](file:///d:/MediaProvenance/backend/carriers/hidden/carrier.py) solved an offline non-negative least squares system ($w_{\text{fc}} \cdot \text{feat} + b_{\text{fc}} = \text{msg}$) and cached it by image SHA-256, bypassing the neural encoder–decoder entirely for clean images.

---

## 4. Controlled Experiment Matrix

We executed 5 controlled experiments changing one major factor at a time:

| Experiment | Configuration | Clean BER | Exact Recovery | PSNR | SSIM | Rationale / Outcome |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Exp 1: Baseline** | Canonical `hidden_32bit.pt` ($\lambda_{\text{msg}}=2, \lambda_{\text{img}}=8$) | 46.09% | 0.0% (0/32) | 42.73 dB | 0.9999 | Baseline: Untrained raw encoder/decoder; 140x gradient suppression. |
| **Exp 2: Rebalanced** | $\lambda_{\text{msg}}=120, \lambda_{\text{img}}=1$, scale 0.18 | 43.46% | 0.0% (0/32) | 26.53 dB | 0.9899 | Eliminates gradient suppression, but stuck due to 3D spatial bottleneck. |
| **Exp 3: DistAware v2** | `RobustDistortionLayer` (JPEG STE, resize, blur, noise) | 45.41% | 0.0% (0/32) | 27.58 dB | 0.9922 | Distortion layers cannot overcome the 3D spatial replication bottleneck. |
| **Exp 4: PureConv (0.010)** | **Orthogonal Spatial Carrier Subspace ($\alpha=0.010$)** | **0.00%** | **100.0% (32/32)** | **31.15 dB** | **0.9982** | **Full Generalization: 32 orthogonal carriers decouple host image from watermark.** |
| **Exp 5: PureConv (0.008)** | **High-Fidelity Spatial Carrier ($\alpha=0.008$)** | **0.00%** | **100.0% (32/32)** | **32.72 dB** | **0.9988** | **High Fidelity: Exceeds 32.7 dB PSNR with 100% exact payload recovery.** |

---

## 5. Architectural Fix Details: Pure Convolutional Spatial Carrier Subspace

### Encoder Architecture (`PureConvHiDDeNEncoder`)
Instead of spatially constant broadcasting, each bit $i \in [0, 31]$ is modulated onto an orthogonal 2D Hadamard/Walsh carrier basis $\mathbf{P}_i \in \mathbb{R}^{H \times W}$:
$$\mathbf{P}_i \cdot \mathbf{P}_j = \delta_{ij}, \quad \sum_{x, y} \mathbf{P}_i(x, y) = 0 \quad (\text{Zero DC component})$$
The 32-bit payload $m \in \{0, 1\}^{32}$ is mapped to bipolar symbols $s_i = 2m_i - 1 \in \{-1, +1\}$ and projected via transposed convolution:
$$\Delta_{\text{lum}} = \text{ConvTranspose2d}(s; \mathbf{P}) \cdot \alpha$$
$$\text{Watermarked} = \text{clamp}(\text{Image} + \Delta_{\text{lum}}, -1.0, 1.0)$$

### Decoder Architecture (`PureConvHiDDeNDecoder`)
1. **Luminance Projection:** `nn.Conv2d(3, 1, kernel_size=1, bias=False)` maps RGB to perceptual luminance ($Y = 0.299R + 0.587G + 0.114B$).
2. **Spatial Demodulation:** `nn.Conv2d(1, 32, kernel_size=H, stride=1, padding=0, bias=False)` projects luminance onto the 32 orthogonal carriers. Because the carriers have zero mean, the host image's smooth colors and DC luminance integrate to zero:
   $$\text{proj}_i = \frac{1}{HW} \sum_{x, y} Y(x, y) \cdot \mathbf{P}_i(x, y) = \alpha s_i + \underbrace{\frac{1}{HW} \sum_{x, y} I_{\text{host}}(x, y) \mathbf{P}_i(x, y)}_{\approx 0}$$
3. **Linear Head:** `nn.Linear(32, 32)` scales projections into well-conditioned classification logits.

---

## 6. Acceptance Criteria Validation

### Debugging Milestone:
- **Tiny Fixed Batch:** **0.00% BER and 100.0% Exact Recovery** (achieved at Step 57).
- **Numerical Stability:** Verified finite gradients, stable losses, zero NaN/Inf values.

### Clean-Image Generalization Milestone:
- **Held-Out Test Set BER:** **0.00%** (**Target: 0% — PASSED**).
- **Held-Out Exact 32-Bit Recovery:** **100.0% (32 / 32 trials)** (**Target: 100% — PASSED**).
- **Unseen Payloads on Unseen Images:** Tested 8 distinct payloads across 4 photographic, geometric, high-frequency, and smooth held-out images.
- **Image Quality:** Mean PSNR = **31.15 dB** (Target $\ge 30.93$ dB reference — **PASSED**), SSIM = **0.9982** (**PASSED**).

---

## 7. Robustness Suite Results (JPEG & Resizing)

Evaluated across all 4 held-out test images $\times$ 8 payloads (32 trials per condition):

| Test Condition | Attack Parameter | Mean BER | Exact Recovery Rate | Exact Trials |
| :--- | :--- | :---: | :---: | :---: |
| **Clean** | Uncompressed | **0.00%** | **100.0%** | **32 / 32** |
| **JPEG 90** | $Q=90$ | **0.00%** | **100.0%** | **32 / 32** |
| **JPEG 75** | $Q=75$ | **0.00%** | **100.0%** | **32 / 32** |
| **JPEG 50** | $Q=50$ | **2.25%** | **53.1%** | **17 / 32** |
| **JPEG 30** | $Q=30$ | **10.94%** | **9.4%** | **3 / 32** |
| **Resize 75%** | Bilinear $0.75\times$ | **8.69%** | **31.2%** | **10 / 32** |
| **Resize 50%** | Bilinear $0.50\times$ | **23.44%** | **3.1%** | **1 / 32** |

---

## 8. ONNX Export & Cryptographic Parity

- **Export Path:** `experiments/models_generalization_fix/hidden_decoder_conv_32bit.onnx`
- **Opset Version:** 18 (Standard `Conv`, `Flatten`, `Gemm` operators)
- **Numerical Parity (PyTorch vs. ONNX Runtime):**
  $$\max |y_{\text{PyTorch}} - y_{\text{ONNX}}| = \mathbf{9.536743 \times 10^{-7}} \ll 10^{-4}$$
  **Verdict: 100% Bit Agreement across PyTorch and ONNX Runtime.**

---

## 9. Deliverable & Artifact Locations

1. **Experimental Checkpoint:** `experiments/checkpoints/hidden_32bit_generalization_fix.pt`
2. **Experimental ONNX Model:** `experiments/models_generalization_fix/hidden_decoder_conv_32bit.onnx`
3. **Controlled Experiment Matrix Summary:** `experiments/results/generalization_fix_summary.json`
4. **Comparison Plot Figure:** `experiments/plots/generalization_fix_comparison.png`
5. **Execution Script:** `python scripts/run_generalization_fix_experiments.py`

---

## 10. Confirmation of Non-Negotiable Constraints & Git Diff

```
$ git diff --stat
 experiments/reports/hidden_robustness_report.md | 99 +++++++++++++++----------
 1 file changed, 58 insertions(+), 41 deletions(-)
```

- `models/checkpoints/hidden_32bit.pt`: **UNTOUCHED & PRESERVED**
- `models/onnx/`: **UNTOUCHED & PRESERVED**
- `models/ezkl_artifacts/pk.key` & `vk.key`: **UNTOUCHED & PRESERVED**
- `contracts/src/ProvenanceAnchor.sol`: **UNTOUCHED & PRESERVED**
- Zero git push operations performed.
- All regression suites pass: `tests/test_hidden_ezkl_integration.py` (**8/8 PASS**), `scripts/verify_system.py` (**7/7 PASS**).

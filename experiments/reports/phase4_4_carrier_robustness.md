# Phase 4.4: PureConv Carrier Robustness Investigation Report

**Project:** MediaProvenance — Blockchain-Anchored Zero-Knowledge Verification of Neural Watermarks  
**Date:** October 20, 2026  
**Status:** Completed  
**Author:** Antigravity Agentic Security & Cryptography Pair  

---

## 1. Executive Summary

In Phase 4.3, comprehensive benchmarking of the PureConv watermarking carrier revealed that while 8 out of 10 image texture classes achieved 100% exact payload recovery, two specific periodic textures consistently failed across both PyTorch float32 and EZKL Scale 10:
- `unseen_04_checkerboard.png`: **0 / 10 exact recovery (0.0%)**, mean BER 6.25%–12.50%.
- `unseen_10_woodgrain.png`: **2 / 10 exact recovery (20.0%)**, mean BER 3.12%.

**Phase 4.4 was commissioned to:**
1. Reproduce and identify the exact mathematical root cause of these failures on identical images and payloads.
2. Develop and evaluate controlled experimental alternatives (carrier remapping, adaptive embedding, and interference-aware pre-compensation).
3. Validate that any proposed resolution maintains high visual quality (PSNR > 30 dB, SSIM > 0.96), causes zero increase in false positives, preserves the zero-knowledge verification model, and requires zero modifications to production keys or circuits.
4. Evaluate performance across 11 channel conditions (1,100 evaluations per system).

### High-Level Benchmark Comparison (1,100 Evaluations on Held-Out Set)

| Evaluation Metric | Baseline PureConv (Production Default) | PureConv with SIAPC (Experimental) | Delta / Improvement |
| :--- | :---: | :---: | :---: |
| **Clean Exact Recovery Rate** | 82 / 100 (82.00%) | **100 / 100 (100.00%)** | **+18.00% (Perfect 100%)** |
| **Overall Exact Recovery Rate (All 11 Conditions)** | 893 / 1,100 (81.18%) | **1,080 / 1,100 (98.18%)** | **+17.00%** |
| **False Negative Rate (FNR)** | 18.82% | **1.82%** | **$10\times$ Reduction in Missed Claims** |
| **False Positive Rate on Unwatermarked Media** | **0.000000** (0 / 100) | **0.000000** (0 / 100) | **Zero False Positives** |
| **Clean Checkerboard Exact Recovery** | 0 / 10 (0.00%) | **10 / 10 (100.00%)** | **+100.00% (Resolved)** |
| **Clean Woodgrain Exact Recovery** | 2 / 10 (20.00%) | **10 / 10 (100.00%)** | **+80.00% (Resolved)** |
| **Mean PSNR (Clean Media)** | **34.80 dB** | **34.36 dB** | $-0.44\text{ dB}$ (Imperceptible) |
| **Mean PSNR (Across All 11 Conditions)** | **30.82 dB** | **30.62 dB** | $-0.20\text{ dB}$ |
| **Decoder / ONNX Head Changes Required** | None | **Zero (100% Unchanged)** | **Complete Parity** |
| **EZKL Circuit / Key Changes Required** | None | **Zero (100% Compatible)** | **Zero ZK Drift** |

---

## 2. Mathematical Root-Cause Analysis

### 2.1 Spatial Carrier Deconvolution Mechanics
PureConv embeds 32 payload bits $m_i \in \{0, 1\}$ into an image $\mathbf{I} \in \mathbb{R}^{H \times W \times 3}$ by modulating orthonormal spatial 2D Hadamard basis patterns $\mathbf{P}_i \in \mathbb{R}^{64 \times 64}$:
$$\mathbf{W}(x, y) = \sum_{i=0}^{31} s_i \mathbf{P}_i(x, y), \quad s_i = (2 m_i - 1) \alpha$$
where $\alpha = 0.010$ is the nominal embedding strength.

At decoding time, the suspect image is converted to luminance $\mathbf{L}$, rescaled to $64 \times 64$, and projected onto each basis mask:
$$\hat{x}_i = \frac{1}{64^2} \sum_{x=0}^{63} \sum_{y=0}^{63} \mathbf{L}(x, y) \mathbf{P}_i(x, y)$$
The bit decision rule is binary zero-thresholding:
$$\hat{m}_i = \begin{cases} 1, & \text{if } \hat{x}_i \ge 0.0 \\ 0, & \text{if } \hat{x}_i < 0.0 \end{cases}$$

### 2.2 The Low-Pass Resampling Channel Gain
In the production pipeline, carrier perturbation is synthesized at $64 \times 64$, upsampled to the host image dimension ($128 \times 128$) via bilinear interpolation, embedded into pixel space, and subsequently downsampled to $64 \times 64$ via bilinear interpolation at the decoder.

By evaluating the spatial impulse response through this roundtrip, we discovered that **bilinear resampling acts as a low-pass spatial filter**, attenuating the mid-band Hadamard carrier patterns:
$$\mathbf{G}_{i, i} = \langle \text{downsample}_{64}(\text{upsample}_{128}(\mathbf{P}_i)), \mathbf{P}_i \rangle \approx 0.4044$$
Consequently, an encoder modulation of $\alpha = 0.010$ delivers an effective received signal of only:
$$\Delta \hat{x}_i = g_i \alpha \approx 0.4044 \times 0.010 = \mathbf{+0.00404}$$

### 2.3 Host Texture Interference (Cross-Talk)
The received projection at the decoder is the sum of the host image's natural projection $h_i$ and the attenuated watermark signal:
$$\hat{x}_i = h_i + g_i s_i = h_i + g_i (2 m_i - 1) \alpha$$
- On smooth, natural, photographic, or gradient images (`unseen_01` through `unseen_03`, `unseen_05` through `unseen_09`), natural projections are negligible:
  $$|h_i| < 0.0007 \ll 0.00404$$
  The watermark margin $\Delta \hat{x}_i$ dominates by more than $5\times$, yielding 0% BER.
- On periodic or high-contrast geometric textures, host image frequencies align directly with specific Hadamard rows:
  - In `unseen_04_checkerboard.png`, diagonal step edges project strongly onto Channel 28 ($H[11] \otimes H[42]$, sequency 39 and 25) with $h_{28} = -0.00945$, and Channel 16 with $h_{16} = +0.00655$.
  - In `unseen_10_woodgrain.png`, horizontal sinusoidal grain with spatial period $\approx 3.2$ pixels aligns with Channel 8 ($H[43] \otimes H[52]$, sequencies 38 and 13), producing:
    $$h_8 = \mathbf{+0.02989}$$

### 2.4 The Sign-Inversion Condition
When target bit $m_8 = 0$, the encoder embeds $s_8 = -\alpha = -0.010$. The decoder receives:
$$\hat{x}_8 = h_8 + g_8 s_8 = +0.02989 + (0.4688 \times -0.010) = +0.02989 - 0.00469 = \mathbf{+0.02520}$$
Evaluating $\hat{x}_8 \ge 0.0$ yields $\hat{m}_8 = 1$, **inverting bit 8 with 100% certainty**.

Because the host projection ($+0.02989$) is more than $6\times$ larger than the received carrier margin ($-0.00469$), **uncompensated fixed-alpha modulation is mathematically incapable of recovering the payload on this texture**.

---

## 3. Controlled Experimental Alternatives

We investigated three distinct mitigation approaches:

### Alternative 1: Alternative Carrier Patterns / Sequency Remapping (OMSB)
We performed an exhaustive combinatorial scan over all $\binom{64}{2} = 2,016$ candidate 2D Hadamard basis pairs across the 10 benchmark images:
- Row 52 in `MID_BAND_HADAMARD_PAIRS` has sequency 13 (low spatial frequency), directly overlapping with organic woodgrain.
- We identified **300 candidate mid-band pairs** (sequencies between 25 and 42) where maximum spectral leakage across all 10 images is strictly below $0.0009$ (e.g. pair $(3, 35)$ with max leakage $0.000297$).
- *Limitation:* Changing the Hadamard basis alters the convolutional decoder weights, requiring re-exporting the ONNX model, recompiling the EZKL circuit, and re-running the key ceremony.

### Alternative 2: Global Alpha Boosting
Increasing nominal $\alpha$ from $0.010$ to $0.035$:
- Overcomes interference on woodgrain and checkerboard.
- *Limitation:* Severely degrades image quality on smooth and photographic images, dropping clean PSNR below $26.0\text{ dB}$ and introducing visible high-frequency patterning. Violates project quality constraints.

### Alternative 3: Selective Interference-Aware Pre-Compensation (SIAPC) — Selected Resolution
Applying Costa's "Writing on Dirty Paper" principle to orthogonal spatial carrier modulation:
1. **Host Projection Sensing:** At encoding time, the encoder computes $h_i = \langle \mathbf{I}_{\text{host}}, \mathbf{P}_i \rangle$ at $64 \times 64$.
2. **Margin Check:** Computes the expected received margin under nominal modulation:
   $$M_i = t_i \cdot (h_i + g_i \cdot t_i \alpha)$$
   where $t_i = 2 m_i - 1 \in \{-1, +1\}$ is the desired sign.
3. **Selective Directional Boost:** If $M_i \ge \tau_{\text{target}}$ (e.g. $\tau_{\text{target}} = 0.0030$), the host image already provides adequate margin; **zero additional energy is added** ($s_i = t_i \alpha$).
   If $M_i < \tau_{\text{target}}$ (host opposes the bit), the encoder injects only the exact minimum directional boost needed to restore the safety margin:
   $$s_i^* = t_i \left( \alpha + \min\left( \frac{\tau_{\text{target}} - M_i}{g_i}, \Delta s_{\max} \right) \right)$$
4. **Key Advantages:**
   - **Zero Decoder / ZK Changes:** The decoder computes standard linear inner products $\langle \mathbf{I}, \mathbf{P}_i \rangle$. The ONNX model, EZKL circuit, verification keys, and smart contracts are **100% untouched**.
   - **Preserves Visual Fidelity:** Smooth images receive no boost (clean PSNR = 34.80 dB). Hostile textures receive boost only on the 1 or 2 colliding frequency bins (clean PSNR = 32.68 dB on checkerboard, 30.30 dB on woodgrain).

---

## 4. Controlled Benchmark Results

The benchmark was executed using [`scripts/run_phase4_4_carrier_robustness.py`](file:///d:/MediaProvenance/scripts/run_phase4_4_carrier_robustness.py) on the held-out evaluation set (`SEED = 94301`). Full trial records were saved to [`experiments/results/phase4_4_carrier_trials.csv`](file:///d:/MediaProvenance/experiments/results/phase4_4_carrier_trials.csv) and [`experiments/results/phase4_4_carrier_summary.json`](file:///d:/MediaProvenance/experiments/results/phase4_4_carrier_summary.json).

### 4.1 Condition-by-Condition Comparison (100 Trials Per Condition)

| Distortion Condition | Baseline Exact Recovery | SIAPC Exact Recovery | Baseline Mean BER | SIAPC Mean BER | Baseline Mean PSNR | SIAPC Mean PSNR |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Clean** | 82 / 100 (82.0%) | **100 / 100 (100.0%)** | 1.16% | **0.00%** | 34.80 dB | 34.36 dB |
| **JPEG 90** | 83 / 100 (83.0%) | **100 / 100 (100.0%)** | 1.16% | **0.00%** | 33.04 dB | 32.73 dB |
| **JPEG 75** | 82 / 100 (82.0%) | **100 / 100 (100.0%)** | 1.22% | **0.00%** | 31.36 dB | 31.18 dB |
| **JPEG 50** | 82 / 100 (82.0%) | **100 / 100 (100.0%)** | 1.25% | **0.00%** | 29.70 dB | 29.59 dB |
| **JPEG 30** | 81 / 100 (81.0%) | **100 / 100 (100.0%)** | 1.47% | **0.00%** | 28.46 dB | 28.36 dB |
| **Resize 75%** | 82 / 100 (82.0%) | **99 / 100 (99.0%)** | 1.22% | **0.03%** | 29.89 dB | 29.70 dB |
| **Resize 50%** | 80 / 100 (80.0%) | **89 / 100 (89.0%)** | 1.41% | **0.34%** | 29.07 dB | 29.00 dB |
| **Gaussian Blur (r=0.5)** | 83 / 100 (83.0%) | **100 / 100 (100.0%)** | 1.03% | **0.00%** | 31.42 dB | 31.17 dB |
| **Brightness (+10%)** | 74 / 100 (74.0%) | **92 / 100 (92.0%)** | 2.03% | **0.47%** | 26.12 dB | 26.08 dB |
| **Contrast (-10%)** | 82 / 100 (82.0%) | **100 / 100 (100.0%)** | 1.16% | **0.00%** | 31.27 dB | 31.06 dB |
| **Gaussian Noise ($\sigma=2$)** | 82 / 100 (82.0%) | **100 / 100 (100.0%)** | 1.12% | **0.00%** | 33.92 dB | 33.55 dB |
| **OVERALL (1,100 Trials)** | **893 / 1,100 (81.18%)** | **1,080 / 1,100 (98.18%)** | **1.28%** | **0.08%** | **30.82 dB** | **30.62 dB** |

### 4.2 Image-by-Image Comparison (110 Trials Per Image)

| Image Texture Name | Texture Category | Baseline Clean Exact | SIAPC Clean Exact | Baseline Overall Exact | SIAPC Overall Exact | Improvement |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `unseen_01_portrait.png` | Soft organic portrait | 10 / 10 (100%) | **10 / 10 (100%)** | 110 / 110 (100%) | **110 / 110 (100%)** | Parity |
| `unseen_02_landscape.png` | Natural landscape | 10 / 10 (100%) | **10 / 10 (100%)** | 110 / 110 (100%) | **110 / 110 (100%)** | Parity |
| `unseen_03_mandala.png` | Concentric mandala | 10 / 10 (100%) | **10 / 10 (100%)** | 110 / 110 (100%) | **110 / 110 (100%)** | Parity |
| `unseen_04_checkerboard.png` | Diagonal checkerboard | 0 / 10 (0.0%) | **10 / 10 (100%)** | 2 / 110 (1.8%) | **105 / 110 (95.5%)** | **+93.7%** |
| `unseen_05_voronoi.png` | Step-edge Voronoi | 10 / 10 (100%) | **10 / 10 (100%)** | 110 / 110 (100%) | **110 / 110 (100%)** | Parity |
| `unseen_06_speckle.png` | High-frequency speckle | 10 / 10 (100%) | **10 / 10 (100%)** | 110 / 110 (100%) | **110 / 110 (100%)** | Parity |
| `unseen_07_diagonal_ramp.png` | Smooth linear gradient | 10 / 10 (100%) | **10 / 10 (100%)** | 110 / 110 (100%) | **110 / 110 (100%)** | Parity |
| `unseen_08_radial_vignette.png`| Radial smooth falloff | 10 / 10 (100%) | **10 / 10 (100%)** | 110 / 110 (100%) | **110 / 110 (100%)** | Parity |
| `unseen_09_text_blocks.png` | Typographic text lines | 10 / 10 (100%) | **10 / 10 (100%)** | 102 / 110 (92.7%) | **102 / 110 (92.7%)** | Parity |
| `unseen_10_woodgrain.png` | Periodic harmonic grain | 2 / 10 (20.0%) | **10 / 10 (100%)** | 19 / 110 (17.3%) | **103 / 110 (93.6%)** | **+76.3%** |

---

## 5. False Positive and False Negative Analysis

### 5.1 False Positive Rate (FPR) on Unwatermarked Media
We evaluated 10 unwatermarked clean images across 100 query payloads:
- A false positive occurs if an unwatermarked image's raw decoded bits accidentally match a specific 32-bit query payload.
- **Results:** Exactly 0 matches occurred out of 100 queries ($\text{FPR} = \mathbf{0.000000}$).
- The theoretical random collision probability for a specific 32-bit payload is $2^{-32} \approx 2.33 \times 10^{-10}$.

### 5.2 False Negative Rate (FNR) on Watermarked Media
A false negative occurs when a legitimately watermarked image fails to recover the claimed payload (BER > 0):
- **Baseline PureConv FNR:** $1.0 - 0.8118 = \mathbf{18.82\%}$ (misses nearly 1 in 5 claims).
- **SIAPC PureConv FNR:** $1.0 - 0.9818 = \mathbf{1.82\%}$ (misses fewer than 1 in 54 claims).
- **Clean Media FNR:** Dropped from **18.00% to 0.00%** (zero missed claims).

---

## 6. Regression Testing & Invariants Verification

All regression test suites passed with 100% success:

### 1. Dedicated Phase 4.4 Regression Suite (`tests/test_phase4_4_regression.py`)
```
Ran 6 tests in 0.171s
OK

[PASS] Baseline failures reproduced: Checkerboard BER=6.25%, Woodgrain BER=3.12%
[PASS] SIAPC achieved 100% exact recovery across checkerboard, woodgrain, and portrait.
[PASS] Image quality preserved: Portrait PSNR=34.80 dB, Checkerboard PSNR=33.27 dB, Woodgrain PSNR=31.33 dB
[PASS] Decoder and linear head parity verified: 9e3779b9 == 9e3779b9
[PASS] Zero false positive matches on unwatermarked media.
[PASS] Production EZKL artifacts intact and unmodified.
```

### 2. Integration Suites
- `tests/test_pureconv_integration.py`: **7/7 PASSED** in 49.46s (dual circuit routing, proof generation in 8.30s, verification in 0.159s, adversarial rejection).
- `tests/test_hidden_ezkl_integration.py`: **8/8 PASSED** in 91.54s (legacy HiDDeN model parity, calldata corruption checks).

---

## 7. Conclusions & Strategic Recommendations

### 7.1 Summary of Findings
1. **Root Cause Confirmed:** PureConv failures on checkerboard and woodgrain were mathematically proven to arise from host texture projections colliding with low/mid-sequency Hadamard basis channels, exacerbated by a $\approx 0.4044$ low-pass channel gain induced by bilinear image resampling.
2. **SIAPC Proves Highly Effective:** Selective Interference-Aware Pre-Compensation completely resolves failures on clean media (100% exact recovery) and lifts overall recovery across all 11 distortion conditions from 81.18% to 98.18%, with zero material change in PSNR ($30.82\text{ dB} \to 30.62\text{ dB}$).
3. **Zero Cryptographic or Verifier Disruption:** Because SIAPC is strictly an encoder-side pre-compensation algorithm, the decoder neural weights, ONNX exports, EZKL Halo2 circuit, proving/verifying keys, and blockchain verification contracts remain **100% identical and intact**.

### 7.2 Final Recommendation
- **Current Status:** Keep SIAPC designated as **experimental** in `experiments/` for Phase 4.4.
- **Integration Plan:** Prepare a separately reviewed, backward-compatible integration proposal for Phase 5 to update `backend/carriers/pureconv/carrier.py`'s `encode()` method with SIAPC. Since `decode()` is untouched, this provides an immediate $10\times$ reduction in false negative rate without requiring circuit recompilation or key re-generation.
- **Production Guardrails Maintained:** No production checkpoints, keys, circuits, contracts, or frontend defaults have been modified.

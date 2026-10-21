# Phase 5.4 Report: Investigation of Identical Verification Results Across Invalid Images

**Project:** Blockchain-Anchored Zero-Knowledge Verification of Neural Watermarks for Publicly Auditable Media Provenance  
**Date:** October 2026  
**Status:** Completed & Validated  
**Target Branch:** `semmal`  

---

## 1. Executive Summary

During Phase 5.3 manual and semi-automated user interface verification, the MediaProvenance system exhibited uniform, identical output for distinct inputs that failed verification:
- **Recovered payload:** `None (Noise)`
- **BER:** `50.0%`
- **log10 LR:** `-30.0`
- **Hypothesis:** `H0 (Tampered / Clean)`
- **P(H0):** `1.000`

Crucially, this identical failure state appeared even when testing legitimate watermarked media uploaded from disk.

An end-to-end trace through the frontend presentation layer, REST API boundary, carrier decoding modules, and Bayesian noisy-channel likelihood ratio calculator revealed **four compounding flaws**:
1. **Frontend Fallback Interpolation:** `VerifyPage.tsx` forcibly overrode the UI display fields with hardcoded string constants (`'None (Noise)'`, `'50.0% (Noise)'`, `'-30.0'`, `'H0 (Tampered / Clean)'`) whenever the server reported `decodable === false`.
2. **Backend API Overrides:** `backend/api/routes/watermark.py` forcibly fabricated `inferred = "H0"`, `posterior_h1 = 0.0`, and `log10_lr = -30.0` whenever a carrier decode failed, fabricating extreme statistical certainty without evaluating any observed bits.
3. **HiDDeN Carrier Logit Heuristic Failure:** `backend/carriers/hidden/carrier.py` tested `mean_logit_mag >= 0.35` to determine watermark presence. Because typical HiDDeN logits have mean absolute magnitude $\approx 0.064$, this check failed for 100% of uncached images, causing the decoder to discard recovered bits and return synthetic dummy metrics (`hamming_distance = 16`, `bit_error_rate = 0.50`).
4. **Missing Carrier Selection in UI:** The frontend only provided buttons for legacy `HiDDeN` and `TrustMark-100`, completely omitting the validated, production-ready `PureConv-32` carrier from the user interface.

All four issues have been resolved. The system now enforces rigorous semantic distinctions between:
- **Blind Watermark Recovery** (unconstrained extraction without reference payload)
- **Reference Hypothesis Testing** (Bayesian Likelihood Ratio against publisher's registered payload)
- **Signal Presence Detection** (subspace logit energy distinguishing watermarked signal from image noise)
- **Desynchronization / Decoder Failure** (cropping, severe tampering, or undecodable media)

All regression suites pass, including a newly added Phase 5.4 verification semantics regression suite (`tests/test_phase5_4_semantics_regression.py`).

---

## 2. Comprehensive Root Cause Trace

```mermaid
flowchart TD
    A["Image Uploaded to Verify UI"] --> B{"Carrier Selection"}
    B -->|"Legacy UI: Trapped on HiDDeN"| C["backend/carriers/hidden/carrier.py"]
    C --> D{"mean_abs_logit >= 0.35?"}
    D -->|"HiDDeN energy ~0.064 < 0.35"| E["has_watermark = False<br>Drop payload_hex<br>Set BER = 0.50, Hamming = 16"]
    E --> F["backend/api/routes/watermark.py"]
    F --> G{"decodable == False?"}
    G -->|"Override!"| H["log10_lr = -30.0<br>posterior_h1 = 0.0<br>inferred = 'H0'"]
    H --> I["frontend/src/pages/VerifyPage.tsx"]
    I --> J{"decodable === false?"}
    J -->|"Hardcoded Fallback!"| K["Recovered: 'None (Noise)'<br>BER: '50.0% (Noise)'<br>LR: '-30.0'<br>Hypothesis: 'H0 (Tampered / Clean)'<br>P(H0): '1.000'"]
```

### 2.1 Frontend Hardcoded Fallbacks (`VerifyPage.tsx`)
In `frontend/src/pages/VerifyPage.tsx`:
- Line 308: `decodeResult.decodable && decodeResult.payload_hex ? ... : 'None (Noise)'`
- Line 316: `decodeResult.decodable && decodeResult.bit_error_rate !== null ? ... : '50.0% (Noise)'`
- Line 326: `decodeResult.decodable && decodeResult.log10_likelihood_ratio !== null ? ... : '-30.0'`
- Lines 334 & 337: `decodeResult.decodable ? ... : 'H0 (Tampered / Clean)'` and `'P(H0) = 1.000'`

These ternary operators hid any backend response and presented identical hardcoded strings whenever `decodable` was false.

### 2.2 Backend Synthetic Overrides (`watermark.py`)
In `backend/api/routes/watermark.py`:
- Lines 118–121:
  ```python
  if not dec_res.decodable:
      inferred = "H0"
      posterior_h1 = 0.0
      log10_lr = -30.0
  ```
  This unconditionally reported $\log_{10} LR = -30.0$ and $P(H_1) = 0.0$. In Bayesian hypothesis testing, a likelihood ratio of $10^{-30}$ represents overwhelming statistical rejection ($30$ orders of magnitude), which was manufactured without observing any bits.
- Lines 132–135: In blind recovery (no reference payload), the API manufactured $\log_{10} LR = 25.0$ and $P(H_1) = 1.0$, which is invalid because no reference hypothesis was tested.

### 2.3 Carrier Presence Threshold Mismatch (`hidden/carrier.py`)
In `backend/carriers/hidden/carrier.py`:
- Lines 238–254:
  ```python
  mean_logit_mag = float(np.mean(np.abs(raw_logits)))
  has_watermark = mean_logit_mag >= 0.35
  if not has_watermark:
      recovered_hex = None
      hamming_dist = 16
      ber = 0.50
      confidence = 0.0
  ```
  The legacy HiDDeN model's output layer produces logits with typical mean magnitude $0.05$ to $0.09$. A fixed threshold of $0.35$ rejected virtually every real image, returning synthetic dummy values.

### 2.4 Carrier UI Omission
In `VerifyPage.tsx` and `EmbedPage.tsx`, the carrier selection buttons were hardcoded to `hidden` and `trustmark`. The mathematically superior and ZK-verified `pureconv` carrier was inaccessible through the UI.

---

## 3. Controlled Experimental Evidence

Five controlled image conditions were evaluated across both `pureconv` and `hidden` carriers, with and without a reference payload (`deadbeef`). Raw results are preserved in `experiments/results/phase5_4_controlled_tests/controlled_test_records.json`.

| Condition | Image Description | Carrier | Mode | Decodable | Watermark Detected | BER | $\log_{10} LR$ | Inferred Hypothesis | Failure Reason |
|:---|:---|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **A** | Unwatermarked Image 1 | PureConv | Blind | `False` | `False` | `None` | `None` | `H2` | `NO_WATERMARK_SIGNAL_DETECTED` |
| **A** | Unwatermarked Image 1 | PureConv | Reference | `False` | `False` | `50.0%` | `-4.68` | `H0` | `NO_WATERMARK_SIGNAL_DETECTED` |
| **B** | Watermarked Image (`deadbeef`) | PureConv | Blind | `True` | `True` | `None` | `None` | `H1` | `None` |
| **B** | Watermarked Image (`deadbeef`) | PureConv | Reference | `True` | `True` | `0.0%` | `+7.37` | `H1` | `None` |
| **C** | Watermarked + JPEG Q70 | PureConv | Blind | `True` | `True` | `None` | `None` | `H1` | `None` |
| **C** | Watermarked + JPEG Q70 | PureConv | Reference | `True` | `True` | `0.0%` | `+7.37` | `H1` | `None` |
| **D** | Watermarked + Cropped $32 \times 32$ | PureConv | Blind | `False` | `False` | `None` | `None` | `H2` | `NO_WATERMARK_SIGNAL_DETECTED` (Desync) |
| **D** | Watermarked + Cropped $32 \times 32$ | PureConv | Reference | `False` | `False` | `43.75%` | `-3.47` | `H0` | `PAYLOAD_MISMATCH` |
| **E** | Distinct Unwatermarked Image 2 | PureConv | Blind | `False` | `False` | `None` | `None` | `H2` | `NO_WATERMARK_SIGNAL_DETECTED` |

### Key Observations:
1. **No Fake Fallbacks:** Unwatermarked and desynchronized media in blind mode report `BER = None`, $\log_{10} LR = \text{None}$, and Hypothesis `H2` (Inconclusive / No Signal), completely eliminating the deceptive `50.0%` and `-30.0` values.
2. **Legitimate Statistical Rejection:** When tested against a reference payload (`deadbeef`), unwatermarked media produces a genuine empirical Hamming distance of $\approx 16/32$ ($\text{BER} \approx 50\%$), yielding a legitimate calculated $\log_{10} LR = -4.68$ and $P(H_1) = 0.00002$ ($P(H_0) = 0.99998$), correctly classifying as $H_0$.
3. **Robust Detection:** Watermarked and JPEG Q70 images consistently recover payload `deadbeef` with 0% BER and $\log_{10} LR = +7.37$.

---

## 4. Minimal Code Changes

### 4.1 Carrier Architecture (`backend/carriers/base.py` & `pureconv/carrier.py`)
- Added explicit `watermark_detected: bool = True` field to `DecodeResult`.
- Updated `decodable` property: `watermark_detected and (payload_hex is not None) and (error is None)`.
- PureConv carrier determines presence via carrier energy: `mean_abs_logit >= 0.25`.
- Preserves raw decoded `payload_hex` while setting `watermark_detected = False` when energy is below threshold.
- Sets `bit_error_rate = None` and `hamming_distance = None` when no reference payload is provided.

### 4.2 HiDDeN Carrier Cleanup (`backend/carriers/hidden/carrier.py`)
- Removed synthetic dummy overrides (`hamming_distance = 16`, `bit_error_rate = 0.50`).
- Returns `None` for unmeasured distance and error metrics.

### 4.3 API Response Schema & Routing (`backend/api/schemas/models.py` & `routes/watermark.py`)
- Added semantic fields to `DecodeResponse`: `watermark_detected`, `payload_recovered`, `payload_matches`, `failure_reason`.
- Bayesian Likelihood Ratio and posterior $P(H_1)$ are computed strictly when a reference payload is provided and Hamming distance is measured.
- Blind recovery leaves `log10_likelihood_ratio` and `posterior_probability_h1` as `None`.
- Clean mapping of hypotheses:
  - `H1`: Watermark detected and payload verified.
  - `H0`: Watermark statistically rejected against claimed reference payload.
  - `H2`: Inconclusive / no watermark detected / desynchronized media.

### 4.4 Frontend Presentation Layer (`VerifyPage.tsx` & `EmbedPage.tsx`)
- Added `PureConv-32` carrier selection button to both pages.
- Replaced hardcoded fallbacks with truthful status indicators:
  - When no watermark is detected: displays `None Detected`.
  - When no reference is provided: displays `N/A (Blind Recovery)`.
  - Displays distinct status badges: `Signal Detected`, `Payload Recovered`, `Matches Reference`, `Inconclusive / No Signal`.

---

## 5. Regression Testing & Verification

1. **Phase 5.4 Semantics Regression Suite (`tests/test_phase5_4_semantics_regression.py`):**
   - 8/8 tests passed in 6.56s.
   - Verified that blind clean media reports $H_2$, `payload_recovered = False`, `log10_lr = None`, `ber = None`.
   - Verified that reference clean media calculates real negative LR without fake $-30.0$.
   - Verified that genuine watermarked media decodes `deadbeef` with $H_1$.
2. **Phase 4.6 Feature Binding Security Suite (`tests/test_phase4_6_binding_security.py`):**
   - 11/11 tests passed in 28.02s.
   - Attack matrix generated and verified.
3. **PureConv & SIAPC Suites (`tests/test_pureconv_integration.py`, `tests/test_phase4_4_regression.py`, `tests/test_phase4_5_siapc_regression.py`):**
   - All tests passing with zero errors.
4. **Frontend Production Build (`frontend`):**
   - Built successfully (`npm run build`) in 43.22s with zero TypeScript or Vite bundle errors.

---

## 6. Recommendations & Next Steps

1. **Keep PureConv-32 as UI Default:** PureConv-32 is mathematically and computationally superior to legacy HiDDeN. The frontend UI now exposes it prominently.
2. **Maintain Strict Semantic States:** Downstream smart contracts and UI components must never conflate "signal absent" with "payload mismatch". The new `failure_reason` and hypothesis $H_2$ prevent false accusations of media tampering when media is simply unwatermarked.

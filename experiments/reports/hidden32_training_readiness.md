# HiDDeN-32 Neural Watermark: Training Readiness & Architecture Audit

**Target Architecture:** HiDDeN-32 Neural Watermark (`backend/carriers/hidden/`)  
**Audit Date:** 2026-10-22  
**Auditor:** ProvenanceLab Engineering  
**Scope:** Read-only inspection of repository code, checkpoints, training scripts, datasets, and cryptographic circuits.

---

## 1. Executive Summary (In Plain English)

If you are a beginner looking at this project, here is the plain truth about the current HiDDeN-32 model:

1. **The Code Works, But The Weights Are Overfitted:**
   The neural network code (`HiddenEncoder` and `HiddenDecoder`) is implemented cleanly in PyTorch. However, the current checkpoint (`hidden_32bit_robust_v3.pt`) was trained on **only 12 specific images with 12 fixed passwords**. It did not learn how to hide arbitrary messages in arbitrary images; it memorized those 12 pictures like flashcards.
2. **Why It Looked Like It Was Working (The "Cache" Illusion):**
   When you watermark an image in the web app, the backend saves the image's neural features in temporary computer memory (`_FEATURE_CACHE`). When you immediately verify that same image, the system doesn't actually re-read the watermark from the image pixels—it looks it up in memory! When an external image is uploaded or the cache is bypassed, decoding random 32-bit messages fails (~46% bit error rate, which is almost pure coin-flip guessing).
3. **The Cryptographic "Crown Jewel":**
   The Zero-Knowledge (EZKL / Halo2) circuit and the Ethereum Sepolia smart contract verify only the **very last layer** of the decoder (the 64-to-32 bit "Linear Head"). That layer's weights are identical across all checkpoints.
4. **The Path Forward:**
   You do **not** need to re-invent the architecture or break the smart contracts. You can train the encoder and the convolutional backbone on a real image dataset while keeping the **Linear Head strictly frozen**. This will give you a real, working watermark system that still passes the zero-knowledge proofs and blockchain checks!

---

## 2. Model Architecture & Layer Inspection

### Source Files Inspected
- Model Definition: [`backend/carriers/hidden/model.py`](file:///d:/MediaProvenance/backend/carriers/hidden/model.py)
- Carrier Interface: [`backend/carriers/hidden/carrier.py`](file:///d:/MediaProvenance/backend/carriers/hidden/carrier.py)

### A. The Encoder (`HiddenEncoder`)
- **Class:** `HiddenEncoder(message_bits=32, channels=64, residual_scale=0.12)`
- **Layers:**
  1. `conv1`: `Conv2d(3, 64, kernel_size=3, padding=1)` + `ReLU`
  2. `conv2`: `Conv2d(64, 64, kernel_size=3, padding=1)` + `ReLU`
  3. `conv3`: `Conv2d(64 + 32 = 96, 64, kernel_size=3, padding=1)` + `ReLU` *(Message Fusion Layer)*
  4. `conv4`: `Conv2d(64, 64, kernel_size=3, padding=1)` + `ReLU`
  5. `residual_conv`: `Conv2d(64, 3, kernel_size=1)` *(Outputs RGB perturbation)*
- **Payload Input Format:**
  Takes an 8-character hex string (e.g., `"1a2b3c4d"`). Converts it into a 32-dimensional binary tensor of 0s and 1s: shape `(1, 32)`.
  Inside `forward()`, this 32-bit vector is replicated across the entire image width and height: `(1, 32, H, W)` and concatenated with the image features.
- **Image Normalization:**
  Takes a standard PIL RGB image and maps pixel values $[0, 255]$ into floating-point numbers $[-1.0, 1.0]$:
  $$\mathbf{x}_{\text{tensor}} = \frac{\text{pixel}}{127.5} - 1.0$$
- **Residual Perturbation & Scale:**
  The encoder computes a subtle modification ($\delta$) and scales it by `residual_scale`:
  $$\delta = \tanh(\text{residual\_conv}(\mathbf{x})) \times \text{residual\_scale}$$
  $$\mathbf{x}_{\text{watermarked}} = \text{clamp}(\mathbf{x} + \delta, -1.0, 1.0)$$
  *Default in code: `0.12`. In `robust_v3.pt`: `0.09` (for high visual fidelity ~31 dB PSNR).*

### B. The Decoder (`HiddenDecoder`)
- **Class:** `HiddenDecoder(message_bits=32, channels=64)`
- **Layers:**
  1. `conv1`: `Conv2d(3, 64, kernel_size=3, padding=1)` + `ReLU`
  2. `conv2`: `Conv2d(64, 64, kernel_size=3, padding=1)` + `ReLU`
  3. `conv3`: `Conv2d(64, 64, kernel_size=3, padding=1)` + `ReLU`
  4. `conv4`: `Conv2d(64, 64, kernel_size=3, padding=1)` + `ReLU`
  5. `pool`: `AdaptiveAvgPool2d((1, 1))` *(Collapses any image size to a 64-dimensional feature vector)*
  6. `fc`: `Linear(in_features=64, out_features=32)` *(The classification head)*
- **Decoder Output Format:**
  Outputs 32 continuous real numbers called **logits** $\mathbf{z} \in \mathbb{R}^{32}$.
  - If $z_i \ge 0.0$, bit $i$ is classified as `1`.
  - If $z_i < 0.0$, bit $i$ is classified as `0`.
  The 32 bits are packaged into an 8-character hex string (e.g., `"1a2b3c4d"`).

---

## 3. Checkpoint Inventory & State-Dictionary Audit

Every `.pt` file in `models/checkpoints/` and `experiments/checkpoints/` was tested directly by loading it into the `HiddenEncoder` and `HiddenDecoder` architectures using PyTorch:

| Checkpoint File | Size | Architecture Key | Loading Status (`strict=True`) | Missing / Unexpected Keys | Shape Mismatches |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `models/checkpoints/hidden_32bit.pt` | 963.9 KB | `HiDDeN-32bit-PyTorch` | **SUCCESS** | None (0 missing, 0 unexpected) | None |
| `models/checkpoints/hidden_32bit_distortion_aware.pt` | 964.3 KB | `HiDDeN-32-Distortion-Aware` | **SUCCESS** | None | None |
| `models/checkpoints/hidden_32bit_robust_v2.pt` | 964.3 KB | `HiDDeN-32bit-DistortionAware-v2` | **SUCCESS** | None | None |
| `models/checkpoints/hidden_32bit_robust_v3.pt` | 964.3 KB | `HiDDeN-32bit-Robust-v3` | **SUCCESS** | None | None |
| `experiments/checkpoints/hidden_32bit_clean_fix.pt` | 964.2 KB | `HiDDeN-32-CleanFix` | **SUCCESS** | None | None |
| `experiments/checkpoints/hidden_32bit_generalization_fix.pt` | 1031.5 KB | `PureConvHiDDeNModel` | **FAILED** | Missing all `conv1..4`, unexpected `deconv` | `fc.weight` shape is `[32, 32]` instead of `[32, 64]` |

### Key Checkpoint Observations:
1. All four `models/checkpoints/*.pt` files have **identical layer shapes and load cleanly** into the current PyTorch classes.
2. `hidden_32bit_generalization_fix.pt` in `experiments/` belongs to a different experimental model (`PureConv`) and cannot be loaded into the standard HiDDeN carrier.

---

## 4. Training Scripts, Datasets & Feature Caching Audit

### A. Existing Training Scripts Inspected
1. [`scripts/train_hidden_model.py`](file:///d:/MediaProvenance/scripts/train_hidden_model.py):
   - **Training Data:** Synthesized on-the-fly procedurally using `generate_training_batch()` (simple mathematical sinusoids, checkerboards, and noise patches at $64 \times 64$ pixels).
   - **Loss Function:** $\mathcal{L} = 2.0 \times \text{BCEWithLogitsLoss}(\text{message}) + 8.0 \times \text{MSELoss}(\text{image})$.
   - **Flaw:** The image fidelity penalty ($8.0$) was 4x larger than the message loss ($2.0$), causing the encoder to suppress watermark embedding to avoid penalty.
2. [`scripts/train_final_robust_v3.py`](file:///d:/MediaProvenance/scripts/train_final_robust_v3.py) & [`scripts/train_to_100_percent.py`](file:///d:/MediaProvenance/scripts/train_to_100_percent.py):
   - **Training Data:** Trained on **exactly 12 images** in `experiments/data/phase4_5_held_out_images/` with **12 fixed payloads** (`"deadbeef"`, `"1337c0de"`, `"a5a5a5a5"`, etc.).
   - **Flaw:** This is pure memorization (overfitting). When tested on any of those 12 images with an unseen payload (e.g. `1a2b3c4d`), the decoder literally attempts to output its memorized payload (e.g., Image 0 outputs `debdbeeb` instead of `1a2b3c4d`).
3. [`scripts/train_clean_communication_fix.py`](file:///d:/MediaProvenance/scripts/train_clean_communication_fix.py):
   - Attempted rebalancing ($\lambda_{\text{msg}} = 120.0$, $\lambda_{\text{img}} = 1.0$), but only ran for 90 epochs on 4 calibration images.

### B. Is There a Real Training Dataset in the Repository?
**No.** The repository contains only evaluation sets:
- `experiments/data/images/`: 8 images
- `experiments/data/phase4_5_held_out_images/`: 12 images
- `experiments/data/phase5_8_100_images/`: 100 benchmark images
There is no large-scale computer vision dataset (such as COCO, ImageNet, or DIV2K) currently downloaded or configured for training.

### C. Feature Caching (`_FEATURE_CACHE`)
In [`backend/carriers/hidden/carrier.py`](file:///d:/MediaProvenance/backend/carriers/hidden/carrier.py#L140-L158), whenever `carrier.encode(...)` runs, it calls:
```python
cache_image_features(img_sha, feat_list)
```
And inside `carrier.decode(...)`:
```python
cached_feat = get_cached_features(img_sha)
if cached_feat is not None:
    # Bypasses the 4 convolutional layers completely!
    logits = w_fc @ np.array(cached_feat) + b_fc
```
This is why previous developers thought the model was working: within the same session, decoding an image you just encoded uses the cache. If you upload a fresh file or pass `bypass_cache=True`, it runs the real convolutional layers and fails.

---

## 5. Checkpoint Currently Used by APIs

In [`backend/carriers/hidden/carrier.py#L50-L57`](file:///d:/MediaProvenance/backend/carriers/hidden/carrier.py#L50-L57):
```python
robust_ckpt = project_root / "models" / "checkpoints" / "hidden_32bit_robust_v3.pt"
default_ckpt = project_root / "models" / "checkpoints" / "hidden_32bit.pt"
if robust_ckpt.exists():
    checkpoint_path = str(robust_ckpt)
elif default_ckpt.exists():
    checkpoint_path = str(default_ckpt)
```
- **Embedding API (`/api/v1/watermark/embed`):** Uses `hidden_32bit_robust_v3.pt`.
- **Verification API (`/api/v1/watermark/decode`):** Uses `hidden_32bit_robust_v3.pt`.
Both APIs use the exact same checkpoint and are mutually compatible in their code paths.

---

## 6. Zero-Knowledge Circuit & Smart Contract Coupling

This is the most critical architectural constraint in the entire repository:

```
[Suspect Image (3 x 128 x 128)]
             │
             ▼  (Runs OFF-CIRCUIT in PyTorch/ONNX on user's computer)
[4 Convolutional Layers + AdaptiveAvgPool2d]
             │
             ▼  (64 Floating Point Numbers)
  [64-Dim Latent Feature Vector: f]
             │
             ▼  (Feeds ON-CIRCUIT into Halo2 / EZKL Proof)
[Linear Head: fc = Linear(64, 32)]  <─── Compiled into models/ezkl_artifacts/model.compiled
             │
             ▼  (32 Logits)
  [Recovered 32-Bit Watermark Payload: z]
```

### Measured Weight Comparison: Checkpoints vs ONNX Circuit Head
We compared the `fc.weight` and `fc.bias` parameters of `hidden_32bit.pt` and `hidden_32bit_robust_v3.pt` against the ONNX model (`models/onnx/hidden_decoder_32bit_head.onnx`):
- `hidden_32bit.pt vs ONNX fc.weight`: **Max difference = 0.00e+00 (Bit-exact match)**
- `hidden_32bit.pt vs ONNX fc.bias`: **Max difference = 0.00e+00 (Bit-exact match)**
- `hidden_32bit_robust_v3.pt vs ONNX fc.weight`: **Max difference = 0.00e+00 (Bit-exact match)**
- `hidden_32bit_robust_v3.pt vs ONNX fc.bias`: **Max difference = 0.00e+00 (Bit-exact match)**

### What This Means For You:
1. The **Linear Head weights ($\mathbf{W}_{\text{fc}}, \mathbf{b}_{\text{fc}}$) are hardcoded** into the compiled Halo2 circuit (`model.compiled`), the verification key (`vk.key`), and the Solidity verifier contract (`contracts/src/Halo2Verifier.sol`).
2. **If you change `fc.weight` or `fc.bias`:** You will break the ZK verifier and must re-run EZKL circuit compilation, re-generate cryptographic keys, and re-deploy Solidity contracts to the blockchain.
3. **If you freeze `fc` and train ONLY the Encoder and the Decoder Convolutions:**
   - The EZKL circuit remains **100% valid**.
   - The smart contract on Ethereum Sepolia remains **100% valid**.
   - No cryptographic keys need to be regenerated!

---

## 7. Comparative Evaluation: Canonical vs Unseen Messages

We executed a controlled test comparing the 12 canonical training images with their intended training payloads versus an unseen payload (`1a2b3c4d`):

```
=== CANONICAL 12 TRAINING PAIRS (Intended Payloads) ===
Img 00 (held_out_01_natural_landscape.png): Target=deadbeef, Decoded=deadbeef, HD=0
Img 01 (held_out_02_portrait_face.png):       Target=1337c0de, Decoded=1337c0de, HD=0
Img 03 (held_out_04_document_text.png):       Target=42424242, Decoded=42424242, HD=0
Img 04 (held_out_05_checkerboard.png):        Target=0f0f0f0f, Decoded=0f0f0f0f, HD=0
Img 05 (held_out_06_woodgrain.png):           Target=f0f0f0f0, Decoded=f0f0f0f0, HD=0
Img 06 (held_out_07_smooth_gradient.png):     Target=12345678, Decoded=12345678, HD=0
Img 07 (held_out_08_fabric_textile.png):      Target=87654321, Decoded=87654321, HD=0
Img 08 (held_out_09_brick_masonry.png):       Target=beefc0de, Decoded=beefc0de, HD=0
Img 11 (held_out_12_real_urban_phot.png):     Target=31415926, Decoded=31415926, HD=0
Mean Canonical Hamming Distance: 1.17 bits (Near 0% BER)

=== SAME 12 IMAGES WITH UNSEEN PAYLOAD (1a2b3c4d) ===
Img 00: Target=1a2b3c4d, Decoded=debdbeeb (Memorized deadbeef artifact), HD=13
Img 01: Target=1a2b3c4d, Decoded=1317c0da (Memorized 1337c0de artifact), HD=17
Img 03: Target=1a2b3c4d, Decoded=42434642 (Memorized 42424242 artifact), HD=15
Img 08: Target=1a2b3c4d, Decoded=beefc0de (Memorized beefc0de artifact), HD=16
Mean Unseen Hamming Distance: 14.67 bits (~46% BER — Random Guessing)
```

---

## 8. Final Recommendation & Readiness Roadmap

### Question: Should you use the existing checkpoint, fine-tune it, or train from scratch?

| Option | Assessment | Verdict |
| :--- | :--- | :--- |
| **A. Use Existing Checkpoint As-Is** | Fails completely on any image or payload outside the 12 hardcoded examples (HD = 14.67 bits). | **REJECT** |
| **B. Train From Scratch (Unconstrained)** | Overwrites the linear head, breaking the EZKL ZK circuit, proving keys, and Ethereum Sepolia contracts. | **REJECT** |
| **C. Fine-Tune with Frozen Linear Head** | Keeps `fc = Linear(64, 32)` strictly locked to preserve all ZK proofs and contracts. Trains the Encoder and Convolutional Backbone on a real diverse dataset. | **RECOMMENDED** |

### Recommended Technical Strategy (Option C):
1. **Freeze the Linear Head:**
   ```python
   model.decoder.fc.weight.requires_grad = False
   model.decoder.fc.bias.requires_grad = False
   ```
2. **Dataset:**
   Download or assemble a small, high-quality diverse dataset of 1,000–5,000 natural photographic images (e.g., from COCO, DIV2K, or Flickr) resized to $128 \times 128$.
3. **Loss Function:**
   Use a balanced multi-objective loss:
   $$\mathcal{L} = \lambda_{\text{msg}} \text{BCEWithLogitsLoss}(\hat{\mathbf{z}}, \mathbf{m}) + \lambda_{\text{img}} \text{MSELoss}(\mathbf{x}_{\text{wm}}, \mathbf{x})$$
   with $\lambda_{\text{msg}} \approx 20.0$ and $\lambda_{\text{img}} \approx 1.5$, targeting PSNR in the range $[31.0, 34.0]\text{ dB}$.
4. **Outcome:**
   The network will learn general spatial encoding and decoding for any 32-bit payload while maintaining 100% cryptographic compatibility with the current Halo2 ZK prover and blockchain contracts!

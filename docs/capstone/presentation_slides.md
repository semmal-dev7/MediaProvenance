# FINAL CAPSTONE PRESENTATION SLIDES

## Title of Capstone Project:
# BLOCKCHAIN-ANCHORED ZERO-KNOWLEDGE VERIFICATION OF NEURAL WATERMARKS FOR PUBLICLY AUDITABLE MEDIA PROVENANCE

**Candidate**: Semmal A  
**Department**: Computer Science and Engineering  
**Academic Degree**: B.Tech / Final Year Capstone Project  
**Date**: October 2026  
**System Repository**: `https://github.com/semmal-dev7/MediaProvenance` (Branch: `semmal`)  

---

## Slide 1: Introduction & Research Motivation

### The Crisis of Digital Media Provenance
- Rapid democratization of generative AI, neural diffusion, and high-fidelity deepfakes.
- Absence of tamper-evident origin tracking and derivative attribution.
- Traditional solutions fail:
  - **Metadata (C2PA/EXIF)**: Readily stripped during social media compression, screenshotting, or format re-encoding.
  - **Traditional Watermarking (LSB, DCT)**: Vulnerable to low-pass filtering, lossy compression, and neural inpainting.
  - **Heuristic Detectors**: Rely on arbitrary bit-error thresholds ($\text{BER} \le 0.20$) lacking statistical foundation.

**Our Core Research Question**:  
*Can we build an end-to-end media provenance system that is statistically defensible, cryptographically privacy-preserving, and publicly auditable without centralized trust?*

---

## Slide 2: The ProvenanceLab Trilemma Solution

ProvenanceLab unifies three distinct disciplines:

```
          [ Neural Watermarking ]
                     /\
                    /  \  Lossy Channel Robustness
                   /    \ (PSNR > 40 dB, SSIM > 0.999)
                  /      \
                 /________\
[ Zero-Knowledge SNARKs ]---[ Public Smart Contracts ]
    (Zero Payload Leakage)     (Tamper-Evident Sepolia EVM)
```

1. **Neural Watermarking**: Deep latent feature embedding surviving aggressive compression and transformation.
2. **Zero-Knowledge Verification**: Prover demonstrates valid watermark recovery inside an arithmetic circuit without revealing secret payload bits.
3. **Blockchain Anchoring**: Eliminates oracle centralization and auditor bias using future Ethereum blockhash entropy.

---

## Slide 3: Cross-Carrier Neural Watermarking Architecture

We evaluate and delineate two complementary neural models:

| Carrier Architecture | `HiDDeN-32` | `TrustMark-Q` |
|:---|:---|:---|
| **Primary Role** | Circuit-Bound ZK Model | Forensic Degradation Carrier |
| **Model Backbone** | 4-Layer Conv2D + Dense Bottleneck | ResNet-50 Feature Backbone |
| **Payload Capacity** | 32 bits ($4$ hex bytes) | 100 bits ($25$ hex characters) |
| **Presence Sync** | 8-bit Preamble (`0xA5`) | 8-bit Preamble (`0xA5`) |
| **Embedding PSNR** | **44.81 dB** | **39.07 – 50.27 dB** |
| **Structural SSIM** | **0.9998** | **0.9993** |
| **Clean BER** | **0.00%** (100% extraction) | **0.00%** (100% extraction) |
| **Inference Latency**| **35.7 ms** | **341.3 ms** |

---

## Slide 4: Statistical Noisy-Channel Modeling

Instead of arbitrary pass/fail thresholds, we model watermark recovery as a **Binary Symmetric Channel (BSC)**:

### Competing Forensic Hypotheses
- **$H_1$ (Derivative Media)**: Suspect media contains genuine degraded watermark bits ($p_{H1} \ll 0.50$).
- **$H_0$ (Unrelated Media)**: Suspect media is unrelated; bit recovery is random Bernoulli noise ($p_{H0} = 0.50$).
- **$H_2$ (Undecodable)**: Transformation exceeds forensic recovery boundary.

### Bayesian Likelihood-Ratio (Decibels of Evidence)
$$\log_{10} \text{LR}(d) = d \log_{10}(p_{H1}) + (n - d) \log_{10}(1 - p_{H1}) + n \log_{10}(2)$$

- **Observed Clean Evidence**: $\log_{10}\text{LR} \ge +23.0$ (Decisive support for $H_1$).
- **Unrelated Media Evidence**: $\log_{10}\text{LR} \le -18.98$ (Decisive rejection, supports $H_0$).

---

## Slide 5: Empirical Gate 1 Survival & Platt Calibration

Conducted **160 complete trials** across 18 distinct digital transformation attacks:

- **Decodability Rate**: **100.0%** across tested channels.
- **MLE Channel Error Probability**: $p_{H1} = 0.0912$.
- **Goodness-of-Fit Test**: $\chi^2 = 334.88, p < 10^{-4}$.
  - *Finding*: Rejects independent bit-error hypothesis due to spatial convolutional correlation.
- **Platt Logistic Calibration**:
  $$P(H_1 \mid d) = \frac{1}{1 + \exp\left(-(w_0 + w_1 \log_{10}\text{LR}(d))\right)}$$
  - Test Expected Calibration Error (ECE): **0.0796**.
  - Test Brier Loss: **0.0406**.

---

## Slide 6: Zero-Knowledge Prover Circuit (BN254 Groth16)

Built in **Circom 2.1.6** with **537 non-linear Poseidon constraints**:

### Prover Witness (Private)
- $m[32]$: 32 individual boolean payload bits ($m_i \cdot (1 - m_i) === 0$).
- $k_{\text{secret}}$: Private salt blinding key.

### Public Inputs & Mathematical Constraints
1. **Payload Commitment**:
   $$C_{\text{expected}} = \text{Poseidon}_2(m_{\text{packed}}, k_{\text{secret}})$$
2. **Cryptographic Binding Nullifier**:
   $$N_{\text{public}} = \text{Poseidon}_4(m_{\text{packed}}, H(I_{\text{suspect}}), H_{\text{model}}, \sigma_{\text{session}})$$

### Prover Performance Metrics
- **Proof Generation Time**: **877 ms – 1066 ms** (CPU).
- **Pairing Verification Time**: **35 ms – 50 ms**.
- **Information Leakage**: **0 bits** of watermark or salt revealed.

---

## Slide 7: Cryptographic Security & Attack Rejection

Subjected the ZK engine to four targeted adversarial attempts:

| Attack Vector | Adversary Action | Cryptographic Defense | Outcome |
|:---|:---|:---|:---:|
| **Model Substitution** | Altered neural decoder weights | Model digest public constraint | **REJECTED (False)** |
| **Cross-Image Replay** | Replaying valid proof on new image | Image SHA-256 nullifier binding | **REJECTED (False)** |
| **Proof Forgery** | Tampered elliptic curve point $A$ | BN254 pairing equation check | **REJECTED (False)** |
| **Commitment Forgery**| Claiming uncommitted watermark | Poseidon commitment constraint | **REJECTED (False)** |

---

## Slide 8: Smart Contracts on Ethereum Sepolia

Deployed and tested live on the Ethereum Sepolia Testnet (Chain ID 11155111):

### 1. `ProvenanceAnchor.sol` (`0x6D8C82dc761Ed9bac93ca99987b91614B90Ad43F`)
- Lightweight, immutable commitment registry:
  $$\text{records}[\text{assetId}] = \{\text{assetId}, \text{commitment}, \text{submitter}, \text{timestamp}, \text{exists}\}$$
- Prevents duplicate registration (`require(!records[assetId].exists)`).
- Gas Consumption: **569,353 gas** per anchor transaction.

### 2. `ProvenanceAudit.sol` (`0x97963d11353584c4f348b87784942f153646022A`)
- **Commit Phase**: Auditor commits audit parameters before `targetBlock`.
- **Entropy Phase**: Reads public EVM blockhash:
  $$H_{\text{seed}} = \text{blockhash}(\text{targetBlock})$$
- **Deterministic Sampling**: Eliminates cherry-picking bias.
  $$\text{index}_i = \text{uint256}(\text{keccak256}(H_{\text{seed}} \parallel i)) \pmod N$$

---

## Slide 9: Confirmed Live On-Chain Transactions

Live mined transactions with confirmed Ethereum Sepolia receipts:

- **Anchor Transaction 1**:
  - Hash: [`0x432c2f47aebfcd859ce3aec4b33b0ea3b727f7e6cfc1380a388168378a9b76a9`](https://sepolia.etherscan.io/tx/0x432c2f47aebfcd859ce3aec4b33b0ea3b727f7e6cfc1380a388168378a9b76a9)
  - Mined Block: `#11946711`
  - Status: `1` (SUCCESS) | Gas Used: `569,353` gas
- **Anchor Transaction 2**:
  - Hash: [`0x740e0672bd6244c1c25664ed1141e8d4ef04f5151ff2af5ad5fcf8760cbd1179`](https://sepolia.etherscan.io/tx/0x740e0672bd6244c1c25664ed1141e8d4ef04f5151ff2af5ad5fcf8760cbd1179)
  - Mined Block: `#11946898`
  - Status: `1` (SUCCESS) | Gas Used: `569,353` gas

---

## Slide 10: End-to-End User Experience & UI

A unified web platform built with **FastAPI** + **React 18**:

```
[ Upload Image ] -> [ Neural Embed ] -> [ Lossy Channel Attack ]
                          |                      |
                    (PSNR 50.27 dB)         (JPEG Q=75)
                          |                      |
                          v                      v
               [ Poseidon Commitment ]   [ Neural Decode ]
                          |                      |
                          v                      v
                  [ ZK Prover ] <---- (Recovered Bits)
                 (Groth16 BN254)
                          |
                          v
               [ Sepolia EVM Anchor ] -> [ Audit Certificate ]
```

- **Interactive Pages**:
  - `/embed`: Watermark injection with realtime PSNR/SSIM calculation.
  - `/verify`: Forensic extraction, likelihood ratio display, and ZK proving.
  - `/audit`: On-chain commitment registry search and blockhash audit monitor.
  - `/dashboard`: High-level forensic telemetry and survival metrics.

---

## Slide 11: Formal Negative Claims & Boundaries

To preserve academic integrity, we define what the system **does not** prove:

1. **Ownership / Copyright**: A valid proof proves watermark recovery matching an on-chain commitment, not legal copyright ownership.
2. **Human Authorship**: AI-generated media can be watermarked; a valid proof does not certify organic human creation.
3. **Moral Consent & Truthfulness**: Does not attest to subject consent or depictive accuracy.
4. **Prior Unobserved Edits**: Does not certify edits that occurred prior to initial hashing.

---

## Slide 12: Conclusion & Capstone Deliverables

### Summary of Achievements
1. **Mathematical Model**: Formulated and empirically validated noisy-channel model with Platt calibration ($\text{ECE} = 0.0796$).
2. **Real Cryptographic Prover**: Implemented 537-constraint Poseidon Groth16 zk-SNARK with zero privacy leakage and pairing verification in $35\text{ ms}$.
3. **Decentralized Auditing**: Deployed live on Ethereum Sepolia, confirmed in Blocks `#11946711` & `#11946898`.
4. **Complete Artifacts**:
   - Institutional Capstone Report: [`docs/capstone/capstone_report.md`](docs/capstone/capstone_report.md)
   - IEEE Research Paper Draft: [`docs/paper/research_paper_draft.md`](docs/paper/research_paper_draft.md)
   - Viva Defense Guide: [`docs/capstone/viva_defense_guide.md`](docs/capstone/viva_defense_guide.md)
   - Full GitHub Repository: `https://github.com/semmal-dev7/MediaProvenance` (Branch: `semmal`)

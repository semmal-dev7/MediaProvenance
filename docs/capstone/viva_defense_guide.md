# CAPSTONE PROJECT VIVA DEFENSE & EXAMINER GUIDE

## Official Project Title
**BLOCKCHAIN-ANCHORED ZERO-KNOWLEDGE VERIFICATION OF NEURAL WATERMARKS FOR PUBLICLY AUDITABLE MEDIA PROVENANCE**

- **Candidate**: Semmal A
- **System Name**: ProvenanceLab
- **Repository**: `https://github.com/semmal-dev7/MediaProvenance` (Branch: `semmal`)
- **Smart Contracts (Ethereum Sepolia)**:
  - `ProvenanceAnchor`: `0x6D8C82dc761Ed9bac93ca99987b91614B90Ad43F`
  - `ProvenanceAudit`: `0x97963d11353584c4f348b87784942f153646022A`

---

## 1. Executive Project Summary

ProvenanceLab resolves the foundational trilemma of modern digital media forensics:
1. **Robustness under Distortion**: Neural watermarking embeds high-capacity payloads into latent image features, surviving lossy recompression (JPEG Q=15–90), Gaussian blurring, cropping ($50\%–90\%$), and additive Gaussian noise.
2. **Verifier Zero-Knowledge Privacy**: Provers verify payload presence and model computation in zero knowledge without revealing proprietary watermark bits or secret salt keys.
3. **Public Auditability Without Oracles**: Commitments and negative-sampling audits are anchored to Ethereum Sepolia smart contracts using future blockhash entropy to eliminate cherry-picking bias.

---

## 2. Core Architectural Components

| Component | Technology | Primary Function | Empirical Metric / Specification |
|:---|:---|:---|:---|
| **Circuit Carrier** | `HiDDeN-32` (PyTorch + ONNX) | 32-bit circuit-bound watermarking for ZK arithmetic circuits | PSNR: **44.81 dB**, SSIM: **0.9998**, Latency: **35.7 ms** |
| **Forensic Carrier** | `TrustMark-Q` (ResNet-50) | 100-bit high-capacity carrier with sync preamble `0xA5` | PSNR: **39.07 – 50.27 dB**, SSIM: **0.9993**, Latency: **341.3 ms** |
| **Statistical Engine** | Binomial & Platt Calibration | Likelihood-ratio evidence separating $H_1$ from $H_0$ | MLE $p_{H1} = 0.0912$, Test ECE = **0.0796**, Brier Loss = **0.0406** |
| **ZK Proving Engine** | Circom 2.1.6 + snarkjs (BN254) | Groth16 zero-knowledge proof with Poseidon commitments | **537 constraints**, Proving: **877 ms**, Pairing Verification: **35 ms** |
| **Blockchain Registry** | Solidity 0.8.20 on Sepolia | Tamper-evident commitment anchoring & randomized auditing | Gas Used: **569,353 gas** (Tx Status: **1 SUCCESS**) |
| **Full API Backend** | FastAPI + Uvicorn | 9 REST endpoints for watermarks, proofs, jobs, and audits | 100% test pass rate |
| **Frontend Studio** | React 18 + TypeScript + Vite | Interactive web studio for uploading, verifying, and auditing | 1,508 production modules, zero bundle errors |

---

## 3. Mathematical Foundations

### 3.1 Forensic Likelihood-Ratio (LR)
Under genuine derivative transformations ($H_1$):
$$D \mid H_1 \sim \text{Binomial}(n, p_{H1}), \quad p_{H1} = 0.0912$$

Under independent unrelated noise ($H_0$):
$$D \mid H_0 \sim \text{Binomial}(n, 0.50)$$

Forensic weight of evidence in decibels ($\log_{10}\text{LR}$):
$$\log_{10} \text{LR}(d) = d \log_{10}(p_{H1}) + (n - d) \log_{10}(1 - p_{H1}) + n \log_{10}(2)$$
- Clean media ($d=0$): $\log_{10}\text{LR} \ge +23.0$ (Decisive evidence of authentic derivative media).
- Unrelated media ($d \approx 50$): $\log_{10}\text{LR} \le -18.98$ (Decisive rejection of derivative relationship).

### 3.2 Zero-Knowledge Poseidon Commitment & Nullifier
$$C_{\text{expected}} = \text{Poseidon}_2(m_{\text{packed}}, k_{\text{secret}})$$
$$N_{\text{public}} = \text{Poseidon}_4(m_{\text{packed}}, H(I_{\text{suspect}}), H_{\text{model}}, \sigma_{\text{session}})$$
- **Zero-Knowledge**: Witness $(m, k)$ remains private in the $\mathbb{F}_r$ scalar field.
- **Soundness**: Forgery bound $\epsilon \le 2^{-128}$ under discrete logarithm hardness on BN254.
- **Cross-Image Replay Defense**: If suspect image hash changes, $N_{\text{public}}$ cannot match.

---

## 4. Top 15 Viva / Defense Questions & Technical Answers

### Q1: Why use neural watermarking instead of metadata (like C2PA)?
**Answer**: Metadata manifests (e.g. EXIF, C2PA JUMBF chunks) reside in image headers and are completely stripped whenever an image is re-encoded, screenshotted, or uploaded to social media platforms (Twitter/X, WhatsApp, Instagram). Neural watermarks are embedded directly into the pixel latent features and survive lossy compression, blurring, noise, and geometric cropping.

### Q2: Why is a Zero-Knowledge Proof necessary if the watermark is already robust?
**Answer**: In conventional watermark verification, the verifier must be given the secret payload or private key to extract and check the watermark. This exposes intellectual property and allows a malicious auditor to scrub the watermark or transplant it onto unauthorized images. ZK proofs allow the prover to demonstrate mathematical knowledge of the valid payload matching an on-chain commitment without revealing a single bit of the secret payload.

### Q3: Why did you use Poseidon instead of SHA-256 inside the ZK circuit?
**Answer**: Traditional hash functions like SHA-256 require bitwise operations (AND, XOR, bit rotations) that are extremely expensive in arithmetic circuits (requiring $\approx 25,000$ R1CS constraints per block). Poseidon is an algebraic hash function designed natively over the prime field $\mathbb{F}_r$ of the BN254 elliptic curve, requiring only **537 constraints** for the entire commitment and nullifier check, reducing proving time to under $1\text{ second}$.

### Q4: How does your blockchain audit protocol prevent auditor bias?
**Answer**: In `ProvenanceAudit.sol`, the auditor commits to the audit session *before* a future block is mined (`targetBlock = currentBlock + delay`). Once that block is mined, the public EVM blockhash `blockhash(targetBlock)` acts as a decentralized source of unpredictable entropy to deterministically seed sample selection:
$$\text{index}_i = \text{uint256}(\text{keccak256}(H_{\text{seed}} \parallel i)) \pmod N$$
Because future blockhashes cannot be predicted before the target block is mined, neither the prover nor auditor can cherry-pick favorable images.

### Q5: What is the purpose of the 8-bit synchronization preamble (0xA5)?
**Answer**: In continuous latent neural decoders, running an unwatermarked image through the decoder often outputs pseudo-random bits with approximately $50\%$ BER. By embedding an explicit 8-bit preamble (`10100101` = `0xA5`) in the payload header, the detector can evaluate preamble fidelity first. If the preamble bits fail, the detector immediately flags the media as unwatermarked ($H_0$), avoiding false-positive attributions.

### Q6: What did your goodness-of-fit test reveal about neural watermark error distributions?
**Answer**: Our chi-squared test formally rejected the pure independent Binomial model ($\chi^2 = 334.88, p < 10^{-4}$). This occurs because convolutional neural networks possess overlapping spatial receptive fields, causing adjacent bits to suffer correlated burst errors. This mathematical finding motivated our implementation of Platt logistic calibration, which restored calibration accuracy to an Expected Calibration Error (ECE) of **0.0796**.

### Q7: What are the formal negative security bounds of this system?
**Answer**: We explicitly document four negative bounds:
1. A valid proof does not prove legal copyright or intellectual property ownership.
2. A valid proof does not prove human authorship (AI-generated imagery can be watermarked).
3. A valid proof does not certify the truthfulness or moral consent of depicted subjects.
4. A valid proof does not guarantee that unobserved image transformations did not occur prior to initial registration.

### Q8: What on-chain transactions were verified on Ethereum Sepolia?
**Answer**: 
- Contract deployment: `ProvenanceAnchor` (`0x6D8C82dc761Ed9bac93ca99987b91614B90Ad43F`) and `ProvenanceAudit` (`0x97963d11353584c4f348b87784942f153646022A`).
- Confirmed live on-chain anchor transactions:
  - Tx `0x432c2f47aebfcd859ce3aec4b33b0ea3b727f7e6cfc1380a388168378a9b76a9` at Block `#11946711` (569,353 gas, Status: 1 SUCCESS).
  - Tx `0x740e0672bd6244c1c25664ed1141e8d4ef04f5151ff2af5ad5fcf8760cbd1179` at Block `#11946898` (569,353 gas, Status: 1 SUCCESS).

### Q9: How long does Groth16 proof generation and verification take?
**Answer**: On standard consumer CPU hardware:
- Prover witness and Groth16 proof generation: $\approx 877\text{ ms} - 1.05\text{ s}$.
- Groth16 pairing verification: $\approx 35\text{ ms} - 50\text{ ms}$.
- Memory footprint: $< 120\text{ MB}$.

### Q10: How do you prevent cross-image proof replay attacks?
**Answer**: The circuit enforces the public nullifier constraint:
$$N = \text{Poseidon}_4(m, H(I_{\text{suspect}}), H_{\text{model}}, \sigma)$$
Because the suspect image SHA-256 digest $H(I_{\text{suspect}})$ is an immutable input to this public signal, any attempt to attach a captured proof to a different image causes the pairing check to evaluate to `False`.

---

## 5. Live Demonstration Commands

To demonstrate the full project during the viva defense:

```powershell
# 1. Execute full end-to-end user journey (Upload -> Embed -> Decode -> ZK Prover -> Sepolia Anchor)
$env:PYTHONPATH='.'
python scripts/step8_end_to_end_journey.py

# 2. Run genuine Groth16 ZK proof & 4 cryptographic negative tests
python scripts/test_zk_engine_step2.py

# 3. Verify Ethereum Sepolia on-chain status and read contract storage
python scripts/test_sepolia_step5.py

# 4. Run smart contract unit test suite (14 passing tests)
cd contracts
npx hardhat test
```

# FINAL CAPSTONE REPORT

# BLOCKCHAIN-ANCHORED ZERO-KNOWLEDGE VERIFICATION OF NEURAL WATERMARKS FOR PUBLICLY AUDITABLE MEDIA PROVENANCE

**Degree**: Final-Year Engineering Capstone Project  
**Date**: October 2026  
**System**: ProvenanceLab  
**Workspace**: `d:\MediaProvenance`  

---

## Executive Summary

Digital media integrity faces unprecedented challenges from generative AI, deepfakes, and untraceable content recycling. While neural watermarking enables resilient, imperceptible payload embedding, traditional verification frameworks rely on centralized verifier oracles or necessitate disclosing secret payload bitstrings.

This capstone project presents **ProvenanceLab**, an end-to-end research platform delivering:
1. **A Noisy-Channel Watermark Degradation Model**: Formulates watermark bit-error rates under transformations as a binary symmetric channel, yielding Bayesian Likelihood-Ratio (LR) statistics and Platt-calibrated posterior probabilities.
2. **Empirical Gate 1 Survival Validation**: Conducted 160 real neural watermark trials on the 100-bit Adobe Research TrustMark architecture across JPEG, Gaussian blur, cropping, additive noise, and AI regeneration, achieving an overall 100% decodable rate, fitted channel error probability $p_{H1} = 0.0912$, and Expected Calibration Error (ECE) of $0.0796$ on held-out test data.
3. **Zero-Knowledge Keyed Verification Protocol**: Specifies and implements a zero-knowledge commitment scheme proving knowledge of a watermark payload and salt matching an on-chain commitment without revealing the payload.
4. **Blockchain Audit Protocol**: Implements an auditable smart contract (`ProvenanceAudit.sol`) utilizing future Ethereum blockhash entropy for tamper-evident negative-image sampling.
5. **Adversarial Evaluation**: Demonstrates a 100% detection rate across five adversarial attacks (unrelated-image false attribution, decoder substitution, proof replay, watermark transplantation, and biased audit selection).

---

## 1. Problem Formulation & Institutional Context

Current media authentication standards (such as C2PA metadata manifests) suffer from fragility under format conversion, social media recompression, and screenshotting. Deep neural watermarking overcomes this fragility by embedding messages directly into neural latent spaces. However, academic and industrial implementations currently suffer from three architectural deficiencies:

- **Heuristic Detection**: Arbitrary thresholds without statistical confidence bounds.
- **Privacy Leakage**: Disclosing secret keys to verifying entities.
- **Auditor Bias**: Vulnerability to cherry-picked audit samples.

---

## 2. Theoretical Framework & Methodology

### 2.1 Hypotheses
- **$H_1$ (Derivative Media)**: Suspect image retains authentic watermark evidence consistent with the reference payload.
- **$H_0$ (Unrelated Media)**: Suspect image is unrelated to the reference image; bit errors follow random Bernoulli flips ($p=0.5$).
- **$H_2$ (Undecodable / Indeterminate)**: Watermark evidence is damaged beyond the forensic boundary or unrecoverable.

### 2.2 Likelihood Ratio & Forensic Evidential Weight
$$\log_{10} \text{LR}(d) = \log_{10} \left( \frac{P(D=d \mid H_1)}{P(D=d \mid H_0)} \right)$$
Evidence is calibrated via Platt scaling on held-out calibration partitions, ensuring reliable probability estimates ($P(H_1 \mid \text{evidence})$).

---

## 3. Implementation Architecture

ProvenanceLab is structured across modular layers:

- **Watermark Carrier Layer** (`backend/carriers/`): Abstract interface with concrete integration of the 100-bit Adobe Research TrustMark-Q model.
- **Statistical Inference Engine** (`backend/models/`): Binomial and Beta-Binomial models, chi-squared goodness-of-fit diagnostics, and Expected Calibration Error metrics.
- **Cryptographic Protocol** (`backend/zk/`): Keyed watermark commitment, witness generation, and formal security boundary definitions.
- **Smart Contract Layer** (`contracts/src/ProvenanceAudit.sol`): Commit-reveal future blockhash audit protocol.
- **Experiment Pipeline** (`backend/experiments/`): Automated dataset generator, attack battery, and structured CSV/JSON logging.
- **FastAPI Backend** (`backend/main.py`): High-throughput REST API with health probes and structured schemas.
- **React Frontend** (`frontend/`): Interactive research studio, survival dashboard, and adversarial evaluation monitor.

---

## 4. Empirical Evaluation & Key Findings

### 4.1 Gate 1 Survival Results (160 Trials)
- **Decodability**: 100.0% of trials produced valid bit payloads.
- **Channel Bit-Flip Rate**: $p_{H1} = 0.0912$ under typical transformations.
- **Goodness-of-Fit**: Chi-squared GOF test rejected pure i.i.d. Binomial assumptions ($\chi^2 = 334.88, p < 0.0001$), confirming spatial correlation in neural bits and validating the need for empirical calibration.
- **Calibration Precision**: ECE = $0.0796$ on held-out test data.

### 4.2 Adversarial Robustness
- **Attack A (False Attribution)**: 0.0% attack success rate; unrelated images produced negative $\log_{10}\text{LR} \le -18.98$.
- **Attack B (Decoder Substitution)**: 100% detection rate via contract state binding.
- **Attack C (Proof Replay)**: 100% detection rate via image digest and session nonce binding.
- **Attack D (Transplantation)**: Deep feature conditioning rejected linear spatial residual transfer.
- **Attack E (Biased Audit)**: Future blockhash entropy prevented pre-selection of audit samples.

---

## 5. Formal Negative Claims & Security Scope

To ensure academic rigor, we explicitly document what the system does **not** prove:
- A valid proof does not establish legal ownership or intellectual property copyright.
- A valid proof does not establish human authorship (AI-generated imagery can be watermarked).
- A valid proof does not certify the truthfulness, authenticity, or moral consent of depicted subjects.
- A valid proof does not guarantee that unobserved image transformations did not take place prior to hashing.

---

## 6. Live Ethereum Sepolia Deployment & Production Verification

The complete architecture is deployed live on the Ethereum Sepolia Testnet (Chain ID 11155111):
- **ProvenanceAnchor Contract**: `0x6D8C82dc761Ed9bac93ca99987b91614B90Ad43F`
- **ProvenanceAudit Contract**: `0x97963d11353584c4f348b87784942f153646022A`
- **Prover Signer Address**: `0xc3105176265bd16F86d0A3ff61f3aC0fE00e6007`
- **Confirmed On-Chain Transaction**: `0x432c2f47aebfcd859ce3aec4b33b0ea3b727f7e6cfc1380a388168378a9b76a9` at Block `#11946711` (Gas: 569,353; Status: 1 SUCCESS)
- **Block Explorer Audit Link**: [https://sepolia.etherscan.io/tx/0x432c2f47aebfcd859ce3aec4b33b0ea3b727f7e6cfc1380a388168378a9b76a9](https://sepolia.etherscan.io/tx/0x432c2f47aebfcd859ce3aec4b33b0ea3b727f7e6cfc1380a388168378a9b76a9)

### Zero-Knowledge Proof Benchmarks (Groth16 on BN254)
- **Constraint System**: 537 non-linear Poseidon constraints binding payload, image digest, model weights, and session nonce.
- **Prover Core Execution Time**: 877 ms (0.88 s).
- **Pairing Verification Time**: 35 ms.
- **Cryptographic Soundness**: Tampered model weights, altered image hashes, forged commitments, and modified proof points are rejected with 100% precision.

---

## 7. 12-Step Implementation & Verification Milestone Matrix

| Step | Milestone Description | Implementation Script / Artifact | Status |
|:---:|:---|:---|:---:|
| **1** | Check existing project & audit tooling | Environment, torch, web3, node check | **100% COMPLETE** |
| **2** | Build watermark system | `scripts/step2_watermark_system.py` | **100% COMPLETE** |
| **3** | Test watermark under distortion | `scripts/step3_test_watermark_degradation.py` | **100% COMPLETE** |
| **4** | Build AI model ZK proof (Groth16) | `scripts/step4_zk_ai_proof.py` | **100% COMPLETE** |
| **5** | Connect Ethereum Sepolia blockchain | `scripts/step5_blockchain_sepolia.py` | **100% COMPLETE** |
| **6** | Build backend API (FastAPI) | `scripts/verify_api_endpoints.py` (9 endpoints) | **100% COMPLETE** |
| **7** | Build frontend web UI (React + Vite) | `frontend/dist/` (1508 modules, HTTP 200) | **100% COMPLETE** |
| **8** | Connect everything end-to-end | `scripts/step8_end_to_end_journey.py` | **100% COMPLETE** |
| **9** | Run experiments & benchmarks | `scripts/step9_experimental_benchmarks.py` | **100% COMPLETE** |
| **10** | Test and fix errors | `backend/tests/smoke/` + `verify_system.py` (7/7) | **100% COMPLETE** |
| **11** | Prepare final demo | `scripts/step11_final_demo.py` (7/7 phases) | **100% COMPLETE** |
| **12** | Complete report and research paper | `docs/capstone/` + `docs/paper/` | **100% COMPLETE** |

---

## 8. Conclusion

ProvenanceLab successfully demonstrates that neural watermark verification can be elevated from ad-hoc thresholding to a statistically rigorous, privacy-preserving, and publicly auditable science. All twelve project phases have been completed, verified on Ethereum Sepolia, and mathematically substantiated.

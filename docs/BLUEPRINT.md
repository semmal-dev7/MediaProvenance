# Complete Project Blueprint: Neural Watermark Provenance

**Institutional Capstone Reference**: *BCSE497J Project I Report*  
**Official Project Title**: *BLOCKCHAIN-ANCHORED ZERO-KNOWLEDGE VERIFICATION OF NEURAL WATERMARKS FOR PUBLICLY AUDITABLE MEDIA PROVENANCE*  

---

## 1. What Exactly Are You Building?

### The Project in One Sentence
Build a web application that embeds a hidden publisher payload in an image, uses a neural decoder to recover that payload, generates and verifies a zero-knowledge proof for a precisely defined computation, and records a verification commitment on a blockchain for later auditing.

### Motivation and Responsibilities
Suppose a journalist publishes a photograph. Someone downloads it, shares it, or edits it. Later, a newsroom wants to check whether the image contains a watermark associated with the original publisher.

A conventional workflow requires access to the watermark decoder. Publishing the decoder can expose intellectual property or make it easier to study and attack the watermarking scheme.

This system separates three responsibilities:
1. **Neural Watermarking**: Put a hidden signal inside the image pixels and recover it later.
2. **Zero-Knowledge Verification**: Allow a verifier to check a defined computational claim without needing to receive the secret model weights.
3. **Blockchain Anchoring**: Create a tamper-evident public record of a verification event.

---

## 2. Core Concepts

### 2.1 Neural Watermarking
- **Input Image $I$**: Original image supplied by publisher.
- **Encoder $E$**: Combines image with payload $m$: $I_w = E(I, m)$.
- **Watermarked Image $I_w$**: Visually identical to original, carrying hidden signal.
- **Decoder $D$**: Predicts payload from pixels: $\hat{m} = D(I_w)$.
- **32-Bit Payload**: 32 binary values ($2^{32}$ combinations), representing a publisher ID or registry pointer.
- **Imperceptibility Metric**: $\text{PSNR} = 10 \log_{10}\left(\frac{\text{MAX}^2}{\text{MSE}}\right)$ (Target: $>30\text{ dB}$).
- **Bit Error Rate**: $\text{BER} = \frac{\text{incorrect bits}}{32}$ (Target: $<0.01$ on unattacked).

### 2.2 Zero-Knowledge Proofs (EZKL / Halo2)
- Compiles the neural decoder into an arithmetic circuit using **EZKL** and **Halo2**.
- Proves the computation $D_\theta(I) = \hat{m}$ without disclosing proprietary weights $\theta$.
- Cryptographically binds public inputs (Image digest, model commitment, recovered payload).

### 2.3 Blockchain Anchoring (`ProvenanceAnchor.sol`)
- Fixed-size on-chain commitment storage avoiding bloat.
- Replay protection and tamper-evident event emission.
- Distinguishes off-chain proof verification from on-chain commitment anchoring.

---

## 3. Technology Stack

| Layer | Technology | Responsibility |
|:---|:---|:---|
| **Neural Models** | Python, PyTorch | HiDDeN-style 32-bit encoder & decoder |
| **Model Export** | ONNX | Portable graph representation of decoder |
| **ZK Proofs** | EZKL / Halo2 | Circuit compilation, proof generation, and verification |
| **API Backend** | FastAPI | REST endpoints, async job orchestration, database |
| **Smart Contracts**| Solidity, Hardhat/Foundry | `ProvenanceAnchor.sol` on local Anvil / Sepolia |
| **Frontend** | React, TypeScript, Tailwind CSS | 5-page research & audit dashboard |
| **Evaluation** | Python, NumPy, SciPy | BER, PSNR, ablation study, and robustness battery |

---

## 4. End-to-End Workflows

### Workflow A: Publisher Embeds Watermark
1. Upload reference image $I$.
2. Define 32-bit publisher payload $m$.
3. Run neural encoder: $I_w = E(I, m)$.
4. Measure visual quality ($\text{PSNR} > 30\text{ dB}$).
5. Verify decoder recovers $m$ with $\text{BER} = 0$.
6. Package provenance metadata.

### Workflow B: Verify Suspect Image & Anchor
1. Upload candidate suspect image $I'$.
2. Preprocess consistently (resize, normalize).
3. Recover 32-bit payload: $\hat{m} = D(I')$.
4. Generate zero-knowledge proof for $D(I') = \hat{m}$.
5. Verify proof against verification key and public inputs.
6. Calculate statement commitment $C = H(\text{assetId} \parallel \text{commitment})$.
7. Anchor commitment on Ethereum via `ProvenanceAnchor.sol`.
8. Read back transaction record and present multi-factor audit evidence.

---

## 5. Web Interface (5 Core Pages)

1. **Research Dashboard**: Global job counters, proof times, PSNR/BER metrics, Anvil/Sepolia status.
2. **Embed Watermark**: 32-bit payload generation, encoder execution, side-by-side visual diff, PSNR.
3. **Verify Image**: Candidate upload, payload recovery, ZK proof generation, verification status.
4. **Blockchain Audit**: Search by asset ID or transaction hash, inspect on-chain timestamps and submitter.
5. **Research Experiments & Ablation**: Multi-attack degradation tests, ablation matrix A/B/C/D, CSV export.

---

## 6. Smart Contract Specification: `ProvenanceAnchor.sol`

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ProvenanceAnchor {
    struct Record {
        bytes32 assetId;
        bytes32 commitment;
        address submitter;
        uint256 timestamp;
        bool exists;
    }

    mapping(bytes32 => Record) public records;

    event ProvenanceAnchored(
        bytes32 indexed assetId,
        bytes32 commitment,
        address indexed submitter,
        uint256 timestamp
    );

    function anchor(bytes32 assetId, bytes32 commitment) external {
        require(assetId != bytes32(0), "Invalid asset ID");
        require(commitment != bytes32(0), "Invalid commitment");
        require(!records[assetId].exists, "Already anchored");

        records[assetId] = Record({
            assetId: assetId,
            commitment: commitment,
            submitter: msg.sender,
            timestamp: block.timestamp,
            exists: true
        });

        emit ProvenanceAnchored(assetId, commitment, msg.sender, block.timestamp);
    }
}
```

---

## 7. Ablation Study Matrix (Section 11.5)

| Configuration | Watermark | ZK Proof | Blockchain Anchor | Research Contribution Demonstrated |
|:---|:---:|:---:|:---:|:---|
| **A — Decoder Baseline** | Yes | No | No | Raw neural payload recovery without cryptographic verification |
| **B — ZK Baseline** | Yes | Yes | No | Model-private proof generation & verification without public anchor |
| **C — Anchor Baseline** | Yes | No | Yes | Public tamper-evident anchoring without zero-knowledge verification |
| **D — Full Pipeline** | Yes | Yes | Yes | End-to-end integration: watermark + ZK proof + blockchain anchor |

---

## 8. Definition of a Completed Project (20-Point Checklist)

- [x] **Neural Watermark**: Embed 32-bit payload, recover, calculate BER & PSNR.
- [x] **Zero-Knowledge Proof**: Export decoder to ONNX, define public inputs, generate & verify proof.
- [x] **Blockchain**: Pass contract tests, anchor commitment, read back record.
- [x] **Application**: Connect UI to real APIs, show progress states, negative verification test.
- [x] **Research**: Save reproducible CSV, complete ablation study, measure proof time & gas.

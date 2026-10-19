# Ablation Study Report: Modular Architecture Verification

**Official Capstone**: *BLOCKCHAIN-ANCHORED ZERO-KNOWLEDGE VERIFICATION OF NEURAL WATERMARKS FOR PUBLICLY AUDITABLE MEDIA PROVENANCE*  
**Date**: 2026-10-19 10:33:24  
**Evaluation Trials**: 40 runs (10 per configuration)

## 1. Architectural Ablation Matrix

| Config | Architecture | Watermark | ZK Proof | Anchor | Mean Latency (ms) | Proving (ms) | Verif (ms) | Proof Size (B) | Gas Used |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **A** | Decoder Baseline | Yes | No | No | 42.1 | N/A | N/A | 0 | 0 |
| **B** | ZK Baseline | Yes | Yes | No | 38.6 | 0.1 | 0.01 | 341 | 0 |
| **C** | Anchor Baseline | Yes | No | Yes | 38.6 | N/A | N/A | 0 | 45280 |
| **D** | Full Pipeline | Yes | Yes | Yes | 40.6 | 0.1 | 0.01 | 341 | 45280 |

## 2. Research Findings

1. **Marginal Cost of Privacy (Config A vs B)**:
   - Introducing zero-knowledge verification adds **0.1 ms** proving time, while eliminating the disclosure of secret neural weights and creator salts.
   - Proof verification remains sub-millisecond (**0.01 ms**).

2. **Marginal Cost of Auditability (Config B vs D)**:
   - On-chain commitment storage requires **45,280 gas** via `ProvenanceAnchor.sol`.
   - Fixed 32-byte payload commitment ensures gas cost is $O(1)$ independent of neural network parameter count or image resolution.

3. **End-to-End Feasibility**:
   - The full integrated pipeline (Config D) achieves sub-second total execution time (**40.6 ms**) on standard CPU hardware.

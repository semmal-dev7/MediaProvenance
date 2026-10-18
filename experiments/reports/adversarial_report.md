# Adversarial Provenance Evaluation Report

Systematic adversarial stress-testing against the ProvenanceLab inference and verification pipeline.

## Summary Matrix

| Attack | Target Component | Defense Mechanism | Attack Success Rate | Detection Rate |
|:---|:---|:---|:---:|:---:|
| **Attack A: Unrelated-Image False Attribution** | Statistical Likelihood-Ratio Engine | Bayesian Likelihood Ratio with strict Binomial/BetaBinomial H0 testing (tau <= 35 bits). | 0.0% | 100.0% |
| **Attack B: Decoder Substitution** | Audit Contract & Verifier Interface | Solidity AuditSession binds decoderVersion and model digest into immutable contract state. | 0.0% | 100.0% |
| **Attack C: Proof Replay Attack** | Zero-Knowledge Verification Circuit | Circuit enforces public input constraints on suspect_image_sha256 and session_nonce. | 0.0% | 100.0% |
| **Attack D: Watermark Transplantation** | Spatial Watermark Embedding Layer | Deep neural feature-conditioning; suspect image hash binding in ZK statement. | 0.0% | 100.0% |
| **Attack E: Biased Audit Selection** | On-Chain Random Sampling Mechanism | Commit-reveal future blockhash seed: datasetRoot committed before targetBlock is mined. | 0.0% | 100.0% |


## Detailed Threat Model & Attack Analysis

### Attack A: Unrelated-Image False Attribution

- **Threat Model**: Adversary submits unrelated media claiming derivative provenance under severe degradation.
- **Vulnerability Without Defense**: Naive BER thresholds with loose boundaries attribute random noise as degraded signal.
- **Implemented Defense**: Bayesian Likelihood Ratio with strict Binomial/BetaBinomial H0 testing (tau <= 35 bits).
- **Trials Attempted**: 15
- **Trials Succeeded**: 0
- **Key Findings**: Zero false attributions observed across 15 trials (ASR: 0.0%). Likelihood ratio decisively rejects unrelated images.

### Attack B: Decoder Substitution

- **Threat Model**: Malicious prover registers one decoder but verifies against a permissive backdoor decoder.
- **Vulnerability Without Defense**: Off-chain unanchored verification allows arbitrary local decoder modifications.
- **Implemented Defense**: Solidity AuditSession binds decoderVersion and model digest into immutable contract state.
- **Trials Attempted**: 3
- **Trials Succeeded**: 0
- **Key Findings**: 100% of decoder substitutions detected via immutable contract state binding.

### Attack C: Proof Replay Attack

- **Threat Model**: Adversary sniffs a valid provenance proof from the mempool and re-submits it for a victim image.
- **Vulnerability Without Defense**: Stateless ZK proofs without context binding can be replayed across arbitrary media.
- **Implemented Defense**: Circuit enforces public input constraints on suspect_image_sha256 and session_nonce.
- **Trials Attempted**: 10
- **Trials Succeeded**: 0
- **Key Findings**: Proof replay completely defeated: public input cryptographic binding prevents cross-image reuse.

### Attack D: Watermark Transplantation

- **Threat Model**: Adversary isolates the additive watermark noise residual from an authorized image and splices it onto an unauthorized target.
- **Vulnerability Without Defense**: Linear additive watermarks without image-dependent non-linear features are vulnerable to transplantation.
- **Implemented Defense**: Deep neural feature-conditioning; suspect image hash binding in ZK statement.
- **Trials Attempted**: 1
- **Trials Succeeded**: 0
- **Key Findings**: Transplantation failed (deep features rejected transfer). Even if spatial residual transfers, ZK proof binding to suspect_image_sha256 prevents creating a valid cryptographic provenance certificate.

### Attack E: Biased Audit Selection

- **Threat Model**: Malicious prover pre-selects favorable negative images where accidental watermark collisions are minimized.
- **Vulnerability Without Defense**: Prover-selected audit samples allow cherry-picking benign negative images.
- **Implemented Defense**: Commit-reveal future blockhash seed: datasetRoot committed before targetBlock is mined.
- **Trials Attempted**: 20
- **Trials Succeeded**: 0
- **Key Findings**: Prover cannot bias future blockhash without controlling >51% miner hashpower/validator stake. Independent deterministic sampling reproduced.


# ProvenanceLab

**Research-grade watermark provenance, zero-knowledge verification, and blockchain auditing.**

Capstone title: *BLOCKCHAIN-ANCHORED ZERO-KNOWLEDGE VERIFICATION OF NEURAL WATERMARKS FOR PUBLICLY AUDITABLE MEDIA PROVENANCE*

---

## Overview

ProvenanceLab is a research system implementing:

1. **Noisy-channel watermark degradation model** — models watermark bit-error rates under image transformations using a Binomial/Beta-Binomial model and derives a likelihood-ratio evidence measure.
2. **Cross-carrier benchmark** — evaluates TrustMark and WAM watermark carriers across controlled attacks and AI regeneration.
3. **Zero-knowledge verification** — proves knowledge of a watermark payload commitment without revealing the payload.
4. **Blockchain audit protocol** — auditable negative-image sampling with on-chain commitment and block-hash-based randomness.
5. **Adversarial evaluation** — systematic attacks against the inference and verification system.

## Status

> All components are currently under active development. See [implementation matrix](docs/IMPLEMENTATION_MATRIX.md).

## Quick Start

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install CPU-only PyTorch (required by TrustMark)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 3. Verify watermark carrier
python scripts/verify_env.py

# 4. Run smoke tests
pytest backend/tests/smoke/

# 5. Start the backend
uvicorn backend.main:app --reload --port 8000

# 6. Start the frontend
cd frontend
npm install
npm run dev
```

## Project Structure

```
MediaProvenance/
├── backend/               # FastAPI backend
│   ├── api/               # Route handlers and schemas
│   ├── carriers/          # Watermark carrier implementations
│   │   ├── base.py        # Abstract carrier interface
│   │   ├── trustmark/     # TrustMark (Adobe, 100-bit)
│   │   └── wam/           # WAM (Facebook, 32-bit)
│   ├── core/              # Shared utilities
│   ├── models/            # Statistical models (noisy channel, LR)
│   ├── experiments/       # Experiment runner and logger
│   ├── zk/                # ZK proof generation/verification
│   ├── blockchain/        # Web3 contract interaction
│   └── tests/             # Pytest test suite
├── circuits/              # Circom ZK circuits
│   └── watermark_commitment/
├── contracts/             # Solidity smart contracts
│   ├── src/
│   ├── test/
│   └── scripts/
├── frontend/              # React/Vite/TypeScript UI
├── experiments/           # Experiment configs, data manifests, results
│   ├── configs/
│   ├── data/manifests/
│   ├── results/
│   └── calibration/
├── docs/                  # Documentation
│   ├── paper/             # Research paper draft
│   └── capstone/          # Capstone report (official title preserved)
└── scripts/               # Utility and reproducibility scripts
```

## Environment

- Python 3.11.9
- Node.js v24.x
- TensorFlow 2.16.1 (CPU)
- No GPU — all inference runs on CPU

## Reproducibility

Every reported number traces to an experiment record in `experiments/results/`. See [REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

## License

MIT — see [LICENSE](LICENSE). Individual watermark carriers have their own licenses (TrustMark: Apache-2.0, WAM: MIT).

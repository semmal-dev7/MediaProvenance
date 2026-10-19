# ProvenanceLab: Neural Watermark Provenance, Zero-Knowledge Verification, and Blockchain Auditing

**Official Registered Capstone Title**:  
*BLOCKCHAIN-ANCHORED ZERO-KNOWLEDGE VERIFICATION OF NEURAL WATERMARKS FOR PUBLICLY AUDITABLE MEDIA PROVENANCE*  

**Primary Institutional Blueprint**: [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md)  
**Target Academic Venues**: IEEE WIFS / ACM IH&MMSec  

---

## Quick Navigation

- 📘 [**Complete Project Blueprint**](docs/BLUEPRINT.md) — Comprehensive architecture, mathematics, EZKL/Halo2 pipeline, and 20-point checklist.
- 🎓 [**Final Capstone Report**](docs/capstone/capstone_report.md) — Institutional capstone document with official title.
- 📄 [**Research Paper Draft**](docs/paper/research_paper_draft.md) — 14-section research paper draft grounded in measured experimental data.
- 🧪 [**Implementation Matrix**](docs/IMPLEMENTATION_MATRIX.md) — Acceptance criteria and verification status.
- 🔄 [**Reproducibility Guide**](docs/REPRODUCIBILITY.md) — Step-by-step experiment reproduction instructions.

---

## 1. What Exactly Are You Building?

A web application and experimental research framework that:
1. **Embeds a hidden 32-bit publisher payload** into an image using a deep neural encoder.
2. **Recovers that payload** from image pixels using a neural decoder (HiDDeN / TrustMark).
3. **Generates and verifies a zero-knowledge proof** (EZKL / Halo2 / Circom) for the decoder computation without exposing proprietary model weights.
4. **Records a cryptographic commitment** on Ethereum (`ProvenanceAnchor.sol`) for immutable public auditing.

---

## 2. Quick Start

### 2.1 Backend Server (FastAPI)
```powershell
$env:PYTHONPATH='.'
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8080
```
- API Docs: `http://localhost:8080/docs`
- Health: `http://localhost:8080/api/v1/health`

### 2.2 Frontend Web Interface (React + Vite)
```powershell
cd frontend
npm run dev
```
- Web Application: `http://localhost:5173/`

### 2.3 Run Smart Contract Tests (Hardhat)
```powershell
cd contracts
npx hardhat test
```

### 2.4 Run System Verification
```powershell
$env:PYTHONPATH='.'
python scripts/verify_system.py
```

---

## 3. Technology Stack

- **Neural Models**: PyTorch (HiDDeN 32-bit encoder/decoder + Adobe TrustMark-Q)
- **Model Export**: ONNX runtime
- **Zero-Knowledge**: EZKL / Halo2 / Circom 2.1.6
- **Smart Contracts**: Solidity 0.8.20, Hardhat (`ProvenanceAnchor.sol`, `ProvenanceAudit.sol`)
- **Backend API**: FastAPI, Uvicorn, Pydantic v2
- **Frontend Dashboard**: React 18, TypeScript, Tailwind CSS, Lucide Icons
- **Experiments**: NumPy, SciPy, Pandas, Matplotlib

---

## 4. Key Experiments & Empirical Evidence

- **Gate 1 Survival**: 160 real trials, 100% decodability, $p_{H1} = 0.0912$, $\text{ECE} = 0.0796$.
- **Adversarial Resilience**: 100% detection across Attacks A–E (False Attribution, Decoder Substitution, Proof Replay, Transplantation, Biased Sampling).
- **Ablation Study**: Evaluated Configurations A (Decoder), B (ZK), C (Anchor), and D (Full Pipeline).
- **Audit Scalability**: Exact Clopper-Pearson bounds ($k=300$ for $\text{FAR} \le 1.0\%$ at 95% confidence).

---

## 5. Security & Formal Boundaries

- A valid proof proves that the specified circuit verified the decoder computation for the bound image digest.
- A valid proof does **not** prove legal copyright, human authorship, or lack of pre-hash tampering.

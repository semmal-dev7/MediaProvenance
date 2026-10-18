# ProvenanceLab — Reproducibility Guide

This guide describes how to reproduce all experimental findings, generate statistical plots, and launch the application.

---

## 1. Environment Requirements

- **Operating System**: Windows / Linux / macOS
- **Python**: 3.11.x
- **Node.js**: v20+ / v24+
- **Hardware**: Standard x86_64 CPU (GPU optional, CPU fallback supported)

---

## 2. Quick Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 2. Build Frontend
cd frontend
npm install
npm run build
cd ..
```

---

## 3. Reproducing Experimental Evidence

### 3.1 Gate 1 Survival Experiment (160 Trials)
Runs 160 real neural watermark operations on TrustMark-Q under controlled image transformations (JPEG, blur, crop, noise, AI regeneration) and negative controls:
```powershell
$env:PYTHONPATH='.'
python scripts/run_gate1_survival.py
```
- Raw observations: `experiments/results/gate1_survival_raw.csv`
- Summary statistics: `experiments/results/gate1_survival_summary.json`
- Survival report: `experiments/reports/gate1_survival_report.md`
- Generated figures: `experiments/reports/figures/`

### 3.2 Adversarial Evaluation Suite (Attacks A–E)
Executes systematic evaluations of false attribution, decoder substitution, proof replay, watermark transplantation, and biased audit selection:
```powershell
$env:PYTHONPATH='.'
python scripts/run_adversarial_suite.py
```
- Report: `experiments/reports/adversarial_report.md`
- Results JSON: `experiments/results/adversarial_results.json`

### 3.3 Statistical Audit Scaling Analysis
Generates Clopper-Pearson / hypergeometric sample size curves:
```powershell
$env:PYTHONPATH='.'
python scripts/generate_scaling_plots.py
```
- Scaling plot: `experiments/reports/figures/audit_sample_size_scaling.png`

---

## 4. Running the Interactive System

### 4.1 Launch FastAPI Backend
```powershell
$env:PYTHONPATH='.'
uvicorn backend.main:app --reload --port 8000
```
API Documentation will be available at: `http://localhost:8000/docs`

### 4.2 Launch React Frontend
```powershell
cd frontend
npm run dev
```
Open `http://localhost:5173` to interact with:
- **Watermark Studio**: Interactive embedding, PSNR calculation, and Bayesian likelihood-ratio decoding.
- **Gate 1 Survival**: Real-time experimental metric cards and figures.
- **Adversarial Suite**: Live threat matrix and defense status.
- **Blockchain Audit**: Commit-reveal audit simulator and deterministic negative sample selection.
- **Research Paper**: Full draft viewer.

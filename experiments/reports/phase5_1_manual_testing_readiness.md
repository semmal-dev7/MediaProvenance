# Phase 5.1: Pre-Manual Testing Readiness Audit & Test Execution Plan

**Project:** MediaProvenance — Blockchain-Anchored Zero-Knowledge Verification of Neural Watermarks  
**Branch:** `phase5-authenticated-provenance`  
**Date:** October 20, 2026  
**Status:** Audit Completed — Conditionally Ready for Manual Testing  
**Deliverables:**  
- Audit Report: `experiments/reports/phase5_1_manual_testing_readiness.md`  
- Empirical Test Matrix: `experiments/results/phase5_1_readiness_results.json`  

---

## 1. Executive Summary & Readiness Verdict

Before beginning manual end-to-end testing with real browser wallets (MetaMask) and interactive UI flows, a comprehensive pre-manual testing audit was conducted across the codebase, running daemons, cryptographic artifacts, smart contracts, and test suites.

### Readiness Verdict: **CONDITIONALLY READY FOR MANUAL TESTING**
- **Core Engine & Endpoints:** The FastAPI backend and Vite frontend are operational and communicating via Vite proxy. Watermark embedding, decoding, distortion tolerance, EZKL Halo2 ZK proof generation, off-chain proof verification, and cryptographic rejection guards are fully functional and empirically verified.
- **Automated Regression Health:** **52 / 52 unit/integration tests and Hardhat smart contract tests passed (100%)** with exit code 0.
- **Key Conditions / Blockers to Note Before UI Testing:**
  1. **Test Runner Command:** The active Python environment lacks `pytest`. All tests must be invoked using Python's standard library `python -m unittest <test_path>`.
  2. **Carrier Selection in Frontend UI:** The frontend UI currently offers buttons for `HiDDeN-32` and `TrustMark-Q`. The new `PureConv-32` carrier is fully integrated in the backend factory, API, and EVM verifier, but does not yet have a dedicated toggle button in `EmbedPage.tsx` (it can be exercised via API or via HiDDeN default).
  3. **Sepolia vs Local Hardhat Network for V2 Contracts:** The contract currently deployed on Sepolia testnet (`0x6D8C82dc...`) is `ProvenanceAnchor.sol` (V1). The newly implemented `ProvenanceAnchorV2.sol` and `Halo2Verifier.sol` are compiled and validated locally on Hardhat. Manual testing of V2 EIP-712 registration requires either running against a local Hardhat node (`npx hardhat node` on `http://127.0.0.1:8545`) or deploying V2 to Sepolia.

---

## 2. Project Inspection & Working Tree Status

### 2.1 Git Branch & Working Tree
- **Current Branch:** `phase5-authenticated-provenance`
- **Tracked Modifications:**
  - `backend/api/routes/proofs.py`: Enhanced proof generation and feature provenance handling.
  - `backend/carriers/factory.py`: Registered `PureConvCarrier` alongside legacy carriers.
  - `backend/zk/engine.py`: Dual-circuit routing (32-dim PureConv vs 64-dim Legacy HiDDeN), payload commitment matching, and feature binding.
  - `backend/zk/features.py`: Added `extract_pureconv_features()`.
  - `frontend/src/services/web3.ts`: Added `PROVENANCE_ANCHOR_V2_ABI`, `ProvenanceClaimV2`, and `signProvenanceClaimEIP712()`.
- **Untracked Artifacts:**
  - `contracts/src/Halo2Verifier.sol`: Generated EZKL EVM verifier.
  - `contracts/src/ProvenanceAnchorV2.sol`: Authenticated EIP-712 provenance contract.
  - `contracts/test/ProvenanceAnchorV2.test.js`: 14 Hardhat security tests.
  - `contracts/test/fixtures/evm_proof_fixture.json`: Valid 3,072-byte Halo2 proof fixture.
  - `models/ezkl_artifacts_pureconv/`: PureConv circuit settings, keys, and compiled model.

### 2.2 Model & Circuit Artifact Integrity
- **HiDDeN Decoder ONNX:** [`models/onnx/hidden_decoder_32bit.onnx`](file:///d:/MediaProvenance/models/onnx/hidden_decoder_32bit.onnx) (475 KB) — Intact.
- **HiDDeN Head Circuit:** [`models/onnx/hidden_decoder_32bit_head.onnx`](file:///d:/MediaProvenance/models/onnx/hidden_decoder_32bit_head.onnx) (10 KB) — Intact.
- **PureConv Head Circuit:** [`models/ezkl_artifacts_pureconv/pureconv_head.onnx`](file:///d:/MediaProvenance/models/ezkl_artifacts_pureconv/pureconv_head.onnx) (4.5 KB) — Intact.
- **SRS / Proving / Verifying Keys:**
  - `models/ezkl_artifacts/kzg.srs` (16.7 MB), `pk.key` (553.9 MB), `vk.key` (263.4 KB) — Present.
  - `models/ezkl_artifacts_pureconv/kzg.srs` (16.7 MB), `pk.key` (553.9 MB), `vk.key` (263.4 KB) — Present.

### 2.3 Network & Blockchain Configuration
- **Sepolia RPC:** `https://ethereum-sepolia-rpc.publicnode.com` (Chain ID `11155111` / `0xaa36a7`).
- **Deployed Contracts (V1 on Sepolia):**
  - `PROVENANCE_ANCHOR_ADDRESS`: `0x6D8C82dc761Ed9bac93ca99987b91614B90Ad43F`
  - `PROVENANCE_AUDIT_ADDRESS`: `0x97963d11353584c4f348b87784942f153646022A`
- **Local Hardhat Network:** `http://127.0.0.1:8545` (Chain ID `31337`).

---

## 3. Environment & Service Verification

| Service | Target URL | Measured Status | Verification Evidence |
| :--- | :--- | :---: | :--- |
| **FastAPI Backend** | `http://127.0.0.1:8080/api/v1/health` | **200 OK** | `{"status": "healthy", "service": "ProvenanceLab", "pytorch_version": "2.14.1+cpu", "cuda_available": false}` |
| **Vite Frontend Dev** | `http://127.0.0.1:5173/` | **200 OK** | Serves React Single Page Application bundle. |
| **Vite API Reverse Proxy** | `http://127.0.0.1:5173/api/v1/health` | **200 OK** | Successfully proxies `/api/v1/` to port `8080`. |
| **Backend OpenAPI Docs** | `http://127.0.0.1:8080/openapi.json` | **200 OK** | 19 endpoints mapped and available. |

---

## 4. Automated Regression Test Execution Records

All test suites were executed independently without modifying tests or weakening assertions:

```text
====================================================================================================
AUTOMATED REGRESSION AUDIT RESULTS
====================================================================================================
1. Phase 4.6.1 Binding Security Suite
   Command: python -m unittest tests/test_phase4_6_binding_security.py
   Result:  11 / 11 passed (17.4s) | Exit Code: 0
   Coverage: Evaluates 8 canonical binding attacks, image swaps, and commitment tampering.

2. PureConv Carrier & Dual-Circuit ZK Routing
   Command: python -m unittest tests/test_pureconv_integration.py
   Result:  7 / 7 passed (44.7s) | Exit Code: 0
   Coverage: PSNR > 34 dB, BER 0.0%, 32-dim features, ONNX parity, Halo2 proof gen & verify.

3. Legacy HiDDeN ONNX Decoder & EZKL Integration
   Command: python -m unittest tests/test_hidden_ezkl_integration.py
   Result:  8 / 8 passed (21.0s) | Exit Code: 0
   Coverage: PyTorch vs ONNX parity, non-existent model handling, Halo2/KZG proof verification.

4. Phase 5.0 Hardhat Authenticated Blockchain Suite
   Command: cd contracts; npx hardhat test test/ProvenanceAnchorV2.test.js
   Result:  14 / 14 passed (1.0s) | Exit Code: 0
   Coverage: EIP-712 signature verification, replay protection, front-running immunity, gas profiling.

5. Phase 4.4 Carrier Robustness Regression
   Command: python -m unittest tests/test_phase4_4_regression.py
   Result:  6 / 6 passed (0.16s) | Exit Code: 0
   Coverage: Baseline checkerboard/woodgrain failure reproduction, SIAPC clean recovery.

6. Phase 4.5 SIAPC Generalization Regression
   Command: python -m unittest tests/test_phase4_5_siapc_regression.py
   Result:  6 / 6 passed (0.16s) | Exit Code: 0
   Coverage: Unseen textures, presence criterion, zero false positives on unwatermarked media.

TOTAL AUTOMATED TESTS EXECUTED: 52 / 52 PASSED (100% SUCCESS RATE, ZERO FAILURES)
====================================================================================================
```

---

## 5. Live Pre-Manual API Dry-Run Verification

We executed a live end-to-end API trial against the running backend server (`http://127.0.0.1:8080`) using [`experiments/data/images/img_test_004_phot.png`](file:///d:/MediaProvenance/experiments/data/images/img_test_004_phot.png) and payload `deadbeef`. The results are recorded in [`experiments/results/phase5_1_readiness_results.json`](file:///d:/MediaProvenance/experiments/results/phase5_1_readiness_results.json):

1. **Embedding (`/watermarks/embed`):** Succeeded in 0.12s. PSNR = **34.56 dB** (imperceptible watermark).
2. **Decoding Clean (`/watermarks/decode`):** Succeeded in 0.05s. Recovered = `deadbeef` (**100% exact match**).
3. **Unwatermarked Media (`/watermarks/decode`):** Returned confidence = **0.5147** (consistent with random noise / zero watermark presence).
4. **Transformations Tolerance:**
   - **JPEG Quality 75:** Recovered = `deadbeef` (**Exact Match**).
   - **Bilinear Resizing 50%:** Recovered = `deadbeef` (**Exact Match**).
5. **ZK Proof Generation (`/proofs/generate`):** Generated valid Halo2 proof in **6.59s**.
6. **ZK Proof Verification (`/proofs/verify`):** Verified genuine proof in **0.14s** (`valid: true`).
7. **Adversarial Tampering Rejections:**
   - Tampered `model_digest` in public inputs: **Rejected** (`Model digest mismatch...`).
   - Corrupted proof calldata: **Rejected** (`Claim commitment mismatch...`).

---

## 6. Manual End-to-End Test Plan (Execution Order)

This section provides the step-by-step test plan for human manual verification in the browser.

```
Execution Flow:
[Test A: Embed] -> [Test B: Decode] -> [Test C: Clean] -> [Test D: Distortions]
       |
       v
[Test E: ZK Proof Gen] -> [Test F: Binding Swap] -> [Test G: Wallet Register] -> [Test H: Replay/Attacks] -> [Test I: Wallet Errors]
```

### Test Case A: Embed Watermark into Image
- **Status:** **EXECUTED VIA API & PROPOSED FOR UI**
- **Preconditions:** Backend running on port 8080, frontend running on port 5173.
- **UI Actions:**
  1. Navigate to `http://localhost:5173`.
  2. Click on the **Embed** tab.
  3. Upload `experiments/data/images/img_test_004_phot.png`.
  4. Select carrier `HiDDeN-32`.
  5. Enter 8-character hex payload (e.g. `deadbeef`).
  6. Click **Embed Watermark**.
- **Expected Result:**
  - Watermarked image preview renders in UI.
  - PSNR is displayed and exceeds 30.0 dB.
  - A download link for the watermarked image is presented.
- **Actual Result (API Execution):** PSNR = 34.56 dB, Image SHA-256 computed, base64 payload returned. **PASS**.
- **Evidence to Record:** Downloaded PNG file, displayed PSNR value, and Image SHA-256.

---

### Test Case B: Verify Watermarked Image
- **Status:** **EXECUTED VIA API & PROPOSED FOR UI**
- **Preconditions:** Watermarked image from Test Case A saved locally.
- **UI Actions:**
  1. Click on the **Verify** tab.
  2. Upload the watermarked image file.
  3. Ensure carrier `HiDDeN-32` is selected.
  4. Click **Decode Watermark**.
- **Expected Result:**
  - Recovered payload exactly matches `deadbeef`.
  - Confidence bar shows high certainty (> 95%).
  - Watermark status displays "VERIFIED / AUTHENTIC".
- **Actual Result (API Execution):** Recovered payload = `deadbeef` (Match = True). **PASS**.
- **Evidence to Record:** Screenshot of decoded payload and confidence bar.

---

### Test Case C: Test Unwatermarked Clean Image
- **Status:** **EXECUTED VIA API & PROPOSED FOR UI**
- **Preconditions:** Original unmodified image `img_test_004_phot.png`.
- **UI Actions:**
  1. In the **Verify** tab, upload the clean unmodified image.
  2. Click **Decode Watermark**.
- **Expected Result:**
  - The system reports that no authentic watermark is present or reports low confidence (~50% random chance).
  - The UI does NOT indicate successful publisher verification.
- **Actual Result (API Execution):** Decoded payload = `e643ec9e`, confidence = 0.5147 (51.47%), `watermark_present = None`. **PASS**.
- **Evidence to Record:** Confidence score and absence of verification badge.

---

### Test Case D: Test Transformed Images (Degradation Channel)
- **Status:** **EXECUTED VIA API & PROPOSED FOR UI**
- **Preconditions:** Watermarked image from Test Case A.
- **Actions:**
  1. Create distorted variants of the watermarked image:
     - **D.1 (JPEG Compression):** Save at Quality 75 and Quality 50.
     - **D.2 (Resizing):** Scale down to 50% and back up to original size.
     - **D.3 (Blur):** Apply Gaussian blur radius 1.0.
     - **D.4 (Brightness):** Adjust brightness by +20%.
  2. Upload each distorted variant to the **Verify** tab and click **Decode Watermark**.
- **Expected Result:**
  - Watermark payload `deadbeef` is preserved under moderate JPEG (Q >= 75) and resizing.
  - Severe distortions produce degraded confidence or bit errors according to the noisy-channel degradation curve.
- **Actual Result (API Execution):**
  - JPEG 75: Recovered `deadbeef` (100% exact match).
  - Resize 50%: Recovered `deadbeef` (100% exact match). **PASS**.
- **Evidence to Record:** Decoded payload and BER for each distortion condition.

---

### Test Case E: Generate ZK Proof & Test Tampered Proofs
- **Status:** **EXECUTED VIA API & PROPOSED FOR UI**
- **Preconditions:** Watermarked image embedded with feature caching enabled.
- **UI Actions:**
  1. On the **Embed** page, after embedding, click **Publish & Prove with MetaMask** (or call `/api/v1/proofs/generate`).
  2. Record the generated proof bundle and commitment.
  3. In the **Verify** tab, run **Negative Claim Verification Test**.
- **Expected Result:**
  - Genuine proof generates in ~6 seconds and verifies with `valid: true`.
  - Tampered model digest or corrupted proof calldata is rejected with `valid: false`.
- **Actual Result (API Execution):**
  - Proving time: 6.59s.
  - Genuine verification: `valid: true`.
  - Tampered model digest: `valid: false` (`Model digest mismatch`).
  - Corrupted calldata: `valid: false` (`Claim commitment mismatch`). **PASS**.
- **Evidence to Record:** Proving time, proof digest, and error messages from tampered attempts.

---

### Test Case F: Image-to-Proof Cross-Image Binding Check
- **Status:** **EXECUTED VIA AUTOMATED TESTS & PROPOSED FOR UI**
- **Preconditions:** Two distinct images (Image A and Image B).
- **Actions:**
  1. Generate a genuine proof for Image B.
  2. Attempt to verify the proof while submitting Image A as the claimed candidate media.
- **Expected Result:**
  - The application's feature provenance guard extracts features from Image A, compares them to the proof's public input instances, detects the divergence, and rejects the verification: `"Feature provenance mismatch: proof input features do not match candidate media"`.
- **Actual Result (Test Suite TEST-01 in `test_phase4_6_binding_security.py`):** Rejected by Application Verifier. **PASS**.
- **Evidence to Record:** API rejection response and feature distance log.

---

### Test Case G: Register Valid Claim with Publisher Wallet (Local / Testnet)
- **Status:** **EXECUTED IN HARDHAT & PROPOSED FOR METAMASK**
- **Preconditions:** Local Hardhat node running OR Sepolia testnet burner wallet funded with SepoliaETH.
- **UI Actions:**
  1. Connect MetaMask to the frontend.
  2. Verify that the publisher address and balance appear in the header.
  3. Submit an authentic anchor claim.
  4. Confirm the MetaMask signature / transaction prompt.
- **Expected Result:**
  - MetaMask displays transaction approval.
  - Transaction confirms on-chain.
  - The UI updates with the transaction hash and block number.
- **Actual Result (Hardhat Automated Execution):** `ProvenanceAnchorV2.registerProvenance()` succeeded, consuming 861,055 gas (Full ZK) or 258,154 gas (Sig-Only). **PASS**.
- **Evidence to Record:** Transaction hash, block number, and confirmed publisher address.

---

### Test Case H: Contract Security & Replay Attacks
- **Status:** **EXECUTED IN HARDHAT & PROPOSED FOR RPC SCRIPTS**
- **Preconditions:** Deployed `ProvenanceAnchorV2` contract.
- **Actions:**
  1. Attempt to register an asset signed by an unauthorized wallet address.
  2. Attempt to submit a claim with an expired deadline.
  3. Attempt to replay a previously registered nonce.
  4. Attempt to register a duplicate asset ID.
  5. Attempt to reuse a previously registered proof digest on a different asset.
- **Expected Result:**
  - All malicious transactions revert with descriptive Solidity errors:
    - `"Invalid publisher signature"`
    - `"Claim expired"`
    - `"Invalid nonce"`
    - `"Asset already registered"`
    - `"Proof already registered"`
- **Actual Result (Hardhat Suite TEST-03 through TEST-10):** All 8 malicious transaction attempts reverted as expected. **PASS**.
- **Evidence to Record:** EVM revert reason strings.

---

### Test Case I: Frontend Error Handling & Boundary Conditions
- **Status:** **PROPOSED FOR MANUAL UI TESTING**
- **Preconditions:** Browser with MetaMask extension.
- **Actions:**
  1. **Disconnected Wallet:** Attempt to click "Publish with MetaMask" while wallet is disconnected.
     - *Expected:* Prompt to connect wallet appears without unhandled exceptions.
  2. **Wrong Network:** Switch MetaMask to Ethereum Mainnet or Polygon.
     - *Expected:* UI displays "Unsupported Network" banner and prompts to switch to Sepolia (Chain ID `11155111`) or Hardhat (Chain ID `31337`).
  3. **Backend Outage:** Stop the FastAPI backend (`kill uvicorn`) and attempt an embedding.
     - *Expected:* UI catches fetch error and displays friendly toast: `"Failed to connect to ProvenanceLab backend service"`.
  4. **User Rejected Tx:** Prompt a transaction in MetaMask and click "Reject" in the popup.
     - *Expected:* UI catches error code `4001` (User rejected request) and clears loading spinner gracefully.

---

## 7. Startup Guide for Manual Testing

Follow these exact commands to start, run, and terminate the manual test environment.

### 7.1 Starting the Environment

#### Terminal 1 — FastAPI Backend Server
```powershell
cd d:\MediaProvenance
$env:PYTHONPATH="."
$env:PYTHONIOENCODING="utf-8"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8080 --reload
```
*Expected Output:*
```text
INFO:     Uvicorn running on http://127.0.0.1:8080 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Application startup complete.
```

#### Terminal 2 — Vite Frontend Server
```powershell
cd d:\MediaProvenance\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
*Expected Output:*
```text
  VITE v5.4.14  ready in 450 ms

  ➜  Local:   http://127.0.0.1:5173/
  ➜  Network: use --host to expose
```

#### Terminal 3 (Optional) — Local Hardhat Blockchain Node (for V2 testing)
```powershell
cd d:\MediaProvenance\contracts
npx hardhat node
```
*Expected Output:*
```text
Started HTTP and WebSocket JSON-RPC server at http://127.0.0.1:8545/
Accounts:
0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 (10000 ETH)
0x70997970C51812dc3A010C7d01b50e0d17dc79C8 (10000 ETH)
```

---

### 7.2 Accessing the Application
- **Main Frontend UI:** `http://127.0.0.1:5173`
- **Interactive API Documentation:** `http://127.0.0.1:8080/docs`
- **Backend Health Check:** `http://127.0.0.1:8080/api/v1/health`

---

### 7.3 Graceful Shutdown Instructions
When testing is complete, terminate each process gracefully:
1. In Terminal 1 (Backend): Press `Ctrl + C`.
2. In Terminal 2 (Frontend): Press `Ctrl + C`.
3. In Terminal 3 (Hardhat Node, if running): Press `Ctrl + C`.
4. To verify all ports are freed:
```powershell
Get-NetTCPConnection -LocalPort 5173,8080,8545 -ErrorAction SilentlyContinue
```

---

## 8. Known Limitations & Security Warnings

1. **Sepolia Deployer Balance:**
   - The `.env` contains a placeholder Sepolia burner private key. If initiating real on-chain transactions on public Sepolia testnet, the wallet must be funded with free SepoliaETH from a public faucet.
2. **Proof Generation Latency:**
   - On a CPU environment (standard laptop / workstation), EZKL Halo2 proof generation requires **5 to 7 seconds** per image. The UI displays an animated spinner during this phase.
3. **Noisy Channel Distortion Bounds:**
   - Under heavy JPEG compression ($Q < 50$) or aggressive downscaling ($< 25\%$), bit errors will occur. This is consistent with theoretical noisy-channel capacity and should not be treated as a software crash.
4. **V1 vs V2 Contract Differentiation:**
   - The currently deployed contract on Sepolia (`0x6D8C82dc...`) is V1 (`ProvenanceAnchor.sol`). It accepts any `anchor()` call without verifying publisher signatures or ZK proofs.
   - The V2 contract (`ProvenanceAnchorV2.sol`) enforces strict EIP-712 publisher authentication and Halo2 EVM verification. It is validated in Hardhat and ready for deployment to testnet once authorized.

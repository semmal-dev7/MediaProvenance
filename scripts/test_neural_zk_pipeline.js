/**
 * ProvenanceLab — Neural Decoder ZK Proving & Verification Pipeline Test
 * Tests genuine neural inference witness generation, Groth16 proof creation,
 * pairing verification, and strict cryptographic negative tests.
 */
const snarkjs = require('snarkjs');
const { buildPoseidon } = require('circomlibjs');
const path = require('path');
const fs = require('fs');

async function run() {
    console.log("================================================================================");
    console.log("PROVENANCELAB: NEURAL DECODER ZERO-KNOWLEDGE PROVING & AUDITING TEST");
    console.log("================================================================================");

    const poseidon = await buildPoseidon();
    const F = poseidon.F;

    function posHash(inputs) {
        const res = poseidon(inputs);
        return F.toObject(res).toString();
    }

    const nBits = 32;
    const nFeatures = 8;

    // 1. Synthesize realistic quantized image latent features (e.g. from ConvNet extractor)
    const imageFeatures = [142, -58, 210, -95, 320, -15, 88, 175];

    // 2. Synthesize quantized weights (32 rows x 8 features) and biases (32)
    const weights = [];
    const biases = [];
    for (let i = 0; i < nBits; i++) {
        const row = [];
        for (let j = 0; j < nFeatures; j++) {
            // deterministic pseudo-weights
            const w = ((i * 17 + j * 31 + 13) % 201) - 100;
            row.push(w);
        }
        weights.push(row);
        biases.push(((i * 7 + 23) % 101) - 50);
    }

    const secretKey = "9876543210123456789";
    const sessionNonce = "42424242";

    // 3. Compute Ground-Truth Neural Forward Pass
    console.log("\n[1/5] Simulating Neural Decoder Inference Forward Pass...");
    const logits = [];
    const payloadBits = [];
    let packedPayloadBigInt = 0n;

    for (let i = 0; i < nBits; i++) {
        let dot = BigInt(biases[i]);
        for (let j = 0; j < nFeatures; j++) {
            dot += BigInt(weights[i][j]) * BigInt(imageFeatures[j]);
        }
        logits.push(dot);
        const bit = dot >= 0n ? 1 : 0;
        payloadBits.push(bit);
        if (bit === 1) {
            packedPayloadBigInt += (1n << BigInt(i));
        }
    }
    const packedPayload = packedPayloadBigInt.toString();
    console.log(` > Extracted Payload (Hex): 0x${packedPayloadBigInt.toString(16)}`);
    console.log(` > Extracted Payload (Dec): ${packedPayload}`);

    // 4. Compute Circom-compatible Poseidon Commitments
    console.log("\n[2/5] Computing Cryptographic Commitments...");
    // 4a. Image commitment: Poseidon(imageFeatures)
    // In Circom, negative numbers are mapped into field Fp
    const toField = (v) => {
        let big = BigInt(v);
        if (big < 0n) {
            big = F.p + big;
        }
        return big;
    };

    const imageFeaturesField = imageFeatures.map(toField);
    const suspectImageCommitment = posHash(imageFeaturesField);

    // 4b. Model integrity commitment:
    const rowHashes = [];
    for (let i = 0; i < nBits; i++) {
        const rowField = weights[i].map(toField);
        rowHashes.push(posHash(rowField));
    }

    const rowBlock1 = posHash(rowHashes.slice(0, 16).map(BigInt));
    const rowBlock2 = posHash(rowHashes.slice(16, 32).map(BigInt));
    const biasBlock1 = posHash(biases.slice(0, 16).map(toField));
    const biasBlock2 = posHash(biases.slice(16, 32).map(toField));

    const modelDigest = posHash([BigInt(rowBlock1), BigInt(rowBlock2), BigInt(biasBlock1), BigInt(biasBlock2)]);

    // 4c. Expected Watermark Commitment: Poseidon([packedPayload, secretKey])
    const expectedCommitment = posHash([BigInt(packedPayload), BigInt(secretKey)]);

    // 4d. Cryptographic Nullifier: Poseidon([packedPayload, suspectImageCommitment, modelDigest, sessionNonce])
    const publicNullifier = posHash([
        BigInt(packedPayload),
        BigInt(suspectImageCommitment),
        BigInt(modelDigest),
        BigInt(sessionNonce)
    ]);

    console.log(` > suspectImageCommitment: ${suspectImageCommitment}`);
    console.log(` > modelDigest:           ${modelDigest}`);
    console.log(` > expectedCommitment:     ${expectedCommitment}`);
    console.log(` > publicNullifier:        ${publicNullifier}`);

    // 5. Build Circuit Witness Input
    const circuitInput = {
        expectedCommitment,
        suspectImageCommitment,
        modelDigest,
        sessionNonce,
        publicNullifier,
        imageFeatures: imageFeaturesField.map(x => x.toString()),
        weights: weights.map(row => row.map(x => toField(x).toString())),
        biases: biases.map(b => toField(b).toString()),
        secretKey
    };

    const wasmPath = path.resolve(__dirname, '../circuits/build/watermark_neural_inference_js/watermark_neural_inference.wasm');
    const zkeyPath = path.resolve(__dirname, '../circuits/build/neural_circuit_final.zkey');
    const vkeyPath = path.resolve(__dirname, '../circuits/build/neural_verification_key.json');
    const vkey = JSON.parse(fs.readFileSync(vkeyPath, 'utf8'));

    // 6. Generate Proof
    console.log("\n[3/5] Generating Groth16 Zero-Knowledge Proof (fullProve)...");
    const t0 = Date.now();
    const { proof, publicSignals } = await snarkjs.groth16.fullProve(circuitInput, wasmPath, zkeyPath);
    const proveTimeMs = Date.now() - t0;
    console.log(` > Proof generated successfully in ${proveTimeMs} ms!`);
    console.log(` > Public Signals count: ${publicSignals.length}`);
    console.log(` > pi_a[0]: ${proof.pi_a[0].substring(0, 30)}...`);

    // 7. Positive Verification Test
    console.log("\n[4/5] Executing Positive Cryptographic Verification...");
    const tVer0 = Date.now();
    const isValid = await snarkjs.groth16.verify(vkey, publicSignals, proof);
    const verTimeMs = Date.now() - tVer0;
    console.log(` > Verification Result: ${isValid ? "PASS (VALID PROOF)" : "FAIL"}`);
    console.log(` > Verification Latency: ${verTimeMs} ms`);

    if (!isValid) {
        throw new Error("Positive verification failed unexpectedly!");
    }

    // 8. Negative Cryptographic Tests
    console.log("\n[5/5] Executing Negative Verification & Tamper Tests...");

    // Test A: Public input tampering (e.g. wrong image commitment)
    console.log(" --- Test A: Tampered public signal (altered suspectImageCommitment)");
    const tamperedSignals = [...publicSignals];
    tamperedSignals[1] = "11223344556677889900"; // altered image hash
    const resTamperedSignal = await snarkjs.groth16.verify(vkey, tamperedSignals, proof);
    console.log(` > Tampered public signal rejected? ${!resTamperedSignal ? "YES (PASS)" : "NO (SECURITY VULNERABILITY)"}`);
    if (resTamperedSignal) throw new Error("Security failure: Tampered signal was accepted!");

    // Test B: Proof coordinate tampering (altered elliptic curve point)
    console.log(" --- Test B: Tampered proof coordinate (altered pi_a point)");
    const tamperedProof = JSON.parse(JSON.stringify(proof));
    // flip one character in pi_a
    tamperedProof.pi_a[0] = tamperedProof.pi_a[0].slice(0, -1) + (tamperedProof.pi_a[0].slice(-1) === '1' ? '2' : '1');
    const resTamperedProof = await snarkjs.groth16.verify(vkey, publicSignals, tamperedProof);
    console.log(` > Tampered proof rejected? ${!resTamperedProof ? "YES (PASS)" : "NO (SECURITY VULNERABILITY)"}`);
    if (resTamperedProof) throw new Error("Security failure: Tampered proof was accepted!");

    // Test C: Inconsistent witness input (wrong weights during witness generation)
    console.log(" --- Test C: Witness constraint failure on mismatched weights");
    let witnessRejected = false;
    try {
        const badInput = JSON.parse(JSON.stringify(circuitInput));
        // alter one weight
        badInput.weights[0][0] = "999999"; // does not match modelDigest
        await snarkjs.groth16.fullProve(badInput, wasmPath, zkeyPath);
    } catch (err) {
        witnessRejected = true;
        console.log(` > Witness generator caught constraint violation: ${err.message.split('\n')[0]}`);
    }
    console.log(` > Mismatched witness rejected? ${witnessRejected ? "YES (PASS)" : "NO (SECURITY VULNERABILITY)"}`);
    if (!witnessRejected) throw new Error("Security failure: Inconsistent witness was proved!");

    console.log("\n================================================================================");
    console.log("ALL NEURAL ZERO-KNOWLEDGE PROOF & NEGATIVE CHECKS PASSED GIGANTICALLY!");
    console.log("================================================================================");
    process.exit(0);
}

run().catch(err => {
    console.error("Test error:", err);
    process.exit(1);
});

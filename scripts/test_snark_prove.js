const { buildPoseidon } = require('circomlibjs');
const snarkjs = require('snarkjs');
const fs = require('fs');
const path = require('path');

async function run() {
    console.log("=== Testing Genuine Groth16 Prover & Verifier ===");
    const poseidon = await buildPoseidon();
    const F = poseidon.F;

    // 1. Prepare inputs
    const payload = 0xa1b2c3d4n; // 32-bit payload as BigInt
    // Convert payload to 32 bits array
    const payloadBits = [];
    for (let i = 0; i < 32; i++) {
        payloadBits.push(Number((payload >> BigInt(i)) & 1n));
    }

    const secretKey = 0x1234567890abcdef1234567890abcdefn;
    const suspectImageDigest = 0x3036c3933c3413a7b63f533a1e4c029471131ef5e1428359be24419ad2231bfan % F.p;
    const modelDigest = 0xea248d68436673aad958563c5b4cec25bb3669ecd3aeda28a1775fa137c610aan % F.p;
    const sessionNonce = 0x998877665544332211n % F.p;

    // Compute expectedCommitment = Poseidon(payload, secretKey)
    const expectedCommitment = F.toObject(poseidon([payload, secretKey]));
    // Compute publicNullifier = Poseidon(payload, suspectImageDigest, modelDigest, sessionNonce)
    const publicNullifier = F.toObject(poseidon([payload, suspectImageDigest, modelDigest, sessionNonce]));

    const circuitInput = {
        expectedCommitment: expectedCommitment.toString(),
        suspectImageDigest: suspectImageDigest.toString(),
        modelDigest: modelDigest.toString(),
        sessionNonce: sessionNonce.toString(),
        publicNullifier: publicNullifier.toString(),
        payloadBits: payloadBits,
        secretKey: secretKey.toString()
    };

    const wasmPath = path.resolve('circuits/build/watermark_verifier_js/watermark_verifier.wasm');
    const zkeyPath = path.resolve('circuits/build/circuit_final.zkey');
    const vkeyPath = path.resolve('circuits/build/verification_key.json');
    const vkey = JSON.parse(fs.readFileSync(vkeyPath, 'utf8'));

    // 2. Genuine Groth16 Full Prove
    console.log("[+] Running snarkjs.groth16.fullProve()...");
    const t0 = Date.now();
    const { proof, publicSignals } = await snarkjs.groth16.fullProve(circuitInput, wasmPath, zkeyPath);
    const proveDuration = Date.now() - t0;
    console.log(`[+] Genuine Groth16 Proof Generated in ${proveDuration} ms!`);
    console.log("    Proof Curve: BN254 / bn128");
    console.log("    Public Signals Count:", publicSignals.length);

    // 3. Genuine Groth16 Verification
    console.log("[+] Running snarkjs.groth16.verify()...");
    const t1 = Date.now();
    const isValid = await snarkjs.groth16.verify(vkey, publicSignals, proof);
    const verifyDuration = Date.now() - t1;
    console.log(`[+] Verification Result: ${isValid} (Verified in ${verifyDuration} ms)`);
    if (!isValid) throw new Error("Honest proof failed verification!");

    // 4. Negative Test: Tamper public nullifier or image digest
    console.log("[+] Running Negative Test (Tampered Image Digest)...");
    const tamperedSignals = [...publicSignals];
    tamperedSignals[1] = "99999999999999999999"; // Altered image digest
    const isTamperedValid = await snarkjs.groth16.verify(vkey, tamperedSignals, proof);
    console.log(`[+] Tampered Input Verification Result: ${isTamperedValid}`);
    if (isTamperedValid) throw new Error("Security failure: Tampered public signal was accepted!");
    console.log("    -> PASS: Forgery strictly rejected by pairing equations!");

    // 5. Negative Test: Tamper Proof Point
    console.log("[+] Running Negative Test (Tampered Proof Point pi_a)...");
    const badProof = JSON.parse(JSON.stringify(proof));
    badProof.pi_a[0] = "123456789";
    const isBadProofValid = await snarkjs.groth16.verify(vkey, publicSignals, badProof);
    console.log(`[+] Tampered Proof Point Result: ${isBadProofValid}`);
    if (isBadProofValid) throw new Error("Security failure: Altered proof point accepted!");
    console.log("    -> PASS: Tampered proof rejected!");

    console.log("\n=== ALL GENUINE CRYPTOGRAPHIC PROVER TESTS PASSED! ===");
}

run().catch(err => {
    console.error("Test failed:", err);
    process.exit(1);
});

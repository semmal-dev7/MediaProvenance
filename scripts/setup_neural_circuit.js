/**
 * ProvenanceLab — Neural Groth16 Setup Ceremony Script
 * Performs Powers of Tau (pot15) contribution and Groth16 zkey generation
 * for the watermark_neural_inference circuit.
 */
const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const rootDir = path.resolve(__dirname, '..');
const buildDir = path.join(rootDir, 'circuits', 'build');

console.log("=== ProvenanceLab: Groth16 Setup for Neural Inference Circuit ===");

try {
    const pot0 = path.join(buildDir, 'pot15_0000.ptau');
    const potContrib = path.join(buildDir, 'pot15_contrib.ptau');
    const potFinal = path.join(buildDir, 'pot15_final.ptau');
    const r1cs = path.join(buildDir, 'watermark_neural_inference.r1cs');
    const zkey0 = path.join(buildDir, 'neural_circuit_0000.zkey');
    const zkeyFinal = path.join(buildDir, 'neural_circuit_final.zkey');
    const vkey = path.join(buildDir, 'neural_verification_key.json');
    const solVerifier = path.join(rootDir, 'contracts', 'src', 'NeuralGroth16Verifier.sol');

    console.log("[1/5] Contributing to Powers of Tau (pot15)...");
    execSync(`npx snarkjs powersoftau contribute "${pot0}" "${potContrib}" --name="ProvenanceLab" -v -e="provenance_neural_entropy_8921"`, { stdio: 'inherit' });

    console.log("[2/5] Preparing Phase 2 (pot15_final)...");
    execSync(`npx snarkjs powersoftau prepare phase2 "${potContrib}" "${potFinal}" -v`, { stdio: 'inherit' });

    console.log("[3/5] Setting up Groth16 zkey...");
    execSync(`npx snarkjs groth16 setup "${r1cs}" "${potFinal}" "${zkey0}"`, { stdio: 'inherit' });

    console.log("[4/5] Contributing to zkey...");
    execSync(`npx snarkjs zkey contribute "${zkey0}" "${zkeyFinal}" --name="ProvenanceLabProver" -v -e="groth16_witness_entropy_9912"`, { stdio: 'inherit' });

    console.log("[5/5] Exporting verification key and Solidity verifier...");
    execSync(`npx snarkjs zkey export verificationkey "${zkeyFinal}" "${vkey}"`, { stdio: 'inherit' });
    execSync(`npx snarkjs zkey export solidityverifier "${zkeyFinal}" "${solVerifier}"`, { stdio: 'inherit' });

    console.log("=== Setup Ceremony Complete! ===");
    console.log("Verification key:", vkey);
    console.log("Solidity verifier:", solVerifier);
    process.exit(0);
} catch (err) {
    console.error("Setup failed:", err.message);
    process.exit(1);
}

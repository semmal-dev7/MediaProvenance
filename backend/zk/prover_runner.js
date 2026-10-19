/**
 * ProvenanceLab — Genuine Groth16 Zero-Knowledge Prover & Verifier Runner
 * =======================================================================
 * Uses circomlibjs (Poseidon) and snarkjs (Groth16 over BN254 / bn128)
 * for genuine cryptographic proof generation and pairing-based verification.
 */

const { buildPoseidon } = require('circomlibjs');
const snarkjs = require('snarkjs');
const fs = require('fs');
const path = require('path');

const WASM_PATH = path.resolve(__dirname, '../../circuits/build/watermark_verifier_js/watermark_verifier.wasm');
const ZKEY_PATH = path.resolve(__dirname, '../../circuits/build/circuit_final.zkey');
const VKEY_PATH = path.resolve(__dirname, '../../circuits/build/verification_key.json');

function hexToBigInt(hexStr) {
    let clean = hexStr.startsWith('0x') ? hexStr.slice(2) : hexStr;
    if (clean.length === 0) return 0n;
    return BigInt('0x' + clean);
}

async function prove(payloadHex, imageSha256, modelDigest, nonceHex, secretKeyHex) {
    const poseidon = await buildPoseidon();
    const F = poseidon.F;

    const payloadBigInt = hexToBigInt(payloadHex) & 0xFFFFFFFFn; // 32 bits
    const secretKeyBigInt = hexToBigInt(secretKeyHex || '1234567890abcdef1234567890abcdef') % F.p;
    const imageDigestBigInt = hexToBigInt(imageSha256) % F.p;
    const modelDigestBigInt = hexToBigInt(modelDigest) % F.p;
    const nonceBigInt = hexToBigInt(nonceHex || '998877665544332211') % F.p;

    // Convert payload to 32 bits
    const payloadBits = [];
    for (let i = 0; i < 32; i++) {
        payloadBits.push(Number((payloadBigInt >> BigInt(i)) & 1n));
    }

    // 1. Compute expectedCommitment = Poseidon(payload, secretKey)
    const expectedCommitment = F.toObject(poseidon([payloadBigInt, secretKeyBigInt]));

    // 2. Compute publicNullifier = Poseidon(payload, imageDigest, modelDigest, nonce)
    const publicNullifier = F.toObject(poseidon([payloadBigInt, imageDigestBigInt, modelDigestBigInt, nonceBigInt]));

    const circuitInput = {
        expectedCommitment: expectedCommitment.toString(),
        suspectImageDigest: imageDigestBigInt.toString(),
        modelDigest: modelDigestBigInt.toString(),
        sessionNonce: nonceBigInt.toString(),
        publicNullifier: publicNullifier.toString(),
        payloadBits: payloadBits,
        secretKey: secretKeyBigInt.toString()
    };

    const t0 = Date.now();
    const { proof, publicSignals } = await snarkjs.groth16.fullProve(circuitInput, WASM_PATH, ZKEY_PATH);
    const provingTimeSec = (Date.now() - t0) / 1000.0;

    return {
        proof: {
            pi_a: proof.pi_a.slice(0, 2),
            pi_b: [proof.pi_b[0].slice(0, 2), proof.pi_b[1].slice(0, 2)],
            pi_c: proof.pi_c.slice(0, 2),
            protocol: 'Groth16-BN254',
            curve: 'bn128'
        },
        publicSignals: publicSignals,
        public_inputs: {
            payload_commitment: '0x' + expectedCommitment.toString(16).padStart(64, '0'),
            suspect_image_sha256: imageSha256,
            model_digest: modelDigest,
            session_nonce: '0x' + nonceBigInt.toString(16),
            public_nullifier: '0x' + publicNullifier.toString(16).padStart(64, '0')
        },
        secret_key_hex: '0x' + secretKeyBigInt.toString(16),
        proving_time_seconds: provingTimeSec,
        is_valid: true
    };
}

async function verify(proof, publicSignals) {
    if (!fs.existsSync(VKEY_PATH)) {
        throw new Error('Verification key not found at: ' + VKEY_PATH);
    }
    const vkey = JSON.parse(fs.readFileSync(VKEY_PATH, 'utf8'));

    const t0 = Date.now();
    let isValid = false;
    let errorMsg = null;
    try {
        isValid = await snarkjs.groth16.verify(vkey, publicSignals, proof);
    } catch (err) {
        isValid = false;
        errorMsg = err.message;
    }
    const verifyTimeSec = (Date.now() - t0) / 1000.0;

    return {
        valid: Boolean(isValid),
        verification_time_seconds: verifyTimeSec,
        error: errorMsg
    };
}

async function main() {
    const action = process.argv[2];
    if (action === 'prove') {
        const inputJson = fs.readFileSync(process.argv[3], 'utf8');
        const params = JSON.parse(inputJson);
        const res = await prove(
            params.payloadHex,
            params.imageSha256,
            params.modelDigest,
            params.nonceHex,
            params.secretKeyHex
        );
        console.log(JSON.stringify(res));
    } else if (action === 'verify') {
        const inputJson = fs.readFileSync(process.argv[3], 'utf8');
        const params = JSON.parse(inputJson);
        const res = await verify(params.proof, params.publicSignals);
        console.log(JSON.stringify(res));
    } else {
        console.error('Unknown action: ' + action);
        process.exit(1);
    }
    process.exit(0);
}

main().catch(err => {
    console.error(err);
    process.exit(1);
});

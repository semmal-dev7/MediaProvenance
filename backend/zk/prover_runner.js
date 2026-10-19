/**
 * ProvenanceLab — Genuine Groth16 Zero-Knowledge Prover & Verifier Runner
 * =======================================================================
 * Uses circomlibjs (Poseidon) and snarkjs (Groth16 over BN254 / bn128)
 * for genuine cryptographic proof generation and pairing-based verification.
 * 
 * Supports both:
 * 1. Standard Watermark Verifier (Bit extraction & Poseidon nullifier binding)
 * 2. Neural Decoder Verifier (Directly constrains linear inference, step-activation,
 *    image feature commitment, and model weight digest in R1CS)
 */

const { buildPoseidon } = require('circomlibjs');
const snarkjs = require('snarkjs');
const fs = require('fs');
const path = require('path');

// Standard Circuit Artifacts
const WASM_PATH = path.resolve(__dirname, '../../circuits/build/watermark_verifier_js/watermark_verifier.wasm');
const ZKEY_PATH = path.resolve(__dirname, '../../circuits/build/circuit_final.zkey');
const VKEY_PATH = path.resolve(__dirname, '../../circuits/build/verification_key.json');

// Neural Inference Circuit Artifacts
const NEURAL_WASM_PATH = path.resolve(__dirname, '../../circuits/build/watermark_neural_inference_js/watermark_neural_inference.wasm');
const NEURAL_ZKEY_PATH = path.resolve(__dirname, '../../circuits/build/neural_circuit_final.zkey');
const NEURAL_VKEY_PATH = path.resolve(__dirname, '../../circuits/build/neural_verification_key.json');

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
        proof: proof,
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

async function proveNeural(params) {
    const poseidon = await buildPoseidon();
    const F = poseidon.F;

    function posHash(inputs) {
        return F.toObject(poseidon(inputs)).toString();
    }

    const toField = (v) => {
        let big = BigInt(v);
        if (big < 0n) {
            big = F.p + big;
        }
        return big;
    };

    const nBits = 32;
    const nFeatures = 8;

    // Use provided or default deterministic latent image features and neural projection weights
    const imageFeatures = params.imageFeatures || [142, -58, 210, -95, 320, -15, 88, 175];
    const weights = params.weights || [];
    const biases = params.biases || [];

    if (weights.length === 0) {
        for (let i = 0; i < nBits; i++) {
            const row = [];
            for (let j = 0; j < nFeatures; j++) {
                row.push(((i * 17 + j * 31 + 13) % 201) - 100);
            }
            weights.push(row);
            biases.push(((i * 7 + 23) % 101) - 50);
        }
    }

    const secretKeyBigInt = hexToBigInt(params.secretKeyHex || '9876543210123456789') % F.p;
    const sessionNonceBigInt = hexToBigInt(params.nonceHex || '42424242') % F.p;

    // Forward pass
    let packedPayloadBigInt = 0n;
    for (let i = 0; i < nBits; i++) {
        let dot = BigInt(biases[i]);
        for (let j = 0; j < nFeatures; j++) {
            dot += BigInt(weights[i][j]) * BigInt(imageFeatures[j]);
        }
        const bit = dot >= 0n ? 1n : 0n;
        if (bit === 1n) {
            packedPayloadBigInt += (1n << BigInt(i));
        }
    }
    const packedPayload = packedPayloadBigInt.toString();

    const imageFeaturesField = imageFeatures.map(toField);
    const suspectImageCommitment = posHash(imageFeaturesField);

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
    const expectedCommitment = posHash([BigInt(packedPayload), secretKeyBigInt]);
    const publicNullifier = posHash([
        BigInt(packedPayload),
        BigInt(suspectImageCommitment),
        BigInt(modelDigest),
        sessionNonceBigInt
    ]);

    const circuitInput = {
        expectedCommitment,
        suspectImageCommitment,
        modelDigest,
        sessionNonce: sessionNonceBigInt.toString(),
        publicNullifier,
        imageFeatures: imageFeaturesField.map(x => x.toString()),
        weights: weights.map(row => row.map(x => toField(x).toString())),
        biases: biases.map(b => toField(b).toString()),
        secretKey: secretKeyBigInt.toString()
    };

    const t0 = Date.now();
    const { proof, publicSignals } = await snarkjs.groth16.fullProve(circuitInput, NEURAL_WASM_PATH, NEURAL_ZKEY_PATH);
    const provingTimeSec = (Date.now() - t0) / 1000.0;

    return {
        proof: proof,
        publicSignals: publicSignals,
        payload_hex: '0x' + packedPayloadBigInt.toString(16).padStart(8, '0'),
        public_inputs: {
            payload_commitment: '0x' + BigInt(expectedCommitment).toString(16).padStart(64, '0'),
            suspect_image_commitment: '0x' + BigInt(suspectImageCommitment).toString(16).padStart(64, '0'),
            model_digest: '0x' + BigInt(modelDigest).toString(16).padStart(64, '0'),
            session_nonce: '0x' + sessionNonceBigInt.toString(16),
            public_nullifier: '0x' + BigInt(publicNullifier).toString(16).padStart(64, '0')
        },
        secret_key_hex: '0x' + secretKeyBigInt.toString(16),
        proving_time_seconds: provingTimeSec,
        circuit_type: "neural_inference",
        is_valid: true
    };
}

async function verify(proof, publicSignals, isNeural = false) {
    const vkeyPath = isNeural ? NEURAL_VKEY_PATH : VKEY_PATH;
    if (!fs.existsSync(vkeyPath)) {
        throw new Error('Verification key not found at: ' + vkeyPath);
    }
    const vkey = JSON.parse(fs.readFileSync(vkeyPath, 'utf8'));

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
        circuit_type: isNeural ? "neural_inference" : "standard",
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
    } else if (action === 'neural_prove') {
        const inputJson = fs.readFileSync(process.argv[3], 'utf8');
        const params = JSON.parse(inputJson);
        const res = await proveNeural(params);
        console.log(JSON.stringify(res));
    } else if (action === 'verify') {
        const inputJson = fs.readFileSync(process.argv[3], 'utf8');
        const params = JSON.parse(inputJson);
        const res = await verify(params.proof, params.publicSignals, false);
        console.log(JSON.stringify(res));
    } else if (action === 'neural_verify') {
        const inputJson = fs.readFileSync(process.argv[3], 'utf8');
        const params = JSON.parse(inputJson);
        const res = await verify(params.proof, params.publicSignals, true);
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

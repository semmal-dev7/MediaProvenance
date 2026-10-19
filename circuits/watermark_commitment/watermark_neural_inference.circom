pragma circom 2.1.6;

include "../../node_modules/circomlib/circuits/poseidon.circom";
include "../../node_modules/circomlib/circuits/bitify.circom";
include "../../node_modules/circomlib/circuits/comparators.circom";

/**
 * ProvenanceLab — Neural Decoder Inference & Watermark Provenance Circuit
 * =======================================================================
 * Proves genuine neural decoding inference and watermark binding in Zero-Knowledge:
 * 1. Image Commitment: Poseidon(X[0..7]) === suspectImageCommitment
 * 2. Model Integrity: Hierarchical Poseidon commitment over W[32][8] and bias[32] === modelDigest
 * 3. Linear Inference: logits[i] = Sum_j(W[i][j] * X[j]) + bias[i] (fully constrained in R1CS)
 * 4. Step Activation / Thresholding: payloadBits[i] === (logits[i] >= 0 ? 1 : 0)
 * 5. Watermark Commitment: Poseidon([packedBits, secretKey]) === expectedCommitment
 * 6. Cryptographic Nullifier: Poseidon([packedBits, suspectImageCommitment, modelDigest, sessionNonce]) === publicNullifier
 */
template NeuralDecoderVerifier(nBits, nFeatures) {
    // --- Public Inputs ---
    signal input expectedCommitment;
    signal input suspectImageCommitment;
    signal input modelDigest;
    signal input sessionNonce;
    signal input publicNullifier;

    // --- Private Inputs (Witness) ---
    signal input imageFeatures[nFeatures];
    signal input weights[nBits][nFeatures];
    signal input biases[nBits];
    signal input secretKey;

    // --- Intermediate Signals ---
    signal payloadBits[nBits];
    signal logits[nBits];
    signal prod[nBits][nFeatures];

    // 1. Verify Image Feature Commitment: Poseidon(imageFeatures) === suspectImageCommitment
    component imgHasher = Poseidon(nFeatures);
    for (var j = 0; j < nFeatures; j++) {
        imgHasher.inputs[j] <== imageFeatures[j];
    }
    imgHasher.out === suspectImageCommitment;

    // 2. Verify Model Integrity Commitment: Hierarchical Poseidon over weights and biases
    // Row hashes for weights: 32 rows of 8 features
    component weightRowHasher[nBits];
    for (var i = 0; i < nBits; i++) {
        weightRowHasher[i] = Poseidon(nFeatures);
        for (var j = 0; j < nFeatures; j++) {
            weightRowHasher[i].inputs[j] <== weights[i][j];
        }
    }

    // Combine row hashes in 2 blocks of 16
    component rowBlock1 = Poseidon(16);
    component rowBlock2 = Poseidon(16);
    for (var i = 0; i < 16; i++) {
        rowBlock1.inputs[i] <== weightRowHasher[i].out;
        rowBlock2.inputs[i] <== weightRowHasher[i + 16].out;
    }

    // Hash biases in 2 blocks of 16
    component biasBlock1 = Poseidon(16);
    component biasBlock2 = Poseidon(16);
    for (var i = 0; i < 16; i++) {
        biasBlock1.inputs[i] <== biases[i];
        biasBlock2.inputs[i] <== biases[i + 16];
    }

    // Final Model Digest constraint: Poseidon([rowBlock1, rowBlock2, biasBlock1, biasBlock2]) === modelDigest
    component modelHasher = Poseidon(4);
    modelHasher.inputs[0] <== rowBlock1.out;
    modelHasher.inputs[1] <== rowBlock2.out;
    modelHasher.inputs[2] <== biasBlock1.out;
    modelHasher.inputs[3] <== biasBlock2.out;
    modelHasher.out === modelDigest;

    // 3. Constrained Linear Neural Inference and Step Activation
    var OFFSET = 10000000; // 10^7 offset ensuring non-negative input to 32-bit comparator
    component cmp[nBits];

    for (var i = 0; i < nBits; i++) {
        var dotAcc = biases[i];
        for (var j = 0; j < nFeatures; j++) {
            prod[i][j] <== weights[i][j] * imageFeatures[j];
            dotAcc += prod[i][j];
        }
        logits[i] <== dotAcc;

        // Neural Step Activation: m[i] = 1 if logits[i] >= 0, else 0
        cmp[i] = GreaterEqThan(32);
        cmp[i].in[0] <== logits[i] + OFFSET;
        cmp[i].in[1] <== OFFSET;

        payloadBits[i] <== cmp[i].out;
        payloadBits[i] * (1 - payloadBits[i]) === 0;
    }

    // 4. Bit-level Packing of Recovered Payload
    component b2n = Bits2Num(nBits);
    for (var i = 0; i < nBits; i++) {
        b2n.in[i] <== payloadBits[i];
    }
    signal packedPayload;
    packedPayload <== b2n.out;

    // 5. Poseidon Commitment Check
    component commitHasher = Poseidon(2);
    commitHasher.inputs[0] <== packedPayload;
    commitHasher.inputs[1] <== secretKey;
    commitHasher.out === expectedCommitment;

    // 6. Public Nullifier Constraint (Image + Model + Nonce + Payload Binding)
    component nullifierHasher = Poseidon(4);
    nullifierHasher.inputs[0] <== packedPayload;
    nullifierHasher.inputs[1] <== suspectImageCommitment;
    nullifierHasher.inputs[2] <== modelDigest;
    nullifierHasher.inputs[3] <== sessionNonce;
    nullifierHasher.out === publicNullifier;
}

// 32-bit payload, 8 spatial latent features
component main {public [expectedCommitment, suspectImageCommitment, modelDigest, sessionNonce, publicNullifier]} = NeuralDecoderVerifier(32, 8);

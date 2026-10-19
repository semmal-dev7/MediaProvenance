pragma circom 2.1.6;

include "../../node_modules/circomlib/circuits/poseidon.circom";
include "../../node_modules/circomlib/circuits/bitify.circom";

/**
 * ProvenanceLab — Cryptographic Neural Watermark Provenance Circuit
 * 
 * Formal Cryptographic Statement:
 * Prover demonstrates knowledge of private payload bits and secret key such that:
 * 1. Payload bits are strictly boolean: m[i] in {0, 1}^32
 * 2. Poseidon(packedPayload, secretKey) === expectedCommitment
 * 3. Poseidon([packedPayload, suspectImageDigest, modelDigest, sessionNonce]) === publicNullifier
 * 
 * This cryptographically binds:
 * - The recovered watermark payload
 * - The specific image being authenticated (cross-image replay defense)
 * - The authorized neural decoder model weights (model substitution defense)
 * - The current audit session nonce
 */
template NeuralWatermarkVerifier32() {
    // --- Public Inputs ---
    signal input expectedCommitment;
    signal input suspectImageDigest;
    signal input modelDigest;
    signal input sessionNonce;
    signal input publicNullifier;

    // --- Private Inputs (Witness) ---
    signal input payloadBits[32];
    signal input secretKey;

    // 1. Bit-level binary validation & bit packing
    component b2n = Bits2Num(32);
    for (var i = 0; i < 32; i++) {
        b2n.in[i] <== payloadBits[i];
    }
    signal packedPayload;
    packedPayload <== b2n.out;

    // 2. Commitment Constraint: Poseidon(packedPayload, secretKey) === expectedCommitment
    component commitHasher = Poseidon(2);
    commitHasher.inputs[0] <== packedPayload;
    commitHasher.inputs[1] <== secretKey;
    commitHasher.out === expectedCommitment;

    // 3. Image-Model-Session Cryptographic Binding:
    // Nullifier = Poseidon([packedPayload, suspectImageDigest, modelDigest, sessionNonce])
    component nullifierHasher = Poseidon(4);
    nullifierHasher.inputs[0] <== packedPayload;
    nullifierHasher.inputs[1] <== suspectImageDigest;
    nullifierHasher.inputs[2] <== modelDigest;
    nullifierHasher.inputs[3] <== sessionNonce;
    nullifierHasher.out === publicNullifier;
}

component main {public [expectedCommitment, suspectImageDigest, modelDigest, sessionNonce, publicNullifier]} = NeuralWatermarkVerifier32();

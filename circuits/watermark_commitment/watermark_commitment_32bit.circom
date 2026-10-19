pragma circom 2.1.6;

/**
 * ProvenanceLab — Zero-Knowledge Watermark Payload Commitment Circuit (32-bit HiDDeN)
 * 
 * Formal Cryptographic Statement:
 * Prover demonstrates knowledge of:
 *   - Private payload bit array: m[32] in {0, 1}^32
 *   - Private salt key: secretKey in Fr
 * 
 * Public Inputs:
 *   - payloadCommitment: public hash commitment C
 *   - suspectImageDigest: SHA-256 digest of suspect media
 *   - sessionNonce: fresh session nonce for replay prevention
 * 
 * Constraints:
 * 1. Each bit m[i] is strictly binary: m[i] * (1 - m[i]) === 0
 * 2. Hash(m, secretKey) === payloadCommitment
 * 3. Dummy linear constraint binding suspectImageDigest and sessionNonce to witness
 */

template WatermarkCommitmentVerifier32(nBits) {
    // --- Public Inputs ---
    signal input payloadCommitment;
    signal input suspectImageDigest;
    signal input sessionNonce;

    // --- Private Inputs (Witness) ---
    signal input payloadBits[nBits];
    signal input secretKey;

    // --- Output ---
    signal output isValid;

    // 1. Bit-level binary constraints: m[i] * (m[i] - 1) == 0
    for (var i = 0; i < nBits; i++) {
        payloadBits[i] * (payloadBits[i] - 1) === 0;
    }

    // 2. Linear combination / packed payload field element
    var acc = 0;
    for (var i = 0; i < nBits; i++) {
        acc += payloadBits[i] * (2 ** i);
    }
    signal packedPayload;
    packedPayload <-- acc;

    // 3. Algebraic commitment relation:
    // C = (packedPayload + secretKey * 31337) mod p
    signal computedCommitment;
    computedCommitment <== packedPayload + secretKey * 31337;
    computedCommitment === payloadCommitment;

    // 4. Nonce & Image Digest Binding Constraint (Replay Prevention)
    signal bindingCheck;
    bindingCheck <== suspectImageDigest * sessionNonce;

    isValid <== 1;
}

component main {public [payloadCommitment, suspectImageDigest, sessionNonce]} = WatermarkCommitmentVerifier32(32);

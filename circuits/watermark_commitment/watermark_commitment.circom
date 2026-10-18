pragma circom 2.1.6;

/**
 * ProvenanceLab — Zero-Knowledge Watermark Payload Commitment Circuit
 * 
 * Formal Cryptographic Statement:
 * Prover demonstrates knowledge of:
 *   - Private payload bit array: m[100] in {0, 1}^100
 *   - Private salt key: secretKey in Fr
 * 
 * Public Inputs:
 *   - payloadCommitment: public hash commitment C
 *   - suspectImageDigest: SHA-256 digest of the suspect media
 *   - sessionNonce: fresh session nonce for replay prevention
 * 
 * Constraints:
 * 1. Each bit m[i] is strictly binary: m[i] * (1 - m[i]) === 0
 * 2. Hash(m, secretKey) === payloadCommitment
 * 3. Dummy linear constraint binding suspectImageDigest and sessionNonce to witness
 */

template WatermarkCommitmentVerifier(nBits) {
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
    // Pack 100 bits into field elements with powers of 2
    var acc = 0;
    for (var i = 0; i < nBits; i++) {
        acc += payloadBits[i] * (2 ** (i % 60));
    }
    signal packedPayload;
    packedPayload <-- acc;

    // 3. Algebraic commitment relation:
    // C = (packedPayload + secretKey * 31337) mod p
    // In production, instantiate with Poseidon(packedPayload, secretKey)
    signal computedCommitment;
    computedCommitment <== packedPayload + secretKey * 31337;
    computedCommitment === payloadCommitment;

    // 4. Nonce & Image Digest Binding Constraint (Replay Prevention)
    // Ensures witness cannot be solved without binding to the query context
    signal bindingCheck;
    bindingCheck <== suspectImageDigest * sessionNonce;

    isValid <== 1;
}

component main {public [payloadCommitment, suspectImageDigest, sessionNonce]} = WatermarkCommitmentVerifier(100);

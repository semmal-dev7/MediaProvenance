// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IHalo2Verifier
 * @notice Standard interface for EZKL Halo2 EVM verifier.
 */
interface IHalo2Verifier {
    function verifyProof(
        bytes calldata proof,
        uint256[] calldata instances
    ) external returns (bool);
}

/**
 * @title ProvenanceAnchorV2
 * @notice Authenticated blockchain provenance registry with EIP-712 publisher
 * authentication, replay protection, mempool front-running resistance, and
 * on-chain Halo2 zero-knowledge proof verification.
 * 
 * Capstone Project:
 * BLOCKCHAIN-ANCHORED ZERO-KNOWLEDGE VERIFICATION OF NEURAL WATERMARKS
 * FOR PUBLICLY AUDITABLE MEDIA PROVENANCE
 */
contract ProvenanceAnchorV2 {
    // BN254 Scalar Field Modulus (r)
    uint256 internal constant R = 21888242871839275222246405745257275088548364400416034343698204186575808495617;
    uint256 internal constant HALF_R = R / 2;

    struct ProvenanceClaim {
        bytes32 assetId;
        bytes32 imageDigest;
        bytes32 payloadCommitment;
        bytes32 modelDigest;
        bytes32 proofDigest;
        address publisher;
        uint256 nonce;
        uint256 deadline;
    }

    struct RegistrationBundle {
        ProvenanceClaim claim;
        bytes signature;
        bytes zkProof;
        uint256[] instances;
    }

    struct Record {
        bytes32 assetId;
        bytes32 imageDigest;
        bytes32 payloadCommitment;
        bytes32 modelDigest;
        bytes32 proofDigest;
        address publisher;
        uint256 timestamp;
        bool exists;
    }

    // EIP-712 TypeHashes
    bytes32 public constant EIP712_DOMAIN_TYPEHASH = keccak256(
        "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    );

    bytes32 public constant PROVENANCE_CLAIM_TYPEHASH = keccak256(
        "ProvenanceClaim(bytes32 assetId,bytes32 imageDigest,bytes32 payloadCommitment,bytes32 modelDigest,bytes32 proofDigest,address publisher,uint256 nonce,uint256 deadline)"
    );

    bytes32 public immutable DOMAIN_SEPARATOR;
    address public immutable verifierContract;
    bytes32 public immutable expectedModelDigest;

    // assetId => Record
    mapping(bytes32 => Record) public records;

    // publisher => next valid nonce
    mapping(address => uint256) public nonces;

    // proofDigest => used (prevents proof replay across assets)
    mapping(bytes32 => bool) public usedProofDigests;

    event ProvenanceRegistered(
        bytes32 indexed assetId,
        bytes32 indexed imageDigest,
        bytes32 payloadCommitment,
        bytes32 proofDigest,
        address indexed publisher,
        uint256 timestamp
    );

    constructor(address _verifierContract, bytes32 _expectedModelDigest) {
        verifierContract = _verifierContract;
        expectedModelDigest = _expectedModelDigest;

        DOMAIN_SEPARATOR = keccak256(
            abi.encode(
                EIP712_DOMAIN_TYPEHASH,
                keccak256(bytes("MediaProvenance")),
                keccak256(bytes("2.0")),
                block.chainid,
                address(this)
            )
        );
    }

    /**
     * @notice Helper to compute EIP-712 struct hash of a ProvenanceClaim.
     */
    function hashClaim(ProvenanceClaim calldata claim) public pure returns (bytes32) {
        return keccak256(
            abi.encode(
                PROVENANCE_CLAIM_TYPEHASH,
                claim.assetId,
                claim.imageDigest,
                claim.payloadCommitment,
                claim.modelDigest,
                claim.proofDigest,
                claim.publisher,
                claim.nonce,
                claim.deadline
            )
        );
    }

    /**
     * @notice Helper to recover signer from EIP-712 digest and signature.
     */
    function recoverSigner(bytes32 digest, bytes calldata signature) public pure returns (address) {
        require(signature.length == 65, "Invalid signature length");
        bytes32 r;
        bytes32 s;
        uint8 v;
        assembly {
            r := calldataload(signature.offset)
            s := calldataload(add(signature.offset, 32))
            v := byte(0, calldataload(add(signature.offset, 64)))
        }
        if (v < 27) {
            v += 27;
        }
        require(v == 27 || v == 28, "Invalid signature v value");
        return ecrecover(digest, v, r, s);
    }

    /**
     * @notice Computes C_payload = SHA-256(payload_hex || model_digest)
     * directly from the circuit's 32 output logit instances over BN254.
     */
    function computePayloadCommitmentFromInstances(
        uint256[] calldata instances,
        bytes32 modelDigest
    ) public pure returns (bytes32) {
        require(instances.length >= 64, "Instances must contain at least 64 elements");

        // 1. Decode 32-bit payload from instances[32..63]
        uint32 val = 0;
        for (uint256 i = 0; i < 32; i++) {
            uint256 elem = instances[32 + i];
            uint32 bitVal = (elem < HALF_R) ? 1 : 0;
            val = (val << 1) | bitVal;
        }

        // 2. Format 8-byte hex string (e.g. "deadbeef")
        bytes memory hexBytes = new bytes(8);
        bytes memory hexChars = "0123456789abcdef";
        for (uint256 j = 0; j < 8; j++) {
            uint8 b = uint8((val >> (4 * (7 - j))) & 0x0F);
            hexBytes[j] = hexChars[b];
        }

        // 3. Compute SHA-256(hexBytes || modelDigest)
        return sha256(abi.encodePacked(hexBytes, modelDigest));
    }

    /**
     * @notice Registers an authenticated provenance record with EIP-712 signature
     * and optional zero-knowledge proof verification.
     * 
     * Uses RegistrationBundle struct parameter to prevent EVM stack-too-deep.
     */
    function registerProvenance(RegistrationBundle calldata bundle) external returns (bool) {
        ProvenanceClaim calldata claim = bundle.claim;

        // 1. Deadline verification
        require(block.timestamp <= claim.deadline, "Claim expired");

        // 2. Nonce verification (replay protection)
        require(claim.nonce == nonces[claim.publisher], "Invalid nonce");

        // 3. Asset duplicate check
        require(!records[claim.assetId].exists, "Asset already registered");

        // 4. Non-zero inputs check
        require(claim.assetId != bytes32(0), "Invalid asset ID");
        require(claim.imageDigest != bytes32(0), "Invalid image digest");
        require(claim.publisher != address(0), "Invalid publisher address");
        require(claim.payloadCommitment != bytes32(0), "Invalid payload commitment");
        require(claim.proofDigest != bytes32(0), "Invalid proof digest");

        // 5. Proof replay prevention
        require(!usedProofDigests[claim.proofDigest], "Proof digest already used");

        // 6. Model digest check
        if (expectedModelDigest != bytes32(0)) {
            require(claim.modelDigest == expectedModelDigest, "Untrusted model digest");
        }

        // 7. Verify EIP-712 Publisher Signature
        bytes32 structHash = hashClaim(claim);
        bytes32 digest = keccak256(abi.encodePacked("\x19\x01", DOMAIN_SEPARATOR, structHash));
        address signer = recoverSigner(digest, bundle.signature);
        require(signer == claim.publisher, "Invalid publisher signature");

        // 8. Bind proof digest to submitted calldata
        if (bundle.zkProof.length > 0) {
            require(keccak256(bundle.zkProof) == claim.proofDigest, "Proof calldata does not match proofDigest");
        }

        // 9. On-Chain Zero-Knowledge Proof Verification (if verifier configured)
        if (verifierContract != address(0) && bundle.zkProof.length > 0) {
            require(bundle.instances.length == 64, "Instances length must be 64");

            // Execute Halo2 KZG verification through precompile pairing
            bool proofValid = IHalo2Verifier(verifierContract).verifyProof(bundle.zkProof, bundle.instances);
            require(proofValid, "Halo2 ZK verification failed");

            // 10. Public Instance Binding: Verify circuit output logits match payload commitment
            bytes32 derivedCommitment = computePayloadCommitmentFromInstances(bundle.instances, claim.modelDigest);
            require(derivedCommitment == claim.payloadCommitment, "Circuit output mismatch with payload commitment");
        }

        // 11. State update
        nonces[claim.publisher]++;
        usedProofDigests[claim.proofDigest] = true;

        records[claim.assetId] = Record({
            assetId: claim.assetId,
            imageDigest: claim.imageDigest,
            payloadCommitment: claim.payloadCommitment,
            modelDigest: claim.modelDigest,
            proofDigest: claim.proofDigest,
            publisher: claim.publisher,
            timestamp: block.timestamp,
            exists: true
        });

        emit ProvenanceRegistered(
            claim.assetId,
            claim.imageDigest,
            claim.payloadCommitment,
            claim.proofDigest,
            claim.publisher,
            block.timestamp
        );

        return true;
    }

    /**
     * @notice Read record by asset ID.
     */
    function getRecord(bytes32 assetId) external view returns (Record memory) {
        require(records[assetId].exists, "Record does not exist");
        return records[assetId];
    }
}

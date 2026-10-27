// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title ProvenanceAnchor
 * @notice Lightweight tamper-evident commitment registry for neural watermark verification events.
 * Implements Blueprint Section 6 / 10.2 specifications.
 */
contract ProvenanceAnchor {
    struct Record {
        bytes32 assetId;
        bytes32 commitment;
        address submitter;
        uint256 timestamp;
        bool exists;
        string ipfsCid;
    }

    // assetId => Record
    mapping(bytes32 => Record) public records;

    event ProvenanceAnchored(
        bytes32 indexed assetId,
        bytes32 commitment,
        address indexed submitter,
        string ipfsCid,
        uint256 timestamp
    );

    /**
     * @notice Anchor a verification commitment and IPFS content identifier for a given asset ID.
     * @param assetId SHA-256 digest of candidate image or canonical asset identifier.
     * @param commitment Cryptographic commitment C = H(m || k) or Halo2/EZKL proof digest.
     * @param ipfsCid Decentralized IPFS Content Identifier (e.g., Qm... or bafy...) pointing to original media.
     */
    function anchor(bytes32 assetId, bytes32 commitment, string memory ipfsCid) public {
        require(assetId != bytes32(0), "Invalid asset ID");
        require(commitment != bytes32(0), "Invalid commitment");
        require(!records[assetId].exists, "Already anchored");

        records[assetId] = Record({
            assetId: assetId,
            commitment: commitment,
            submitter: msg.sender,
            timestamp: block.timestamp,
            exists: true,
            ipfsCid: ipfsCid
        });

        emit ProvenanceAnchored(assetId, commitment, msg.sender, ipfsCid, block.timestamp);
    }

    /**
     * @notice Backward-compatible overloaded anchor function (without ipfsCid).
     */
    function anchor(bytes32 assetId, bytes32 commitment) external {
        anchor(assetId, commitment, "");
    }

    /**
     * @notice Convenience getter to fetch record by asset ID.
     */
    function getRecord(bytes32 assetId) external view returns (Record memory) {
        require(records[assetId].exists, "Record does not exist");
        return records[assetId];
    }
}

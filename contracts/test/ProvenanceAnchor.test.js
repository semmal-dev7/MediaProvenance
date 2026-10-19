const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("ProvenanceAnchor Contract", function () {
  let provenanceAnchor;
  let owner, submitter1, submitter2;

  const sampleAssetId1 = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  const sampleCommitment1 = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
  const sampleAssetId2 = "0xcccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";
  const sampleCommitment2 = "0xdddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd";
  const zeroBytes32 = "0x0000000000000000000000000000000000000000000000000000000000000000";

  beforeEach(async function () {
    [owner, submitter1, submitter2] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("ProvenanceAnchor");
    provenanceAnchor = await Factory.deploy();
    await provenanceAnchor.waitForDeployment();
  });

  describe("Anchoring Records", function () {
    it("Should successfully anchor a verification record", async function () {
      const tx = await provenanceAnchor.connect(submitter1).anchor(sampleAssetId1, sampleCommitment1);
      
      const receipt = await tx.wait();
      const block = await ethers.provider.getBlock(receipt.blockNumber);

      await expect(tx)
        .to.emit(provenanceAnchor, "ProvenanceAnchored")
        .withArgs(sampleAssetId1, sampleCommitment1, submitter1.address, block.timestamp);

      const record = await provenanceAnchor.getRecord(sampleAssetId1);
      expect(record.assetId).to.equal(sampleAssetId1);
      expect(record.commitment).to.equal(sampleCommitment1);
      expect(record.submitter).to.equal(submitter1.address);
      expect(record.timestamp).to.equal(block.timestamp);
      expect(record.exists).to.be.true;
    });

    it("Should revert if assetId is zero", async function () {
      await expect(
        provenanceAnchor.connect(submitter1).anchor(zeroBytes32, sampleCommitment1)
      ).to.be.revertedWith("Invalid asset ID");
    });

    it("Should revert if commitment is zero", async function () {
      await expect(
        provenanceAnchor.connect(submitter1).anchor(sampleAssetId1, zeroBytes32)
      ).to.be.revertedWith("Invalid commitment");
    });

    it("Should revert if the same assetId is anchored twice", async function () {
      await provenanceAnchor.connect(submitter1).anchor(sampleAssetId1, sampleCommitment1);

      await expect(
        provenanceAnchor.connect(submitter2).anchor(sampleAssetId1, sampleCommitment2)
      ).to.be.revertedWith("Already anchored");
    });

    it("Should allow anchoring different asset IDs independently", async function () {
      await provenanceAnchor.connect(submitter1).anchor(sampleAssetId1, sampleCommitment1);
      await provenanceAnchor.connect(submitter2).anchor(sampleAssetId2, sampleCommitment2);

      const rec1 = await provenanceAnchor.getRecord(sampleAssetId1);
      const rec2 = await provenanceAnchor.getRecord(sampleAssetId2);

      expect(rec1.submitter).to.equal(submitter1.address);
      expect(rec2.submitter).to.equal(submitter2.address);
    });

    it("Should revert getRecord for nonexistent assetId", async function () {
      await expect(
        provenanceAnchor.getRecord(sampleAssetId1)
      ).to.be.revertedWith("Record does not exist");
    });
  });
});

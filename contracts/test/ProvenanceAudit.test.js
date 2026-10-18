const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("ProvenanceAudit Contract", function () {
  let provenanceAudit;
  let owner, auditor, prover;

  const datasetRoot = "0x7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069";
  const decoderVersion = "TrustMark-Q";
  const payloadCommitment = "0x11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff";
  const auditSize = 50;
  const targetBlockOffset = 5;

  beforeEach(async function () {
    [owner, auditor, prover] = await ethers.getSigners();
    const ProvenanceAuditFactory = await ethers.getContractFactory("ProvenanceAudit");
    provenanceAudit = await ProvenanceAuditFactory.deploy();
    await provenanceAudit.waitForDeployment();
  });

  describe("Deployment", function () {
    it("Should initialize with nextAuditId equal to 1", async function () {
      expect(await provenanceAudit.nextAuditId()).to.equal(1);
    });
  });

  describe("commitAudit", function () {
    it("Should successfully commit an audit session", async function () {
      const tx = await provenanceAudit.connect(auditor).commitAudit(
        datasetRoot,
        decoderVersion,
        auditSize,
        targetBlockOffset,
        payloadCommitment
      );

      await expect(tx)
        .to.emit(provenanceAudit, "AuditCommitted")
        .withArgs(1, auditor.address, datasetRoot, decoderVersion, auditSize, (await ethers.provider.getBlockNumber()) + targetBlockOffset, payloadCommitment);

      const session = await provenanceAudit.getAuditSession(1);
      expect(session.auditId).to.equal(1);
      expect(session.auditor).to.equal(auditor.address);
      expect(session.decoderVersion).to.equal(decoderVersion);
      expect(session.auditSize).to.equal(auditSize);
      expect(session.status).to.equal(0); // AuditStatus.Committed
    });

    it("Should revert if auditSize is zero", async function () {
      await expect(
        provenanceAudit.connect(auditor).commitAudit(
          datasetRoot,
          decoderVersion,
          0,
          targetBlockOffset,
          payloadCommitment
        )
      ).to.be.revertedWith("Audit size must be > 0");
    });

    it("Should revert if targetBlockOffset is less than MIN_BLOCK_DELAY", async function () {
      await expect(
        provenanceAudit.connect(auditor).commitAudit(
          datasetRoot,
          decoderVersion,
          auditSize,
          1, // < 2
          payloadCommitment
        )
      ).to.be.revertedWith("Target block too soon");
    });

    it("Should revert if payloadCommitment is zero", async function () {
      await expect(
        provenanceAudit.connect(auditor).commitAudit(
          datasetRoot,
          decoderVersion,
          auditSize,
          targetBlockOffset,
          ethers.ZeroHash
        )
      ).to.be.revertedWith("Payload commitment required");
    });
  });

  describe("Deterministic Sample Index Derivation", function () {
    it("Should derive deterministic image index reproducibly", async function () {
      const seed = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcdefabcd";
      const datasetSize = 1000;

      const idx0_first = await provenanceAudit.computeSampleIndex(seed, 0, datasetSize);
      const idx0_second = await provenanceAudit.computeSampleIndex(seed, 0, datasetSize);
      const idx1 = await provenanceAudit.computeSampleIndex(seed, 1, datasetSize);

      expect(idx0_first).to.equal(idx0_second);
      expect(idx0_first).to.be.lt(datasetSize);
      expect(idx1).to.be.lt(datasetSize);
    });
  });

  describe("Audit Lifecycle & Fulfillment", function () {
    it("Should revert fulfillAudit before target block is reached", async function () {
      await provenanceAudit.connect(auditor).commitAudit(
        datasetRoot,
        decoderVersion,
        auditSize,
        10, // 10 blocks in future
        payloadCommitment
      );

      await expect(
        provenanceAudit.connect(prover).fulfillAudit(1, 15, true, "0x")
      ).to.be.revertedWith("Target block not yet reached");
    });

    it("Should fulfill audit once target block is mined and prevent replay", async function () {
      await provenanceAudit.connect(auditor).commitAudit(
        datasetRoot,
        decoderVersion,
        auditSize,
        2, // 2 blocks in future
        payloadCommitment
      );

      // Mine blocks to pass target block
      await ethers.provider.send("evm_mine");
      await ethers.provider.send("evm_mine");
      await ethers.provider.send("evm_mine");

      const tx = await provenanceAudit.connect(prover).fulfillAudit(1, 12, true, "0x");
      await expect(tx).to.emit(provenanceAudit, "AuditFulfilled");

      const session = await provenanceAudit.getAuditSession(1);
      expect(session.status).to.equal(1); // AuditStatus.Fulfilled
      expect(session.maxObservedHammingDistance).to.equal(12);
      expect(session.allTrialsPassed).to.be.true;

      // Replay attempt on same audit session must be rejected!
      await expect(
        provenanceAudit.connect(prover).fulfillAudit(1, 12, true, "0x")
      ).to.be.revertedWith("Audit not in committed state");
    });
  });
});

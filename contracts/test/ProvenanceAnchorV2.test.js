const { expect } = require("chai");
const { ethers } = require("hardhat");
const fs = require("fs");
const path = require("path");

describe("ProvenanceAnchorV2 — Authenticated Blockchain Provenance", function () {
  let verifier;
  let anchorV2;
  let owner, alice, bob, charlie;
  let chainId;
  let fixture;

  const zeroBytes32 = "0x0000000000000000000000000000000000000000000000000000000000000000";

  before(async function () {
    const fixturePath = path.join(__dirname, "fixtures", "evm_proof_fixture.json");
    expect(fs.existsSync(fixturePath), "Fixture file must exist").to.be.true;
    fixture = JSON.parse(fs.readFileSync(fixturePath, "utf-8"));
  });

  beforeEach(async function () {
    [owner, alice, bob, charlie] = await ethers.getSigners();
    const network = await ethers.provider.getNetwork();
    chainId = network.chainId;

    // Deploy Halo2Verifier
    const VerifierFactory = await ethers.getContractFactory("Halo2Verifier");
    verifier = await VerifierFactory.deploy();
    await verifier.waitForDeployment();

    // Deploy ProvenanceAnchorV2 with verifier and expected model digest
    const AnchorFactory = await ethers.getContractFactory("ProvenanceAnchorV2");
    anchorV2 = await AnchorFactory.deploy(
      await verifier.getAddress(),
      fixture.model_digest
    );
    await anchorV2.waitForDeployment();
  });

  function getDomain(contractAddress) {
    return {
      name: "MediaProvenance",
      version: "2.0",
      chainId: chainId,
      verifyingContract: contractAddress,
    };
  }

  const types = {
    ProvenanceClaim: [
      { name: "assetId", type: "bytes32" },
      { name: "imageDigest", type: "bytes32" },
      { name: "payloadCommitment", type: "bytes32" },
      { name: "modelDigest", type: "bytes32" },
      { name: "proofDigest", type: "bytes32" },
      { name: "publisher", type: "address" },
      { name: "nonce", type: "uint256" },
      { name: "deadline", type: "uint256" },
    ],
  };

  async function createValidClaim(publisher, overrides = {}) {
    const block = await ethers.provider.getBlock("latest");
    const nonce = await anchorV2.nonces(publisher.address);
    const deadline = block.timestamp + 3600;

    const claim = {
      assetId: overrides.assetId || fixture.image_sha256,
      imageDigest: overrides.imageDigest || fixture.image_sha256,
      payloadCommitment: overrides.payloadCommitment || fixture.payload_commitment,
      modelDigest: overrides.modelDigest || fixture.model_digest,
      proofDigest: overrides.proofDigest || fixture.proof_digest,
      publisher: overrides.publisher || publisher.address,
      nonce: overrides.nonce !== undefined ? overrides.nonce : nonce,
      deadline: overrides.deadline || deadline,
    };

    const domain = getDomain(await anchorV2.getAddress());
    const signer = overrides.signer || publisher;
    const signature = await signer.signTypedData(domain, types, claim);

    return {
      claim,
      signature,
      zkProof: overrides.zkProof !== undefined ? overrides.zkProof : fixture.proof_bytes_hex,
      instances: overrides.instances !== undefined ? overrides.instances : fixture.instances,
    };
  }

  describe("1. Authentic Registration & Gas Measurement", function () {
    it("Should successfully register authenticated provenance with on-chain ZK verification", async function () {
      const bundle = await createValidClaim(alice);

      const tx = await anchorV2.connect(alice).registerProvenance(bundle);
      const receipt = await tx.wait();

      console.log(`\n    [GAS BENCHMARK] Full On-Chain ZK Verification Gas: ${receipt.gasUsed.toString()}`);
      expect(receipt.gasUsed).to.be.gt(0);

      // Verify event emitted
      await expect(tx)
        .to.emit(anchorV2, "ProvenanceRegistered")
        .withArgs(
          bundle.claim.assetId,
          bundle.claim.imageDigest,
          bundle.claim.payloadCommitment,
          bundle.claim.proofDigest,
          alice.address,
          (await ethers.provider.getBlock(receipt.blockNumber)).timestamp
        );

      // Verify stored record
      const rec = await anchorV2.getRecord(bundle.claim.assetId);
      expect(rec.assetId).to.equal(bundle.claim.assetId);
      expect(rec.imageDigest).to.equal(bundle.claim.imageDigest);
      expect(rec.payloadCommitment).to.equal(bundle.claim.payloadCommitment);
      expect(rec.modelDigest).to.equal(bundle.claim.modelDigest);
      expect(rec.proofDigest).to.equal(bundle.claim.proofDigest);
      expect(rec.publisher).to.equal(alice.address);
      expect(rec.exists).to.be.true;

      // Verify nonce incremented
      expect(await anchorV2.nonces(alice.address)).to.equal(1n);
    });

    it("Should measure gas for signature-only authenticated registration without ZK verifier", async function () {
      // Deploy anchor without verifier
      const AnchorFactory = await ethers.getContractFactory("ProvenanceAnchorV2");
      const anchorSigOnly = await AnchorFactory.deploy(ethers.ZeroAddress, fixture.model_digest);
      await anchorSigOnly.waitForDeployment();

      const block = await ethers.provider.getBlock("latest");
      const claim = {
        assetId: fixture.image_sha256,
        imageDigest: fixture.image_sha256,
        payloadCommitment: fixture.payload_commitment,
        modelDigest: fixture.model_digest,
        proofDigest: fixture.proof_digest,
        publisher: alice.address,
        nonce: 0n,
        deadline: block.timestamp + 3600,
      };

      const domain = getDomain(await anchorSigOnly.getAddress());
      const signature = await alice.signTypedData(domain, types, claim);

      const bundle = {
        claim,
        signature,
        zkProof: "0x",
        instances: [],
      };

      const tx = await anchorSigOnly.connect(alice).registerProvenance(bundle);
      const receipt = await tx.wait();

      console.log(`    [GAS BENCHMARK] Signature-Only Authenticated Anchor Gas: ${receipt.gasUsed.toString()}`);
      expect(receipt.gasUsed).to.be.lt(300000n);
    });
  });

  describe("2. Security Invariants & Attack Rejections", function () {
    it("Should reject when signed by wrong publisher (unauthorized signer)", async function () {
      // Bob signs a claim stating publisher is Alice
      const bundle = await createValidClaim(alice, { signer: bob });

      await expect(
        anchorV2.connect(alice).registerProvenance(bundle)
      ).to.be.revertedWith("Invalid publisher signature");
    });

    it("Should reject when claim attributes are substituted after signing", async function () {
      const bundle = await createValidClaim(alice);

      // Maliciously swap assetId to a different image
      const tamperedBundle = {
        ...bundle,
        claim: {
          ...bundle.claim,
          assetId: "0x" + "9".repeat(64),
        },
      };

      await expect(
        anchorV2.connect(alice).registerProvenance(tamperedBundle)
      ).to.be.revertedWith("Invalid publisher signature");
    });

    it("Should reject expired claims (deadline in the past)", async function () {
      const block = await ethers.provider.getBlock("latest");
      const expiredDeadline = block.timestamp - 100;
      const bundle = await createValidClaim(alice, { deadline: expiredDeadline });

      await expect(
        anchorV2.connect(alice).registerProvenance(bundle)
      ).to.be.revertedWith("Claim expired");
    });

    it("Should reject reused nonce (replay attack)", async function () {
      const bundle1 = await createValidClaim(alice);
      await anchorV2.connect(alice).registerProvenance(bundle1);

      // Attempt to reuse nonce 0 with a fresh asset
      const bundleReplay = await createValidClaim(alice, {
        assetId: "0x" + "8".repeat(64),
        nonce: 0n,
      });

      await expect(
        anchorV2.connect(alice).registerProvenance(bundleReplay)
      ).to.be.revertedWith("Invalid nonce");
    });

    it("Should reject duplicate registration of the same asset ID", async function () {
      const bundle1 = await createValidClaim(alice);
      await anchorV2.connect(alice).registerProvenance(bundle1);

      // Try to register the same asset ID again with nonce 1
      const bundleDup = await createValidClaim(alice, {
        assetId: bundle1.claim.assetId,
        nonce: 1n,
        proofDigest: "0x" + "7".repeat(64),
      });

      await expect(
        anchorV2.connect(alice).registerProvenance(bundleDup)
      ).to.be.revertedWith("Asset already registered");
    });

    it("Should reject reuse of the same proof digest across different assets", async function () {
      const bundle1 = await createValidClaim(alice);
      await anchorV2.connect(alice).registerProvenance(bundle1);

      // Try to reuse the proof digest for asset 2
      const bundleProofReplay = await createValidClaim(alice, {
        assetId: "0x" + "6".repeat(64),
        imageDigest: "0x" + "6".repeat(64),
        proofDigest: bundle1.claim.proofDigest,
        nonce: 1n,
      });

      await expect(
        anchorV2.connect(alice).registerProvenance(bundleProofReplay)
      ).to.be.revertedWith("Proof digest already used");
    });

    it("Should reject untrusted model digests", async function () {
      const fakeModelDigest = "0x" + "4".repeat(64);
      const bundle = await createValidClaim(alice, { modelDigest: fakeModelDigest });

      await expect(
        anchorV2.connect(alice).registerProvenance(bundle)
      ).to.be.revertedWith("Untrusted model digest");
    });

    it("Should reject when zkProof calldata does not match proofDigest", async function () {
      const bundle = await createValidClaim(alice, {
        proofDigest: "0x" + "3".repeat(64), // Mismatch with actual keccak256(zkProof)
      });

      await expect(
        anchorV2.connect(alice).registerProvenance(bundle)
      ).to.be.revertedWith("Proof calldata does not match proofDigest");
    });

    it("Should reject corrupted ZK proof calldata", async function () {
      const corruptedProof = "0x" + "00".repeat(3072);
      const corruptedDigest = ethers.keccak256(corruptedProof);

      const bundle = await createValidClaim(alice, {
        zkProof: corruptedProof,
        proofDigest: corruptedDigest,
      });

      // Halo2Verifier will revert inside ec_pairing or point validation
      await expect(
        anchorV2.connect(alice).registerProvenance(bundle)
      ).to.be.reverted;
    });

    it("Should reject altered public instance output logits", async function () {
      // Alter the output logit of the first bit
      const alteredInstances = [...fixture.instances];
      // Flip instance element 32 (first output logit) from positive to negative
      alteredInstances[32] = "2000000000000000000000000000000000000000000000000000000000000000";

      const bundle = await createValidClaim(alice, {
        instances: alteredInstances,
      });

      // Halo2 pairing verification or circuit output payload mismatch check will reject
      await expect(
        anchorV2.connect(alice).registerProvenance(bundle)
      ).to.be.reverted;
    });
  });

  describe("3. Mempool Front-Running & Griefing Resistance", function () {
    it("Should safely attribute publisher to Alice even when Bob front-runs in the mempool", async function () {
      // Alice creates and signs a valid registration bundle
      const bundle = await createValidClaim(alice);

      // Bob intercepts the bundle in the mempool and calls registerProvenance
      const frontRunTx = await anchorV2.connect(bob).registerProvenance(bundle);
      const receipt = await frontRunTx.wait();

      console.log(`    [MEMPOOL ATTACK] Bob front-runs Alice's tx. Gas paid by Bob: ${receipt.gasUsed.toString()}`);

      // Inspect record stored on-chain
      const rec = await anchorV2.getRecord(bundle.claim.assetId);

      // VERIFY: The record's publisher is strictly Alice, NOT Bob!
      expect(rec.publisher).to.equal(alice.address);
      expect(rec.publisher).to.not.equal(bob.address);
      expect(rec.exists).to.be.true;

      // Alice's nonce was consumed cleanly
      expect(await anchorV2.nonces(alice.address)).to.equal(1n);
      // Bob's nonce was untouched
      expect(await anchorV2.nonces(bob.address)).to.equal(0n);
    });

    it("Should reject Bob if Bob tries to hijack Alice's claim by substituting his own address", async function () {
      // Alice signs claim for Alice
      const bundleAlice = await createValidClaim(alice);

      // Bob alters publisher to Bob but reuses Alice's signature
      const hijackedBundle = {
        ...bundleAlice,
        claim: {
          ...bundleAlice.claim,
          publisher: bob.address,
        },
      };

      await expect(
        anchorV2.connect(bob).registerProvenance(hijackedBundle)
      ).to.be.revertedWith("Invalid publisher signature");
    });
  });
});

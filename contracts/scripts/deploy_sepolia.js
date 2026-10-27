const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("=================================================");
  console.log("ProvenanceLab -- Deploying Smart Contracts to Sepolia");
  console.log("=================================================");

  const signers = await hre.ethers.getSigners();
  const deployer = signers.length > 0 ? signers[0] : null;
  if (!deployer) {
    console.log("\n[SETUP REQUIRED] No Sepolia private key found in .env.");
    console.log("To deploy ProvenanceAnchor to Ethereum Sepolia:");
    console.log("1. Open .env in the project root: d:\\MediaProvenance\\.env");
    console.log("2. Set SEPOLIA_PRIVATE_KEY=<your_testnet_burner_wallet_private_key>");
    console.log("3. Ensure that account has free testnet ETH from a faucet (e.g. https://sepoliafaucet.com/)");
    console.log("4. Run: npx hardhat run scripts/deploy_sepolia.js --network sepolia\n");
    process.exit(0);
  }

  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log(`Deployer Address : ${deployer.address}`);
  console.log(`Deployer Balance : ${hre.ethers.formatEther(balance)} ETH`);
  console.log(`Network Name     : ${hre.network.name}`);
  console.log(`Chain ID         : ${(await hre.ethers.provider.getNetwork()).chainId}`);

  if (balance === 0n) {
    console.warn("\n[WARNING] Deployer balance is 0 ETH. You need Sepolia testnet ETH.");
    console.warn("Get free Sepolia testnet ETH from faucets:");
    console.warn("  - https://cloud.google.com/application/web3/faucet/ethereum/sepolia");
    console.warn("  - https://sepoliafaucet.com/");
    console.warn("  - https://faucets.chain.link/sepolia");
  }

  // 1. Deploy ProvenanceAnchor (with IPFS CID support)
  console.log("\n[1/2] Deploying ProvenanceAnchor.sol (with IPFS CID support)...");
  const ProvenanceAnchorFactory = await hre.ethers.getContractFactory("ProvenanceAnchor");
  const anchorContract = await ProvenanceAnchorFactory.deploy();
  await anchorContract.waitForDeployment();
  const anchorAddress = await anchorContract.getAddress();
  console.log(`  [PASS] ProvenanceAnchor deployed to: ${anchorAddress}`);
  console.log(`  Etherscan Link: https://sepolia.etherscan.io/address/${anchorAddress}`);

  // 2. ProvenanceAudit (preserve existing deployment to save Sepolia ETH)
  let auditAddress = "0x97963d11353584c4f348b87784942f153646022A";
  const deploymentsDir = path.join(__dirname, "../deployments");
  const outPath = path.join(deploymentsDir, "sepolia.json");
  if (fs.existsSync(outPath)) {
    try {
      const existing = JSON.parse(fs.readFileSync(outPath, "utf-8"));
      if (existing?.contracts?.ProvenanceAudit?.address) {
        auditAddress = existing.contracts.ProvenanceAudit.address;
      }
    } catch (e) {
      // ignore
    }
  }
  console.log(`\n[2/2] Reusing existing ProvenanceAudit at: ${auditAddress}`);
  console.log(`  Etherscan Link: https://sepolia.etherscan.io/address/${auditAddress}`);

  // Save deployment records
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const deploymentData = {
    network: hre.network.name,
    chainId: Number((await hre.ethers.provider.getNetwork()).chainId),
    deployedAt: new Date().toISOString(),
    deployer: deployer.address,
    contracts: {
      ProvenanceAnchor: {
        address: anchorAddress,
        etherscan: `https://sepolia.etherscan.io/address/${anchorAddress}`,
      },
      ProvenanceAudit: {
        address: auditAddress,
        etherscan: `https://sepolia.etherscan.io/address/${auditAddress}`,
      },
    },
  };

  fs.writeFileSync(outPath, JSON.stringify(deploymentData, null, 2));
  console.log(`\nDeployment manifest saved to: ${outPath}`);
  console.log("=================================================");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });

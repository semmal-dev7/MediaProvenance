/**
 * ProvenanceLab — Web3 & MetaMask Integration Service
 * ====================================================
 * Implements two distinct roles:
 * 1. Image Publisher (MetaMask):
 *    - Connects browser wallet
 *    - Signs and submits proof commitment to Sepolia smart contract
 *    - Pays the transaction gas fee in SepoliaETH
 * 
 * 2. Image Verifier (Zero Gas / Read-Only):
 *    - Queries Sepolia smart contract state via public RPC (eth_call)
 *    - Verifies ZK proof off-chain
 *    - Pays ZERO blockchain gas fees ($0.00)
 */

import { ethers } from 'ethers';

export const PROVENANCE_ANCHOR_ADDRESS = "0x6D8C82dc761Ed9bac93ca99987b91614B90Ad43F";
export const SEPOLIA_CHAIN_ID_DEC = 11155111;
export const SEPOLIA_CHAIN_ID_HEX = "0xaa36a7";
export const SEPOLIA_RPC_URL = "https://ethereum-sepolia-rpc.publicnode.com";

export const PROVENANCE_ANCHOR_ABI = [
  "function anchor(bytes32 assetId, bytes32 commitment) external",
  "function getRecord(bytes32 assetId) external view returns (tuple(bytes32 assetId, bytes32 commitment, address submitter, uint256 timestamp, bool exists))",
  "function records(bytes32) external view returns (bytes32 assetId, bytes32 commitment, address submitter, uint256 timestamp, bool exists)",
  "event ProvenanceAnchored(bytes32 indexed assetId, bytes32 commitment, address indexed submitter, uint256 timestamp)"
];

export interface WalletState {
  connected: boolean;
  address: string | null;
  chainId: number | null;
  balanceEth: string | null;
  error: string | null;
}

export interface OnChainRecord {
  exists: boolean;
  assetId: string;
  commitment: string;
  submitter: string;
  timestamp: number;
  dateFormatted?: string;
  etherscanUrl?: string;
}

/**
 * Ensures input hex is formatted as a valid 32-byte (0x + 64 hex chars) string.
 */
export function formatBytes32(hex: string): string {
  let clean = hex.startsWith('0x') ? hex.slice(2) : hex;
  if (clean.length > 64) {
    clean = clean.slice(0, 64);
  }
  return '0x' + clean.padStart(64, '0');
}

export async function getConnectedAccount(): Promise<string | null> {
  if (typeof window === 'undefined' || !(window as any).ethereum) {
    return null;
  }
  try {
    const ethereum = (window as any).ethereum;
    const provider = new ethers.BrowserProvider(ethereum);
    const accounts = await provider.listAccounts();
    return accounts.length > 0 ? accounts[0].address : null;
  } catch {
    return null;
  }
}

/**
 * Connects to user's MetaMask extension, switching to Sepolia if needed.
 */
export async function connectMetaMask(): Promise<{ address: string; provider: ethers.BrowserProvider; signer: ethers.Signer }> {
  if (typeof window === 'undefined' || !(window as any).ethereum) {
    throw new Error('MetaMask is not detected. Please install MetaMask from https://metamask.io');
  }

  const ethereum = (window as any).ethereum;
  const provider = new ethers.BrowserProvider(ethereum);

  // Request accounts
  const accounts = await provider.send("eth_requestAccounts", []);
  if (!accounts || accounts.length === 0) {
    throw new Error('No Ethereum accounts authorized in MetaMask.');
  }

  // Check network
  const network = await provider.getNetwork();
  if (Number(network.chainId) !== SEPOLIA_CHAIN_ID_DEC) {
    try {
      await ethereum.request({
        method: 'wallet_switchEthereumChain',
        params: [{ chainId: SEPOLIA_CHAIN_ID_HEX }],
      });
    } catch (switchError: any) {
      if (switchError.code === 4902) {
        await ethereum.request({
          method: 'wallet_addEthereumChain',
          params: [{
            chainId: SEPOLIA_CHAIN_ID_HEX,
            chainName: 'Ethereum Sepolia Testnet',
            nativeCurrency: { name: 'Sepolia ETH', symbol: 'SEP', decimals: 18 },
            rpcUrls: [SEPOLIA_RPC_URL],
            blockExplorerUrls: ['https://sepolia.etherscan.io'],
          }],
        });
      } else {
        throw new Error('Please switch your MetaMask network to Ethereum Sepolia.');
      }
    }
  }

  const signer = await provider.getSigner();
  const address = await signer.getAddress();

  return { address, provider, signer };
}

/**
 * Publisher Action: Sign and submit proof commitment to Sepolia smart contract.
 * Publisher pays gas in Sepolia ETH.
 */
export async function anchorWithMetaMask(
  assetIdHex: string,
  commitmentHex: string
): Promise<{
  txHash: string;
  blockNumber: number;
  gasUsed: string;
  submitter: string;
  etherscanUrl: string;
}> {
  const { signer, address } = await connectMetaMask();

  const formattedAssetId = formatBytes32(assetIdHex);
  const formattedCommitment = formatBytes32(commitmentHex);

  const contract = new ethers.Contract(
    PROVENANCE_ANCHOR_ADDRESS,
    PROVENANCE_ANCHOR_ABI,
    signer
  );

  // Send transaction through MetaMask
  const tx = await contract.anchor(formattedAssetId, formattedCommitment);
  
  // Wait for 1 confirmation
  const receipt = await tx.wait(1);

  const etherscanUrl = `https://sepolia.etherscan.io/tx/${receipt.hash}`;

  // Notify backend to cache confirmed transaction record
  try {
    await fetch('/api/v1/anchors/record_tx', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        asset_id: formattedAssetId,
        commitment: formattedCommitment,
        submitter: address,
        tx_hash: receipt.hash,
        block_number: Number(receipt.blockNumber),
      }),
    });
  } catch (err) {
    console.warn('Backend record sync warning:', err);
  }

  return {
    txHash: receipt.hash,
    blockNumber: Number(receipt.blockNumber),
    gasUsed: receipt.gasUsed ? receipt.gasUsed.toString() : 'N/A',
    submitter: address,
    etherscanUrl,
  };
}

/**
 * Verifier Action: Read record directly from Sepolia smart contract for FREE.
 * Pays 0 gas ($0.00). Does NOT require a wallet connection.
 */
export async function readRecordFromSepoliaFree(assetIdHex: string): Promise<OnChainRecord> {
  const formattedAssetId = formatBytes32(assetIdHex);

  // Use public read-only JSON-RPC provider (zero gas, no wallet required)
  const provider = new ethers.JsonRpcProvider(SEPOLIA_RPC_URL);
  const contract = new ethers.Contract(
    PROVENANCE_ANCHOR_ADDRESS,
    PROVENANCE_ANCHOR_ABI,
    provider
  );

  try {
    const record = await contract.getRecord(formattedAssetId);
    const ts = Number(record.timestamp);
    return {
      exists: Boolean(record.exists),
      assetId: record.assetId,
      commitment: record.commitment,
      submitter: record.submitter,
      timestamp: ts,
      dateFormatted: ts > 0 ? new Date(ts * 1000).toLocaleString() : 'N/A',
      etherscanUrl: `https://sepolia.etherscan.io/address/${PROVENANCE_ANCHOR_ADDRESS}`,
    };
  } catch (err: any) {
    return {
      exists: false,
      assetId: formattedAssetId,
      commitment: '0x0000000000000000000000000000000000000000000000000000000000000000',
      submitter: '0x0000000000000000000000000000000000000000',
      timestamp: 0,
      dateFormatted: 'Not Anchored On-Chain',
    };
  }
}

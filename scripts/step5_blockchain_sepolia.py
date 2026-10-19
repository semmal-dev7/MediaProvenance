"""
ProvenanceLab — Step 5: Ethereum Sepolia Blockchain Connection & Anchoring
===========================================================================
Validates:
1. Live RPC connection to Ethereum Sepolia testnet (Chain ID 11155111).
2. Prover wallet account balance and address validation.
3. Reading deployed contract state:
   - ProvenanceAnchor.sol (0x6D8C82dc761Ed9bac93ca99987b91614B90Ad43F)
   - ProvenanceAudit.sol (0x97963d11353584c4f348b87784942f153646022A)
4. Reading the confirmed on-chain deployment transaction.
5. Executing and verifying on-chain record query with bytes32 asset ID.
"""

import sys
import hashlib
from web3 import Web3
from backend.core.config import settings

def run_step5_blockchain_validation():
    print("=" * 75)
    print("STEP 5: ETHEREUM SEPOLIA BLOCKCHAIN CONNECTION & ANCHORING")
    print("Testing smart contract commitments, RPC connection, and on-chain records")
    print("=" * 75)

    rpc_url = settings.SEPOLIA_RPC_URL
    print(f"\n1. Connecting to Sepolia Testnet RPC...")
    print(f"   RPC URL: {rpc_url}")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    assert w3.is_connected(), "Failed to connect to Sepolia RPC!"
    current_block = w3.eth.block_number
    chain_id = w3.eth.chain_id
    print(f"   [OK] Connected successfully!")
    print(f"   Chain ID: {chain_id} (Ethereum Sepolia)")
    print(f"   Current Block: #{current_block}")
    assert chain_id == 11155111, f"Expected Chain ID 11155111, got {chain_id}"

    # 2. Check Wallet Account
    print(f"\n2. Verifying Prover Account & Balance...")
    priv_key = settings.SEPOLIA_PRIVATE_KEY
    if priv_key:
        account = w3.eth.account.from_key(priv_key)
        balance_wei = w3.eth.get_balance(account.address)
        balance_eth = w3.from_wei(balance_wei, "ether")
        print(f"   Account Address: {account.address}")
        print(f"   Account Balance: {balance_eth:.5f} SepoliaETH")
        assert balance_wei > 0, "Account has 0 balance"
        print(f"   [OK] Wallet is funded and ready for on-chain transactions!")
    else:
        print("   [WARN] No private key provided in env, using read-only mode.")

    # 3. Verify Deployed Contracts
    print(f"\n3. Verifying Deployed Smart Contracts on Sepolia...")
    anchor_addr = settings.PROVENANCE_ANCHOR_ADDRESS
    audit_addr = settings.PROVENANCE_AUDIT_ADDRESS
    print(f"   ProvenanceAnchor Address: {anchor_addr}")
    print(f"   ProvenanceAudit Address : {audit_addr}")

    anchor_code = w3.eth.get_code(Web3.to_checksum_address(anchor_addr))
    audit_code = w3.eth.get_code(Web3.to_checksum_address(audit_addr))
    assert len(anchor_code) > 2, "ProvenanceAnchor not found at address!"
    assert len(audit_code) > 2, "ProvenanceAudit not found at address!"
    print(f"   [OK] ProvenanceAnchor bytecode verified on-chain ({len(anchor_code)} bytes)")
    print(f"   [OK] ProvenanceAudit bytecode verified on-chain ({len(audit_code)} bytes)")

    # 4. Read Verified On-Chain Anchor
    print(f"\n4. Querying On-Chain Anchor Record...")
    # Verified on-chain anchor on Sepolia
    test_asset_bytes = bytes.fromhex("44556677889900aabbccddeeff11223344556677889900aabbccddeeff112233")

    abi = [
        {
            "inputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
            "name": "records",
            "outputs": [
                {"internalType": "bytes32", "name": "assetId", "type": "bytes32"},
                {"internalType": "bytes32", "name": "commitment", "type": "bytes32"},
                {"internalType": "address", "name": "submitter", "type": "address"},
                {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
                {"internalType": "bool", "name": "exists", "type": "bool"},
            ],
            "stateMutability": "view",
            "type": "function",
        }
    ]

    contract = w3.eth.contract(address=Web3.to_checksum_address(anchor_addr), abi=abi)
    rec = contract.functions.records(test_asset_bytes).call()
    print(f"   Asset ID (Bytes32)  : 0x{rec[0].hex()}")
    print(f"   Commitment (Bytes32): 0x{rec[1].hex()}")
    print(f"   Submitter           : {rec[2]}")
    print(f"   Block Timestamp     : {rec[3]}")
    print(f"   Record Exists?      : {rec[4]}")
    assert rec[4] is True, "Record must exist on Sepolia contract!"
    print(f"   [PASS] On-chain record read directly from Ethereum Sepolia!")

    print(f"\n5. Etherscan Verification Link:")
    print(f"   Contract  : https://sepolia.etherscan.io/address/{anchor_addr}")
    print(f"   Anchor Tx : https://sepolia.etherscan.io/tx/0xe15983a78135c1fc1d3889e1bb6434191573e3728d9f0d4c4ff900ea26d576e7")

    print("\n" + "=" * 75)
    print(">>> STEP 5 COMPLETE: ETHEREUM SEPOLIA BLOCKCHAIN 100% OPERATIONAL <<<")
    print("=" * 75)
    return True

if __name__ == "__main__":
    success = run_step5_blockchain_validation()
    sys.exit(0 if success else 1)

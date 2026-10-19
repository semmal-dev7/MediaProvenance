"""
Step 5 Verification: Genuine Ethereum Sepolia Integration Test
==============================================================
Validates:
1. Live RPC connection to Sepolia.
2. Direct on-chain verification of deployed contract bytecodes:
   - ProvenanceAnchor (0x6D8C82dc761Ed9bac93ca99987b91614B90Ad43F)
   - ProvenanceAudit (0x97963d11353584c4f348b87784942f153646022A)
3. Reading genuine mined transaction receipts from Ethereum Sepolia with status == 1.
4. Verifying contract state read operations using getRecord().
"""

from web3 import Web3
from backend.core.config import settings

def run_sepolia_tests():
    print("=" * 75)
    print("STEP 5: GENUINE ETHEREUM SEPOLIA INTEGRATION VERIFICATION")
    print("=" * 75)

    rpc_url = settings.SEPOLIA_RPC_URL
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    assert w3.is_connected(), "Failed to connect to Sepolia RPC"
    chain_id = w3.eth.chain_id
    current_block = w3.eth.block_number

    print(f"\n1. Network Status:")
    print(f"   [+] Chain ID:      {chain_id} (Ethereum Sepolia)")
    print(f"   [+] Current Block: #{current_block}")
    assert chain_id == 11155111, f"Expected 11155111, got {chain_id}"

    # 2. Verify Deployed Contracts
    print(f"\n2. Deployed Contract Bytecode Verification:")
    anchor_addr = settings.PROVENANCE_ANCHOR_ADDRESS
    audit_addr = settings.PROVENANCE_AUDIT_ADDRESS

    anchor_code = w3.eth.get_code(Web3.to_checksum_address(anchor_addr))
    audit_code = w3.eth.get_code(Web3.to_checksum_address(audit_addr))
    
    print(f"   [+] ProvenanceAnchor ({anchor_addr}): Bytecode size = {len(anchor_code)} bytes")
    print(f"   [+] ProvenanceAudit  ({audit_addr}): Bytecode size = {len(audit_code)} bytes")
    assert len(anchor_code) > 100, "ProvenanceAnchor has no deployed bytecode on Sepolia!"
    assert len(audit_code) > 100, "ProvenanceAudit has no deployed bytecode on Sepolia!"

    # 3. Verify On-Chain Transaction Receipt
    tx_hash = "0x432c2f47aebfcd859ce3aec4b33b0ea3b727f7e6cfc1380a388168378a9b76a9"
    print(f"\n3. Querying Mined Transaction Receipt on Sepolia:")
    print(f"   Tx Hash: {tx_hash}")
    receipt = w3.eth.get_transaction_receipt(tx_hash)
    print(f"   [+] Mined Block Number: #{receipt.blockNumber}")
    print(f"   [+] Gas Used:           {receipt.gasUsed:,} gas")
    print(f"   [+] On-Chain Status:    {receipt.status} (1 = SUCCESS)")
    print(f"   [+] Etherscan Link:     https://sepolia.etherscan.io/tx/{tx_hash}")
    assert receipt.status == 1, f"On-chain transaction failed with status {receipt.status}"

    # 4. Verify Reading State from Contract
    print(f"\n4. Querying ProvenanceAnchor Contract Storage via getRecord():")
    abi = [
        {
            "inputs": [{"internalType": "bytes32", "name": "assetId", "type": "bytes32"}],
            "name": "getRecord",
            "outputs": [
                {
                    "components": [
                        {"internalType": "bytes32", "name": "assetId", "type": "bytes32"},
                        {"internalType": "bytes32", "name": "commitment", "type": "bytes32"},
                        {"internalType": "address", "name": "submitter", "type": "address"},
                        {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
                        {"internalType": "bool", "name": "exists", "type": "bool"},
                    ],
                    "internalType": "struct ProvenanceAnchor.Record",
                    "name": "",
                    "type": "tuple",
                }
            ],
            "stateMutability": "view",
            "type": "function",
        }
    ]
    contract = w3.eth.contract(address=Web3.to_checksum_address(anchor_addr), abi=abi)
    # Query confirmed asset
    test_asset_bytes = bytes.fromhex("8001599531890fe563dd6b08c4e58a0a9a176cd58fd9f35f28c20582190ce970")
    record = contract.functions.getRecord(test_asset_bytes).call()
    print(f"   [+] Asset ID:    0x{record[0].hex()}")
    print(f"   [+] Commitment:  0x{record[1].hex()}")
    print(f"   [+] Submitter:   {record[2]}")
    print(f"   [+] Timestamp:   {record[3]}")
    print(f"   [+] Exists:      {record[4]}")
    assert record[4] is True, "Expected anchor record to exist on-chain"
    assert record[0] == test_asset_bytes, "Asset ID mismatch"

    print("\n" + "=" * 75)
    print(">>> STEP 5: ALL SEPOLIA BLOCKCHAIN CHECKS PASSED WITH GENUINE RECEIPT! <<<")
    print("=" * 75)

if __name__ == "__main__":
    run_sepolia_tests()

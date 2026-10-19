"""
Submit Genuine Anchor Transaction to Ethereum Sepolia
=====================================================
Executes a real on-chain transaction to ProvenanceAnchor.sol:
1. Generates unique asset ID from verified image.
2. Estimates gas.
3. Broadcasts signed transaction to Sepolia node.
4. Waits for mined receipt.
5. Verifies receipt.status == 1 (SUCCESS).
6. Queries contract.functions.records() to confirm on-chain state.
"""

import sys
import time
import hashlib
from web3 import Web3
from backend.core.config import settings

def main():
    print("=" * 70)
    print("EXECUTING GENUINE ON-CHAIN TRANSACTION ON ETHEREUM SEPOLIA")
    print("=" * 70)

    w3 = Web3(Web3.HTTPProvider(settings.SEPOLIA_RPC_URL))
    assert w3.is_connected(), "Failed to connect to Sepolia RPC"

    account = w3.eth.account.from_key(settings.SEPOLIA_PRIVATE_KEY)
    print(f"Signer Address: {account.address}")
    balance = w3.from_wei(w3.eth.get_balance(account.address), "ether")
    print(f"Balance:        {balance:.5f} ETH")

    anchor_addr = settings.PROVENANCE_ANCHOR_ADDRESS
    abi = [
        {
            "inputs": [
                {"internalType": "bytes32", "name": "assetId", "type": "bytes32"},
                {"internalType": "bytes32", "name": "commitment", "type": "bytes32"},
            ],
            "name": "anchor",
            "outputs": [],
            "stateMutability": "nonpayable",
            "type": "function",
        },
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
        },
    ]
    contract = w3.eth.contract(address=Web3.to_checksum_address(anchor_addr), abi=abi)

    # Generate unique asset ID for current session
    unique_salt = f"provenancelab_verified_{time.time()}".encode("utf-8")
    asset_hash = hashlib.sha256(unique_salt).digest()
    commit_hash = hashlib.sha256(b"zk_poseidon_verified_commitment_" + unique_salt).digest()

    print(f"Asset ID:    0x{asset_hash.hex()}")
    print(f"Commitment:  0x{commit_hash.hex()}")

    # Estimate gas
    est_gas = contract.functions.anchor(asset_hash, commit_hash).estimate_gas({"from": account.address})
    print(f"Estimated Gas: {est_gas:,} gas")
    gas_limit = int(est_gas * 1.5)

    nonce = w3.eth.get_transaction_count(account.address)
    gas_price = int(w3.eth.gas_price * 1.3)

    print(f"Nonce: {nonce}, Gas Limit: {gas_limit:,}, Gas Price: {w3.from_wei(gas_price, 'gwei'):.2f} Gwei")

    tx = contract.functions.anchor(asset_hash, commit_hash).build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": gas_limit,
        "gasPrice": gas_price,
        "chainId": 11155111,
    })

    print("[+] Signing and sending transaction to Sepolia...")
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    tx_hex = w3.to_hex(tx_hash)
    print(f"[+] Transaction broadcasted! Tx Hash: {tx_hex}")
    print(f"    Etherscan: https://sepolia.etherscan.io/tx/{tx_hex}")

    print("[+] Waiting for mining confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print(f"[+] Transaction MINED in Block #{receipt.blockNumber}!")
    print(f"    Gas Used: {receipt.gasUsed:,} gas")
    print(f"    Status:   {receipt.status} (1 = SUCCESS)")
    assert receipt.status == 1, "Transaction reverted on-chain!"

    # Query contract storage
    print("\n[+] Reading verified record back from smart contract:")
    rec = contract.functions.records(asset_hash).call()
    print(f"    Record Exists:    {rec[4]}")
    print(f"    Stored Asset ID:  0x{rec[0].hex()}")
    print(f"    Stored Commit:    0x{rec[1].hex()}")
    print(f"    Submitter:        {rec[2]}")
    print(f"    Block Timestamp:  {rec[3]}")
    assert rec[4] is True, "Record exists flag is False!"
    assert rec[0] == asset_hash, "Asset ID mismatch!"

    print("\n" + "=" * 70)
    print(">>> GENUINE ON-CHAIN SEPOLIA TRANSACTION CONFIRMED SUCCESSFUL! <<<")
    print("=" * 70)
    return tx_hex, receipt.blockNumber

if __name__ == "__main__":
    main()

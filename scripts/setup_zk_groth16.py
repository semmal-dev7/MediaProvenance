"""
ProvenanceLab — Groth16 Trusted Setup for Watermark Verifier Circuit
===================================================================
1. Creates Powers of Tau ceremony (power 10: 1024 constraints for 537-constraint circuit).
2. Generates proving key (zkey) and verification key (verification_key.json).
3. Exports on-chain Solidity verifier (Groth16Verifier.sol).
"""

import subprocess
import os
import sys
import time

def run_cmd(cmd: str):
    print(f">> {cmd}")
    t0 = time.time()
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FAILED (code {res.returncode}):\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")
        sys.exit(1)
    print(f"Done in {time.time()-t0:.2f}s")
    return res.stdout

def setup():
    build_dir = os.path.abspath("circuits/build")
    os.makedirs(build_dir, exist_ok=True)
    
    ptau_0 = os.path.join(build_dir, "pot10_0000.ptau")
    ptau_contrib = os.path.join(build_dir, "pot10_contrib.ptau")
    ptau_final = os.path.join(build_dir, "pot10_final.ptau")
    r1cs = os.path.join(build_dir, "watermark_verifier.r1cs")
    zkey = os.path.join(build_dir, "circuit_final.zkey")
    vkey = os.path.join(build_dir, "verification_key.json")
    sol_verifier = os.path.abspath("contracts/src/Groth16Verifier.sol")

    print("--- 1. Powers of Tau Ceremony ---")
    run_cmd(f'npx snarkjs powersoftau new bn128 10 "{ptau_0}"')
    run_cmd(f'npx snarkjs powersoftau contribute "{ptau_0}" "{ptau_contrib}" --name="ProvenanceLab" -e="random_salt_123456789"')
    run_cmd(f'npx snarkjs powersoftau prepare phase2 "{ptau_contrib}" "{ptau_final}"')

    print("--- 2. Groth16 Circuit Setup ---")
    run_cmd(f'npx snarkjs groth16 setup "{r1cs}" "{ptau_final}" "{zkey}"')
    
    print("--- 3. Export Verification Key ---")
    run_cmd(f'npx snarkjs zkey export verificationkey "{zkey}" "{vkey}"')

    print("--- 4. Export Solidity Verifier ---")
    run_cmd(f'npx snarkjs zkey export solidityverifier "{zkey}" "{sol_verifier}"')

    print("\nGroth16 ZK Setup Complete!")
    print(f"Verification Key: {vkey} ({os.path.getsize(vkey)} bytes)")
    print(f"Solidity Verifier: {sol_verifier} ({os.path.getsize(sol_verifier)} bytes)")

if __name__ == "__main__":
    setup()

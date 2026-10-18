"""
ProvenanceLab — Zero-Knowledge Watermark Verification Protocol
==============================================================

Formal Cryptographic Statement:
--------------------------------
Let m in {0, 1}^n be a secret watermark bit-payload (e.g. n=100 bits).
Let k in {0, 1}^256 be a high-entropy secret key/salt known only to the authorized creator.
Let I_suspect be a suspect image with cryptographic content hash H(I_suspect) in {0, 1}^256.

Statement accepted by the ZK Verification Circuit:
    Given Public Inputs:
        - C in {0, 1}^256 : Payload Commitment C = H(m || k)
        - H_suspect in {0, 1}^256 : Suspect Image Digest
        - session_nonce in {0, 1}^256 : Fresh Replay-Prevention Nonce
    The Prover proves knowledge of Private Witness:
        - m in {0, 1}^n
        - k in {0, 1}^256
    Such that:
        1. C == H(m || k)
        2. Proof is cryptographically bound to (H_suspect, session_nonce).

What this Proof ESTABLISHES:
    - The prover possessed the exact secret watermark payload m and key k
      matching public commitment C.
    - Zero knowledge: No observer or verifier learns any bits of m or k.
    - Replay immunity: Proof cannot be replayed for another image or audit session.

What this Proof DOES NOT ESTABLISH (Formal Negative Claims):
    - Legal ownership or copyright title of the image.
    - Human authorship (the image could be AI-generated).
    - Moral rights, consent, or intent of the author.
    - That no unobserved transformations or edits occurred prior to hashing.
    - That the watermark cannot be transplanted if an adversary obtains the key k.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class ZKProofStatement:
    payload_commitment: str      # Public C (hex)
    suspect_image_sha256: str    # Public H_suspect (hex)
    session_nonce: str           # Public nonce (hex)
    prover_address: str          # Public address / identity
    proof_system: str            # "Groth16-BN254" or "PLONK"
    circuit_identifier: str      # "watermark_commitment_v1"
    proof_calldata: str          # Hex or JSON serialized proof elements
    timestamp: float


class ZKWatermarkProtocol:
    """Implements cryptographic operations for keyed watermark commitments and verification."""

    @staticmethod
    def commit_payload(payload_hex: str, secret_key_hex: Optional[str] = None) -> Tuple[str, str]:
        """
        Compute cryptographically secure commitment C = SHA256(payload || secret_key).
        Returns (commitment_hex, secret_key_hex).
        """
        if secret_key_hex is None:
            secret_key_hex = secrets.token_hex(32)

        # Ensure even number of hex digits for byte conversion
        clean_payload = payload_hex if len(payload_hex) % 2 == 0 else "0" + payload_hex
        data = bytes.fromhex(clean_payload) + bytes.fromhex(secret_key_hex)
        commitment = hashlib.sha256(data).hexdigest()
        return commitment, secret_key_hex

    @staticmethod
    def generate_witness(
        payload_hex: str,
        secret_key_hex: str,
        suspect_image_sha256: str,
        session_nonce: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Constructs private witness and public inputs for circuit execution.
        """
        if session_nonce is None:
            session_nonce = secrets.token_hex(16)

        commitment, _ = ZKWatermarkProtocol.commit_payload(payload_hex, secret_key_hex)

        # Convert payload bits to array of integers {0, 1} for circuit constraints
        val = int(payload_hex, 16)
        n_bits = len(payload_hex) * 4
        payload_bits = [(val >> (n_bits - 1 - i)) & 1 for i in range(n_bits)]

        witness = {
            "public": {
                "payload_commitment": commitment,
                "suspect_image_sha256": suspect_image_sha256,
                "session_nonce": session_nonce,
            },
            "private": {
                "payload_bits": payload_bits,
                "payload_hex": payload_hex,
                "secret_key": secret_key_hex,
            },
        }
        return witness

    @staticmethod
    def verify_commitment_offchain(
        commitment_hex: str,
        payload_hex: str,
        secret_key_hex: str,
    ) -> bool:
        """
        Deterministic off-chain verification of the commitment relation C == H(m || k).
        """
        expected, _ = ZKWatermarkProtocol.commit_payload(payload_hex, secret_key_hex)
        return secrets.compare_digest(commitment_hex.lower(), expected.lower())

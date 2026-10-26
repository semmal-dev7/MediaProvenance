"""
ProvenanceLab — Pinata IPFS Decentralized Storage Service
==========================================================
Handles pinning watermarked reference media to IPFS via Pinata Cloud API,
resolving content-addressed CIDs, and providing gateway URLs for the
decentralized media provenance reveal protocol.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from backend.core.config import settings

logger = logging.getLogger(__name__)

B58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

IPFS_STORAGE_DIR = settings.BASE_DIR / "data" / "ipfs"
IPFS_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def b58encode(data: bytes) -> str:
    """Encodes arbitrary byte sequences to Base58 (Bitcoin/IPFS standard)."""
    n = int.from_bytes(data, "big")
    chars = []
    while n > 0:
        n, r = divmod(n, 58)
        chars.append(B58_ALPHABET[r])
    for b in data:
        if b == 0:
            chars.append(B58_ALPHABET[0])
        else:
            break
    return "".join(reversed(chars))


def compute_fallback_cid(data: bytes) -> str:
    """Computes a standard IPFS v0 Multihash CID (Qm...) for a byte sequence."""
    sha256_hash = hashlib.sha256(data).digest()
    # Multihash framing: 0x12 = sha256, 0x20 = 32 bytes length
    multihash = b"\x12\x20" + sha256_hash
    return b58encode(multihash)


class PinataIPFSService:
    """
    Decentralized Pinata IPFS Service.
    Pins images to Pinata Cloud and resolves them via dedicated gateways.
    """

    PIN_FILE_URL = "https://api.pinata.cloud/pinning/pinFileToIPFS"

    def __init__(self, jwt: Optional[str] = None, gateway: Optional[str] = None):
        self.jwt = jwt or os.getenv("PINATA_JWT") or settings.PINATA_JWT
        self.gateway = (
            gateway
            or os.getenv("PINATA_GATEWAY")
            or settings.PINATA_GATEWAY
            or "gateway.pinata.cloud"
        ).strip().rstrip("/")
        self.storage_dir = IPFS_STORAGE_DIR

    def has_pinata_credentials(self) -> bool:
        """Returns True if a valid Pinata JWT is configured."""
        return bool(self.jwt and len(self.jwt.strip()) > 20)

    def pin_image(
        self,
        image_bytes: bytes,
        filename: str = "watermarked_media.png",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Pins an image to IPFS via Pinata.
        Falls back to local content-addressed store if Pinata credentials
        are missing or network is unavailable, ensuring zero downtime.
        """
        cid = None
        pinned_to_cloud = False
        pinata_response = {}

        # 1. Attempt Pinata Cloud Pinning if JWT is present
        if self.has_pinata_credentials():
            try:
                headers = {
                    "Authorization": f"Bearer {self.jwt.strip()}",
                }
                files = {
                    "file": (filename, image_bytes, "image/png"),
                }
                data = {}
                if metadata:
                    pinata_metadata = {
                        "name": filename,
                        "keyvalues": {
                            k: str(v) for k, v in metadata.items() if v is not None
                        },
                    }
                    data["pinataMetadata"] = json.dumps(pinata_metadata)

                resp = requests.post(
                    self.PIN_FILE_URL,
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=15,
                )
                if resp.status_code == 200:
                    res_json = resp.json()
                    cid = res_json.get("IpfsHash")
                    pinned_to_cloud = True
                    pinata_response = res_json
                    logger.info("Successfully pinned %s to Pinata IPFS with CID: %s", filename, cid)
                else:
                    logger.warning(
                        "Pinata API returned status %d: %s. Falling back to local IPFS content addressing.",
                        resp.status_code,
                        resp.text,
                    )
            except Exception as e:
                logger.warning("Pinata upload failed (%s). Falling back to local content addressing.", e)

        # 2. Local fallback / offline deterministic CID generation
        if not cid:
            cid = compute_fallback_cid(image_bytes)
            logger.info("Generated deterministic IPFS CIDv0: %s", cid)

        # 3. Cache locally in data/ipfs/<cid>.png for zero-latency retrieval
        local_cache_path = self.storage_dir / f"{cid}.png"
        try:
            with open(local_cache_path, "wb") as f:
                f.write(image_bytes)
        except Exception as e:
            logger.warning("Could not write to local IPFS cache %s: %s", local_cache_path, e)

        gateway_url = f"https://{self.gateway}/ipfs/{cid}"
        api_proxy_url = f"/api/v1/ipfs/{cid}"

        return {
            "success": True,
            "cid": cid,
            "ipfs_uri": f"ipfs://{cid}",
            "gateway_url": gateway_url,
            "api_proxy_url": api_proxy_url,
            "pinned_to_cloud": pinned_to_cloud,
            "size_bytes": len(image_bytes),
            "filename": filename,
        }

    def get_image_bytes(self, cid: str) -> Optional[bytes]:
        """
        Retrieves image bytes for a given CID, checking local cache first,
        then falling back to the Pinata gateway.
        """
        clean_cid = cid.replace("ipfs://", "").strip()
        local_path = self.storage_dir / f"{clean_cid}.png"
        if local_path.exists():
            try:
                with open(local_path, "rb") as f:
                    return f.read()
            except Exception as e:
                logger.warning("Error reading cached IPFS file: %s", e)

        # Try downloading from gateway
        gateway_url = f"https://{self.gateway}/ipfs/{clean_cid}"
        try:
            resp = requests.get(gateway_url, timeout=10)
            if resp.status_code == 200:
                data = resp.content
                # Cache it
                with open(local_path, "wb") as f:
                    f.write(data)
                return data
        except Exception as e:
            logger.warning("Could not fetch CID %s from gateway %s: %s", clean_cid, gateway_url, e)

        return None

    def get_image_base64(self, cid: str) -> Optional[str]:
        """Returns data URI base64 string for an IPFS CID."""
        b = self.get_image_bytes(cid)
        if b:
            encoded = base64.b64encode(b).decode("utf-8")
            return f"data:image/png;base64,{encoded}"
        return None


# Global singleton instance
ipfs_service = PinataIPFSService()

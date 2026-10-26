"""
ProvenanceLab — IPFS REST API Routes
====================================
Serves decentralized media assets pinned via Pinata IPFS,
provides IPFS status diagnostics, and handles media retrieval.
"""

from __future__ import annotations

import io
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from backend.services.ipfs_service import ipfs_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ipfs", tags=["ipfs"])


class IPFSConfigUpdate(BaseModel):
    pinata_jwt: str
    pinata_gateway: Optional[str] = None


@router.get("/status")
async def get_ipfs_status():
    """Returns the current status of the Pinata IPFS service."""
    return {
        "pinata_configured": ipfs_service.has_pinata_credentials(),
        "gateway": ipfs_service.gateway,
        "storage_dir": str(ipfs_service.storage_dir),
    }


@router.post("/config")
async def update_ipfs_config(req: IPFSConfigUpdate):
    """Dynamically updates the Pinata JWT key and gateway for the active session."""
    ipfs_service.jwt = req.pinata_jwt.strip()
    if req.pinata_gateway:
        ipfs_service.gateway = req.pinata_gateway.strip().rstrip("/")
    return {
        "success": True,
        "pinata_configured": ipfs_service.has_pinata_credentials(),
        "gateway": ipfs_service.gateway,
    }


@router.get("/{cid}")
async def get_ipfs_asset(cid: str):
    """
    Resolves and serves an IPFS asset by CID.
    Streams directly from local content cache or proxies from Pinata Gateway.
    """
    clean_cid = cid.replace("ipfs://", "").strip()
    local_path = ipfs_service.storage_dir / f"{clean_cid}.png"
    if local_path.exists():
        return FileResponse(
            path=str(local_path),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=31536000, immutable"},
        )

    # Attempt fetch via gateway
    data = ipfs_service.get_image_bytes(clean_cid)
    if not data:
        raise HTTPException(status_code=404, detail=f"IPFS asset with CID '{cid}' not found.")

    return Response(
        content=data,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )

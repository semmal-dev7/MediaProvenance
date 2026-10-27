"""
ProvenanceLab — Blockchain Anchors API Routes
=============================================
"""

from __future__ import annotations

import asyncio
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.services.job_manager import job_manager

router = APIRouter(prefix="/anchors", tags=["anchors"])


class CreateAnchorRequest(BaseModel):
    asset_id: str = Field(..., description="Bytes32 hex digest of candidate image or asset")
    commitment: str = Field(..., description="Bytes32 hex commitment C = H(m || k)")
    submitter: Optional[str] = Field("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")
    ipfs_cid: Optional[str] = Field(None, description="Decentralized IPFS CID")


class RecordMetamaskTxRequest(BaseModel):
    asset_id: str = Field(..., description="Bytes32 hex digest of candidate image or asset")
    commitment: str = Field(..., description="Bytes32 hex commitment C = H(m || k)")
    submitter: str = Field(..., description="MetaMask publisher address")
    tx_hash: str = Field(..., description="Confirmed Sepolia transaction hash")
    block_number: int = Field(..., description="Confirmed Sepolia block number")
    ipfs_cid: Optional[str] = Field(None, description="Decentralized IPFS CID")


@router.post("")
async def create_anchor(req: CreateAnchorRequest):
    """Anchor a verification commitment on the Provenance registry."""
    record = job_manager.anchor_commitment(
        asset_id=req.asset_id,
        commitment=req.commitment,
        submitter=req.submitter or "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        ipfs_cid=req.ipfs_cid,
    )
    return {
        "success": True,
        "record": record.__dict__,
    }


@router.post("/record_tx")
async def record_metamask_anchor(req: RecordMetamaskTxRequest):
    """Register an on-chain anchor submitted directly via the publisher's MetaMask."""
    record = job_manager.record_onchain_anchor(
        asset_id=req.asset_id,
        commitment=req.commitment,
        submitter=req.submitter,
        tx_hash=req.tx_hash,
        block_number=req.block_number,
        ipfs_cid=req.ipfs_cid,
    )
    return {
        "success": True,
        "record": record.__dict__,
    }


@router.post("/sync")
async def sync_anchors():
    """Trigger an on-chain event sync to pull latest Sepolia transactions."""
    new_count = await asyncio.to_thread(job_manager.sync_onchain_anchors)
    return {
        "success": True,
        "synced_new_records": new_count,
        "total_records": len(job_manager.list_anchors()),
    }


@router.get("")
async def list_anchors():
    """List all registered provenance anchor records."""
    anchors = job_manager.list_anchors()
    return [a.__dict__ for a in anchors]


@router.get("/{query}")
async def get_anchor(query: str):
    """Retrieve an anchored provenance record by asset ID or transaction hash."""
    record = job_manager.get_anchor(query)
    if not record:
        raise HTTPException(status_code=404, detail=f"No anchor record found for {query}")
    return record.__dict__

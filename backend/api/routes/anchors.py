"""
ProvenanceLab — Blockchain Anchors API Routes
=============================================
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.services.job_manager import job_manager

router = APIRouter(prefix="/anchors", tags=["anchors"])


class CreateAnchorRequest(BaseModel):
    asset_id: str = Field(..., description="Bytes32 hex digest of candidate image or asset")
    commitment: str = Field(..., description="Bytes32 hex commitment C = H(m || k)")
    submitter: Optional[str] = Field("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")


@router.post("")
async def create_anchor(req: CreateAnchorRequest):
    """Anchor a verification commitment on the Provenance registry."""
    record = job_manager.anchor_commitment(
        asset_id=req.asset_id,
        commitment=req.commitment,
        submitter=req.submitter or "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    )
    return {
        "success": True,
        "record": record.__dict__,
    }


@router.get("/{asset_id}")
async def get_anchor(asset_id: str):
    """Retrieve an anchored provenance record by asset ID."""
    record = job_manager.get_anchor(asset_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"No anchor record found for asset {asset_id}")
    return record.__dict__


@router.get("")
async def list_anchors():
    """List all registered provenance anchor records."""
    anchors = job_manager.list_anchors()
    return [a.__dict__ for a in anchors]

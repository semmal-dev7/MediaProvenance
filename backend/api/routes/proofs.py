"""
ProvenanceLab — Zero-Knowledge Proofs & Job Queue API Routes
============================================================
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException

from backend.services.job_manager import job_manager
from backend.zk.engine import zk_engine

router = APIRouter(prefix="/proofs", tags=["proofs"])


class CreateProofRequest(BaseModel):
    payload_hex: str = Field(..., description="Recovered watermark payload in hex")
    image_sha256: str = Field(..., description="SHA-256 content digest of image")
    prover_address: Optional[str] = Field("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")
    image_features: Optional[List[float]] = Field(None, description="64-dimensional latent features from HiDDeN decoder")
    allow_synthetic: Optional[bool] = Field(False, description="Test-only option to allow synthetic test features")


class VerifyProofRequest(BaseModel):
    proof: Dict[str, Any] = Field(..., description="EZKL proof calldata")
    public_inputs: Dict[str, Any] = Field(..., description="Bound public inputs")


@router.post("")
async def submit_proof_job(req: CreateProofRequest):
    """
    Queue an asynchronous zero-knowledge proof and blockchain anchoring job.
    Returns the assigned job_id for state tracking.
    """
    clean_sha = req.image_sha256.lower().strip()
    features = None
    if req.allow_synthetic and req.image_features is not None:
        features = req.image_features
    elif req.image_features is not None:
        raise HTTPException(
            status_code=400,
            detail="Untrusted client-supplied image features rejected. Features must be extracted server-side from uploaded media.",
        )
    else:
        from backend.zk.features import get_cached_features
        features = get_cached_features(clean_sha)

    job = job_manager.create_job(
        payload_hex=req.payload_hex,
        image_sha256=clean_sha,
        prover_address=req.prover_address or "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
        image_features=features,
        allow_synthetic=bool(req.allow_synthetic),
    )
    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "created_at": job.created_at,
    }


@router.post("/generate")
async def generate_proof_direct(req: CreateProofRequest):
    """
    Directly generates the genuine EZKL zero-knowledge proof without server-side anchoring,
    returning the proof bundle, asset_id, and commitment for publisher MetaMask submission.
    """
    clean_sha = req.image_sha256.lower().strip()
    if not clean_sha.startswith("0x"):
        clean_sha = "0x" + clean_sha

    features = None
    if req.allow_synthetic and req.image_features is not None:
        features = req.image_features
    elif req.image_features is not None:
        raise HTTPException(
            status_code=400,
            detail="Untrusted client-supplied image features rejected. Features must be extracted server-side from uploaded media.",
        )
    else:
        from backend.zk.features import get_cached_features
        features = get_cached_features(clean_sha)

    try:
        proof_result = zk_engine.generate_proof(
            payload_hex=req.payload_hex,
            image_sha256=clean_sha,
            prover_address=req.prover_address or "0x0000000000000000000000000000000000000000",
            image_features=features,
            allow_synthetic=bool(req.allow_synthetic),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    commitment = proof_result.get("proof_digest") or proof_result["public_inputs"]["payload_commitment"]
    asset_id = clean_sha

    return {
        "success": True,
        "asset_id": asset_id,
        "commitment": commitment,
        "proof_digest": proof_result.get("proof_digest"),
        "payload_commitment": proof_result["public_inputs"]["payload_commitment"],
        "proof_result": proof_result,
    }


@router.post("/verify")
async def verify_proof(req: VerifyProofRequest):
    """
    Verify zero-knowledge proof against public inputs (model digest, payload commitment, image digest).
    """
    res = zk_engine.verify_proof(req.proof, req.public_inputs)
    return res


# Also mount /jobs router
jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])


@jobs_router.get("/{job_id}")
async def get_job_status(job_id: str):
    """
    Retrieve asynchronous job status and artifacts (queued, proving, anchoring, confirmed).
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    return {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "payload_hex": job.payload_hex,
        "image_sha256": job.image_sha256,
        "prover_address": job.prover_address,
        "error": job.error,
        "proof_result": job.proof_result,
        "anchor_record": job.anchor_record.__dict__ if job.anchor_record else None,
    }


@jobs_router.get("")
async def list_jobs():
    """List recent proof & anchor jobs."""
    jobs = job_manager.list_jobs()
    return [
        {
            "job_id": j.job_id,
            "status": j.status,
            "progress": j.progress,
            "created_at": j.created_at,
            "updated_at": j.updated_at,
            "payload_hex": j.payload_hex,
            "image_sha256": j.image_sha256,
            "error": j.error,
        }
        for j in jobs[:20]
    ]

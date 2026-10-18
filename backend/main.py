"""
ProvenanceLab — Main FastAPI Application
=========================================

Capstone Title:
BLOCKCHAIN-ANCHORED ZERO-KNOWLEDGE VERIFICATION OF NEURAL WATERMARKS
FOR PUBLICLY AUDITABLE MEDIA PROVENANCE
"""

from __future__ import annotations

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.experiments import router as experiments_router
from backend.api.routes.watermark import router as watermark_router
from backend.core.config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("provenancelab")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Research-grade watermark provenance, zero-knowledge verification, "
        "and blockchain auditing. "
        f"\n\nOfficial Capstone: {settings.CAPSTONE_TITLE}"
    ),
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(watermark_router, prefix="/api/v1")
app.include_router(experiments_router, prefix="/api/v1")


@app.get("/api/v1/health")
async def health_check():
    """Health status and environment capabilities."""
    import torch
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "capstone_title": settings.CAPSTONE_TITLE,
        "pytorch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
    }


@app.get("/")
async def root():
    return {
        "title": settings.PROJECT_NAME,
        "capstone_title": settings.CAPSTONE_TITLE,
        "docs_url": "/docs",
        "health_url": "/api/v1/health",
    }

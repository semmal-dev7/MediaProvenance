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
from backend.api.routes.watermark import router as watermark_router, watermarks_router
from backend.api.routes.proofs import router as proofs_router, jobs_router
from backend.api.routes.anchors import router as anchors_router
from backend.api.routes.ipfs import router as ipfs_router
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
app.include_router(watermarks_router, prefix="/api/v1")
app.include_router(proofs_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(anchors_router, prefix="/api/v1")
app.include_router(ipfs_router, prefix="/api/v1")
app.include_router(experiments_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """Sync on-chain anchors on startup in background."""
    import asyncio
    from backend.services.job_manager import job_manager
    try:
        asyncio.create_task(asyncio.to_thread(job_manager.sync_onchain_anchors))
    except Exception as e:
        logger.warning("Could not schedule on-chain anchor sync at startup: %s", e)


@app.get("/health")
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


from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import HTTPException

dist_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if dist_dir.exists() and (dist_dir / "index.html").exists():
    if (dist_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path in ("docs", "redoc", "openapi.json", "health"):
            raise HTTPException(status_code=404, detail="Not Found")
        file_path = dist_dir / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(dist_dir / "index.html")
else:
    @app.get("/")
    async def root():
        return {
            "title": settings.PROJECT_NAME,
            "capstone_title": settings.CAPSTONE_TITLE,
            "docs_url": "/docs",
            "health_url": "/api/v1/health",
        }

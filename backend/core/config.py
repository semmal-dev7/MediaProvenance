"""
ProvenanceLab — Core Configuration & Environment Settings
"""

from __future__ import annotations

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "ProvenanceLab"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Capstone Formal Title
    CAPSTONE_TITLE: str = (
        "BLOCKCHAIN-ANCHORED ZERO-KNOWLEDGE VERIFICATION OF NEURAL WATERMARKS "
        "FOR PUBLICLY AUDITABLE MEDIA PROVENANCE"
    )

    # Base Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    EXPERIMENTS_DIR: Path = BASE_DIR / "experiments"
    RESULTS_DIR: Path = EXPERIMENTS_DIR / "results"
    DATA_DIR: Path = EXPERIMENTS_DIR / "data"
    CIRCUITS_DIR: Path = BASE_DIR / "circuits"
    CONTRACTS_DIR: Path = BASE_DIR / "contracts"

    # Watermark Carrier
    DEFAULT_CARRIER: str = "trustmark"
    TRUSTMARK_VARIANT: str = "Q"
    TRUSTMARK_PAYLOAD_BITS: int = 100

    # Blockchain
    ETH_RPC_URL: str = "http://127.0.0.1:8545"
    CHAIN_ID: int = 31337
    AUDIT_CONTRACT_ADDRESS: str = ""

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()

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

    # Sepolia Testnet
    SEPOLIA_RPC_URL: str = "https://ethereum-sepolia-rpc.publicnode.com"
    SEPOLIA_PRIVATE_KEY: str = ""
    ETHERSCAN_API_KEY: str = ""
    PROVENANCE_ANCHOR_ADDRESS: str = ""
    PROVENANCE_AUDIT_ADDRESS: str = ""

    # Pinata IPFS Configuration
    PINATA_JWT: str = os.getenv("PINATA_JWT", "")
    PINATA_GATEWAY: str = os.getenv("PINATA_GATEWAY", "gateway.pinata.cloud")

    class Config:
        case_sensitive = True
        env_file = ".env"
        extra = "allow"


settings = Settings()

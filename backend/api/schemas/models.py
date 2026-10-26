"""
ProvenanceLab — Pydantic API Schemas
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EncodeRequest(BaseModel):
    payload_hex: Optional[str] = Field(None, description="Hex-encoded payload bits. If omitted, cryptographically generated.")
    carrier: str = Field("trustmark", description="Watermark carrier to use ('trustmark', 'wam')")


class EncodeResponse(BaseModel):
    success: bool
    payload_hex: str
    payload_bits: int
    carrier_name: str
    carrier_version: str
    psnr_db: Optional[float] = None
    elapsed_seconds: float
    image_sha256: str
    image_features: Optional[List[float]] = None
    watermarked_image_base64: Optional[str] = None
    ipfs_cid: Optional[str] = None
    ipfs_url: Optional[str] = None
    error: Optional[str] = None


class DecodeRequest(BaseModel):
    reference_payload_hex: Optional[str] = Field(None, description="Optional reference payload to compute Hamming distance vs suspect")
    carrier: str = Field("trustmark", description="Carrier used for decoding")


class DecodeResponse(BaseModel):
    success: bool
    decodable: bool
    payload_hex: Optional[str] = None
    payload_bits: int
    hamming_distance: Optional[int] = None
    bit_error_rate: Optional[float] = None
    confidence: Optional[float] = None
    mean_logit_magnitude: Optional[float] = None
    rms_energy: Optional[float] = None
    neural_certainty: Optional[float] = None
    expected_ber: Optional[float] = None
    carrier_name: str
    carrier_version: str
    elapsed_seconds: float
    # Distinct verification semantics
    watermark_detected: bool = False
    payload_recovered: bool = False
    payload_matches: Optional[bool] = None
    failure_reason: Optional[str] = None
    # Bayesian Likelihood Ratio & Provenance inference
    log10_likelihood_ratio: Optional[float] = None
    posterior_probability_h1: Optional[float] = None
    inferred_hypothesis: str = "H2"  # H1 (derivative), H0 (unrelated), H2 (indeterminate/undecodable)
    image_sha256: Optional[str] = None
    # Phase 5.7 Distinct Provenance & Authentication Semantics
    proof_valid: Optional[bool] = None
    image_binding_verified: Optional[bool] = None
    publisher_authenticated: Optional[bool] = None
    anchor_found: Optional[bool] = None
    registered_anchor: Optional[Dict[str, Any]] = None
    is_derivative: Optional[bool] = None
    tamper_detected: Optional[bool] = None
    original_asset_id: Optional[str] = None
    original_ipfs_cid: Optional[str] = None
    original_ipfs_url: Optional[str] = None
    original_image_url: Optional[str] = None
    original_image_base64: Optional[str] = None
    error: Optional[str] = None


class RunExperimentRequest(BaseModel):
    carrier: str = "trustmark"
    n_samples: int = Field(24, ge=4, le=200)
    calibration_ratio: float = Field(0.5, ge=0.2, le=0.8)
    experiment_id: str = "exp_gate1_survival"


class RunExperimentResponse(BaseModel):
    success: bool
    experiment_id: str
    total_trials: int
    decodable_rate: float
    carrier: str
    p_H1_mle: Optional[float] = None
    test_ece: Optional[float] = None
    csv_path: str
    message: str

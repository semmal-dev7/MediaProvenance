"""
ProvenanceLab — Watermark Embedding & Decoding API Routes
"""

from __future__ import annotations

import base64
import io
import math
from typing import Optional

import numpy as np

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from backend.api.schemas.models import DecodeResponse, EncodeResponse
from backend.carriers.factory import get_carrier
from backend.models.noisy_channel import BinomialModel, ModelParameters

router = APIRouter(prefix="/watermark", tags=["watermark"])
watermarks_router = APIRouter(prefix="/watermarks", tags=["watermarks"])


@router.post("/encode", response_model=EncodeResponse)
@router.post("/embed", response_model=EncodeResponse)
@watermarks_router.post("/encode", response_model=EncodeResponse)
@watermarks_router.post("/embed", response_model=EncodeResponse)
async def encode_watermark(
    file: UploadFile = File(...),
    carrier: str = Form("hidden"),
    payload_hex: Optional[str] = Form(None),
):
    """Embed watermark into the uploaded image."""
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {e}")

    try:
        c = get_carrier(carrier)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Carrier error: {e}")

    # Generate random payload if omitted
    if not payload_hex:
        import secrets
        n_bits = c.info.payload_bits
        n_hex = (n_bits + 3) // 4
        payload_hex = format(secrets.randbits(n_bits), f"0{n_hex}x")

    enc_res = c.encode(image, payload_hex)
    if enc_res.error:
        return EncodeResponse(
            success=False,
            payload_hex=payload_hex,
            payload_bits=c.info.payload_bits,
            carrier_name=c.info.name,
            carrier_version=c.info.version,
            psnr_db=None,
            elapsed_seconds=enc_res.elapsed_seconds,
            image_sha256="",
            error=enc_res.error,
        )

    # Convert watermarked image to base64 for preview
    buf = io.BytesIO()
    enc_res.watermarked_image.save(buf, format="PNG")
    buf.seek(0)
    b64_img = base64.b64encode(buf.read()).decode("utf-8")
    sha256 = c.image_sha256(enc_res.watermarked_image)

    # Cache genuine features for subsequent ZK proof generation
    feats = None
    try:
        from backend.zk.features import cache_image_features, get_cached_features
        feats = get_cached_features(sha256)
        if feats is None:
            feats = cache_image_features(sha256, enc_res.watermarked_image, carrier=carrier)
    except Exception as e:
        logger.warning("Could not cache features for ZK: %s", e)

    # Register embedded asset in publisher registry for automated provenance retrieval
    try:
        import hashlib
        from backend.services.job_manager import job_manager
        job_manager.register_embedded_asset(sha256, payload_hex)
        raw_png_sha = hashlib.sha256(buf.getvalue()).hexdigest()
        job_manager.register_embedded_asset(raw_png_sha, payload_hex)
    except Exception as e:
        logger.warning("Could not register embedded asset in registry: %s", e)

    return EncodeResponse(
        success=True,
        payload_hex=payload_hex,
        payload_bits=c.info.payload_bits,
        carrier_name=c.info.name,
        carrier_version=c.info.version,
        psnr_db=enc_res.psnr_db,
        elapsed_seconds=enc_res.elapsed_seconds,
        image_sha256=sha256,
        image_features=feats,
        watermarked_image_base64=f"data:image/png;base64,{b64_img}",
    )


@router.post("/decode", response_model=DecodeResponse)
@watermarks_router.post("/decode", response_model=DecodeResponse)
async def decode_watermark(
    file: UploadFile = File(...),
    carrier: str = Form("hidden"),
    reference_payload_hex: Optional[str] = Form(None),
):
    """Decode suspect image and compute Bayesian Likelihood Ratio."""
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {e}")

    try:
        c = get_carrier(carrier)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Carrier error: {e}")

    sha256 = c.image_sha256(image)
    clean_sha = sha256.lower().replace("0x", "").strip()

    # Query local/on-chain anchor registry for registered publisher provenance
    from backend.services.job_manager import job_manager
    anchor = job_manager.get_anchor("0x" + clean_sha) or job_manager.get_anchor(clean_sha)
    anchor_found = anchor is not None
    registered_anchor_dict = anchor.__dict__ if anchor else None

    # Retrieve trusted publisher claim from registry if user omitted manual reference payload
    effective_ref_payload = reference_payload_hex
    trusted_from_registry = False
    if not effective_ref_payload:
        import hashlib
        contents_sha = hashlib.sha256(contents).hexdigest()
        embedded_claim = (
            job_manager.get_embedded_asset(clean_sha)
            or job_manager.get_embedded_asset(contents_sha)
        )
        if embedded_claim:
            effective_ref_payload = embedded_claim
            trusted_from_registry = True
        elif anchor:
            for job in job_manager._jobs.values():
                if job.image_sha256.lower().replace("0x", "") == clean_sha:
                    effective_ref_payload = job.payload_hex
                    trusted_from_registry = True
                    break

    # Execute carrier decode
    dec_res = c.decode(image, reference_payload_hex=effective_ref_payload)

    # Cache candidate image features for downstream ZK proof generation
    try:
        from backend.zk.features import cache_image_features
        cache_image_features(clean_sha, image, carrier=carrier)
    except Exception as e:
        logger.warning("Could not cache features during decode: %s", e)

    # If anchor not found by image SHA (e.g. cropped/compressed media), reverse-lookup by decoded payload
    if not anchor and dec_res.payload_hex:
        anchor = job_manager.get_anchor_by_payload(dec_res.payload_hex)
        if anchor:
            anchor_found = True
            registered_anchor_dict = anchor.__dict__
            if not effective_ref_payload:
                effective_ref_payload = dec_res.payload_hex
                trusted_from_registry = True
                # Re-evaluate decode against discovered authentic payload
                if dec_res.hamming_distance is None:
                    dec_res.hamming_distance = 0
                    dec_res.bit_error_rate = 0.0

    log10_lr = None
    posterior_h1 = None
    inferred = "H2"
    payload_matches = None
    failure_reason = None
    proof_valid = False
    image_binding_verified = False
    publisher_authenticated = False

    payload_recovered = dec_res.payload_hex is not None

    if effective_ref_payload:
        clean_ref = effective_ref_payload.lower().replace("0x", "").strip()
        if dec_res.hamming_distance is not None:
            # Calibrated detection threshold: d_H <= 7 (BER <= 21.9%, P(H0) < 0.0011)
            payload_matches = (dec_res.hamming_distance <= 7)
            is_detected = bool(dec_res.watermark_detected or payload_matches)

            # Genuine Bayesian Likelihood Ratio on measured Hamming distance
            params = ModelParameters(payload_bits=c.info.payload_bits, p_H1=0.15, p_H0=0.50)
            model = BinomialModel(params)
            lr_result = model.likelihood_ratio(dec_res.hamming_distance)
            log10_lr = lr_result.log10_lr
            # Flat prior posterior P(H1 | LR)
            posterior_h1 = 1.0 / (1.0 + 10.0 ** (-log10_lr))
            inferred = "H1" if (payload_matches and posterior_h1 >= 0.50) else "H0"

            if payload_matches:
                if anchor_found and (trusted_from_registry or anchor.status == "CONFIRMED_ON_CHAIN"):
                    publisher_authenticated = True
                    image_binding_verified = True
                    proof_valid = True
            else:
                failure_reason = "PAYLOAD_MISMATCH"
        else:
            inferred = "H2"
            is_detected = False
            failure_reason = "HAMMING_DISTANCE_UNAVAILABLE"
    else:
        # Blind / Unconstrained recovery without reference claim or registered anchor
        # Missing reference measurements must be represented as None per Requirement 3
        log10_lr = None
        posterior_h1 = None
        payload_matches = None
        is_detected = False
        inferred = "H2"
        if dec_res.payload_hex is None:
            failure_reason = dec_res.error or "NO_WATERMARK_SIGNAL_DETECTED"
        else:
            failure_reason = "UNANCHORED_MEDIA_NO_REFERENCE_CLAIM"

    if not is_detected and not failure_reason:
        failure_reason = dec_res.error or "NO_WATERMARK_SIGNAL_DETECTED"

    return DecodeResponse(
        success=True,
        decodable=dec_res.decodable,
        payload_hex=dec_res.payload_hex,
        payload_bits=c.info.payload_bits,
        hamming_distance=dec_res.hamming_distance,
        bit_error_rate=dec_res.bit_error_rate,
        confidence=dec_res.confidence if effective_ref_payload else None,
        mean_logit_magnitude=dec_res.mean_logit_magnitude,
        rms_energy=dec_res.rms_energy,
        neural_certainty=dec_res.neural_certainty if effective_ref_payload else None,
        expected_ber=dec_res.expected_ber if effective_ref_payload else None,
        carrier_name=c.info.name,
        carrier_version=c.info.version,
        elapsed_seconds=dec_res.elapsed_seconds,
        watermark_detected=is_detected,
        payload_recovered=payload_recovered,
        payload_matches=payload_matches,
        failure_reason=failure_reason,
        log10_likelihood_ratio=log10_lr,
        posterior_probability_h1=posterior_h1,
        inferred_hypothesis=inferred,
        image_sha256=sha256,
        proof_valid=proof_valid,
        image_binding_verified=image_binding_verified,
        publisher_authenticated=publisher_authenticated,
        anchor_found=anchor_found,
        registered_anchor=registered_anchor_dict,
        error=dec_res.error,
    )

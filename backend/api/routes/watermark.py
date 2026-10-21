"""
ProvenanceLab — Watermark Embedding & Decoding API Routes
"""

from __future__ import annotations

import base64
import io
from typing import Optional

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
        from backend.zk.features import cache_image_features
        feats = cache_image_features(sha256, enc_res.watermarked_image, carrier=carrier)
    except Exception as e:
        logger.warning("Could not cache features for ZK: %s", e)

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

    dec_res = c.decode(image, reference_payload_hex=reference_payload_hex)

    log10_lr = None
    posterior_h1 = None
    inferred = "H2"
    payload_matches = None
    failure_reason = None

    is_detected = getattr(dec_res, "watermark_detected", dec_res.decodable)
    has_payload = (dec_res.payload_hex is not None) and is_detected
    clean_ref = None

    if reference_payload_hex:
        clean_ref = reference_payload_hex.lower().replace("0x", "").strip()
        if dec_res.payload_hex:
            payload_matches = (dec_res.payload_hex.lower() == clean_ref)

        if dec_res.hamming_distance is not None:
            # Genuine Bayesian Likelihood Ratio on measured Hamming distance
            params = ModelParameters(payload_bits=c.info.payload_bits, p_H1=0.15, p_H0=0.50)
            model = BinomialModel(params)
            lr_result = model.likelihood_ratio(dec_res.hamming_distance)
            log10_lr = lr_result.log10_lr
            # Flat prior posterior P(H1 | LR)
            posterior_h1 = 1.0 / (1.0 + 10.0 ** (-log10_lr))
            inferred = "H1" if posterior_h1 >= 0.50 else "H0"
        else:
            inferred = "H2"
            failure_reason = "HAMMING_DISTANCE_UNAVAILABLE"
    else:
        # Blind / Unconstrained recovery: no reference payload provided
        # Do not fabricate log10_lr or posterior_h1 when no reference hypothesis was tested
        log10_lr = None
        posterior_h1 = None
        if is_detected and has_payload:
            inferred = "H1"
        else:
            inferred = "H2"

    if not is_detected:
        failure_reason = dec_res.error or "NO_WATERMARK_SIGNAL_DETECTED"
    elif reference_payload_hex and payload_matches is False:
        failure_reason = "PAYLOAD_MISMATCH"

    sha256 = c.image_sha256(image)

    return DecodeResponse(
        success=True,
        decodable=dec_res.decodable,
        payload_hex=dec_res.payload_hex if (is_detected or reference_payload_hex is not None) else None,
        payload_bits=c.info.payload_bits,
        hamming_distance=dec_res.hamming_distance,
        bit_error_rate=dec_res.bit_error_rate,
        confidence=dec_res.confidence,
        carrier_name=c.info.name,
        carrier_version=c.info.version,
        elapsed_seconds=dec_res.elapsed_seconds,
        watermark_detected=is_detected,
        payload_recovered=has_payload,
        payload_matches=payload_matches,
        failure_reason=failure_reason,
        log10_likelihood_ratio=log10_lr,
        posterior_probability_h1=posterior_h1,
        inferred_hypothesis=inferred,
        image_sha256=sha256,
        error=dec_res.error,
    )

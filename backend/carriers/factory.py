"""
ProvenanceLab — Carrier Registry & Factory
==========================================

Dynamically loads and registers watermark carriers:
- TrustMark (Adobe Research)
- WAM (Facebook Research)
- Fallback/Mock carrier for testing pipeline mechanics when models are unavailable
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Type

from backend.carriers.base import BaseCarrier

logger = logging.getLogger(__name__)

_CARRIER_REGISTRY: Dict[str, BaseCarrier] = {}


def get_carrier(name: str = "trustmark") -> BaseCarrier:
    """Retrieve or instantiate carrier by name."""
    global _CARRIER_REGISTRY
    name_clean = name.lower().strip()

    if name_clean in _CARRIER_REGISTRY:
        return _CARRIER_REGISTRY[name_clean]

    if "pureconv" in name_clean:
        try:
            from backend.carriers.pureconv.carrier import PureConvCarrier
            carrier = PureConvCarrier()
            _CARRIER_REGISTRY[name_clean] = carrier
            return carrier
        except Exception as e:
            logger.warning("Could not instantiate PureConv carrier (%s).", e)
            raise

    if "trustmark" in name_clean:
        try:
            from backend.carriers.trustmark.carrier import TrustMarkCarrier
            carrier = TrustMarkCarrier(model_type="Q", payload_bits=100)
            _CARRIER_REGISTRY[name_clean] = carrier
            return carrier
        except Exception as e:
            logger.warning("Could not instantiate TrustMark carrier (%s). Checking fallbacks.", e)
            raise

    if "hidden" in name_clean:
        try:
            from backend.carriers.hidden.carrier import HiddenCarrier
            carrier = HiddenCarrier()
            _CARRIER_REGISTRY[name_clean] = carrier
            return carrier
        except Exception as e:
            logger.warning("Could not instantiate HiDDeN carrier (%s).", e)
            raise

    raise ValueError(f"Unknown or unsupported watermark carrier: {name}")

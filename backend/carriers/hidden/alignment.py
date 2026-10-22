"""
ProvenanceLab — HiDDeN-32 Geometric Alignment & Redundant Tile Recovery Engine
=============================================================================
Provides:
1. Geometric Resynchronization: Searches and corrects small rotation angles and
   spatial translations to restore CNN grid alignment.
2. Redundant Tile Extraction: Extracts candidate sub-image windows (32x32 / 64x64)
   from cropped or transformed images.
3. Confidence-Weighted Logit Aggregation: Combines decoder logit vectors from
   candidate tiles weighted by logit activation energy.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from PIL import Image


def extract_candidate_tiles(
    img: Image.Image,
    target_tile_size: int = 64,
    min_tile_size: int = 32,
) -> List[Tuple[Image.Image, str]]:
    """
    Extracts candidate tiles and multi-scale crops from a suspect image:
    - Full image resized to target_tile_size
    - Overlapping grid tiles if image is larger than target_tile_size
    - Center crop
    - Four quadrant crops
    """
    candidates: List[Tuple[Image.Image, str]] = []
    w, h = img.size

    # 1. Full image scaled to target size
    full_resized = img.resize((target_tile_size, target_tile_size), Image.Resampling.BICUBIC)
    candidates.append((full_resized, "full_resized"))

    # 2. If image is large enough, extract grid tiles
    if w >= target_tile_size and h >= target_tile_size:
        stride_x = max(16, (w - target_tile_size) // 2) if w > target_tile_size else target_tile_size
        stride_y = max(16, (h - target_tile_size) // 2) if h > target_tile_size else target_tile_size

        for y in range(0, h - target_tile_size + 1, stride_y):
            for x in range(0, w - target_tile_size + 1, stride_x):
                box = (x, y, x + target_tile_size, y + target_tile_size)
                tile = img.crop(box)
                candidates.append((tile, f"tile_grid_{x}_{y}"))

    # 3. Center crop at 80% and 60% if sufficiently large
    for ratio in [0.80, 0.60]:
        cw, ch = int(w * ratio), int(h * ratio)
        if cw >= min_tile_size and ch >= min_tile_size:
            left = (w - cw) // 2
            top = (h - ch) // 2
            c_crop = img.crop((left, top, left + cw, top + ch)).resize(
                (target_tile_size, target_tile_size), Image.Resampling.BICUBIC
            )
            candidates.append((c_crop, f"center_crop_{int(ratio*100)}"))

    return candidates


def estimate_geometric_alignment(
    img: Image.Image,
    eval_fn,
    search_angles: List[float] = [-4.0, -2.0, -1.0, 0.0, 1.0, 2.0, 4.0],
    search_shifts: List[Tuple[int, int]] = [(0, 0), (-4, 0), (4, 0), (0, -4), (0, 4)],
) -> Tuple[Image.Image, float, float]:
    """
    Blind geometric resynchronization: finds rotation and translation parameters
    that maximize the neural watermark activation confidence (mean logit magnitude).
    Uses center-crop padding to eliminate corner interpolation artifacts.
    """
    best_conf = -1.0
    best_img = img
    best_angle = 0.0
    w, h = img.size

    # Inner region margin to exclude black corners after rotation
    margin_x = int(w * 0.08)
    margin_y = int(h * 0.08)

    # 1. Search candidate rotations
    for angle in search_angles:
        if abs(angle) < 1e-3:
            candidate = img
        else:
            # Rotate with border reflection to avoid black borders
            candidate = img.rotate(-angle, resample=Image.Resampling.BICUBIC, expand=False)
            # Crop inner 85% to eliminate edge artifacts and resize back
            candidate = candidate.crop((margin_x, margin_y, w - margin_x, h - margin_y)).resize((w, h), Image.Resampling.BICUBIC)

        conf = eval_fn(candidate)
        if conf > best_conf:
            best_conf = conf
            best_img = candidate
            best_angle = angle

    # 2. Search small translational refinements on the best-rotated candidate
    arr = np.array(best_img)
    refine_best_conf = best_conf
    refine_best_img = best_img

    for dx, dy in search_shifts:
        if dx == 0 and dy == 0:
            continue
        shifted = np.roll(arr, shift=(dy, dx), axis=(0, 1))
        cand_img = Image.fromarray(shifted)
        conf = eval_fn(cand_img)
        if conf > refine_best_conf:
            refine_best_conf = conf
            refine_best_img = cand_img

    return refine_best_img, best_angle, refine_best_conf


def aggregate_candidate_logits(
    logits_list: List[np.ndarray],
    weights: Optional[List[float]] = None,
) -> np.ndarray:
    """
    Aggregates logit predictions from multiple candidate tiles using confidence weighting:
    w_i = exp(alpha * mean(|logit_i|))
    returns: aggregated 32-dimensional logit array
    """
    if not logits_list:
        return np.zeros(32, dtype=np.float32)
    if len(logits_list) == 1:
        return logits_list[0]

    if weights is None:
        # Confidence score proportional to average logit magnitude (SNR)
        confs = [float(np.mean(np.abs(lg))) for lg in logits_list]
        max_c = max(confs) if confs else 1.0
        # Softmax-style sharpening
        weights = [math.exp(min(5.0, (c / (max_c + 1e-6)) * 2.0)) for c in confs]

    total_weight = sum(weights) + 1e-8
    agg = np.zeros(32, dtype=np.float32)
    for lg, w in zip(logits_list, weights):
        agg += (w / total_weight) * lg

    return agg

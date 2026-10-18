"""
ProvenanceLab — Image Degradation & Transformation Suite
========================================================

Implements standard benchmark transformations and realistic channel noise
models to test watermark bit survival and degradation:

1. JPEG Compression (Q=90, 75, 50, 30, 10)
2. Gaussian Blur (kernel radius / sigma = 0.5, 1.0, 2.0, 3.0)
3. Cropping & Resizing (Center crop 90%, 75%, 50% followed by upscale or native)
4. Additive Gaussian / Uniform Noise (sigma = 5, 10, 25)
5. Color / Contrast / Brightness adjustments
6. AI-style Regeneration / Inpainting simulation (controlled latent perturbation)
"""

from __future__ import annotations

import io
import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


@dataclass
class AttackSpec:
    name: str
    category: str
    params: Dict[str, Any]
    severity: float  # Normalized 0.0 to 1.0 scale for easy comparison


class AttackRegistry:
    """Registry of reproducible image degradation operators."""

    @staticmethod
    def jpeg_compression(img: Image.Image, quality: int = 75) -> Image.Image:
        """Apply JPEG compression at specified quality level (1-100)."""
        buffer = io.BytesIO()
        img.convert("RGB").save(buffer, format="JPEG", quality=quality)
        buffer.seek(0)
        return Image.open(buffer).convert("RGB")

    @staticmethod
    def gaussian_blur(img: Image.Image, radius: float = 1.5) -> Image.Image:
        """Apply Gaussian blur with given pixel radius."""
        return img.filter(ImageFilter.GaussianBlur(radius=radius))

    @staticmethod
    def center_crop_and_resize(img: Image.Image, crop_ratio: float = 0.8) -> Image.Image:
        """Crop center region by ratio (e.g. 0.8 = 80% width & height) and resize back to original size."""
        w, h = img.size
        cw, ch = int(w * crop_ratio), int(h * crop_ratio)
        left = (w - cw) // 2
        top = (h - ch) // 2
        cropped = img.crop((left, top, left + cw, top + ch))
        return cropped.resize((w, h), Image.Resampling.BICUBIC)

    @staticmethod
    def resize_down_up(img: Image.Image, scale: float = 0.5) -> Image.Image:
        """Downscale by factor, then upscale back to original resolution."""
        w, h = img.size
        dw, dh = max(16, int(w * scale)), max(16, int(h * scale))
        down = img.resize((dw, dh), Image.Resampling.BILINEAR)
        return down.resize((w, h), Image.Resampling.BICUBIC)

    @staticmethod
    def additive_noise(img: Image.Image, sigma: float = 15.0) -> Image.Image:
        """Add zero-mean Gaussian noise with standard deviation sigma."""
        arr = np.array(img.convert("RGB"), dtype=np.float32)
        rng = np.random.default_rng()
        noise = rng.normal(0.0, sigma, arr.shape)
        noisy = np.clip(arr + noise, 0.0, 255.0).astype(np.uint8)
        return Image.fromarray(noisy)

    @staticmethod
    def brightness_contrast(img: Image.Image, brightness: float = 1.1, contrast: float = 1.1) -> Image.Image:
        """Adjust image brightness and contrast multipliers."""
        enh_b = ImageEnhance.Brightness(img)
        img_b = enh_b.enhance(brightness)
        enh_c = ImageEnhance.Contrast(img_b)
        return enh_c.enhance(contrast)

    @staticmethod
    def simulated_ai_regeneration(
        img: Image.Image, strength: float = 0.50, seed: Optional[int] = 42
    ) -> Image.Image:
        """
        Simulate AI Image-to-Image / diffusion regeneration at a specified denoising strength.
        At strength 0.0: identity.
        At strength 1.0: heavy semantic/high-frequency replacement.
        Intermediate strength: combines spatial frequency preservation with perceptual diffusion noise.
        """
        arr = np.array(img.convert("RGB"), dtype=np.float32)
        rng = np.random.default_rng(seed)

        # High frequency destruction typical of diffusion autoencoders (VAE encoder/decoder blur + noise)
        # 1. Downscale + upscale through simulated latent bottleneck
        w, h = img.size
        latent_w, latent_h = max(32, w // 8), max(32, h // 8)
        latent_approx = img.resize((latent_w, latent_h), Image.Resampling.BILINEAR)
        reconstructed = latent_approx.resize((w, h), Image.Resampling.BICUBIC)
        rec_arr = np.array(reconstructed, dtype=np.float32)

        # 2. Add structural perturbation correlated with strength
        sigma = strength * 35.0
        pert = rng.normal(0.0, sigma, arr.shape)

        # 3. Blend original and synthetic reconstruction
        alpha = min(1.0, strength * 1.2)
        blended = (1.0 - alpha) * arr + alpha * rec_arr + pert
        out = np.clip(blended, 0.0, 255.0).astype(np.uint8)
        return Image.fromarray(out)


def get_standard_attack_suite() -> list[AttackSpec]:
    """Returns a standardized battery of attacks for benchmarks and survival analysis."""
    return [
        AttackSpec(name="identity", category="baseline", params={}, severity=0.0),
        # JPEG suite
        AttackSpec(name="jpeg_q90", category="jpeg", params={"quality": 90}, severity=0.1),
        AttackSpec(name="jpeg_q75", category="jpeg", params={"quality": 75}, severity=0.25),
        AttackSpec(name="jpeg_q50", category="jpeg", params={"quality": 50}, severity=0.50),
        AttackSpec(name="jpeg_q30", category="jpeg", params={"quality": 30}, severity=0.70),
        AttackSpec(name="jpeg_q15", category="jpeg", params={"quality": 15}, severity=0.85),
        # Blur suite
        AttackSpec(name="blur_r1", category="blur", params={"radius": 1.0}, severity=0.2),
        AttackSpec(name="blur_r2", category="blur", params={"radius": 2.0}, severity=0.45),
        AttackSpec(name="blur_r3", category="blur", params={"radius": 3.0}, severity=0.7),
        # Crop & resize suite
        AttackSpec(name="crop_90", category="crop", params={"crop_ratio": 0.9}, severity=0.2),
        AttackSpec(name="crop_75", category="crop", params={"crop_ratio": 0.75}, severity=0.4),
        AttackSpec(name="crop_50", category="crop", params={"crop_ratio": 0.5}, severity=0.75),
        # Scale suite
        AttackSpec(name="scale_0.75", category="scale", params={"scale": 0.75}, severity=0.25),
        AttackSpec(name="scale_0.50", category="scale", params={"scale": 0.50}, severity=0.50),
        # Noise suite
        AttackSpec(name="noise_s10", category="noise", params={"sigma": 10.0}, severity=0.3),
        AttackSpec(name="noise_s25", category="noise", params={"sigma": 25.0}, severity=0.6),
        # AI Regeneration suite
        AttackSpec(name="ai_regen_0.20", category="ai_regen", params={"strength": 0.20}, severity=0.20),
        AttackSpec(name="ai_regen_0.50", category="ai_regen", params={"strength": 0.50}, severity=0.50),
        AttackSpec(name="ai_regen_0.80", category="ai_regen", params={"strength": 0.80}, severity=0.80),
    ]


def apply_attack(img: Image.Image, spec: AttackSpec) -> Image.Image:
    """Execute the attack specified by an AttackSpec on a PIL Image."""
    name = spec.name
    p = spec.params

    if name == "identity":
        return img.copy()
    if "jpeg" in name:
        return AttackRegistry.jpeg_compression(img, quality=p.get("quality", 75))
    if "blur" in name:
        return AttackRegistry.gaussian_blur(img, radius=p.get("radius", 1.0))
    if "crop" in name:
        return AttackRegistry.center_crop_and_resize(img, crop_ratio=p.get("crop_ratio", 0.8))
    if "scale" in name:
        return AttackRegistry.resize_down_up(img, scale=p.get("scale", 0.5))
    if "noise" in name:
        return AttackRegistry.additive_noise(img, sigma=p.get("sigma", 15.0))
    if "ai_regen" in name:
        return AttackRegistry.simulated_ai_regeneration(
            img, strength=p.get("strength", 0.5), seed=p.get("seed", 42)
        )

    raise ValueError(f"Unknown attack specification: {spec}")

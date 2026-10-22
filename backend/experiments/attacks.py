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
    def rotation(img: Image.Image, angle: float) -> Image.Image:
        """Rotate image by angle (degrees) using Bicubic interpolation with border reflection."""
        # Convert to RGB, rotate with BICUBIC, expand=False
        return img.convert("RGB").rotate(angle, resample=Image.Resampling.BICUBIC, expand=False)

    @staticmethod
    def translation(img: Image.Image, dx: int, dy: int) -> Image.Image:
        """Translate image by (dx, dy) pixels with edge reflection/clamping."""
        arr = np.array(img.convert("RGB"))
        h, w, c = arr.shape
        translated = np.zeros_like(arr)
        
        # Source and destination slice calculation
        src_y1 = max(0, -dy)
        src_y2 = min(h, h - dy)
        dst_y1 = max(0, dy)
        dst_y2 = min(h, h + dy)
        
        src_x1 = max(0, -dx)
        src_x2 = min(w, w - dx)
        dst_x1 = max(0, dx)
        dst_x2 = min(w, w + dx)
        
        if dst_y2 > dst_y1 and dst_x2 > dst_x1:
            translated[dst_y1:dst_y2, dst_x1:dst_x2] = arr[src_y1:src_y2, src_x1:src_x2]
        return Image.fromarray(translated)

    @staticmethod
    def unresized_crop(img: Image.Image, crop_ratio: float = 0.75, location: str = "center") -> Image.Image:
        """Crop a sub-region of the image without resizing back to original size."""
        w, h = img.size
        cw, ch = max(32, int(w * crop_ratio)), max(32, int(h * crop_ratio))
        if location == "center":
            left = (w - cw) // 2
            top = (h - ch) // 2
        elif location == "top_left":
            left, top = 0, 0
        elif location == "bottom_right":
            left, top = w - cw, h - ch
        else:
            left = (w - cw) // 2
            top = (h - ch) // 2
        return img.crop((left, top, left + cw, top + ch))

    @staticmethod
    def scaling(img: Image.Image, scale: float = 0.5, interpolation: str = "bilinear") -> Image.Image:
        """Resize image by scale factor without resizing back."""
        w, h = img.size
        nw, nh = max(16, int(w * scale)), max(16, int(h * scale))
        interp_map = {
            "bilinear": Image.Resampling.BILINEAR,
            "bicubic": Image.Resampling.BICUBIC,
            "nearest": Image.Resampling.NEAREST,
        }
        resample_mode = interp_map.get(interpolation.lower(), Image.Resampling.BILINEAR)
        return img.resize((nw, nh), resample_mode)

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


def get_seven_attack_suite() -> list[AttackSpec]:
    """
    Returns the comprehensive 7-attack evaluation suite meeting the research specification:
    1. Clean / Identity
    2. JPEG Compression (Q=90, 70, 50, 40, 20)
    3. Cropping (center crop 90%, 75%, 50% with resize, and unresized crop)
    4. Resizing (scale 0.75, 0.50, 1.25, 1.50 with bilinear and bicubic)
    5. Gaussian Blur (radius 0.5, 1.0, 2.0, 3.0)
    6. Gaussian Noise (sigma 5.0, 15.0, 25.0, 35.0)
    7. Brightness & Contrast (bright 1.25, dark 0.8, high contrast 1.25, low contrast 0.8)
    8. Rotation & Translation (rot 1 deg, 2 deg, 5 deg; trans dx=4, dy=4; dx=8, dy=8)
    9. Combined attacks (JPEG 70 + blur 1.0, JPEG 70 + scale 0.75, noise 15 + blur 1.0, rot 2 + trans 4)
    """
    return [
        # 1. Clean
        AttackSpec(name="identity", category="baseline", params={}, severity=0.0),
        # 2. JPEG
        AttackSpec(name="jpeg_q90", category="jpeg", params={"quality": 90}, severity=0.10),
        AttackSpec(name="jpeg_q70", category="jpeg", params={"quality": 70}, severity=0.30),
        AttackSpec(name="jpeg_q50", category="jpeg", params={"quality": 50}, severity=0.50),
        AttackSpec(name="jpeg_q40", category="jpeg", params={"quality": 40}, severity=0.60),
        AttackSpec(name="jpeg_q20", category="jpeg", params={"quality": 20}, severity=0.80),
        # 3. Cropping
        AttackSpec(name="crop_resize_90", category="crop", params={"crop_ratio": 0.90}, severity=0.20),
        AttackSpec(name="crop_resize_75", category="crop", params={"crop_ratio": 0.75}, severity=0.40),
        AttackSpec(name="crop_resize_50", category="crop", params={"crop_ratio": 0.50}, severity=0.70),
        AttackSpec(name="crop_native_75", category="crop", params={"crop_ratio": 0.75, "native": True, "location": "center"}, severity=0.50),
        AttackSpec(name="crop_native_50", category="crop", params={"crop_ratio": 0.50, "native": True, "location": "top_left"}, severity=0.80),
        # 4. Resizing
        AttackSpec(name="resize_0.75_bilinear", category="resize", params={"scale": 0.75, "interpolation": "bilinear"}, severity=0.25),
        AttackSpec(name="resize_0.50_bilinear", category="resize", params={"scale": 0.50, "interpolation": "bilinear"}, severity=0.50),
        AttackSpec(name="resize_0.50_bicubic", category="resize", params={"scale": 0.50, "interpolation": "bicubic"}, severity=0.50),
        AttackSpec(name="resize_1.25_bilinear", category="resize", params={"scale": 1.25, "interpolation": "bilinear"}, severity=0.25),
        AttackSpec(name="resize_1.50_bicubic", category="resize", params={"scale": 1.50, "interpolation": "bicubic"}, severity=0.40),
        # 5. Gaussian Blur
        AttackSpec(name="blur_r0.5", category="blur", params={"radius": 0.5}, severity=0.15),
        AttackSpec(name="blur_r1.0", category="blur", params={"radius": 1.0}, severity=0.30),
        AttackSpec(name="blur_r2.0", category="blur", params={"radius": 2.0}, severity=0.55),
        AttackSpec(name="blur_r3.0", category="blur", params={"radius": 3.0}, severity=0.80),
        # 6. Gaussian Noise
        AttackSpec(name="noise_s5", category="noise", params={"sigma": 5.0}, severity=0.15),
        AttackSpec(name="noise_s15", category="noise", params={"sigma": 15.0}, severity=0.40),
        AttackSpec(name="noise_s25", category="noise", params={"sigma": 25.0}, severity=0.65),
        AttackSpec(name="noise_s35", category="noise", params={"sigma": 35.0}, severity=0.85),
        # 7. Brightness & Contrast
        AttackSpec(name="bright_1.25", category="color", params={"brightness": 1.25, "contrast": 1.0}, severity=0.25),
        AttackSpec(name="dark_0.80", category="color", params={"brightness": 0.80, "contrast": 1.0}, severity=0.25),
        AttackSpec(name="contrast_1.25", category="color", params={"brightness": 1.0, "contrast": 1.25}, severity=0.25),
        AttackSpec(name="contrast_0.80", category="color", params={"brightness": 1.0, "contrast": 0.80}, severity=0.25),
        AttackSpec(name="bright_contrast_high", category="color", params={"brightness": 1.20, "contrast": 1.20}, severity=0.40),
        # 8. Rotation & Translation
        AttackSpec(name="rot_1deg", category="geometry", params={"angle": 1.0}, severity=0.20),
        AttackSpec(name="rot_2deg", category="geometry", params={"angle": 2.0}, severity=0.40),
        AttackSpec(name="rot_5deg", category="geometry", params={"angle": 5.0}, severity=0.70),
        AttackSpec(name="trans_dx4_dy4", category="geometry", params={"dx": 4, "dy": 4}, severity=0.30),
        AttackSpec(name="trans_dx8_dy8", category="geometry", params={"dx": 8, "dy": 8}, severity=0.55),
        # 9. Combined
        AttackSpec(name="combo_jpeg70_blur1", category="combined", params={"steps": [
            {"type": "jpeg", "quality": 70},
            {"type": "blur", "radius": 1.0},
        ]}, severity=0.50),
        AttackSpec(name="combo_jpeg70_scale75", category="combined", params={"steps": [
            {"type": "jpeg", "quality": 70},
            {"type": "scale", "scale": 0.75},
        ]}, severity=0.55),
        AttackSpec(name="combo_noise15_blur1", category="combined", params={"steps": [
            {"type": "noise", "sigma": 15.0},
            {"type": "blur", "radius": 1.0},
        ]}, severity=0.60),
        AttackSpec(name="combo_rot2_trans4", category="combined", params={"steps": [
            {"type": "rotation", "angle": 2.0},
            {"type": "translation", "dx": 4, "dy": 4},
        ]}, severity=0.65),
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
    if "crop_native" in name or p.get("native"):
        return AttackRegistry.unresized_crop(
            img,
            crop_ratio=p.get("crop_ratio", 0.75),
            location=p.get("location", "center"),
        )
    if "crop" in name:
        return AttackRegistry.center_crop_and_resize(img, crop_ratio=p.get("crop_ratio", 0.8))
    if "resize" in name:
        if "scale" in p:
            return AttackRegistry.scaling(
                img,
                scale=p.get("scale", 0.5),
                interpolation=p.get("interpolation", "bilinear"),
            )
        return AttackRegistry.resize_down_up(img, scale=p.get("scale", 0.5))
    if "scale" in name:
        return AttackRegistry.resize_down_up(img, scale=p.get("scale", 0.5))
    if "noise" in name:
        return AttackRegistry.additive_noise(img, sigma=p.get("sigma", 15.0))
    if "bright" in name or "dark" in name or "contrast" in name or spec.category == "color":
        return AttackRegistry.brightness_contrast(
            img,
            brightness=p.get("brightness", 1.0),
            contrast=p.get("contrast", 1.0),
        )
    if "rot" in name or "angle" in p:
        return AttackRegistry.rotation(img, angle=p.get("angle", 0.0))
    if "trans" in name or ("dx" in p and "dy" in p):
        return AttackRegistry.translation(img, dx=p.get("dx", 0), dy=p.get("dy", 0))
    if "combo" in name or spec.category == "combined":
        out = img.copy()
        for step in p.get("steps", []):
            stype = step.get("type")
            if stype == "jpeg":
                out = AttackRegistry.jpeg_compression(out, quality=step.get("quality", 75))
            elif stype == "blur":
                out = AttackRegistry.gaussian_blur(out, radius=step.get("radius", 1.0))
            elif stype == "scale":
                out = AttackRegistry.scaling(out, scale=step.get("scale", 0.75))
            elif stype == "noise":
                out = AttackRegistry.additive_noise(out, sigma=step.get("sigma", 15.0))
            elif stype == "rotation":
                out = AttackRegistry.rotation(out, angle=step.get("angle", 0.0))
            elif stype == "translation":
                out = AttackRegistry.translation(out, dx=step.get("dx", 0), dy=step.get("dy", 0))
        return out
    if "ai_regen" in name:
        return AttackRegistry.simulated_ai_regeneration(
            img, strength=p.get("strength", 0.5), seed=p.get("seed", 42)
        )

    raise ValueError(f"Unknown attack specification: {spec}")

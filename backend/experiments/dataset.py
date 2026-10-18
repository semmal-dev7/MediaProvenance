"""
ProvenanceLab — Dataset Protocol & Image Generator
==================================================

Defines dataset management for experimental evaluation:
1. Procedural Benchmark Dataset Generator: generates realistic high-entropy
   and natural-like benchmark images with controlled frequency characteristics
   (textures, gradients, geometric structures, photographic noise).
2. Ground-truth relationship labeling:
   - Genuine reference/derivative pairs (H1)
   - Unrelated negative pairs (H0)
   - Severely damaged / undecodable pairs (H2)
3. Fixed train/calibration/test splits avoiding source leakage.
4. Cryptographic hashing (SHA-256) of every source image for provenance tracking.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


@dataclass
class DatasetImageRecord:
    image_id: str
    sha256: str
    relative_path: str
    width: int
    height: int
    category: str
    split: str  # "calibration" or "test"


class BenchmarkDatasetManager:
    """Manages creation, partitioning, and indexing of benchmark image datasets."""

    def __init__(self, base_dir: str = "experiments/data"):
        self.base_dir = base_dir
        self.images_dir = os.path.join(base_dir, "images")
        self.manifest_path = os.path.join(base_dir, "manifests", "dataset_manifest.json")
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)

    @staticmethod
    def generate_synthetic_image(
        category: str,
        size: Tuple[int, int] = (512, 512),
        seed: int = 42,
    ) -> Image.Image:
        """
        Generate reproducible, high-frequency, naturalistic synthetic images
        covering diverse entropy and spatial frequency conditions.
        """
        rng = np.random.default_rng(seed)
        w, h = size

        if category == "smooth_gradient":
            # Continuous smooth color gradients with seed-dependent phase shifts
            phase_r = rng.uniform(0.5, 3.0)
            phase_g = rng.uniform(0.5, 3.0)
            phase_b = rng.uniform(0.5, 3.0)
            x = np.linspace(0, 1, w)
            y = np.linspace(0, 1, h)
            xx, yy = np.meshgrid(x, y)
            r = (np.sin(xx * 3.1415 * phase_r) * 127.5 + 127.5).astype(np.uint8)
            g = (np.cos(yy * 3.1415 * phase_g) * 127.5 + 127.5).astype(np.uint8)
            b = (np.sin((xx + yy) * 3.1415 * phase_b) * 127.5 + 127.5).astype(np.uint8)
            arr = np.stack([r, g, b], axis=-1)
            return Image.fromarray(arr)

        elif category == "geometric_textures":
            # High-contrast edges and geometric shapes
            img = Image.new("RGB", (w, h), (240, 240, 240))
            draw = ImageDraw.Draw(img)
            for i in range(15):
                x0, y0 = rng.integers(0, w - 50, size=2)
                x1, y1 = x0 + rng.integers(20, 100), y0 + rng.integers(20, 100)
                color = tuple(int(c) for c in rng.integers(20, 230, size=3))
                draw.rectangle([x0, y0, x1, y1], fill=color, outline=(0, 0, 0))
            for i in range(10):
                x0, y0 = rng.integers(0, w - 50, size=2)
                rad = rng.integers(15, 60)
                color = tuple(int(c) for c in rng.integers(20, 230, size=3))
                draw.ellipse([x0, y0, x0 + rad, y0 + rad], fill=color)
            return img

        elif category == "high_freq_noise":
            # Perceptual multi-scale noise mimicking natural textures
            base = rng.normal(128, 40, (h, w, 3)).clip(0, 255).astype(np.uint8)
            img = Image.fromarray(base)
            return img.filter(ImageFilter.SMOOTH_MORE)

        elif category == "photographic_sim":
            # Mixed complex scene with background gradient, textures, and features
            x = np.linspace(0, 1, w)
            y = np.linspace(0, 1, h)
            xx, yy = np.meshgrid(x, y)
            bg = (xx * 100 + yy * 80).astype(np.float32)
            noise = rng.normal(0, 20, (h, w)).astype(np.float32)
            lum = np.clip(bg + noise, 0, 255).astype(np.uint8)
            arr = np.stack([lum, (lum * 0.9).astype(np.uint8), (lum * 0.8).astype(np.uint8)], axis=-1)
            img = Image.fromarray(arr)
            draw = ImageDraw.Draw(img)
            for _ in range(8):
                pt1 = (int(rng.integers(0, w)), int(rng.integers(0, h)))
                pt2 = (int(rng.integers(0, w)), int(rng.integers(0, h)))
                draw.line([pt1, pt2], fill=(255, 255, 255), width=3)
            return img

        else:
            # Default uniform pattern
            arr = rng.integers(50, 200, (h, w, 3), dtype=np.uint8)
            return Image.fromarray(arr)

    def prepare_standard_benchmark(
        self,
        n_samples: int = 40,
        calibration_ratio: float = 0.50,
        image_size: Tuple[int, int] = (512, 512),
        seed: int = 101,
    ) -> List[DatasetImageRecord]:
        """
        Creates a standardized benchmark dataset split into Calibration and Test partitions.
        No source image leakage exists across splits.
        """
        categories = ["photographic_sim", "geometric_textures", "high_freq_noise", "smooth_gradient"]
        records: List[DatasetImageRecord] = []

        n_calib = int(n_samples * calibration_ratio)

        for i in range(n_samples):
            split = "calibration" if i < n_calib else "test"
            cat = categories[i % len(categories)]
            img = self.generate_synthetic_image(cat, size=image_size, seed=seed + i)

            raw_bytes = img.tobytes()
            sha = hashlib.sha256(raw_bytes).hexdigest()
            img_id = f"img_{split}_{i:03d}_{cat[:4]}"
            rel_path = os.path.join("images", f"{img_id}.png")
            abs_path = os.path.join(self.base_dir, rel_path)

            img.save(abs_path, format="PNG")

            rec = DatasetImageRecord(
                image_id=img_id,
                sha256=sha,
                relative_path=rel_path.replace("\\", "/"),
                width=image_size[0],
                height=image_size[1],
                category=cat,
                split=split,
            )
            records.append(rec)

        # Write manifest
        manifest_data = {
            "version": "1.0.0",
            "total_images": len(records),
            "calibration_count": n_calib,
            "test_count": n_samples - n_calib,
            "categories": categories,
            "images": [asdict(r) for r in records],
        }
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        return records

    def load_manifest(self) -> Dict:
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_image(self, rel_path: str) -> Image.Image:
        full_path = os.path.join(self.base_dir, rel_path)
        return Image.open(full_path).convert("RGB")

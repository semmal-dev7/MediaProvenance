"""
ProvenanceLab — Step 1: Download Clean Training Photos
======================================================
Downloads a clean, unwatermarked image dataset (COCO-128 or Mini-COCO)
and saves the images directly into:
    experiments/data/train_clean/

Usage:
    python scripts/download_training_data.py
"""

import io
import os
import sys
import zipfile
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEST_DIR = PROJECT_ROOT / "experiments" / "data" / "train_clean"

# Ultralytics COCO-128: 128 diverse real-world images, ~7 MB download
URL_COCO128 = "https://github.com/ultralytics/yolov5/releases/download/v1.0/coco128.zip"


def download_and_extract(url: str, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    print("=" * 70)
    print("STEP 1: DOWNLOADING CLEAN (UNWATERMARKED) DATASET")
    print("=" * 70)
    print(f"Target directory: {dest}")
    print(f"Downloading from: {url}")
    print("Downloading (~7 MB)... please wait a few seconds...")

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req) as resp:
            zip_bytes = resp.read()
        print(f"Download complete! ({len(zip_bytes) / (1024 * 1024):.1f} MB)")

        print("Extracting images...")
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            count = 0
            for member in zf.namelist():
                if member.lower().endswith((".png", ".jpg", ".jpeg")):
                    filename = Path(member).name
                    if not filename:
                        continue
                    out_path = dest / filename
                    with zf.open(member) as src_file, open(out_path, "wb") as dst_file:
                        dst_file.write(src_file.read())
                    count += 1

        print(f"\n[SUCCESS] Extracted {count} clean photos to: {dest}")
        print("You are now ready for Step 2 (training)!")
        print("=" * 70)
    except Exception as e:
        print(f"\n[ERROR] Download failed: {e}")
        print("Alternative: You can manually copy 100-500 JPG or PNG photos into:")
        print(f"  {dest}")


if __name__ == "__main__":
    download_and_extract(URL_COCO128, DEST_DIR)

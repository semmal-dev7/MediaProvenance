import base64
import io
import json
from pathlib import Path
import requests
from PIL import Image

BASE_URL = "http://127.0.0.1:8080/api/v1"
IMG1_PATH = "experiments/data/images/img_test_004_phot.png"
IMG2_PATH = "experiments/data/images/img_calibration_001_geom.png"
PAYLOAD = "deadbeef"

OUTPUT_DIR = Path("experiments/results/phase5_4_controlled_tests")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

test_records = {}

def run_test_suite(carrier_name: str):
    print(f"\n=======================================================")
    print(f"Running controlled tests for carrier: {carrier_name}")
    print(f"=======================================================")
    records = {}

    # 1. Embed watermark into Image 1
    print(f"[*] Embedding {PAYLOAD} into {IMG1_PATH} with {carrier_name}...")
    with open(IMG1_PATH, "rb") as f:
        r_emb = requests.post(
            f"{BASE_URL}/watermarks/embed",
            files={"file": ("orig.png", f, "image/png")},
            data={"carrier": carrier_name, "payload_hex": PAYLOAD}
        )
    emb_data = r_emb.json()
    b64_raw = emb_data["watermarked_image_base64"]
    if "," in b64_raw:
        b64_raw = b64_raw.split(",", 1)[1]
    wm_img_bytes = base64.b64decode(b64_raw)
    wm_img = Image.open(io.BytesIO(wm_img_bytes))
    
    # Save test images
    wm_path = OUTPUT_DIR / f"watermarked_{carrier_name}.png"
    wm_img.save(wm_path)

    # C. JPEG Q70 version
    jpeg_buf = io.BytesIO()
    wm_img.save(jpeg_buf, format="JPEG", quality=70)
    jpeg_bytes = jpeg_buf.getvalue()
    jpeg_path = OUTPUT_DIR / f"watermarked_{carrier_name}_q70.jpg"
    with open(jpeg_path, "wb") as f:
        f.write(jpeg_bytes)

    # D. Cropped version (32x32 surviving tile from center)
    w, h = wm_img.size
    crop_size = 32
    left = (w - crop_size) // 2
    top = (h - crop_size) // 2
    crop_img = wm_img.crop((left, top, left + crop_size, top + crop_size))
    # resize back to original size or model size to preserve spatial grid if needed
    crop_buf = io.BytesIO()
    crop_img.save(crop_buf, format="PNG")
    crop_bytes = crop_buf.getvalue()
    crop_path = OUTPUT_DIR / f"watermarked_{carrier_name}_crop32.png"
    with open(crop_path, "wb") as f:
        f.write(crop_bytes)

    # Controlled Tests:
    # A. Original unwatermarked image
    print("[*] Test A: Original unwatermarked image...")
    with open(IMG1_PATH, "rb") as f:
        r_A = requests.post(f"{BASE_URL}/watermarks/decode", files={"file": ("unwatermarked.png", f, "image/png")}, data={"carrier": carrier_name})
    records["Test_A_unwatermarked"] = {
        "description": "Original unwatermarked image",
        "request": {"carrier": carrier_name, "file": IMG1_PATH},
        "response": r_A.json()
    }

    # B. Original watermarked image
    print("[*] Test B: Original watermarked image...")
    with open(wm_path, "rb") as f:
        r_B = requests.post(f"{BASE_URL}/watermarks/decode", files={"file": ("watermarked.png", f, "image/png")}, data={"carrier": carrier_name})
    records["Test_B_watermarked"] = {
        "description": "Original watermarked image",
        "request": {"carrier": carrier_name, "file": str(wm_path)},
        "response": r_B.json()
    }

    # C. JPEG Q70 version of watermarked image
    print("[*] Test C: JPEG Q70 version...")
    with open(jpeg_path, "rb") as f:
        r_C = requests.post(f"{BASE_URL}/watermarks/decode", files={"file": ("wm_q70.jpg", f, "image/jpeg")}, data={"carrier": carrier_name})
    records["Test_C_jpeg_q70"] = {
        "description": "JPEG Q70 version of watermarked image",
        "request": {"carrier": carrier_name, "file": str(jpeg_path)},
        "response": r_C.json()
    }

    # D. Cropped watermarked image
    print("[*] Test D: Cropped watermarked image...")
    with open(crop_path, "rb") as f:
        r_D = requests.post(f"{BASE_URL}/watermarks/decode", files={"file": ("wm_crop.png", f, "image/png")}, data={"carrier": carrier_name})
    records["Test_D_cropped"] = {
        "description": "Cropped watermarked image (32x32 center crop)",
        "request": {"carrier": carrier_name, "file": str(crop_path)},
        "response": r_D.json()
    }

    # E. Different unwatermarked image
    print("[*] Test E: Different unwatermarked image...")
    with open(IMG2_PATH, "rb") as f:
        r_E = requests.post(f"{BASE_URL}/watermarks/decode", files={"file": ("different_clean.png", f, "image/png")}, data={"carrier": carrier_name})
    records["Test_E_different_unwatermarked"] = {
        "description": "Different unwatermarked image (img_calibration_001_geom.png)",
        "request": {"carrier": carrier_name, "file": IMG2_PATH},
        "response": r_E.json()
    }

    return records

test_records["hidden"] = run_test_suite("hidden")
test_records["pureconv"] = run_test_suite("pureconv")

summary_path = OUTPUT_DIR / "controlled_test_records.json"
with open(summary_path, "w") as f:
    json.dump(test_records, f, indent=2)

print(f"\n[+] All controlled tests completed. Saved to {summary_path}")

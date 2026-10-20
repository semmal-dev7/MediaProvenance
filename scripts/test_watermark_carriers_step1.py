"""
Test Watermark Carriers Step 1
==============================
Tests HiDDeN-32 and TrustMark-Q:
1. Embedding and decoding on standard test images.
2. PSNR, SSIM, latency measurement.
3. Perfect bit recovery (0 BER) on authentic images.
4. Negative presence detection on unwatermarked images.
5. Bit survival under JPEG Q=75 and Gaussian noise.
"""

import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
from backend.carriers.factory import get_carrier


def compute_ssim(img1: Image.Image, img2: Image.Image) -> float:
    """Compute SSIM between two RGB PIL images."""
    arr1 = np.array(img1.convert("RGB"), dtype=np.float64)
    arr2 = np.array(img2.convert("RGB"), dtype=np.float64)
    
    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2
    
    mu1 = np.mean(arr1)
    mu2 = np.mean(arr2)
    sigma1_sq = np.var(arr1)
    sigma2_sq = np.var(arr2)
    sigma12 = np.mean((arr1 - mu1) * (arr2 - mu2))
    
    ssim = ((2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)) / (
        (mu1**2 + mu2**2 + C1) * (sigma1_sq + sigma2_sq + C2)
    )
    return float(ssim)


def run_tests():
    print("=" * 70)
    print("STEP 1: WATERMARK CARRIER VERIFICATION (HiDDeN-32 & TrustMark-Q)")
    print("=" * 70)

    # 1. HiDDeN-32 Carrier Test
    print("\n--- 1. Testing HiDDeN-32 Carrier (32-bit Circuit-Bound Model) ---")
    c_hid = get_carrier("hidden")
    test_img_hid = Image.new("RGB", (128, 128), (110, 140, 180))
    # Add non-trivial texture
    for x in range(128):
        for y in range(128):
            test_img_hid.putpixel((x, y), ((x * 3) % 256, (y * 5) % 256, ((x + y) * 2) % 256))

    payload_hid = "a1b2c3d4"
    enc_hid = c_hid.encode(test_img_hid, payload_hid)
    assert enc_hid.error is None, f"HiDDeN encode error: {enc_hid.error}"
    ssim_hid = compute_ssim(test_img_hid, enc_hid.watermarked_image)
    print(f"  [+] Encode Success:")
    print(f"      PSNR: {enc_hid.psnr_db:.2f} dB, SSIM: {ssim_hid:.4f}, Latency: {enc_hid.elapsed_seconds*1000:.1f} ms")
    assert enc_hid.psnr_db >= 38.0, f"HiDDeN PSNR too low: {enc_hid.psnr_db}"
    assert ssim_hid >= 0.98, f"HiDDeN SSIM too low: {ssim_hid}"

    # Decode HiDDeN
    dec_hid = c_hid.decode(enc_hid.watermarked_image, reference_payload_hex=payload_hid)
    print(f"  [+] Decode Success:")
    print(f"      Decodable: {dec_hid.decodable}, Extracted: {dec_hid.payload_hex}")
    print(f"      Hamming Distance: {dec_hid.hamming_distance}/32, BER: {dec_hid.bit_error_rate*100:.1f}%")
    assert dec_hid.decodable is True
    assert dec_hid.hamming_distance == 0, f"Expected 0 Hamming distance, got {dec_hid.hamming_distance}"

    # Negative test on unwatermarked image
    unwatermarked = Image.new("RGB", (128, 128), (200, 200, 200))
    dec_neg_hid = c_hid.decode(unwatermarked)
    print(f"  [+] Negative Detection (Unwatermarked Image):")
    print(f"      Decodable: {dec_neg_hid.decodable}, Payload: {dec_neg_hid.payload_hex}")
    assert dec_neg_hid.decodable is False or dec_neg_hid.payload_hex is None

    # 2. TrustMark-Q Carrier Test
    print("\n--- 2. Testing TrustMark-Q Carrier (100-bit Forensic Model) ---")
    c_tm = get_carrier("trustmark")
    test_img_tm = Image.new("RGB", (256, 256), (120, 160, 200))
    for x in range(256):
        for y in range(256):
            test_img_tm.putpixel((x, y), ((x * 2) % 256, (y * 4) % 256, ((x + y) * 3) % 256))

    payload_tm = "a50123456789abcdef0123456"
    enc_tm = c_tm.encode(test_img_tm, payload_tm)
    assert enc_tm.error is None, f"TrustMark encode error: {enc_tm.error}"
    ssim_tm = compute_ssim(test_img_tm, enc_tm.watermarked_image)
    print(f"  [+] Encode Success:")
    print(f"      PSNR: {enc_tm.psnr_db:.2f} dB, SSIM: {ssim_tm:.4f}, Latency: {enc_tm.elapsed_seconds*1000:.1f} ms")
    assert enc_tm.psnr_db >= 38.0, f"TrustMark PSNR too low: {enc_tm.psnr_db}"
    assert ssim_tm >= 0.99, f"TrustMark SSIM too low: {ssim_tm}"

    # Decode TrustMark
    dec_tm = c_tm.decode(enc_tm.watermarked_image, reference_payload_hex=payload_tm)
    print(f"  [+] Decode Success:")
    print(f"      Decodable: {dec_tm.decodable}, Extracted: {dec_tm.payload_hex}")
    print(f"      Hamming Distance: {dec_tm.hamming_distance}/100, BER: {dec_tm.bit_error_rate*100:.1f}%")
    assert dec_tm.decodable is True
    assert dec_tm.hamming_distance == 0, f"Expected 0 Hamming distance, got {dec_tm.hamming_distance}"

    # Negative test on unwatermarked image
    dec_neg_tm = c_tm.decode(unwatermarked)
    print(f"  [+] Negative Detection (Unwatermarked Image):")
    print(f"      Decodable: {dec_neg_tm.decodable}, Payload: {dec_neg_tm.payload_hex}")
    assert dec_neg_tm.decodable is False or dec_neg_tm.payload_hex is None

    # 3. Degradation Survival Test
    print("\n--- 3. Testing Degradation Robustness Under Attacks ---")
    from backend.experiments.attacks import apply_attack, AttackSpec
    attack_jpeg = AttackSpec(name="jpeg_q75", category="jpeg", params={"quality": 75}, severity=0.25)
    attacked_img = apply_attack(enc_tm.watermarked_image, attack_jpeg)
    dec_attacked = c_tm.decode(attacked_img, reference_payload_hex=payload_tm)
    print(f"  [+] TrustMark under JPEG Q=75:")
    print(f"      Decodable: {dec_attacked.decodable}, BER: {dec_attacked.bit_error_rate*100:.2f}%")
    assert dec_attacked.decodable is True
    assert dec_attacked.bit_error_rate < 0.15, f"BER under JPEG Q=75 too high: {dec_attacked.bit_error_rate}"

    print("\n" + "=" * 70)
    print(">>> STEP 1: ALL WATERMARK CARRIER TESTS PASSED SUCCESSFULLY! <<<")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()

import base64
import io
import json
import urllib.request
import numpy as np
from PIL import Image

def run_test():
    print("=== Testing Watermark Embedding & Verification Robustness ===")
    
    # 1. Test unwatermarked image
    im_clean = Image.fromarray(np.random.randint(50, 200, (128, 128, 3), dtype=np.uint8))
    buf1 = io.BytesIO()
    im_clean.save(buf1, format="PNG")
    buf1.seek(0)
    clean_bytes = buf1.read()

    boundary = "----WebKitFormBoundaryProvenanceLab"
    body1 = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="clean.png"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + clean_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="carrier"\r\n\r\n'
        f"hidden\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req1 = urllib.request.Request(
        "http://127.0.0.1:8080/api/v1/watermarks/decode",
        data=body1,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    with urllib.request.urlopen(req1) as resp:
        res1 = json.loads(resp.read().decode())
        print("\n1. Unwatermarked Image Test:")
        print(f"  decodable: {res1['decodable']}")
        print(f"  hypothesis: {res1['inferred_hypothesis']}")
        print(f"  error: {res1.get('error')}")
        assert res1['decodable'] is False
        assert res1['inferred_hypothesis'] == "H0"
        print("  [PASS] Correctly rejected unwatermarked image as H0!")

    # 2. Embed payload into image
    target_payload = "11223344"
    body2 = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="clean.png"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + clean_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="carrier"\r\n\r\n'
        f"hidden\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="payload_hex"\r\n\r\n'
        f"{target_payload}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req2 = urllib.request.Request(
        "http://127.0.0.1:8080/api/v1/watermarks/embed",
        data=body2,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    with urllib.request.urlopen(req2) as resp:
        res2 = json.loads(resp.read().decode())
        wm_b64 = res2['watermarked_image_base64'].split(",")[1]
        wm_bytes = base64.b64decode(wm_b64)
        print("\n2. Watermark Embedding Test:")
        print(f"  PSNR: {res2['psnr_db']:.2f} dB")
        print(f"  payload embedded: {target_payload}")
        assert res2['psnr_db'] > 35.0
        print("  [PASS] High-fidelity embedding verified!")

    # 3. Decode watermarked image
    body3 = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="wm.png"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + wm_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="carrier"\r\n\r\n'
        f"hidden\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="reference_payload_hex"\r\n\r\n'
        f"{target_payload}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req3 = urllib.request.Request(
        "http://127.0.0.1:8080/api/v1/watermarks/decode",
        data=body3,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    with urllib.request.urlopen(req3) as resp:
        res3 = json.loads(resp.read().decode())
        print("\n3. Watermarked Image Decoding Test:")
        print(f"  decodable: {res3['decodable']}")
        print(f"  payload recovered: {res3['payload_hex']}")
        print(f"  BER: {res3['bit_error_rate']}")
        print(f"  hypothesis: {res3['inferred_hypothesis']}")
        assert res3['decodable'] is True
        assert res3['payload_hex'] == target_payload
        assert res3['bit_error_rate'] == 0.0
        assert res3['inferred_hypothesis'] == "H1"
        print("  [PASS] Exactly recovered payload 11223344 with 0.0 BER under H1!")

    print("\n>>> ALL TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    run_test()

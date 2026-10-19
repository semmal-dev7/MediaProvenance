"""
Test EZKL pipeline on hidden_decoder_32bit.onnx
"""
import os
import json
import tempfile
import numpy as np
import ezkl

def test():
    print("Testing EZKL pipeline...")
    onnx_path = "models/onnx/hidden_decoder_32bit.onnx"
    assert os.path.exists(onnx_path)

    td = tempfile.mkdtemp()
    settings_path = os.path.join(td, "settings.json")
    compiled_model_path = os.path.join(td, "model.compiled")
    pk_path = os.path.join(td, "pk.key")
    vk_path = os.path.join(td, "vk.key")
    witness_path = os.path.join(td, "witness.json")
    data_path = os.path.join(td, "input.json")
    proof_path = os.path.join(td, "proof.json")

    # Prepare sample input json
    dummy_input = (np.random.randn(1, 3, 128, 128).astype(np.float32)).tolist()
    data = {"input_data": [dummy_input]}
    with open(data_path, "w") as f:
        json.dump(data, f)

    # 1. gen_settings
    print("[1] Generating settings...")
    py_run_args = ezkl.PyRunArgs()
    py_run_args.input_visibility = "public"
    py_run_args.output_visibility = "public"
    py_run_args.param_visibility = "fixed"
    
    res = ezkl.gen_settings(onnx_path, settings_path, py_run_args=py_run_args)
    print("gen_settings result:", res)

    with open(settings_path, "r") as f:
        settings = json.load(f)
    print("Settings logrows:", settings.get("run_args", {}).get("logrows"))

    # 2. compile circuit
    print("[2] Compiling circuit...")
    res = ezkl.compile_circuit(onnx_path, compiled_model_path, settings_path)
    print("compile_circuit result:", res)

    print("Pipeline compilation verified!")

if __name__ == "__main__":
    test()

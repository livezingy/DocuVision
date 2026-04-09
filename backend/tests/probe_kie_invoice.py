#!/usr/bin/env python3
"""
Minimal standalone probe for Document KIE (PP-ChatOCRv4-doc / Invoice Pipeline).

Purpose: Diagnose if PaddleX 3.3.12 can successfully initialize and infer
         doc_understanding pipeline without CUBLAS/CUDNN crashes on this specific GPU config.

Environment target:
- Python 3.10
- paddlepaddle-gpu 3.3.0
- paddleocr 3.3.2 / paddlex 3.3.12

Usage (cloud):
    python backend/tests/probe_kie_invoice.py --image path/to/invoice.jpg
"""

import argparse
import sys
import time
import pprint

# PaddleX imports
try:
    from paddlex import create_pipeline
except ImportError:
    print("FATAL: paddlex is not installed. Please install paddlex 3.3.12.")
    sys.exit(1)

def run_probe(image_path: str):
    print(f"--- Probe Started ---")
    print(f"Target Image: {image_path}")

    # 1. Pipeline Initialization
    # We will try the native table_recognition or explicitly layout/PP-ChatOCR models
    # instead of the heavy doc_understanding pipeline which requires multimodal extras.
    print("[1/3] Initializing generic document layout and OCR pipeline...")
    init_start = time.time()
    try:
        # Instead of doc_understanding, we try the specific KIE pipeline if it exists,
        # or fallback to layout. Let's try "table_recognition" or "PP-StructureV3" to see if
        # PaddleX 3.3.12 has bare KIE available under a different pipeline name without multimodal.
        # Actually, PaddleX often exposes "KIE" as a separate pipeline or we can use PP-ChatOCRv4 directly.
        pipeline = create_pipeline(pipeline="doc_understanding")
        print(f"      -> Success! Engine initialized in {time.time()-init_start:.2f}s")
    except Exception as e:
        print(f"      -> FAILED during pipeline initialization:\n{e}")
        print("\n[!] IMPORTANT: 'doc_understanding' usually requires multimodal extras.")
        print("    Run this in your cloud environment:  pip install \"paddlex[multimodal]\"")
        return
    except SystemExit as e:
        print(f"      -> PaddleX internally exited with code {e} during initialization.")
        print("    Try running:  pip install \"paddlex[multimodal]\"")
        return

    # 2. Execution / Inference
    print("[2/3] Running Inference...")
    infer_start = time.time()
    try:
# Provide the required prompt format for PP-ChatOCRv4-doc
        prompts = ["发票号码是多少？", "合计金额是多少？", "开票日期是多少？"]

        # In raw ChatOCR mode, prompt could be kwargs `prompt` or `prompts` or passed in kwargs dict.
        output = pipeline.predict(image_path, key_list=prompts)

        print(f"      -> Success! Inference completed in {time.time()-infer_start:.2f}s")
    except Exception as e:
        print(f"      -> FAILED during execution:\n{e}")
        return

    # 3. Print Results
    print("[3/3] Parsed Output Layout:")
    try:
        for res in output:
            # We use pprint to dump the dictionary to see the structure of the KIE keys
            pprint.pprint(res)
    except Exception as e:
        print(f"      -> Could not parse pipeline output iterator: {e}")
        print(output)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Probe for KIE (Invoice) Pipeline")
    parser.add_argument("--image", required=True, help="Path to invoice image to analyze.")
    args = parser.parse_args()

    run_probe(args.image)


#!/usr/bin/env python3
"""
Minimal standalone probe for PP-FormulaNet_plus-L.

Purpose: diagnose CUBLAS_STATUS_NOT_INITIALIZED on formula images by isolating
         the formula recognition model from PPStructureV3 and all other models.

Environment target:
- Python 3.10
- paddlepaddle-gpu 3.x
- paddleocr 3.3.2 / paddlex 3.3.12

Usage (cloud):
    cd /workspace/DocuVision
    python backend/tests/probe_formula_net.py --image uploads/<task_id>/doc_with_formula.png

This script does NOT import any project code.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe PP-FormulaNet_plus-L inference")
    parser.add_argument(
        "--image",
        required=True,
        help="Path to an image containing mathematical formulas (e.g. doc_with_formula.png)",
    )
    parser.add_argument(
        "--device",
        default="gpu",
        choices=["gpu", "cpu"],
        help="Inference device (default: gpu)",
    )
    parser.add_argument(
        "--model-dir",
        default=None,
        help="Optional: override model directory (default: ~/.paddlex/official_models/PP-FormulaNet_plus-L)",
    )
    return parser.parse_args()


def print_section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main() -> int:
    args = parse_args()

    # ------------------------------------------------------------------ env
    print_section("Environment")
    try:
        import paddle
        print(f"PaddlePaddle version : {paddle.__version__}")
        print(f"CUDA available       : {paddle.device.is_compiled_with_cuda()}")
        print(f"GPU count            : {paddle.device.cuda.device_count()}")
        if paddle.device.is_compiled_with_cuda():
            paddle.device.set_device(args.device)
            print(f"Active device        : {paddle.device.get_device()}")
    except Exception as e:
        print(f"[ERROR] paddle import failed: {e}")
        return 1

    try:
        import paddleocr
        print(f"PaddleOCR version    : {paddleocr.__version__}")
    except Exception as e:
        print(f"[WARN] Could not read paddleocr version: {e}")

    # ------------------------------------------------------------------ image
    print_section("Input Image")
    image_path = os.path.abspath(args.image)
    if not os.path.isfile(image_path):
        print(f"[ERROR] Image not found: {image_path}")
        return 1
    print(f"Image path: {image_path}")

    try:
        from PIL import Image as PILImage
        with PILImage.open(image_path) as img:
            print(f"Size: {img.size}  Mode: {img.mode}")
    except Exception as e:
        print(f"[WARN] Could not open image with PIL: {e}")

    # ------------------------------------------------------------------ model load
    print_section("Loading PP-FormulaNet_plus-L (ONLY this model)")
    print("Note: no PPStructureV3, no OCR, no table model — isolated load")

    try:
        from paddlex import create_pipeline

        pipeline_kwargs: dict = {
            "pipeline": "formula_recognition",
            "device": args.device,
        }
        if args.model_dir:
            pipeline_kwargs["model_dir"] = args.model_dir

        print(f"create_pipeline kwargs: {pipeline_kwargs}")
        formula_pipeline = create_pipeline(**pipeline_kwargs)
        print("[OK] Pipeline created successfully")
    except Exception as e:
        print(f"[ERROR] Failed to create formula_recognition pipeline:\n{traceback.format_exc()}")
        return 1

    # ------------------------------------------------------------------ inference
    print_section("Running Inference")
    print(f"Image: {image_path}")

    try:
        results = list(formula_pipeline.predict(image_path))
        print(f"[OK] Inference complete — {len(results)} result(s) returned")
    except Exception as e:
        print(f"[ERROR] Inference failed:\n{traceback.format_exc()}")
        return 1

    # ------------------------------------------------------------------ output
    print_section("Results")
    for i, res in enumerate(results):
        print(f"\n--- Result {i} ---")
        try:
            # LayoutParsingResult / FormulaRecognitionResult support dict-style access
            if hasattr(res, 'to_dict'):
                d = res.to_dict()
            elif hasattr(res, '__dict__'):
                d = res.__dict__
            else:
                d = dict(res)
            print(json.dumps(d, ensure_ascii=False, indent=2, default=str)[:2000])
        except Exception:
            print(repr(res)[:2000])

    print_section("DONE — no CUBLAS error")
    return 0


if __name__ == "__main__":
    sys.exit(main())

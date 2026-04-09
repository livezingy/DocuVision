#!/usr/bin/env python3
"""
Minimal standalone probe for formula recognition.

Purpose:
- Diagnose CUBLAS_STATUS_NOT_INITIALIZED and related GPU runtime failures.
- Distinguish model-level failure from pipeline-level failure.

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
import collections
import json
import os
import re
import subprocess
import sys
import time
import traceback


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe formula recognition inference")
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
        "--mode",
        default="model",
        choices=["model", "pipeline", "both"],
        help="Run mode. 'model' is true isolated formula model (recommended).",
    )
    parser.add_argument(
        "--model-name",
        default="PP-FormulaNet_plus-M",
        choices=[
            "PP-FormulaNet_plus-S",
            "PP-FormulaNet_plus-M",
            "PP-FormulaNet_plus-L",
            "PP-FormulaNet-S",
            "PP-FormulaNet-L",
        ],
        help="Formula model name for model mode (default: PP-FormulaNet_plus-M)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Predict batch size for model mode (default: 1)",
    )
    parser.add_argument(
        "--disable-layout",
        action="store_true",
        help="Pipeline mode: disable layout detection and run formula model on full image.",
    )
    parser.add_argument(
        "--disable-preprocess",
        action="store_true",
        help="Pipeline mode: disable doc orientation + unwarping at predict time.",
    )
    parser.add_argument(
        "--pipeline-formula-batch-size",
        type=int,
        default=1,
        help="Pipeline mode: override internal formula_recognition_model batch size (default: 1).",
    )
    parser.add_argument(
        "--print-layout-stats",
        action="store_true",
        help="Pipeline mode: print detected formula box count from layout_det_res.",
    )
    parser.add_argument(
        "--print-label-hist",
        action="store_true",
        help="Pipeline mode: print label histogram from layout_det_res boxes.",
    )
    parser.add_argument(
        "--layout-threshold",
        type=float,
        default=None,
        help="Pipeline mode: override layout detection confidence threshold (e.g. 0.2).",
    )
    parser.add_argument(
        "--two-stage-threshold-retry",
        action="store_true",
        help="Pipeline mode: enable two-stage retry (primary threshold -> fallback threshold).",
    )
    parser.add_argument(
        "--primary-layout-threshold",
        type=float,
        default=0.5,
        help="Primary threshold for two-stage retry (default: 0.5).",
    )
    parser.add_argument(
        "--fallback-layout-threshold",
        type=float,
        default=0.2,
        help="Fallback threshold for two-stage retry (default: 0.2).",
    )
    parser.add_argument(
        "--model-dir",
        default=None,
        help="Optional local model dir override. In model mode this should point to formula model dir.",
    )
    return parser.parse_args()


def print_section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def dump_gpu_snapshot(tag: str) -> None:
    print(f"[GPU SNAPSHOT] {tag}")
    try:
        res = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        if res.returncode == 0 and res.stdout.strip():
            print(res.stdout.strip())
        else:
            print("nvidia-smi unavailable or returned non-zero exit code")
    except Exception as e:
        print(f"nvidia-smi check failed: {e}")


def result_to_dict(res) -> dict:
    if hasattr(res, "json"):
        d = res.json
    elif hasattr(res, "to_dict"):
        d = res.to_dict()
    elif hasattr(res, "__dict__"):
        d = res.__dict__
    else:
        d = dict(res)

    # Most PaddleX result wrappers use {"res": {...}}; unwrap it for diagnostics.
    if isinstance(d, dict) and "res" in d and isinstance(d["res"], dict):
        return d["res"]
    return d


def extract_formulas(d: dict) -> list[str]:
    formulas = []
    if "rec_formula" in d:
        rf = d["rec_formula"]
        if isinstance(rf, str):
            if rf.strip():
                formulas.append(rf)
        elif isinstance(rf, (list, tuple)):
            formulas.extend([str(x) for x in rf])
    if "formula_res_list" in d and isinstance(d["formula_res_list"], list):
        for item in d["formula_res_list"]:
            if isinstance(item, dict) and "rec_formula" in item:
                rf = item["rec_formula"]
                if isinstance(rf, str):
                    if rf.strip():
                        formulas.append(rf)
                elif rf is not None:
                    formulas.append(str(rf))
    return formulas


def formula_quality_info(formula: str) -> dict:
    s = formula or ""
    tokens = re.findall(r"[A-Za-z]+|\\[A-Za-z]+|\d+|[^\s]", s)
    unique_ratio = (len(set(tokens)) / len(tokens)) if tokens else 0.0
    a_ratio = (s.count("A") / len(s)) if s else 0.0
    return {
        "char_len": len(s),
        "token_count": len(tokens),
        "unique_token_ratio": round(unique_ratio, 4),
        "char_A_ratio": round(a_ratio, 4),
        "looks_degenerate": len(s) > 300 and (unique_ratio < 0.2 or a_ratio > 0.15),
    }


def _bbox_to_polygon_xyxy(bbox):
    x1, y1, x2, y2 = bbox
    return [x1, y1, x2, y1, x2, y2, x1, y2]


def adapt_formula_results_for_backend(
    unwrapped_results,
    page_number=1,
    reading_order_start=1,
):
    """
    Convert formula pipeline unwrapped results into backend-ready structures.

    Input:
    - unwrapped_results: list[dict], each item should come from result_to_dict(res).

    Output keys:
    - view_formulas: list for view.formulas[]
    - fused_formula_blocks: list for fused.pages[].blocks (formula-type slice)
    - quality_patch: formula-related metrics patch for quality layer

    Note:
    - When layout detection is disabled, formula_recognition may return only one
      root-level rec_formula without dt_polys. In this case polygon is omitted.
    """
    view_formulas = []
    fused_formula_blocks = []
    formula_idx = 0
    recognized_count = 0

    for result_item in unwrapped_results:
        formula_items = result_item.get("formula_res_list", [])
        if not isinstance(formula_items, list):
            formula_items = []

        # Fallback path: no formula_res_list but root-level rec_formula exists.
        if not formula_items and isinstance(result_item.get("rec_formula"), str):
            formula_items = [
                {
                    "formula_region_id": 1,
                    "rec_formula": result_item.get("rec_formula", ""),
                }
            ]

        for fi in formula_items:
            rec_formula = str(fi.get("rec_formula", "")).strip()
            if not rec_formula:
                continue

            formula_idx += 1
            recognized_count += 1
            fid = f"frm_{formula_idx:04d}"
            rid = int(fi.get("formula_region_id", formula_idx))

            polygon = None
            dt_polys = fi.get("dt_polys", None)
            if isinstance(dt_polys, (list, tuple)) and len(dt_polys) == 4:
                try:
                    x1, y1, x2, y2 = [int(round(float(v))) for v in dt_polys]
                    polygon = _bbox_to_polygon_xyxy([x1, y1, x2, y2])
                except Exception:
                    polygon = None

            view_item = {
                "id": fid,
                "page_number": page_number,
                "reading_order": reading_order_start + formula_idx - 1,
                "source": "formula_recognition",
                "processing_status": "recognized",
                "payload": {
                    "latex": rec_formula,
                    "mathml": None,
                },
                "formula_region_id": rid,
            }
            if polygon is not None:
                view_item["polygon"] = polygon
            view_formulas.append(view_item)

            fused_item = {
                "block_id": fid,
                "type": "formula",
                "processing_status": "recognized",
                "source": "formula_recognition",
                "confidence": None,
                "payload": {
                    "latex": rec_formula,
                    "mathml": None,
                },
                "provenance": None,
            }
            if polygon is not None:
                xs = [polygon[i] for i in [0, 2, 4, 6]]
                ys = [polygon[i] for i in [1, 3, 5, 7]]
                fused_item["polygon_preprocessed"] = polygon
                fused_item["bbox_preprocessed"] = [min(xs), min(ys), max(xs), max(ys)]
            fused_formula_blocks.append(fused_item)

    quality_patch = {
        "formula_blocks_total": formula_idx,
        "formula_blocks_recognized": recognized_count,
    }

    return {
        "view_formulas": view_formulas,
        "fused_formula_blocks": fused_formula_blocks,
        "quality_patch": quality_patch,
    }


def run_model_mode(args: argparse.Namespace, image_path: str) -> int:
    print_section("Mode=model: isolated formula model")
    print("Expected path: create_model -> formula predictor only (no layout/preprocess)")

    from paddlex import create_model

    model_kwargs = {
        "model_name": args.model_name,
        "device": args.device,
    }
    if args.model_dir:
        model_kwargs["model_dir"] = args.model_dir

    print(f"create_model kwargs: {model_kwargs}")
    model = create_model(**model_kwargs)
    model.set_predictor(batch_size=args.batch_size)
    print(f"[OK] Model created, batch_size={args.batch_size}")

    dump_gpu_snapshot("before model.predict")
    t0 = time.perf_counter()
    results = list(model.predict(image_path))
    dt = time.perf_counter() - t0
    dump_gpu_snapshot("after model.predict")

    print(f"[OK] model.predict done in {dt:.3f}s, results={len(results)}")
    total_formula_count = 0
    first_formula = None
    for res in results:
        d = result_to_dict(res)
        formulas = extract_formulas(d)
        total_formula_count += len(formulas)
        if formulas and first_formula is None:
            first_formula = formulas[0]

    print(f"formula_count={total_formula_count}")
    print(f"first_formula={repr(first_formula) if first_formula is not None else None}")
    if first_formula is not None:
        print(f"first_formula_quality={formula_quality_info(first_formula)}")

    if len(results) > 0:
        d0 = result_to_dict(results[0])
        print("result_sample_json:")
        print(json.dumps(d0, ensure_ascii=False, indent=2, default=str)[:2000])

    return 0


def run_pipeline_mode(args: argparse.Namespace, image_path: str) -> int:
    print_section("Mode=pipeline: formula_recognition pipeline")
    print("Expected path: may include doc_preprocessor/layout depending on predict flags")

    from paddlex import create_pipeline

    pipeline_kwargs = {
        "pipeline": "formula_recognition",
        "device": args.device,
    }
    if args.model_dir:
        pipeline_kwargs["model_dir"] = args.model_dir

    print(f"create_pipeline kwargs: {pipeline_kwargs}")
    pipeline = create_pipeline(**pipeline_kwargs)
    print("[OK] Pipeline created")

    # Override internal formula predictor batch size to reduce GPU pressure.
    try:
        inner = getattr(pipeline, "_pipeline", None)
        frm_model = getattr(inner, "formula_recognition_model", None)
        if frm_model is not None and hasattr(frm_model, "set_predictor"):
            frm_model.set_predictor(batch_size=args.pipeline_formula_batch_size)
            print(
                f"[OK] Internal formula_recognition_model batch_size set to {args.pipeline_formula_batch_size}"
            )
    except Exception as e:
        print(f"[WARN] Failed to override internal formula model batch size: {e}")

    def _collect_stats(results):
        total_formula_count = 0
        first_formula = None
        total_layout_formula_boxes = 0
        label_hist = collections.Counter()
        for res in results:
            d = result_to_dict(res)
            boxes = (
                d.get("layout_det_res", {}).get("boxes", [])
                if isinstance(d.get("layout_det_res", {}), dict)
                else []
            )
            layout_formula_boxes = 0
            for b in boxes:
                label = str(b.get("label", "")).lower()
                if label:
                    label_hist[label] += 1
                if label == "formula":
                    layout_formula_boxes += 1
            total_layout_formula_boxes += layout_formula_boxes

            formulas = extract_formulas(d)
            total_formula_count += len(formulas)
            if formulas and first_formula is None:
                first_formula = formulas[0]
        return {
            "formula_count": total_formula_count,
            "layout_formula_box_count": total_layout_formula_boxes,
            "label_hist": dict(label_hist),
            "first_formula": first_formula,
        }

    def run_pipeline_once(layout_threshold=None, stage_name="single"):
        predict_kwargs = {
            "use_layout_detection": not args.disable_layout,
        }
        if layout_threshold is not None:
            predict_kwargs["layout_threshold"] = layout_threshold
        elif args.layout_threshold is not None:
            predict_kwargs["layout_threshold"] = args.layout_threshold

        if args.disable_preprocess:
            predict_kwargs["use_doc_orientation_classify"] = False
            predict_kwargs["use_doc_unwarping"] = False

        print(f"[{stage_name}] predict kwargs: {predict_kwargs}")
        dump_gpu_snapshot(f"before pipeline.predict ({stage_name})")
        t0 = time.perf_counter()
        results = list(pipeline.predict(image_path, **predict_kwargs))
        dt = time.perf_counter() - t0
        dump_gpu_snapshot(f"after pipeline.predict ({stage_name})")
        stats = _collect_stats(results)
        print(
            f"[OK] {stage_name} done in {dt:.3f}s, results={len(results)}, "
            f"formula_count={stats['formula_count']}, "
            f"layout_formula_box_count={stats['layout_formula_box_count']}"
        )
        return results, stats, dt, predict_kwargs

    def run_pipeline_with_two_stage_retry():
        # Stage 1: strict threshold (usually higher precision)
        primary_results, primary_stats, _, _ = run_pipeline_once(
            layout_threshold=args.primary_layout_threshold,
            stage_name="stage1-primary",
        )
        # Retry condition: no formula box or no formula text.
        need_retry = (
            (not args.disable_layout)
            and (
                primary_stats["layout_formula_box_count"] == 0
                or primary_stats["formula_count"] == 0
            )
        )
        if not need_retry:
            print("[two-stage] stage1 already has formula results; skip fallback")
            return primary_results, primary_stats

        print(
            "[two-stage] stage1 has no formula signal; "
            f"retry with fallback threshold={args.fallback_layout_threshold}"
        )
        fallback_results, fallback_stats, _, _ = run_pipeline_once(
            layout_threshold=args.fallback_layout_threshold,
            stage_name="stage2-fallback",
        )
        return fallback_results, fallback_stats

    if args.two_stage_threshold_retry:
        results, stats = run_pipeline_with_two_stage_retry()
    else:
        results, stats, _, _ = run_pipeline_once(stage_name="single")

    print(f"formula_count={stats['formula_count']}")
    if args.print_layout_stats:
        print(f"layout_formula_box_count={stats['layout_formula_box_count']}")
    if args.print_label_hist:
        print(f"layout_label_hist={stats['label_hist']}")
    print(
        f"first_formula={repr(stats['first_formula']) if stats['first_formula'] is not None else None}"
    )
    if stats["first_formula"] is not None:
        print(f"first_formula_quality={formula_quality_info(stats['first_formula'])}")

    if len(results) > 0:
        d0 = result_to_dict(results[0])
        print("result_sample_json:")
        print(json.dumps(d0, ensure_ascii=False, indent=2, default=str)[:2000])

    return 0


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
            if args.device == "gpu":
                dump_gpu_snapshot("startup")
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

    print_section("Probe Config")
    print(f"mode      : {args.mode}")
    print(f"device    : {args.device}")
    print(f"model     : {args.model_name}")
    print(f"batch_size: {args.batch_size}")
    print(f"image     : {image_path}")

    try:
        if args.mode in ("model", "both"):
            run_model_mode(args, image_path)
        if args.mode in ("pipeline", "both"):
            run_pipeline_mode(args, image_path)
    except Exception:
        print(f"[ERROR] Probe failed:\n{traceback.format_exc()}")
        return 1

    print_section("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())

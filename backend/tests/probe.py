#!/usr/bin/env python3
"""Offline probe for chart ROI flow without starting the web service.

Flow:
1) Use LayoutParsingPipeline to detect layout blocks (chart enabled).
2) Extract chart boxes from layout output.
3) Call ChartService.recognize(...) with chart ROI boxes.

Usage examples:
  python backend/tests/probe.py --image test_data/images/screenshots/chart_parsing_02.png --device gpu
  python backend/tests/probe.py --image /workspace/DocuVision/test.png --device cpu --dump-json /tmp/probe_chart.json
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple


# Make imports work when running directly from repo root or backend/tests.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.abspath(os.path.join(_THIS_DIR, ".."))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from app.services.chart_service import ChartService


_CHART_LABELS = {"chart", "flowchart", "figure_table_chart"}


def _to_dict(obj: Any) -> Dict[str, Any]:
    """Best-effort conversion from PaddleX/PaddleOCR result object to dict."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "json"):
        data = obj.json
        if isinstance(data, dict):
            return data
    if hasattr(obj, "to_dict"):
        data = obj.to_dict()
        if isinstance(data, dict):
            return data
    if hasattr(obj, "__dict__"):
        data = obj.__dict__
        if isinstance(data, dict):
            return data
    return {}


def _normalize_box(box: Any) -> Optional[Tuple[float, float, float, float]]:
    """Normalize box to (x1, y1, x2, y2)."""
    if isinstance(box, dict):
        if all(k in box for k in ("x1", "y1", "x2", "y2")):
            try:
                return (
                    float(box["x1"]),
                    float(box["y1"]),
                    float(box["x2"]),
                    float(box["y2"]),
                )
            except Exception:
                return None
        if all(k in box for k in ("x", "y", "width", "height")):
            try:
                x = float(box["x"])
                y = float(box["y"])
                w = float(box["width"])
                h = float(box["height"])
                return (x, y, x + w, y + h)
            except Exception:
                return None

    if isinstance(box, (list, tuple)) and len(box) == 4:
        try:
            return (float(box[0]), float(box[1]), float(box[2]), float(box[3]))
        except Exception:
            return None

    return None


def _iter_blocks_from_layout_result(layout_result: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """Yield candidate blocks from common layout output fields."""
    for key in ("elements", "parsing_res_list"):
        value = layout_result.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield item

    det_res = layout_result.get("layout_det_res")
    if isinstance(det_res, dict):
        boxes = det_res.get("boxes")
        if isinstance(boxes, list):
            for box in boxes:
                if isinstance(box, dict):
                    yield box


def _extract_chart_boxes(layout_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract chart boxes into ChartService expected format."""
    out: List[Dict[str, Any]] = []

    for block in _iter_blocks_from_layout_result(layout_result):
        label = str(
            block.get("label")
            or block.get("type")
            or block.get("category")
            or ""
        ).strip().lower()
        if label not in _CHART_LABELS:
            continue

        raw_box = (
            block.get("bbox")
            or block.get("coordinate")
            or block.get("box")
            or block.get("rect")
        )
        norm = _normalize_box(raw_box)
        if norm is None:
            continue

        x1, y1, x2, y2 = norm
        if x2 <= x1 or y2 <= y1:
            continue

        out.append(
            {
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "source_type": label,
            }
        )

    return out


def _build_layout_pipeline(device: str):
    """Build LayoutParsingPipeline using only supported constructor args."""
    from paddlex.inference.pipelines.layout_parsing.pipeline_v2 import LayoutParsingPipeline

    wanted_kwargs = {
        "use_chart_recognition": True,
        "use_formula_recognition": False,
        "use_table_recognition": True,
        "use_layout_detection": True,
        "use_doc_preprocessor": False,
        "device": device,
    }

    sig = inspect.signature(LayoutParsingPipeline.__init__)
    accepted = set(sig.parameters.keys())
    accepted.discard("self")

    kwargs = {k: v for k, v in wanted_kwargs.items() if k in accepted}
    print(f"[Probe] LayoutParsingPipeline kwargs: {kwargs}")
    return LayoutParsingPipeline(**kwargs)


def _predict_layout(pipeline: Any, image_path: str) -> Dict[str, Any]:
    """Run layout prediction and return first page as dict."""
    # Try example style first.
    try:
        result = pipeline.predict(image_path, chart_only=True)
    except TypeError:
        result = pipeline.predict(image_path)

    if isinstance(result, dict):
        return result

    if isinstance(result, (list, tuple)):
        if not result:
            return {}
        return _to_dict(result[0])

    # PaddleX often returns a generator.
    try:
        first = next(iter(result))
        return _to_dict(first)
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline probe for chart ROI via ChartService")
    parser.add_argument("--image", required=True, help="Path to input image")
    parser.add_argument("--device", default="gpu", choices=["gpu", "cpu"], help="Inference device")
    parser.add_argument("--dump-json", default="", help="Optional output json path")
    args = parser.parse_args()

    image_path = os.path.abspath(args.image)
    if not os.path.isfile(image_path):
        print(f"[Probe][ERROR] Image not found: {image_path}")
        return 2

    print(f"[Probe] Image: {image_path}")
    print(f"[Probe] Device: {args.device}")

    # 1) Layout parsing for chart blocks.
    try:
        layout_pipeline = _build_layout_pipeline(args.device)
    except Exception as exc:
        print(f"[Probe][ERROR] Failed to initialize LayoutParsingPipeline: {exc}")
        return 3

    layout_result = _predict_layout(layout_pipeline, image_path)
    if not layout_result:
        print("[Probe][ERROR] Empty layout result")
        return 4

    chart_boxes = _extract_chart_boxes(layout_result)
    print(f"[Probe] Extracted chart boxes: {len(chart_boxes)}")

    # 2) ChartService ROI inference.
    service = ChartService(device=args.device)
    service_status = service.get_status()
    print(f"[Probe] ChartService status before recognize: {service_status}")

    chart_result = service.recognize(
        image_path,
        layout_chart_boxes=chart_boxes,
        roi_source_image_path=image_path,
    )

    ok = bool(chart_result.get("ok", False))
    stage = chart_result.get("stage", "")
    stats = chart_result.get("stats", {})
    print(f"[Probe] recognize ok={ok} stage={stage} stats={stats}")

    if not ok:
        print(f"[Probe][WARN] error={chart_result.get('error', '')}")
        print(f"[Probe][WARN] error_code={chart_result.get('error_code', '')}")

    if args.dump_json:
        dump_path = os.path.abspath(args.dump_json)
        payload = {
            "image": image_path,
            "device": args.device,
            "chart_boxes": chart_boxes,
            "service_status_before": service_status,
            "chart_result": chart_result,
        }
        with open(dump_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"[Probe] Dumped json to: {dump_path}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

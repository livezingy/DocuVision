"""Pure adapters from formula pipeline results to backend view/fused blocks.

Split from the former formula_service.py monolith (S1 batch 7); zero heavy
imports — dict shaping only. `adapt_formula_results_for_backend` is
re-exported by the formula_service facade (orchestration/steps/envelope.py
lazy-imports it from there).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _bbox_to_polygon_xyxy(bbox: List[int]) -> List[int]:
    x1, y1, x2, y2 = bbox
    return [x1, y1, x2, y1, x2, y2, x1, y2]


def adapt_formula_results_for_backend(
    unwrapped_results: List[Dict[str, Any]],
    page_number: int = 1,
    reading_order_start: int = 1,
) -> Dict[str, Any]:
    """Convert formula pipeline unwrapped results into backend-ready structures."""
    view_formulas: List[Dict[str, Any]] = []
    fused_formula_blocks: List[Dict[str, Any]] = []
    formula_idx = 0
    recognized_count = 0

    for result_item in unwrapped_results:
        formula_items = result_item.get("formula_res_list", [])
        if not isinstance(formula_items, list):
            formula_items = []

        if not formula_items and isinstance(result_item.get("rec_formula"), str):
            formula_items = [
                {
                    "formula_region_id": 1,
                    "rec_formula": result_item.get("rec_formula", ""),
                }
            ]

        for formula_item in formula_items:
            rec_formula = str(formula_item.get("rec_formula", "")).strip()
            if not rec_formula:
                continue

            formula_idx += 1
            recognized_count += 1
            fid = f"frm_{formula_idx:04d}"
            rid = int(formula_item.get("formula_region_id", formula_idx))

            polygon: Optional[List[int]] = None
            dt_polys = formula_item.get("dt_polys", None)
            if isinstance(dt_polys, (list, tuple)) and len(dt_polys) == 4:
                try:
                    x1, y1, x2, y2 = [int(round(float(v))) for v in dt_polys]
                    polygon = _bbox_to_polygon_xyxy([x1, y1, x2, y2])
                except Exception:
                    polygon = None

            view_item: Dict[str, Any] = {
                "id": fid,
                "kind": "formula",
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
            view_item["polygon"] = polygon if polygon is not None else []
            view_formulas.append(view_item)

            fused_item: Dict[str, Any] = {
                "block_id": fid,
                "type": "formula",
                "processing_status": "recognized",
                "source": "formula_recognition",
                "confidence": 1.0,
                "payload": {
                    "latex": rec_formula,
                    "mathml": None,
                },
                "provenance": {
                    "primary_source": "formula_recognition",
                    "primary_text": rec_formula,
                    "merge_strategy": "recognized_by_optional_engine",
                    "merged_at": None,
                    "status": "recognized",
                    "block_type": "formula",
                    "formula_region_id": rid,
                },
            }
            if polygon is not None:
                xs = [polygon[i] for i in [0, 2, 4, 6]]
                ys = [polygon[i] for i in [1, 3, 5, 7]]
                fused_item["polygon_preprocessed"] = polygon
                fused_item["bbox_preprocessed"] = [min(xs), min(ys), max(xs), max(ys)]
            else:
                fused_item["polygon_preprocessed"] = []
                fused_item["bbox_preprocessed"] = []
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

"""Envelope builder helpers — pure functions split from envelope_builder.py (runs/split batch 3).

Moved verbatim (tier A) except: methods became module functions (self dropped,
tier B) and the import header is new. No class state involved.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger  # _apply_inverse_rotation warns when cv2 is unavailable


def _as_confidence(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Coerce layout block confidence; None/missing/invalid → default (None = 未测量 ≠ 0)."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_block_provenance(
    *,
    elem_type: str,
    processing_status: str,
    source: str,
    text_value: str,
) -> Dict[str, Any]:
    """Build normalized provenance for all fused blocks.

    Phase 2 provenance objective: keep a minimal but complete audit trail for each
    block, even when no cross-engine merge occurs.
    """
    merge_strategy = "keep_structure"
    if processing_status == "no_ocr":
        merge_strategy = "no_ocr"
    elif processing_status == "no_ocr_empty":
        merge_strategy = "no_ocr_empty"
    elif processing_status == "skip_table":
        merge_strategy = "table_structure_only"
    elif processing_status == "skip_formula":
        merge_strategy = "formula_placeholder"
    elif processing_status == "skip_seal":
        merge_strategy = "seal_placeholder"
    elif processing_status == "extracted":
        merge_strategy = "region_only"
    elif processing_status == "passthrough_unknown_type":
        merge_strategy = "passthrough_unknown_type"
    elif processing_status == "recognized":
        merge_strategy = "recognized_by_optional_engine"

    return {
        "primary_source": source,
        "primary_text": text_value or "",
        "merge_strategy": merge_strategy,
        "merged_at": None,
        "status": processing_status,
        "block_type": elem_type,
    }


def _normalize_bbox(bbox: Any) -> List[float]:
    """Normalize bbox to [x0, y0, x1, y1] list.

    Handles both:
    - layout_service format: {"x": x0, "y": y0, "width": w, "height": h}
    - x0/y0/x1/y1 dict format
    - list/tuple [x0, y0, x1, y1]
    """
    if isinstance(bbox, dict):
        if "width" in bbox or "height" in bbox:
            x0 = float(bbox.get("x", 0))
            y0 = float(bbox.get("y", 0))
            return [x0, y0, x0 + float(bbox.get("width", 0)), y0 + float(bbox.get("height", 0))]
        return [
            float(bbox.get("x0", bbox.get("x", 0))),
            float(bbox.get("y0", bbox.get("y", 0))),
            float(bbox.get("x1", 0)),
            float(bbox.get("y1", 0)),
        ]
    elif isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        return [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
    return [0.0, 0.0, 0.0, 0.0]


def _apply_inverse_rotation(
    polygon_flat: List[float],
    angle_deg: float,
    input_size: Dict[str, int],
    output_size: Dict[str, int],
) -> List[float]:
    """Convert polygon from preprocessed (output_img) space to original (input_img) space.

    Uses cv2 affine inverse of the forward rotation transform to correctly
    account for both rotation and padding offset.
    """
    if angle_deg == 0.0 or not polygon_flat:
        return polygon_flat

    if cv2 is None:
        logger.warning("OpenCV (cv2) unavailable; skipping inverse-rotation transform")
        return polygon_flat

    w_in = float(input_size.get("width", 0))
    h_in = float(input_size.get("height", 0))
    w_out = float(output_size.get("width", 0))
    h_out = float(output_size.get("height", 0))

    if w_out <= 0 or h_out <= 0 or w_in <= 0 or h_in <= 0:
        return polygon_flat

    # Reconstruct forward affine (input → preprocessed):
    # PaddleX DocPreprocessor rotates around input-image center to correct orientation,
    # then centers the result in the output canvas.
    cx_in, cy_in = w_in / 2.0, h_in / 2.0
    M_fwd = cv2.getRotationMatrix2D((cx_in, cy_in), float(angle_deg), 1.0)
    # Account for padding: the rotated content is centered in output canvas
    M_fwd[0, 2] += (w_out - w_in) / 2.0
    M_fwd[1, 2] += (h_out - h_in) / 2.0

    M_inv = cv2.invertAffineTransform(M_fwd)

    result: List[float] = []
    for i in range(0, len(polygon_flat) - 1, 2):
        x = float(polygon_flat[i])
        y = float(polygon_flat[i + 1])
        x_new = M_inv[0, 0] * x + M_inv[0, 1] * y + M_inv[0, 2]
        y_new = M_inv[1, 0] * x + M_inv[1, 1] * y + M_inv[1, 2]
        result.extend([x_new, y_new])

    return result


def _map_block_type_to_kind(block_type: str) -> str:
    """Map PP-StructureV3 / layout type to view layer kind."""
    t = block_type.lower()
    if t in {"doc_title", "title", "subtitle"}:
        return "title"
    elif t in {"paragraph_title", "abstract_title", "reference_title", "content_title", "section_header"}:
        return "paragraph_title"
    elif t in {"figure_table_chart_title", "caption", "figure_caption", "table_caption"}:
        return "figure_title"
    elif t in {
        "text", "abstract", "content", "reference", "reference_content",
        "algorithm", "aside_text", "author", "date", "references",
        "list", "list_item",
    }:
        return "paragraph"
    elif t in {"header", "header_image", "page_header"}:
        return "header"
    elif t in {"footer", "footer_image", "footnote", "page_footer"}:
        return "footer"
    elif t == "number":
        return "number"
    elif t in {"table"}:
        return "table"
    elif t in {
        "figure", "image", "chart", "picture",
        "figure_table_chart", "flowchart",
    }:
        return "figure"
    elif t in {"formula", "inline_formula", "equation", "formula_body", "display_formula", "formula_number"}:
        return "formula"
    elif t in {"seal", "stamp"}:
        return "seal"
    else:
        return t if t else "paragraph"

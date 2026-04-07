"""
Debug overlay utilities for DocuVision.

These helpers render bounding-box overlays on source images at each pipeline
stage and are only active when settings.ENABLE_DEBUG_OVERLAYS is True.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


def _resolve_debug_overlay_dir() -> str:
    """Resolve output path for debug overlay images."""
    override = os.environ.get("DOCUVISION_DEBUG_OVERLAY_DIR", "").strip()
    if override:
        return override

    # Fall back to project-relative path: <project_root>/outputs/debug_overlays
    # __file__ is: backend/app/core/debug_utils.py  →  go up 3 levels
    backend_dir = Path(__file__).resolve().parent.parent.parent
    project_root = backend_dir.parent
    return str(project_root / "outputs" / "debug_overlays")


def _normalize_bbox_like(raw_bbox: Any) -> Optional[Dict[str, float]]:
    """Normalize various bbox formats into {x, y, width, height}."""
    if raw_bbox is None:
        return None

    if isinstance(raw_bbox, dict):
        if all(k in raw_bbox for k in ("x", "y", "width", "height")):
            try:
                return {
                    "x": float(raw_bbox.get("x", 0.0)),
                    "y": float(raw_bbox.get("y", 0.0)),
                    "width": float(raw_bbox.get("width", 0.0)),
                    "height": float(raw_bbox.get("height", 0.0)),
                }
            except Exception:
                return None
        if all(k in raw_bbox for k in ("x1", "y1", "x2", "y2")):
            try:
                x1 = float(raw_bbox.get("x1", 0.0))
                y1 = float(raw_bbox.get("y1", 0.0))
                x2 = float(raw_bbox.get("x2", x1))
                y2 = float(raw_bbox.get("y2", y1))
                return {
                    "x": x1,
                    "y": y1,
                    "width": max(0.0, x2 - x1),
                    "height": max(0.0, y2 - y1),
                }
            except Exception:
                return None

    if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) >= 4:
        try:
            x1 = float(raw_bbox[0])
            y1 = float(raw_bbox[1])
            x2 = float(raw_bbox[2])
            y2 = float(raw_bbox[3])
            return {
                "x": x1,
                "y": y1,
                "width": max(0.0, x2 - x1),
                "height": max(0.0, y2 - y1),
            }
        except Exception:
            return None

    return None


def save_debug_overlay_image(
    file_path: str,
    task_id: str,
    stage: str,
    elements: List[Dict[str, Any]],
    page_num: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    Render and save a debug overlay image for a specific processing stage.

    Coordinates are treated as image_abs_px for the current pipeline.
    Only called when settings.ENABLE_DEBUG_OVERLAYS is True.
    """
    if not file_path or not os.path.exists(file_path):
        return None

    try:
        from PIL import Image as PILImage, ImageDraw
        import fitz  # PyMuPDF
    except Exception as e:
        logger.warning(f"[DebugOverlay] Dependencies unavailable: {e}")
        return None

    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            doc = fitz.open(file_path)
            try:
                if page_num < 1 or page_num > len(doc):
                    return None
                page = doc[page_num - 1]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                if pix.alpha:
                    image = PILImage.frombytes("RGBA", [pix.width, pix.height], pix.samples).convert("RGB")
                else:
                    image = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
            finally:
                doc.close()
        else:
            image = PILImage.open(file_path).convert("RGB")

        draw = ImageDraw.Draw(image)
        width_px = int(image.width)
        height_px = int(image.height)
        total = 0
        valid = 0
        out_of_bounds = 0

        for el in (elements or []):
            if not isinstance(el, dict):
                continue
            total += 1
            bbox = _normalize_bbox_like(el.get("bbox") or el.get("bounding_box"))
            if not bbox:
                continue

            x = float(bbox.get("x", 0.0))
            y = float(bbox.get("y", 0.0))
            w = float(bbox.get("width", 0.0))
            h = float(bbox.get("height", 0.0))
            if w <= 0 or h <= 0:
                continue

            x1, y1 = x, y
            x2, y2 = x + w, y + h
            if x2 < 0 or y2 < 0 or x1 > width_px or y1 > height_px:
                out_of_bounds += 1

            draw.rectangle([x1, y1, x2, y2], outline=(255, 64, 64), width=2)
            label = str(el.get("type") or el.get("element_type") or "block")
            draw.text((x1 + 2, max(0.0, y1 - 12)), label, fill=(255, 64, 64))
            valid += 1

        output_dir = _resolve_debug_overlay_dir()
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{task_id}_{stage}_p{int(page_num)}.png"
        out_path = os.path.join(output_dir, filename)
        image.save(out_path, format="PNG")

        return {
            "stage": stage,
            "path": out_path,
            "page": int(page_num),
            "width_px": width_px,
            "height_px": height_px,
            "total_elements": total,
            "drawn_elements": valid,
            "out_of_bounds_elements": out_of_bounds,
            "coord_space": "image_abs_px",
        }
    except Exception as e:
        logger.warning(f"[DebugOverlay] Failed to save overlay ({stage}) for task {task_id}: {e}")
        return None

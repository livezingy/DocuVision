"""F1 split (P-027 D8 wiring prerequisite): layout geometry / text pure helpers.

Mechanical extraction out of ``layout_service.py`` - same shape as the P-028 table splits and
the ``table_ocr_blocks.py`` move: the six helpers below are byte-identical to their previous
definitions, moved under :class:`_LayoutGeometryMixin` and reached through
``PPStructureEngine``'s MRO, so every call site and the three tests that load
``layout_service.py`` by file path keep working unchanged.

They are pure: no ``self.*`` state, dependencies limited to stdlib ``re``, ``loguru`` and a
locally imported numpy. The move frees lines inside a file pinned at 1804 so the D8 field
pass-through can land without touching the ratchet.

Deliberately NOT moved: ``_parse_result`` (a test calls it via ``PPStructureEngine.__new__``
and it is the D8 insertion point), ``_call_engine`` (test-called, carries the PaddleOCR #17446
no-kwargs contract), ``_deduplicate_elements`` (a 110-line main-flow dependency with a wider
blast radius) and the visualisation cluster.
"""

import re
from typing import Any, Dict, List, Optional

from loguru import logger


class _LayoutGeometryMixin:
    """Bbox normalisation/containment and short-text helpers for the layout engine."""

    @staticmethod
    def _normalize_bbox_coords(bbox) -> Optional[List[float]]:
        """Flatten bbox/coordinate payloads to [x1, y1, x2, y2] when possible."""
        if bbox is None:
            return None
        try:
            import numpy as np

            if isinstance(bbox, np.ndarray):
                flat = bbox.astype(float).reshape(-1).tolist()
            elif isinstance(bbox, (list, tuple)):
                if len(bbox) == 4 and all(isinstance(v, (int, float)) for v in bbox):
                    flat = [float(v) for v in bbox]
                elif len(bbox) == 1 and isinstance(bbox[0], (list, tuple)):
                    flat = [float(v) for v in bbox[0][:4]]
                elif len(bbox) >= 4 and isinstance(bbox[0], (list, tuple)):
                    flat = [float(v) for v in bbox[0][:4]]
                else:
                    flat = [float(v) for v in bbox[:4]]
            else:
                return None
        except Exception:
            return None

        if len(flat) < 4:
            return None
        return flat[:4]

    def _infer_page_bbox(self, first_item: Any) -> Dict[str, float]:
        """Infer full-page bbox from result payload for html-only outputs."""
        width = 0.0
        height = 0.0

        img_obj = None
        if hasattr(first_item, 'img'):
            img_obj = getattr(first_item, 'img', None)
        elif isinstance(first_item, dict):
            img_obj = first_item.get('img')

        if img_obj is not None:
            try:
                # numpy-like image array
                if hasattr(img_obj, 'shape') and len(img_obj.shape) >= 2:
                    height = float(img_obj.shape[0])
                    width = float(img_obj.shape[1])
                # PIL-like image
                elif hasattr(img_obj, 'size') and isinstance(img_obj.size, tuple) and len(img_obj.size) >= 2:
                    width = float(img_obj.size[0])
                    height = float(img_obj.size[1])
            except Exception:
                pass

        if width <= 0 or height <= 0:
            # Keep non-zero fallback to ensure front-end can render visible annotation box.
            width = 1000.0
            height = 1400.0

        return {"x": 0.0, "y": 0.0, "width": width, "height": height}

    def _extract_table_summary_text(self, table_html: str) -> str:
        """Extract a short readable summary from table HTML for UI tooltip display."""
        if not table_html:
            return "Table detected"
        try:
            import re
            text = re.sub(r"<[^>]+>", " ", table_html)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:220] if text else "Table detected"
        except Exception:
            return "Table detected"

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text to ensure proper spacing between words.
        This fixes issues where OCR returns text without spaces between words.
        """
        if not text:
            return text

        import re

        # First, normalize whitespace: replace multiple spaces/newlines with single space
        # but preserve intentional line breaks (double newlines)
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Preserve paragraph breaks
        text = re.sub(r'[ \t]*\n[ \t]*', ' ', text)  # Single newlines to space

        # Pattern to detect word boundaries:
        # - Lowercase followed by uppercase (e.g., "FuelSaving" -> "Fuel Saving")
        # - Letter followed by number or vice versa
        # - But preserve existing spaces and punctuation

        # Add space between lowercase letter and uppercase letter (word boundary)
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

        # Add space between letter and number (if not already spaced)
        text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)
        text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)

        # Clean up multiple spaces (but preserve paragraph breaks)
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n\n+', '\n\n', text)  # Multiple paragraph breaks to double newline

        # Trim whitespace
        text = text.strip()

        return text

    def _extract_bbox(self, bbox: List) -> Dict[str, float]:
        if len(bbox) == 4:
            return {
                "x": float(bbox[0]),
                "y": float(bbox[1]),
                "width": float(bbox[2] - bbox[0]),
                "height": float(bbox[3] - bbox[1])
            }
        return {"x": 0, "y": 0, "width": 0, "height": 0}

    def _bbox_contains(self, parent_bbox: Dict[str, float], child_bbox: Dict[str, float], threshold: float = 0.9) -> bool:
        """
        Check if parent_bbox contains child_bbox.

        Args:
            parent_bbox: Parent bounding box with x, y, width, height
            child_bbox: Child bounding box with x, y, width, height
            threshold: Minimum overlap ratio to consider as contained (default 0.9)

        Returns:
            True if parent contains child (with threshold overlap)
        """
        # Calculate parent bounds
        parent_x1 = parent_bbox['x']
        parent_y1 = parent_bbox['y']
        parent_x2 = parent_x1 + parent_bbox['width']
        parent_y2 = parent_y1 + parent_bbox['height']

        # Calculate child bounds
        child_x1 = child_bbox['x']
        child_y1 = child_bbox['y']
        child_x2 = child_x1 + child_bbox['width']
        child_y2 = child_y1 + child_bbox['height']

        # Check if child is within parent bounds (with tolerance)
        # Use percentage-based tolerance (5% of parent dimensions)
        tolerance_x = max(parent_bbox['width'] * 0.05, 10.0)  # At least 10 pixels
        tolerance_y = max(parent_bbox['height'] * 0.05, 10.0)  # At least 10 pixels

        if (child_x1 >= parent_x1 - tolerance_x and
            child_y1 >= parent_y1 - tolerance_y and
            child_x2 <= parent_x2 + tolerance_x and
            child_y2 <= parent_y2 + tolerance_y):

            # Calculate overlap ratio (IoU - Intersection over Union of child)
            child_area = child_bbox['width'] * child_bbox['height']
            if child_area > 0:
                # Calculate intersection
                inter_x1 = max(parent_x1, child_x1)
                inter_y1 = max(parent_y1, child_y1)
                inter_x2 = min(parent_x2, child_x2)
                inter_y2 = min(parent_y2, child_y2)

                if inter_x2 > inter_x1 and inter_y2 > inter_y1:
                    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
                    # Use intersection over child area (how much of child is covered by parent)
                    overlap_ratio = inter_area / child_area
                    if overlap_ratio >= threshold:
                        logger.debug(f"Bbox containment: parent={parent_bbox}, child={child_bbox}, overlap_ratio={overlap_ratio:.2%}")
                        return True

        return False


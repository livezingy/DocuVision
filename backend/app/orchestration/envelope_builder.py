"""Envelope builder - transforms pipeline results to Envelope structure.

This module handles:
- Preprocessing metadata extraction
- Fused layer assembly (layout blocks + per-block OCR text fusion)
- View layer construction (coordinate transformation + reading order)
- Quality metrics collection
- Debug artifacts serialization
"""

from __future__ import annotations
from app.orchestration.envelope_builder_helpers import (  # noqa: F401 (re-export)
    _apply_inverse_rotation,
    _as_confidence,
    _build_block_provenance,
    _map_block_type_to_kind,
    _normalize_bbox,
)

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from pathlib import Path
from loguru import logger

try:
    import cv2
except Exception:  # pragma: no cover - optional in lightweight local test env
    cv2 = None  # type: ignore[assignment]
import numpy as np




class EnvelopeBuilder:
    """Builds Envelope responses from orchestrator context."""

    def __init__(self, settings: Any):
        """Initialize builder with service settings."""
        self.settings = settings

    def build_preprocessing_metadata(
        self,
        layout_result: Dict[str, Any],
        use_doc_unwarping: bool,
    ) -> Dict[str, Any]:
        """Extract preprocessing metadata from layout result."""
        return {
            "input_size": layout_result.get("input_size", {}),
            "output_size": layout_result.get("output_size", {}) or {
                "width": layout_result.get("preprocessed_image_width", 0),
                "height": layout_result.get("preprocessed_image_height", 0),
            },
            "use_doc_orientation_classify": layout_result.get("use_doc_orientation_classify", False),
            "use_doc_unwarping": use_doc_unwarping,
            "angle_deg": float(layout_result.get("angle_deg", 0.0)),
            "coordinate_space": "original" if not use_doc_unwarping else "preprocessed",
        }

    def build_raw_layer(
        self,
        layout_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build raw layer with engine outputs."""
        return {
            "pp_structure_v3": layout_result or {},
        }

    # Labels eligible for per-block OCR text replacement (all PP-StructureV3 text labels)
    _OCR_TEXT_LABELS: Set[str] = {
        "doc_title", "paragraph_title", "abstract_title", "reference_title",
        "content_title", "text", "abstract", "content", "reference",
        "reference_content", "algorithm", "header", "header_image",
        "footer", "footer_image", "footnote", "figure_title",
        "aside_text", "number", "formula_number",
        # legacy / general labels
        "title", "subtitle", "figure_caption", "table_caption",
        "list", "list_item",
    }

    _VISION_BLOCK_LABELS: Set[str] = {
        "figure", "image", "chart", "figure_table_chart", "picture",
    }

    def _resolve_processing_status(
        self,
        *,
        elem_type: str,
        original_text: str,
    ) -> str:
        """Resolve processing_status with explicit fallback coverage.

        Phase 2 objective: every block gets a deterministic status that encodes
        how it was handled, including empty-text and unknown-type fallbacks.
        """
        t = (elem_type or "").lower().strip()

        if t == "table":
            return "skip_table"
        if t in {"formula", "inline_formula"}:
            return "skip_formula"
        if t in {"seal", "stamp"}:
            return "skip_seal"
        if t in self._VISION_BLOCK_LABELS:
            return "extracted"
        if t in self._OCR_TEXT_LABELS:
            return "no_ocr" if str(original_text or "").strip() else "no_ocr_empty"
        return "passthrough_unknown_type"


    def build_fused_layer(
        self,
        layout_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build fused layer from PPStructureV3 layout results."""

        # D6: extract preprocessed image dimensions for fused page metadata
        _output_size = layout_result.get("output_size", {}) or {}
        _w_prep = int(float(_output_size.get("width", layout_result.get("preprocessed_image_width", 0))))
        _h_prep = int(float(_output_size.get("height", layout_result.get("preprocessed_image_height", 0))))

        fused_pages = []
        layout_elements = layout_result.get("elements", [])

        # Group elements by page
        elements_by_page: Dict[int, List[Dict[str, Any]]] = {}
        for elem in layout_elements:
            page_num = int(elem.get("page", elem.get("page_id", 1)))
            if page_num not in elements_by_page:
                elements_by_page[page_num] = []
            elements_by_page[page_num].append(elem)

        for page_num in sorted(elements_by_page.keys()):
            fused_blocks = []
            for elem in elements_by_page[page_num]:
                elem_id = str(elem.get("id", ""))
                elem_type = elem.get("type", "unknown").lower()

                # bbox as [x0, y0, x1, y1]
                bbox_prep = _normalize_bbox(elem.get("bbox", {}))
                # polygon_preprocessed is already a flat list [x0,y0,x1,y0,x1,y1,x0,y1]
                polygon_prep = list(elem.get("polygon_preprocessed", []))

                original_text = elem.get("text", "") or ""

                fused_block: Dict[str, Any] = {
                    "block_id": elem_id or f"p{page_num}_b{len(fused_blocks)}",
                    "type": elem_type,
                    "bbox_preprocessed": bbox_prep,
                    "polygon_preprocessed": polygon_prep,
                    "processing_status": "succeeded",
                    "source": "pp_structure_v3",
                    "confidence": _as_confidence(elem.get("confidence")),
                    # F1: carry official reading order (block_order) from layout
                    # so the view layer can restore Enhanced XYCut order instead
                    # of a naive counter. None when the engine did not assign one.
                    "reading_order": elem.get("reading_order"),
                    "payload": {
                        "text": original_text,
                        "confidence": _as_confidence(elem.get("confidence")),
                    },
                    "provenance": {},
                }

                fused_block["processing_status"] = self._resolve_processing_status(
                    elem_type=elem_type,
                    original_text=original_text,
                )

                # Table blocks keep HTML payload if available.
                if elem_type == "table" and elem.get("html"):
                    fused_block["payload"]["html"] = elem["html"]

                fused_block["provenance"] = _build_block_provenance(
                    elem_type=elem_type,
                    processing_status=str(fused_block.get("processing_status", "succeeded")),
                    source=str(fused_block.get("source", "pp_structure_v3")),
                    text_value=str(fused_block.get("payload", {}).get("text", "") or ""),
                )

                fused_blocks.append(fused_block)

            fused_pages.append({
                "page_num": page_num,
                "width_preprocessed": _w_prep,
                "height_preprocessed": _h_prep,
                "blocks": fused_blocks,
            })

        return {"pages": fused_pages}

    def build_view_layer(
        self,
        fused_layer: Dict[str, Any],
        preprocessing_metadata: Dict[str, Any],
        original_image_path: Optional[str] = None,
        preprocessed_image_path: Optional[str] = None,
        kie_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build view layer: transform coordinates and construct reading-ordered elements.

        If USE_DOC_UNWARPING=false:
            - Apply inverse rotation matrix to restore coordinates to original image space
            - coordinate_space = "original"
        Else:
            - Use preprocessed coordinates directly
            - coordinate_space = "preprocessed"
        """
        coordinate_space = preprocessing_metadata.get("coordinate_space", "original")
        angle_deg = preprocessing_metadata.get("angle_deg", 0.0)
        use_doc_unwarping = preprocessing_metadata.get("use_doc_unwarping", False)

        input_size = preprocessing_metadata.get("input_size", {})
        output_size = preprocessing_metadata.get("output_size", {})

        view_pages = []
        aggregated_elements: Dict[str, List] = {
            "paragraphs": [],
            "tables": [],
            "figures": [],
            "formulas": [],
            "seals": [],
        }

        reading_order_counter = 0

        for page in fused_layer.get("pages", []):
            page_num = page.get("page_num", 1)
            view_elements = []

            for block in page.get("blocks", []):
                block_type = block.get("type", "text")
                polygon_prep = list(block.get("polygon_preprocessed", []))

                # Coordinate transformation: only needed when no unwarping but rotation occurred
                if not use_doc_unwarping and angle_deg != 0.0:
                    polygon_view = _apply_inverse_rotation(
                        polygon_prep,
                        angle_deg,
                        input_size,
                        output_size,
                    )
                else:
                    polygon_view = polygon_prep

                # Map block type to view kind
                kind = _map_block_type_to_kind(block_type)

                # F1: prefer official reading order (block_order) carried from
                # layout; fall back to a per-page counter when absent.
                block_reading_order = block.get("reading_order")
                if block_reading_order is not None:
                    view_reading_order = int(block_reading_order)
                else:
                    view_reading_order = reading_order_counter
                    reading_order_counter += 1

                view_element = {
                    "id": block.get("block_id"),
                    "kind": kind,
                    "polygon": polygon_view,
                    "reading_order": view_reading_order,
                    "source": block.get("source", "pp_structure_v3"),
                    "processing_status": block.get("processing_status", "succeeded"),
                    "payload": block.get("payload", {}),
                }

                view_elements.append(view_element)
                reading_order_counter += 1

                # Aggregate by kind
                if kind == "paragraph":
                    aggregated_elements["paragraphs"].append(view_element)
                elif kind == "table":
                    aggregated_elements["tables"].append(view_element)
                elif kind == "figure":
                    aggregated_elements["figures"].append(view_element)
                elif kind == "formula":
                    aggregated_elements["formulas"].append(view_element)
                elif kind == "seal":
                    aggregated_elements["seals"].append(view_element)

            # Page dimensions: use output_size when view is in preprocessed space, else input_size
            if use_doc_unwarping or angle_deg == 0.0:
                page_w = output_size.get("width", 0)
                page_h = output_size.get("height", 0)
            else:
                page_w = input_size.get("width", 0)
                page_h = input_size.get("height", 0)

            page_text_parts: List[str] = []
            for e in view_elements:
                txt = str(e.get("payload", {}).get("text", "") or "").strip()
                if txt:
                    page_text_parts.append(txt)

            view_pages.append({
                "page_num": page_num,
                "width": page_w,
                "height": page_h,
                "elements": view_elements,
                "content": "\n".join(page_text_parts),
                "selection_marks": [],
                "words": [],
            })

        return {
            "pages": view_pages,
            "paragraphs": aggregated_elements["paragraphs"],
            "tables": aggregated_elements["tables"],
            "figures": aggregated_elements["figures"],
            "formulas": aggregated_elements["formulas"],
            "seals": aggregated_elements["seals"],
            "fields": kie_fields if kie_fields else {},
            "sections": [],
            "styles": [],
        }

    def build_quality_layer(
        self,
        fused_layer: Dict[str, Any],
        processing_time_ms: int = 0,
        engines_used: Optional[List[str]] = None,
        table_backfill: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compute quality metrics from fused layer."""
        if engines_used is None:
            engines_used = ["doc_preprocessor", "pp_structure_v3"]

        text_blocks_total = 0
        text_blocks_no_ocr = 0
        table_blocks_total = 0
        figure_blocks_total = 0
        formula_count = 0
        seal_count = 0
        confidences = []

        for page in fused_layer.get("pages", []):
            for block in page.get("blocks", []):
                block_type = block.get("type", "text").lower()

                if block_type in EnvelopeBuilder._OCR_TEXT_LABELS:
                    text_blocks_total += 1
                    status = block.get("processing_status", "succeeded")
                    if status in {"no_ocr", "no_ocr_empty"}:
                        text_blocks_no_ocr += 1

                    conf = block.get("confidence")
                    if conf is not None and conf > 0:
                        confidences.append(conf)

                elif block_type == "table":
                    table_blocks_total += 1
                elif block_type in {"formula", "inline_formula"}:
                    formula_count += 1
                elif block_type in {"seal", "stamp"}:
                    seal_count += 1
                elif block_type in {
                    "figure", "image", "chart", "picture",
                    "figure_table_chart",
                }:
                    figure_blocks_total += 1

        avg_layout_confidence = np.mean(confidences) if confidences else None

        result = {
            "processing_time_ms": processing_time_ms,
            "text_blocks_total": text_blocks_total,
            "text_blocks_no_ocr": text_blocks_no_ocr,
            "table_blocks_total": table_blocks_total,
            "figure_blocks_total": figure_blocks_total,
            "formula_blocks_total": 0,
            "formula_blocks_recognized": 0,
            "formula_count": formula_count,
            "seal_count": seal_count,
            "avg_layout_confidence": float(avg_layout_confidence) if avg_layout_confidence is not None else None,
            "engines_used": engines_used,
        }
        if table_backfill is not None:
            result["table_backfill"] = table_backfill
        return result

    def save_debug_artifacts(
        self,
        job_id: str,
        preprocessing: Dict[str, Any],
        raw: Dict[str, Any],
        fused: Dict[str, Any],
        quality: Dict[str, Any],
        original_image_path: Optional[str] = None,
        preprocessed_image_path: Optional[str] = None,
    ) -> bool:
        """Save debug artifacts to disk if DEBUG_MODE is enabled."""
        if not self.settings.DEBUG_MODE:
            return False

        debug_dir = os.path.join(self.settings.DEBUG_OUTPUT_DIR, job_id)
        os.makedirs(debug_dir, exist_ok=True)

        try:
            # Save JSON files
            with open(os.path.join(debug_dir, "preprocessing.json"), "w") as f:
                json.dump(preprocessing, f, indent=2)

            with open(os.path.join(debug_dir, "raw_pp_structure_v3.json"), "w") as f:
                json.dump(raw.get("pp_structure_v3", {}), f, indent=2)

            with open(os.path.join(debug_dir, "fused.json"), "w") as f:
                json.dump(fused, f, indent=2)

            with open(os.path.join(debug_dir, "quality.json"), "w") as f:
                json.dump(quality, f, indent=2)

            # Save images if available
            if original_image_path and os.path.exists(original_image_path):
                try:
                    img = cv2.imread(original_image_path)
                    if img is not None:
                        output_path = os.path.join(debug_dir, "original_image.png")
                        cv2.imwrite(output_path, img)
                except Exception as e:
                    logger.warning(f"Failed to save original image for debug: {e}")

            if preprocessed_image_path and os.path.exists(preprocessed_image_path):
                try:
                    img = cv2.imread(preprocessed_image_path)
                    if img is not None:
                        output_path = os.path.join(debug_dir, "preprocessed_image.png")
                        cv2.imwrite(output_path, img)
                except Exception as e:
                    logger.warning(f"Failed to save preprocessed image for debug: {e}")

            logger.info(f"Debug artifacts saved to {debug_dir}")

            # Cleanup old debug artifacts (FIFO)
            self._cleanup_old_debug_artifacts()

            return True
        except Exception as e:
            logger.error(f"Failed to save debug artifacts: {e}")
            return False

    # ============================================
    # Helper Methods
    # ============================================
    # Pure helpers live in envelope_builder_helpers (batch 3); staticmethod
    # aliases keep the historical class-attribute surface (`builder._x(...)`)
    # and the module re-export both working.
    _as_confidence = staticmethod(_as_confidence)
    _build_block_provenance = staticmethod(_build_block_provenance)
    _normalize_bbox = staticmethod(_normalize_bbox)
    _apply_inverse_rotation = staticmethod(_apply_inverse_rotation)
    _map_block_type_to_kind = staticmethod(_map_block_type_to_kind)




    def _cleanup_old_debug_artifacts(self) -> None:
        """Keep only the most recent DEBUG_KEEP_LAST_N debug jobs."""
        if not self.settings.DEBUG_MODE:
            return

        debug_dir = self.settings.DEBUG_OUTPUT_DIR
        if not os.path.exists(debug_dir):
            return

        try:
            job_dirs = [
                d for d in os.listdir(debug_dir)
                if os.path.isdir(os.path.join(debug_dir, d))
            ]
            job_dirs.sort(key=lambda d: os.path.getctime(os.path.join(debug_dir, d)), reverse=True)

            # Keep only the first DEBUG_KEEP_LAST_N
            to_remove = job_dirs[self.settings.DEBUG_KEEP_LAST_N:]
            for old_dir in to_remove:
                try:
                    import shutil
                    shutil.rmtree(os.path.join(debug_dir, old_dir))
                except Exception as e:
                    logger.warning(f"Failed to remove old debug dir {old_dir}: {e}")
        except Exception as e:
            logger.warning(f"Failed to cleanup old debug artifacts: {e}")

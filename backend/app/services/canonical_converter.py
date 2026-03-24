"""
Canonical Document Converter (Phase 2)

Converts the internal layout_service / ocr_service output dicts into the
three-layer CanonicalDocument format defined in app/models/canonical_document.py.

Design goals:
  1. Preserve raw data verbatim in raw_payload (Layer 1 – Raw).
  2. Normalise coordinates to both abs [x1,y1,x2,y2] and norm [0-1] (Layer 2 – Canonical).
  3. Apply SemanticMapper rules to assign semantic roles (Layer 3 – Semantic).
  4. Associate visualisation output directories as portable relative paths.
  5. Stay LOCAL/CLOUD compatible — no absolute OS paths anywhere.

Typical usage (called from layout_service after a predict() pass):

    from app.services.canonical_converter import CanonicalConverter

    converter = CanonicalConverter()        # loads base YAML rules once
    canonical_doc = converter.convert(
        task_id=task_id,
        source_type="pdf",
        layout_result=layout_result,        # dict from layout_service.analyze()
        ocr_result=ocr_result,              # dict from ocr_service.recognize() (optional)
        doc_type_hint="unknown",
    )
    # Store in task result
    task["canonical"] = canonical_doc.to_dict(include_raw_payload=True)
    task["canonical_summary"] = canonical_doc.summary()
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.models.canonical_document import (
    CANONICAL_SCHEMA_VERSION,
    CanonicalBlock,
    CanonicalDocument,
    CanonicalPage,
    CanonicalTable,
    ImageMeta,
    OcrLine,
    SourceRefs,
    VisualizationRefs,
    bbox_to_polygon,
    normalize_bbox,
    normalize_polygon,
)
from app.models.mapping_rules import MappingRuleSet
from app.models.semantic_roles import SemanticRole


# ---------------------------------------------------------------------------
# Module-level rule-set cache (loaded once, hot-reload on demand)
# ---------------------------------------------------------------------------

_RULE_SET_CACHE: Optional[MappingRuleSet] = None

def _get_project_root() -> Path:
    """Return the project root directory (two levels above backend/)."""
    # canonical_converter.py lives at: {project_root}/backend/app/services/
    return Path(__file__).resolve().parent.parent.parent.parent


def _default_rules_path() -> Path:
    return _get_project_root() / "backend" / "config" / "semantic_mapping_base.yaml"


def _load_rule_set(rules_path: Optional[str] = None) -> MappingRuleSet:
    """Load (or return the cached) MappingRuleSet from YAML."""
    global _RULE_SET_CACHE
    if rules_path is not None:
        # Explicit path — always reload (used for testing / remapping with a new version)
        rs = MappingRuleSet.from_yaml_file(rules_path)
        logger.info(f"[CanonicalConverter] Loaded rule set from {rules_path}: {rs.describe()}")
        return rs

    if _RULE_SET_CACHE is None:
        path = _default_rules_path()
        try:
            _RULE_SET_CACHE = MappingRuleSet.from_yaml_file(str(path))
            logger.info(f"[CanonicalConverter] Loaded base rule set: {_RULE_SET_CACHE.describe()}")
        except FileNotFoundError:
            logger.warning(
                f"[CanonicalConverter] Rule YAML not found at {path}. "
                "Using built-in minimal rules."
            )
            _RULE_SET_CACHE = _minimal_fallback_rule_set()
    return _RULE_SET_CACHE


def invalidate_rule_cache() -> None:
    """Force the next call to _load_rule_set() to reload from disk."""
    global _RULE_SET_CACHE
    _RULE_SET_CACHE = None


def _minimal_fallback_rule_set() -> MappingRuleSet:
    """Inline minimal rule set used when no YAML file is found."""
    MINIMAL_YAML = """
config:
  mapping_version: "0.1.0"
  taxonomy_version: "azure-like-v1"
  default_role: Paragraph
  confidence_policy:
    min_block_confidence: 0.0
    demote_if_below: 0.2
  storage:
    keep_raw_role: true
    keep_rule_hit_trace: true
    keep_mapping_version: true
normalize:
  raw_label_alias:
    title: doc_title
    doc_title: doc_title
    heading: paragraph_title
    paragraph_title: paragraph_title
    text: text
    paragraph: text
    header: header
    footer: footer
    table: table
    figure: figure
    image: figure
    figure_title: figure_title
    table_title: table_title
    chart_title: figure_title
    formula: formula
    reference: reference
    footnote: footnote
    equation: formula
    list: list
    list_item: list
    aside_text: text
    number: text
rules:
  - id: F001
    enabled: true
    priority: 1000
    when: {raw_label_in: [doc_title]}
    then: {semantic_role: Title}
  - id: F002
    enabled: true
    priority: 950
    when: {raw_label_in: [paragraph_title]}
    then: {semantic_role: SectionHeading}
  - id: F003
    enabled: true
    priority: 900
    when: {raw_label_in: [header]}
    then: {semantic_role: PageHeader}
  - id: F004
    enabled: true
    priority: 900
    when: {raw_label_in: [footer]}
    then: {semantic_role: PageFooter}
  - id: F005
    enabled: true
    priority: 900
    when: {raw_label_in: [table]}
    then: {semantic_role: Table}
  - id: F006
    enabled: true
    priority: 900
    when: {raw_label_in: [figure]}
    then: {semantic_role: Figure}
  - id: F007
    enabled: true
    priority: 850
    when: {raw_label_in: [figure_title, table_title]}
    then: {semantic_role: Caption}
  - id: F008
    enabled: true
    priority: 850
    when: {raw_label_in: [formula]}
    then: {semantic_role: Formula}
  - id: F009
    enabled: true
    priority: 800
    when: {raw_label_in: [reference]}
    then: {semantic_role: Reference}
  - id: F010
    enabled: true
    priority: 800
    when: {raw_label_in: [footnote]}
    then: {semantic_role: Footnote}
  - id: F011
    enabled: true
    priority: 100
    when: {raw_label_in: [text, list]}
    then: {semantic_role: Paragraph}
postprocess:
  merge_adjacent_blocks: {enabled: true}
"""
    return MappingRuleSet.from_yaml_string(MINIMAL_YAML)


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def _bbox_dict_to_abs(bbox: Dict[str, Any]) -> List[float]:
    """
    Convert layout_service's bbox dict {x, y, width, height} to [x1,y1,x2,y2].
    Also handles plain list [x1,y1,x2,y2] inputs for safety.
    """
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        return [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
    if isinstance(bbox, dict):
        x = float(bbox.get("x", 0.0))
        y = float(bbox.get("y", 0.0))
        w = float(bbox.get("width", 0.0))
        h = float(bbox.get("height", 0.0))
        return [x, y, x + w, y + h]
    return [0.0, 0.0, 0.0, 0.0]


def _sha256_short(path: str) -> str:
    """Return first 16 chars of SHA-256 hex digest for a file."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except Exception:
        return ""


def _relative_path(abs_path: str) -> str:
    """
    Convert an absolute path to a relative path from the project root.
    Returns the original string if the conversion fails.

    Used to ensure no absolute Windows paths go into the Canonical document.
    """
    try:
        project_root = _get_project_root()
        rel = Path(abs_path).relative_to(project_root)
        return str(rel).replace("\\", "/")
    except ValueError:
        # Path is not under project root – return as-is but log a warning
        logger.warning(
            f"[CanonicalConverter] Path '{abs_path}' is outside project root; "
            "stored verbatim (may not be portable to cloud)."
        )
        return abs_path


# ---------------------------------------------------------------------------
# CanonicalConverter
# ---------------------------------------------------------------------------

class CanonicalConverter:
    """
    Converts layout_service and ocr_service output dicts into CanonicalDocument.

    Thread-safety: instances are stateless after construction except for the
    module-level rule-set cache. Safe to call from async contexts.
    """

    def __init__(self, rules_path: Optional[str] = None) -> None:
        """
        Args:
            rules_path: Optional explicit path to a mapping YAML.
                        Defaults to backend/config/semantic_mapping_base.yaml.
        """
        self._rule_set = _load_rule_set(rules_path)

    # ── Public entry point ────────────────────────────────────────────────────

    def convert(
        self,
        task_id: str,
        source_type: str,
        layout_result: Dict[str, Any],
        ocr_result: Optional[Dict[str, Any]] = None,
        doc_type_hint: str = "unknown",
        language_hint: str = "",
        file_path: Optional[str] = None,
    ) -> CanonicalDocument:
        """
        Convert layout + OCR service outputs into a CanonicalDocument.

        Args:
            task_id:       Used as the doc_id (links canonical doc to the task).
            source_type:   "pdf" or "image".
            layout_result: Dict returned by PPStructureEngine.analyze() /
                           LayoutService.analyze().
            ocr_result:    Optional dict returned by OCRService.recognize().
                           If provided, OCR lines are stored for lazy-load.
            doc_type_hint: Category hint for domain-specific mapping rules.
            language_hint: Language hint (e.g. "zh", "en").
            file_path:     Absolute path of the original uploaded file.
                           Used to compute SHA-256 and derive relative URI.

        Returns:
            CanonicalDocument with all three layers populated.
        """
        logger.info(
            f"[CanonicalConverter] Converting task_id={task_id} source_type={source_type} "
            f"doc_type_hint={doc_type_hint}"
        )

        # ── Gather page-level image metadata ─────────────────────────────────
        page_layouts: List[Dict[str, Any]] = layout_result.get("page_layouts", [])
        all_elements: List[Dict[str, Any]] = layout_result.get("elements", [])

        # Build per-page element lists when page_layouts is sparse
        page_element_map: Dict[int, List[Dict[str, Any]]] = {}
        for elem in all_elements:
            pg = int(elem.get("page", 1))
            page_element_map.setdefault(pg, []).append(elem)

        # Ensure we have at least one page entry
        total_pages = layout_result.get("total_pages", max(1, len(page_layouts)))
        if total_pages == 0:
            total_pages = max(1, len(page_element_map))

        # Build OCR line index: page_num → list of line dicts
        ocr_line_map = self._build_ocr_line_map(ocr_result)

        # ── Build CanonicalPage list ──────────────────────────────────────────
        canonical_pages: List[CanonicalPage] = []
        canonical_tables: List[CanonicalTable] = []

        for page_idx in range(total_pages):
            page_num = page_idx + 1  # layout_service uses 1-based page numbers

            # Retrieve image metadata from page_layout info if available
            page_layout_info = (
                page_layouts[page_idx] if page_idx < len(page_layouts) else {}
            )
            img_meta = self._build_image_meta(
                task_id=task_id,
                page_idx=page_idx,
                page_layout_info=page_layout_info,
                file_path=file_path,
            )

            page_id = CanonicalDocument.generate_page_id(task_id, page_idx)

            # Elements for this page (1-based page number from layout_service)
            page_elements = page_element_map.get(page_num, [])
            if not page_elements and page_idx < len(page_layouts):
                # Some adapters embed elements inside page_layouts
                page_elements = page_layout_info.get("elements", [])

            blocks, page_tables = self._build_blocks(
                page_id=page_id,
                page_elements=page_elements,
                img_width=float(img_meta.width_px),
                img_height=float(img_meta.height_px),
                doc_type_hint=doc_type_hint,
            )

            # Patch table page_id
            for tbl in page_tables:
                tbl.page_id = page_id
            canonical_tables.extend(page_tables)

            # OCR lines for this page (lazy-load candidates)
            ocr_lines = self._build_ocr_lines(
                page_id=page_id,
                ocr_line_list=ocr_line_map.get(page_num, []),
                img_width=float(img_meta.width_px),
                img_height=float(img_meta.height_px),
            )

            canonical_pages.append(
                CanonicalPage(
                    page_id=page_id,
                    page_index=page_idx,
                    image=img_meta,
                    blocks=blocks,
                    ocr_lines=ocr_lines,
                )
            )

        # ── Build visualization refs ──────────────────────────────────────────
        vis_refs = self._build_visualization_refs()

        # ── Assemble CanonicalDocument ────────────────────────────────────────
        doc = CanonicalDocument(
            doc_id=task_id,
            source_type=source_type,
            page_count=total_pages,
            pages=canonical_pages,
            tables=canonical_tables,
            doc_type_hint=doc_type_hint,
            language_hint=language_hint,
            taxonomy_version=self._rule_set.config.taxonomy_version,
            visualization_refs=vis_refs,
            # Raw layer: store complete layout + ocr outputs verbatim
            raw_payload={
                "layout": self._sanitize_raw(layout_result),
                "ocr": self._sanitize_raw(ocr_result) if ocr_result else {},
            },
        )

        # Validation
        errors = doc.validate()
        if errors:
            logger.warning(
                f"[CanonicalConverter] Validation warnings for task {task_id}: {errors}"
            )

        logger.info(
            f"[CanonicalConverter] Done: {doc.summary()}"
        )
        return doc

    # ── Block building ────────────────────────────────────────────────────────

    def _build_blocks(
        self,
        page_id: str,
        page_elements: List[Dict[str, Any]],
        img_width: float,
        img_height: float,
        doc_type_hint: str,
    ) -> Tuple[List[CanonicalBlock], List[CanonicalTable]]:
        """
        Convert a list of layout_service element dicts into CanonicalBlocks.

        Also extracts CanonicalTable entries for table elements.
        """
        blocks: List[CanonicalBlock] = []
        tables: List[CanonicalTable] = []

        for idx, elem in enumerate(page_elements):
            if not isinstance(elem, dict):
                continue

            block_id = CanonicalDocument.generate_block_id(page_id, idx)
            raw_type = str(elem.get("type", "unknown")).lower()

            # Coordinate conversion: {x, y, width, height} → [x1,y1,x2,y2]
            raw_bbox = elem.get("bbox", {})
            bbox_abs = _bbox_dict_to_abs(raw_bbox)

            # Normalise to [0–1] using the page image size
            if img_width > 0 and img_height > 0:
                bbox_norm = normalize_bbox(bbox_abs, img_width, img_height)
            else:
                bbox_norm = [0.0, 0.0, 0.0, 0.0]

            polygon_abs = bbox_to_polygon(bbox_abs)
            polygon_norm = normalize_polygon(polygon_abs, img_width, img_height)

            content_text = str(elem.get("text", elem.get("content", "")) or "")
            confidence = float(elem.get("confidence", 0.0))

            # Semantic mapping (Layer 3)
            semantic_role, rule_hit_id = self._rule_set.apply(
                raw_label=raw_type,
                doc_type=doc_type_hint,
                content_text=content_text,
                confidence=confidence,
            )

            # Source reference back to raw_payload
            source_refs = SourceRefs(
                layout_index=idx,
                extra={"original_type": elem.get("type", ""), "elem_id": elem.get("id", "")},
            )

            block = CanonicalBlock(
                block_id=block_id,
                block_type_raw=raw_type,
                bbox_abs=bbox_abs,
                bbox_norm=bbox_norm,
                content_text=content_text,
                semantic_role=semantic_role,
                rule_hit_id=rule_hit_id,
                order=idx,
                polygon_abs=polygon_abs,
                polygon_norm=polygon_norm,
                confidence=confidence,
                source_refs=source_refs,
            )
            blocks.append(block)

            # Extract table if present
            if raw_type == "table" and elem.get("html"):
                tbl_id = f"{page_id}_t{idx:04d}"
                tables.append(
                    CanonicalTable(
                        table_id=tbl_id,
                        page_id=page_id,      # will be patched by caller
                        block_id=block_id,
                        html=str(elem.get("html", "")),
                        confidence=confidence,
                    )
                )

        return blocks, tables

    # ── OCR line building ─────────────────────────────────────────────────────

    def _build_ocr_line_map(
        self, ocr_result: Optional[Dict[str, Any]]
    ) -> Dict[int, List[Dict[str, Any]]]:
        """Index OCR line dicts by page number (1-based)."""
        if not ocr_result:
            return {}

        line_map: Dict[int, List[Dict[str, Any]]] = {}
        text_blocks = ocr_result.get("text_blocks", [])
        for block in text_blocks:
            if not isinstance(block, dict):
                continue
            pg = int(block.get("page", 1))
            line_map.setdefault(pg, []).append(block)
        return line_map

    def _build_ocr_lines(
        self,
        page_id: str,
        ocr_line_list: List[Dict[str, Any]],
        img_width: float,
        img_height: float,
    ) -> List[OcrLine]:
        """Convert per-page OCR text_blocks into OcrLine objects."""
        lines: List[OcrLine] = []
        for idx, lb in enumerate(ocr_line_list):
            if not isinstance(lb, dict):
                continue
            text = str(lb.get("text", ""))
            score = float(lb.get("confidence", lb.get("score", 0.0)))
            poly_raw = lb.get("polygon", lb.get("poly", []))

            if poly_raw:
                poly_abs: List[List[float]] = [
                    [float(pt[0]), float(pt[1])]
                    for pt in poly_raw
                    if isinstance(pt, (list, tuple)) and len(pt) >= 2
                ]
            else:
                # Fallback: derive polygon from bbox
                bbox_abs = _bbox_dict_to_abs(lb.get("bbox", {}))
                poly_abs = bbox_to_polygon(bbox_abs)

            poly_norm = normalize_polygon(poly_abs, img_width, img_height)
            lines.append(
                OcrLine(
                    line_id=f"{page_id}_l{idx:04d}",
                    text=text,
                    score=score,
                    poly_abs=poly_abs,
                    poly_norm=poly_norm,
                )
            )
        return lines

    # ── Image metadata ────────────────────────────────────────────────────────

    def _build_image_meta(
        self,
        task_id: str,
        page_idx: int,
        page_layout_info: Dict[str, Any],
        file_path: Optional[str],
    ) -> ImageMeta:
        """
        Build ImageMeta for a page.

        Tries to extract real pixel dimensions from page_layout_info.
        Falls back to a sensible default when unavailable (common in
        image-mode processing where the page and image are the same).
        """
        width_px = int(page_layout_info.get("width", page_layout_info.get("img_width", 0)))
        height_px = int(page_layout_info.get("height", page_layout_info.get("img_height", 0)))

        if width_px <= 0 or height_px <= 0:
            # Try to read dimensions from the actual image file
            candidate_path = page_layout_info.get("image_path", "")
            if candidate_path and os.path.exists(candidate_path):
                try:
                    from PIL import Image as PILImage
                    with PILImage.open(candidate_path) as im:
                        width_px, height_px = im.size
                except Exception:
                    pass

        if width_px <= 0:
            width_px = 1000   # safe fallback
        if height_px <= 0:
            height_px = 1414  # A4-ish safe fallback

        # Build relative URI — never store absolute path in the contract
        img_abs_path = page_layout_info.get("image_path", "")
        if img_abs_path and os.path.isabs(img_abs_path):
            uri = _relative_path(img_abs_path)
        elif img_abs_path:
            uri = img_abs_path.replace("\\", "/")
        elif file_path and page_idx == 0:
            uri = _relative_path(file_path)
        else:
            uri = f"uploads/{task_id}/page_{page_idx:04d}.jpg"

        sha = ""
        if file_path and page_idx == 0 and os.path.exists(str(file_path)):
            sha = _sha256_short(str(file_path))

        return ImageMeta(
            uri=uri,
            width_px=width_px,
            height_px=height_px,
            sha256=sha,
        )

    # ── Visualization refs ────────────────────────────────────────────────────

    def _build_visualization_refs(self) -> VisualizationRefs:
        """
        Return relative paths to visualisation directories created by
        _save_visualization_outputs() in ocr_service and layout_service.
        """
        return VisualizationRefs(
            paddleocr="outputs/paddleocr_visualizations",
            ppstructure="outputs/ppstructure_visualizations",
        )

    # ── Raw payload sanitisation ──────────────────────────────────────────────

    @staticmethod
    def _sanitize_raw(data: Any, depth: int = 0) -> Any:
        """
        Recursively convert non-JSON-serialisable objects (numpy arrays,
        PaddleOCR result objects) into plain Python types, keeping the
        raw structure intact.

        Caps recursion at depth 12 to avoid infinite loops on unusual objects.
        """
        if depth > 12:
            return str(data)

        if data is None or isinstance(data, (bool, int, float, str)):
            return data

        if isinstance(data, dict):
            return {
                str(k): CanonicalConverter._sanitize_raw(v, depth + 1)
                for k, v in data.items()
            }

        if isinstance(data, (list, tuple)):
            return [CanonicalConverter._sanitize_raw(item, depth + 1) for item in data]

        # numpy scalar / array
        try:
            import numpy as np
            if isinstance(data, np.integer):
                return int(data)
            if isinstance(data, np.floating):
                return float(data)
            if isinstance(data, np.ndarray):
                return data.tolist()
        except ImportError:
            pass

        # PaddleOCR result objects often support dict-like access
        try:
            keys = list(data.keys())
            return {
                str(k): CanonicalConverter._sanitize_raw(data[k], depth + 1)
                for k in keys
            }
        except (AttributeError, TypeError):
            pass

        return str(data)


# ---------------------------------------------------------------------------
# Module-level convenience function (used by main.py remapping API)
# ---------------------------------------------------------------------------

def remap_canonical_doc(
    canonical_dict: Dict[str, Any],
    new_taxonomy_version: str,
    doc_type: Optional[str] = None,
    rules_path: Optional[str] = None,
) -> Tuple[Dict[str, Any], int]:
    """
    Re-apply mapping rules to an already-serialised CanonicalDocument dict.

    This is the core of the POST /api/v1/tasks/{id}/remapping endpoint.

    Steps:
      1. Deserialise canonical_dict → CanonicalDocument.
      2. Load the new rule set (or reload from YAML if rules_path given).
      3. Call doc.remap_semantics().
      4. Update taxonomy_version.
      5. Re-serialise and return.

    Args:
        canonical_dict:      Previously serialised CanonicalDocument dict.
        new_taxonomy_version: Version string of the new rule set.
        doc_type:            Override doc_type_hint for the remapping pass.
        rules_path:          Optional path to a specific YAML rules file.

    Returns:
        Tuple of (updated canonical dict, count of changed blocks).
    """
    doc = CanonicalDocument.from_dict(canonical_dict)
    rule_set = _load_rule_set(rules_path)

    # If caller asks for a specific version that differs from current cache, reload
    if (rule_set.config.taxonomy_version != new_taxonomy_version
            and rules_path is None):
        logger.info(
            f"[CanonicalConverter] Requested taxonomy_version={new_taxonomy_version} "
            f"differs from cached={rule_set.config.taxonomy_version}. "
            "Using cached rules (provide rules_path to load a specific version)."
        )

    changed = doc.remap_semantics(rule_set, doc_type=doc_type)
    updated_dict = doc.to_dict(include_raw_payload=True)
    return updated_dict, changed

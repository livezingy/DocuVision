"""
Canonical Document Contract Data Models

Implements the three-layer data architecture described in
docs/R&D/PaddleOCRDataUsage.md and docs/R&D/canonical-document.schema.json:

  Layer 1 – Raw:       raw_payload stores the complete PaddleOCR / PPStructure
                       output verbatim. Used for traceability and re-mapping.

  Layer 2 – Canonical: pages[].blocks normalises coordinates (abs + norm),
                       block identifiers, reading order, and content text.

  Layer 3 – Semantic:  blocks[].semantic_role is the Azure-like role assigned
                       by MappingRuleSet (see mapping_rules.py).

Schema version:   1.0.0   (matches canonical-document.schema.json)
Taxonomy version: azure-like-v1 (default; updated on each remap_semantics call)

Path design (LOCAL / CLOUD compatible):
  All file paths stored in this model (image URIs, visualization_refs) are
  relative to the project root. They are NOT absolute Windows paths.
  This ensures the same JSON is valid on LOCAL (Windows) and CLOUD (Linux GPU).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    # Avoid circular import at runtime; MappingRuleSet only used as a type hint
    from app.models.mapping_rules import MappingRuleSet


__all__ = [
    "ImageMeta",
    "OcrLine",
    "SourceRefs",
    "CanonicalBlock",
    "CanonicalTable",
    "CanonicalPage",
    "VisualizationRefs",
    "CanonicalDocument",
    "CANONICAL_SCHEMA_VERSION",
    "CANONICAL_TAXONOMY_VERSION",
    # Helper utilities
    "normalize_bbox",
    "normalize_polygon",
    "bbox_to_polygon",
]


CANONICAL_SCHEMA_VERSION: str = "1.0.0"
CANONICAL_TAXONOMY_VERSION: str = "azure-like-v1"

# Type aliases for readability
BboxAbs = List[float]        # [x1, y1, x2, y2] in original image pixel coordinates
BboxNorm = List[float]       # [x1n, y1n, x2n, y2n] normalised to [0.0, 1.0]
PointAbs = List[float]       # [x, y] in image pixel coordinates
PointNorm = List[float]      # [xn, yn] normalised to [0.0, 1.0]


# ── Coordinate helper utilities ───────────────────────────────────────────────

def normalize_bbox(bbox_abs: BboxAbs, width: float, height: float) -> BboxNorm:
    """
    Convert an absolute [x1, y1, x2, y2] bbox to normalised [0, 1] coordinates.

    Values are clamped to [0, 1] to handle minor coordinate overflows.
    Returns [0, 0, 0, 0] when width or height is non-positive.
    """
    if width <= 0 or height <= 0:
        return [0.0, 0.0, 0.0, 0.0]
    x1, y1, x2, y2 = float(bbox_abs[0]), float(bbox_abs[1]), float(bbox_abs[2]), float(bbox_abs[3])
    return [
        max(0.0, min(1.0, x1 / width)),
        max(0.0, min(1.0, y1 / height)),
        max(0.0, min(1.0, x2 / width)),
        max(0.0, min(1.0, y2 / height)),
    ]


def normalize_polygon(polygon_abs: List[PointAbs], width: float, height: float) -> List[PointNorm]:
    """
    Convert a list of absolute [x, y] polygon points to normalised [0, 1].
    Silently skips malformed points (fewer than 2 values).
    """
    if width <= 0 or height <= 0:
        return []
    return [
        [max(0.0, min(1.0, pt[0] / width)), max(0.0, min(1.0, pt[1] / height))]
        for pt in polygon_abs
        if len(pt) >= 2
    ]


def bbox_to_polygon(bbox: BboxAbs) -> List[PointAbs]:
    """Convert a [x1, y1, x2, y2] bbox to a 4-corner polygon (clockwise)."""
    x1, y1, x2, y2 = bbox
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def _sha256_file(path: str) -> str:
    """Compute SHA-256 hex digest of a file. Returns '' on any I/O error."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── ImageMeta ─────────────────────────────────────────────────────────────────

@dataclass
class ImageMeta:
    """
    Metadata for a single page image.

    uri is always a path relative to the project root, e.g.:
        "outputs/images/doc_abc/page_001.jpg"
    Never store absolute OS paths here — this JSON travels to the cloud.

    The frontend must compare width_px / height_px against the loaded image
    dimensions before drawing bounding boxes to detect any coordinate mismatch.
    """

    uri: str
    width_px: int
    height_px: int
    dpi_x: float = 72.0
    dpi_y: float = 72.0
    sha256: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "uri": self.uri,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "dpi_x": self.dpi_x,
            "dpi_y": self.dpi_y,
            "sha256": self.sha256,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ImageMeta":
        return cls(
            uri=d["uri"],
            width_px=int(d["width_px"]),
            height_px=int(d["height_px"]),
            dpi_x=float(d.get("dpi_x", 72.0)),
            dpi_y=float(d.get("dpi_y", 72.0)),
            sha256=d.get("sha256", ""),
        )


# ── OcrLine ───────────────────────────────────────────────────────────────────

@dataclass
class OcrLine:
    """
    A single OCR text line. Included in CanonicalPage.ocr_lines only when
    explicitly requested (lazy-load pattern) to keep default payloads small.

    Frontend uses these for fine-grained OCR density overlays when the user
    toggles the OCR line display.
    """

    line_id: str
    text: str
    score: float
    poly_abs: List[PointAbs]    # ≥4 points [x, y] in image pixel space
    poly_norm: List[PointNorm]  # corresponding normalised points

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_id": self.line_id,
            "text": self.text,
            "score": round(self.score, 4),
            "poly_abs": self.poly_abs,
            "poly_norm": self.poly_norm,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OcrLine":
        return cls(
            line_id=d["line_id"],
            text=d.get("text", ""),
            score=float(d.get("score", 0.0)),
            poly_abs=d.get("poly_abs", []),
            poly_norm=d.get("poly_norm", []),
        )


# ── SourceRefs ────────────────────────────────────────────────────────────────

@dataclass
class SourceRefs:
    """
    Back-references from a Canonical block to entries in raw_payload.

    These allow:
    - Debugging: trace exactly which raw element produced this block.
    - Re-mapping: re-run SemanticMapper on the raw data without re-running OCR.
    - Diff: compare canonical output across taxonomy versions.
    """

    layout_index: Optional[int] = None
    "Index of the source element in raw_payload.parsing_res_list."

    ocr_line_indices: List[int] = field(default_factory=list)
    "Indices of associated OCR lines in raw_payload.overall_ocr_res."

    extra: Dict[str, Any] = field(default_factory=dict)
    "Additional provenance fields, e.g. {'original_type': 'paragraph_title'}."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layout_index": self.layout_index,
            "ocr_line_indices": self.ocr_line_indices,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SourceRefs":
        return cls(
            layout_index=d.get("layout_index"),
            ocr_line_indices=list(d.get("ocr_line_indices", [])),
            extra=dict(d.get("extra", {})),
        )


# ── CanonicalBlock ────────────────────────────────────────────────────────────

@dataclass
class CanonicalBlock:
    """
    A single layout block in the Canonical Document, carrying all three layers:

      Raw layer:      block_type_raw  (original PPStructure/PaddleOCR label)
      Canonical layer: block_type_norm, bbox_abs, bbox_norm, polygon_abs/norm,
                       content_text, confidence, order, source_refs
      Semantic layer: semantic_role, rule_hit_id

    Coordinate conventions:
      bbox_abs   : [x1, y1, x2, y2] in original image pixel coordinates (float)
      bbox_norm  : [x1n, y1n, x2n, y2n] normalised to [0.0, 1.0]
      polygon_abs: list of [x, y] corner points
      polygon_norm: same corners, normalised

    polygon_abs is auto-derived from bbox_abs in __post_init__ if not provided.
    """

    block_id: str
    block_type_raw: str
    bbox_abs: BboxAbs
    bbox_norm: BboxNorm
    content_text: str

    # Normalised label (alias-resolved, lower-cased)
    block_type_norm: str = ""

    # Semantic role from rule engine
    semantic_role: str = "Unknown"

    # Which rule produced the semantic role (null when using default fallback)
    rule_hit_id: Optional[str] = None

    # Reading order index (0-based, None if not determined)
    order: Optional[int] = None

    polygon_abs: List[PointAbs] = field(default_factory=list)
    polygon_norm: List[PointNorm] = field(default_factory=list)

    confidence: float = 0.0

    source_refs: SourceRefs = field(default_factory=SourceRefs)

    # Extensible domain-specific attributes
    # e.g. {"invoice_field": "total", "amount": "99.00"}
    attrs: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Auto-derive polygon_abs from bbox when not explicitly provided
        if not self.polygon_abs and len(self.bbox_abs) == 4:
            self.polygon_abs = bbox_to_polygon(self.bbox_abs)
        # Normalise block_type_norm
        if not self.block_type_norm:
            self.block_type_norm = self.block_type_raw.lower().strip()

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "block_id": self.block_id,
            "block_type_raw": self.block_type_raw,
            "block_type_norm": self.block_type_norm,
            "semantic_role": self.semantic_role,
            "order": self.order,
            "bbox_abs": self.bbox_abs,
            "bbox_norm": self.bbox_norm,
            "polygon_abs": self.polygon_abs,
            "polygon_norm": self.polygon_norm,
            "content_text": self.content_text,
            "confidence": round(self.confidence, 4),
            "source_refs": self.source_refs.to_dict(),
        }
        if self.rule_hit_id is not None:
            d["rule_hit_id"] = self.rule_hit_id
        if self.attrs:
            d["attrs"] = self.attrs
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CanonicalBlock":
        return cls(
            block_id=d["block_id"],
            block_type_raw=d["block_type_raw"],
            bbox_abs=list(d["bbox_abs"]),
            bbox_norm=list(d["bbox_norm"]),
            content_text=d.get("content_text", ""),
            block_type_norm=d.get("block_type_norm", ""),
            semantic_role=d.get("semantic_role", "Unknown"),
            rule_hit_id=d.get("rule_hit_id"),
            order=d.get("order"),
            polygon_abs=d.get("polygon_abs", []),
            polygon_norm=d.get("polygon_norm", []),
            confidence=float(d.get("confidence", 0.0)),
            source_refs=SourceRefs.from_dict(d.get("source_refs", {})),
            attrs=dict(d.get("attrs", {})),
        )


# ── CanonicalTable ────────────────────────────────────────────────────────────

@dataclass
class CanonicalTable:
    """
    Structured table data extracted from a Table block.

    html holds the PPStructure-generated HTML representation.
    cell_boxes_abs/norm mirror the block coordinate conventions for cells.
    """

    table_id: str
    page_id: str
    block_id: str
    html: str = ""
    confidence: float = 0.0
    cell_boxes_abs: List[BboxAbs] = field(default_factory=list)
    cell_boxes_norm: List[BboxNorm] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "table_id": self.table_id,
            "page_id": self.page_id,
            "block_id": self.block_id,
            "html": self.html,
            "confidence": round(self.confidence, 4),
            "cell_boxes_abs": self.cell_boxes_abs,
            "cell_boxes_norm": self.cell_boxes_norm,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CanonicalTable":
        return cls(
            table_id=d["table_id"],
            page_id=d["page_id"],
            block_id=d["block_id"],
            html=d.get("html", ""),
            confidence=float(d.get("confidence", 0.0)),
            cell_boxes_abs=d.get("cell_boxes_abs", []),
            cell_boxes_norm=d.get("cell_boxes_norm", []),
        )


# ── CanonicalPage ─────────────────────────────────────────────────────────────

@dataclass
class CanonicalPage:
    """
    A single document page in the Canonical representation.

    ocr_lines is populated only when the caller explicitly enables it
    (include_ocr_lines=True in to_dict). This keeps the default API response
    compact and defers OCR line data to on-demand requests.
    """

    page_id: str
    page_index: int       # 0-based
    image: ImageMeta
    blocks: List[CanonicalBlock] = field(default_factory=list)
    ocr_lines: List[OcrLine] = field(default_factory=list)  # lazy-loaded

    def to_dict(self, include_ocr_lines: bool = False) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "page_id": self.page_id,
            "page_index": self.page_index,
            "image": self.image.to_dict(),
            "blocks": [b.to_dict() for b in self.blocks],
        }
        if include_ocr_lines and self.ocr_lines:
            d["ocr_lines"] = [line.to_dict() for line in self.ocr_lines]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CanonicalPage":
        return cls(
            page_id=d["page_id"],
            page_index=int(d["page_index"]),
            image=ImageMeta.from_dict(d["image"]),
            blocks=[CanonicalBlock.from_dict(b) for b in d.get("blocks", [])],
            ocr_lines=[OcrLine.from_dict(ln) for ln in d.get("ocr_lines", [])],
        )


# ── VisualizationRefs ─────────────────────────────────────────────────────────

@dataclass
class VisualizationRefs:
    """
    Relative paths (from project root) to directories containing the
    save_to_img PNG outputs from PaddleOCR and PPStructureV3.

    These paths are portable across LOCAL and CLOUD environments because
    they are relative, never absolute OS paths.

    Future: when Phase 5 (object storage) is implemented, these fields
    will hold S3/OSS URIs instead of local paths.
    """

    paddleocr: str = ""
    "e.g. 'outputs/paddleocr_visualizations' — relative to project root."

    ppstructure: str = ""
    "e.g. 'outputs/ppstructure_visualizations' — relative to project root."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "paddleocr": self.paddleocr,
            "ppstructure": self.ppstructure,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VisualizationRefs":
        return cls(
            paddleocr=d.get("paddleocr", ""),
            ppstructure=d.get("ppstructure", ""),
        )


# ── CanonicalDocument ─────────────────────────────────────────────────────────

@dataclass
class CanonicalDocument:
    """
    Top-level Canonical Document Contract.

    Three-layer architecture:
      1. raw_payload         → complete PaddleOCR / PPStructure output (Raw)
      2. pages[].blocks      → normalised layout with abs + norm coords (Canonical)
      3. blocks.semantic_role → Azure-like mapped roles (Semantic)

    Schema version:   1.0.0  (canonical-document.schema.json)
    Taxonomy version: azure-like-v1 (updated each time remap_semantics is called)

    JSON size management:
      - gzip compression is handled at the FastAPI GZIPMiddleware level.
      - raw_payload can be excluded from API responses via include_raw_payload=False.
      - ocr_lines are excluded by default (lazy-loaded on demand).

    Path portability (LOCAL / CLOUD):
      - All paths in this document are relative to project root.
      - No absolute Windows paths (D:\\...) are ever stored here.
    """

    doc_id: str
    source_type: str          # "pdf" | "image"
    page_count: int
    pages: List[CanonicalPage]

    schema_version: str = CANONICAL_SCHEMA_VERSION
    taxonomy_version: str = CANONICAL_TAXONOMY_VERSION

    # Hint about document category (drives domain-specific mapping rules)
    doc_type_hint: str = "unknown"   # paper | invoice | receipt | contract | complex_doc

    language_hint: str = ""

    created_at: str = field(default_factory=_utc_now_iso)

    tables: List[CanonicalTable] = field(default_factory=list)

    # Raw layer: complete PaddleOCR / PPStructure output for traceability
    raw_payload: Dict[str, Any] = field(default_factory=dict)

    # Links to PaddleOCR / PPStructure visualisation PNG directories
    visualization_refs: VisualizationRefs = field(default_factory=VisualizationRefs)

    # ── Validation ────────────────────────────────────────────────────────────

    def validate(self) -> List[str]:
        """
        Run basic structural validation.

        Returns a list of human-readable error strings.
        An empty list means the document is valid.
        Does NOT raise — the caller decides how to handle errors.
        """
        errors: List[str] = []

        if not self.doc_id:
            errors.append("doc_id is required and must not be empty")

        if self.source_type not in ("pdf", "image"):
            errors.append(
                f"source_type must be 'pdf' or 'image', got '{self.source_type}'"
            )

        if self.page_count < 1:
            errors.append("page_count must be >= 1")

        if len(self.pages) != self.page_count:
            errors.append(
                f"page_count={self.page_count} does not match len(pages)={len(self.pages)}"
            )

        for pi, page in enumerate(self.pages):
            img = page.image
            if img.width_px <= 0 or img.height_px <= 0:
                errors.append(
                    f"pages[{pi}].image dimensions must be positive "
                    f"(got {img.width_px}x{img.height_px})"
                )
            for bi, block in enumerate(page.blocks):
                if len(block.bbox_abs) != 4:
                    errors.append(
                        f"pages[{pi}].blocks[{bi}].bbox_abs must have 4 elements, "
                        f"got {len(block.bbox_abs)}"
                    )
                if len(block.bbox_norm) != 4:
                    errors.append(
                        f"pages[{pi}].blocks[{bi}].bbox_norm must have 4 elements, "
                        f"got {len(block.bbox_norm)}"
                    )
                else:
                    for vi, v in enumerate(block.bbox_norm):
                        if not (0.0 <= v <= 1.0):
                            errors.append(
                                f"pages[{pi}].blocks[{bi}].bbox_norm[{vi}]={v} "
                                f"is outside [0, 1]"
                            )
                            break
        return errors

    # ── Serialization ─────────────────────────────────────────────────────────

    def to_dict(
        self,
        include_ocr_lines: bool = False,
        include_raw_payload: bool = True,
    ) -> Dict[str, Any]:
        """
        Serialize to a JSON-compatible dict.

        Args:
            include_ocr_lines:   Include per-page OCR line data.
                                 Default False — use the lazy-load API endpoint instead.
            include_raw_payload: Include the complete raw PaddleOCR/PPStructure output.
                                 Default True for full traceability.
                                 Set False for lightweight API responses.
        """
        d: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "doc_id": self.doc_id,
            "source_type": self.source_type,
            "doc_type_hint": self.doc_type_hint,
            "language_hint": self.language_hint,
            "taxonomy_version": self.taxonomy_version,
            "created_at": self.created_at,
            "page_count": self.page_count,
            "visualization_refs": self.visualization_refs.to_dict(),
            "pages": [p.to_dict(include_ocr_lines=include_ocr_lines) for p in self.pages],
            "tables": [t.to_dict() for t in self.tables],
        }
        if include_raw_payload:
            d["raw_payload"] = self.raw_payload
        return d

    def to_json(
        self,
        indent: Optional[int] = None,
        include_ocr_lines: bool = False,
        include_raw_payload: bool = True,
    ) -> str:
        """
        Serialize to a UTF-8 JSON string.

        Pass indent=2 for human-readable output during debugging.
        Production API responses use the default (compact, gzip-compressed).
        """
        return json.dumps(
            self.to_dict(
                include_ocr_lines=include_ocr_lines,
                include_raw_payload=include_raw_payload,
            ),
            ensure_ascii=False,
            indent=indent,
        )

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CanonicalDocument":
        """Deserialize from a dict (e.g. loaded from file or database)."""
        vis_raw = d.get("visualization_refs", {})
        vis = VisualizationRefs.from_dict(vis_raw if isinstance(vis_raw, dict) else {})

        return cls(
            doc_id=d["doc_id"],
            source_type=d["source_type"],
            page_count=int(d["page_count"]),
            pages=[CanonicalPage.from_dict(p) for p in d.get("pages", [])],
            schema_version=d.get("schema_version", CANONICAL_SCHEMA_VERSION),
            taxonomy_version=d.get("taxonomy_version", CANONICAL_TAXONOMY_VERSION),
            doc_type_hint=d.get("doc_type_hint", "unknown"),
            language_hint=d.get("language_hint", ""),
            created_at=d.get("created_at", _utc_now_iso()),
            tables=[CanonicalTable.from_dict(t) for t in d.get("tables", [])],
            raw_payload=dict(d.get("raw_payload", {})),
            visualization_refs=vis,
        )

    @classmethod
    def from_json(cls, s: str) -> "CanonicalDocument":
        """Deserialize from a JSON string."""
        return cls.from_dict(json.loads(s))

    # ── Static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def generate_doc_id() -> str:
        """Generate a short unique document identifier."""
        return f"doc_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def generate_block_id(page_id: str, block_index: int) -> str:
        """Generate a deterministic block identifier."""
        return f"{page_id}_b{block_index:04d}"

    @staticmethod
    def generate_page_id(doc_id: str, page_index: int) -> str:
        """Generate a deterministic page identifier."""
        return f"{doc_id}_p{page_index:04d}"

    # ── Query helpers ─────────────────────────────────────────────────────────

    def get_page(self, page_index: int) -> Optional[CanonicalPage]:
        """Return the CanonicalPage at the given 0-based page_index, or None."""
        for page in self.pages:
            if page.page_index == page_index:
                return page
        return None

    def get_blocks_by_role(self, semantic_role: str) -> List[CanonicalBlock]:
        """
        Return all CanonicalBlocks with the given semantic role across all pages.

        Useful for front-end content panel grouping and batch processing.
        """
        return [
            block
            for page in self.pages
            for block in page.blocks
            if block.semantic_role == semantic_role
        ]

    def get_all_blocks(self) -> List[Tuple[int, CanonicalBlock]]:
        """
        Return all blocks as (page_index, block) tuples, in reading order.
        """
        result: List[Tuple[int, CanonicalBlock]] = []
        for page in self.pages:
            for block in page.blocks:
                result.append((page.page_index, block))
        return result

    def get_table_by_block_id(self, block_id: str) -> Optional[CanonicalTable]:
        """Look up a CanonicalTable by its associated block_id."""
        for table in self.tables:
            if table.block_id == block_id:
                return table
        return None

    # ── Batch re-mapping (Phase 3 / remapping API) ────────────────────────────

    def remap_semantics(
        self,
        rule_set: "MappingRuleSet",
        doc_type: Optional[str] = None,
    ) -> int:
        """
        Re-apply a (potentially updated) MappingRuleSet to all blocks in-place.

        This is the core operation for the POST /api/v1/tasks/{id}/remapping
        endpoint. It allows semantic roles to be updated when rules are upgraded
        without re-running OCR or layout analysis.

        Args:
            rule_set: The new MappingRuleSet to apply.
            doc_type: Override document type (defaults to self.doc_type_hint).

        Returns:
            Count of blocks whose semantic_role changed.
        """
        effective_doc_type = doc_type or self.doc_type_hint or "unknown"
        changed = 0

        for page in self.pages:
            for block in page.blocks:
                new_role, rule_id = rule_set.apply(
                    raw_label=block.block_type_raw,
                    doc_type=effective_doc_type,
                    content_text=block.content_text,
                    confidence=block.confidence,
                )
                if new_role != block.semantic_role:
                    changed += 1
                block.semantic_role = new_role
                block.rule_hit_id = rule_id

        # Update taxonomy version to reflect which rules were applied
        self.taxonomy_version = rule_set.config.taxonomy_version
        return changed

    def summary(self) -> Dict[str, Any]:
        """
        Return a lightweight summary dict for logging and monitoring.
        Does not include block details or raw_payload.
        """
        role_counts: Dict[str, int] = {}
        total_blocks = 0
        for page in self.pages:
            for block in page.blocks:
                role_counts[block.semantic_role] = role_counts.get(block.semantic_role, 0) + 1
                total_blocks += 1

        return {
            "doc_id": self.doc_id,
            "source_type": self.source_type,
            "page_count": self.page_count,
            "total_blocks": total_blocks,
            "total_tables": len(self.tables),
            "taxonomy_version": self.taxonomy_version,
            "semantic_role_distribution": role_counts,
            "created_at": self.created_at,
        }

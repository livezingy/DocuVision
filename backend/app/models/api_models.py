"""Phase 1 API response/request models (envelope structure).

Extracted from ``main.py`` during the v1.8.2 router split (C1a) so domain
routers can declare ``response_model=`` without importing ``app.main``.
Definitions are copied verbatim from main.py — no semantic change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.core.config import settings


class PreprocessingMetadata(BaseModel):
    """Preprocessing layer: input/output dimensions, rotation, coordinate space strategy"""
    input_size: Dict[str, int] = {}  # {"width": int, "height": int}
    output_size: Dict[str, int] = {}  # {"width": int, "height": int}
    use_doc_orientation_classify: bool = False
    use_doc_unwarping: bool = False
    angle_deg: float = 0.0
    coordinate_space: str = "original"  # "original" or "preprocessed"


class RawLayer(BaseModel):
    """Raw layer: engine outputs without transformation"""
    pp_structure_v3: Optional[Dict[str, Any]] = None  # Full PP-StructureV3 output
    paddleocr_blocks: Optional[Dict[str, Any]] = None  # Per-block OCR results keyed by element id


class FusedBlock(BaseModel):
    """A single block in the fused layer after text fusion and coordinate standardization"""
    block_id: str
    type: str  # "text", "table", "figure", "image", "formula", etc.
    bbox_preprocessed: List[float] = []  # [x0, y0, x1, y1]
    polygon_preprocessed: List[float] = []  # [x0,y0,x1,y0,x1,y1,x0,y1] flat in preprocessed coords
    processing_status: str = "succeeded"  # "succeeded", "replaced", "no_match", "low_confidence", "suspicious"
    source: str = "pp_structure_v3"  # "pp_structure_v3", "paddleocr"
    confidence: float = 0.0
    payload: Dict[str, Any] = {}  # Polymorphic by type
    provenance: Optional[Dict[str, Any]] = None  # {"primary_source", "primary_text", "merge_strategy", "merged_at"} or null


class FusedPage(BaseModel):
    """A page in the fused layer"""
    page_num: int
    width_preprocessed: int = 0
    height_preprocessed: int = 0
    blocks: List[FusedBlock] = []


class FusedLayer(BaseModel):
    """Fused layer: layout blocks with per-block OCR text fusion and coordinate standardization"""
    pages: List[FusedPage] = []


class ViewElement(BaseModel):
    """A single element in the view layer (coordinate-transformed and reading-ordered)"""
    id: str
    kind: str  # "paragraph", "table", "figure", "image", "formula", etc.
    polygon: List[float] = []  # [x0,y0,x1,y0,x1,y1,x0,y1] flat in coordinate_space
    reading_order: int = 0
    source: str = "pp_structure_v3"
    processing_status: str = "succeeded"
    payload: Dict[str, Any] = {}


class ViewContent(BaseModel):
    """Content collections for a page in the view layer"""
    paragraphs: List[ViewElement] = []
    tables: List[ViewElement] = []
    figures: List[ViewElement] = []


class ViewPage(BaseModel):
    """A page in the view layer"""
    page_num: int
    width: int = 0
    height: int = 0
    elements: List[ViewElement] = []
    content: str = ""
    selection_marks: List[Any] = []  # Azure compat placeholder
    words: List[Any] = []            # Azure compat placeholder


class ViewLayer(BaseModel):
    """View layer: reading-order-sorted elements with coordinate transformation applied"""
    pages: List[ViewPage] = []
    paragraphs: List[ViewElement] = []  # Aggregated across all pages
    tables: List[ViewElement] = []  # Aggregated across all pages
    figures: List[ViewElement] = []  # Aggregated across all pages
    formulas: List[ViewElement] = []  # Placeholder, empty for Phase 1.1
    seals: List[ViewElement] = []  # Placeholder, empty for Phase 1.1
    fields: Dict[str, Any] = {}  # Placeholder, empty for Phase 1.1
    sections: List[Any] = []  # Azure compat placeholder
    styles: List[Any] = []    # Azure compat placeholder


class QualityLayer(BaseModel):
    """Quality metrics layer"""
    processing_time_ms: int = 0
    text_blocks_total: int = 0
    text_blocks_no_ocr: int = 0
    table_blocks_total: int = 0
    figure_blocks_total: int = 0
    formula_blocks_total: int = 0
    formula_blocks_recognized: int = 0
    formula_blocks_failed: int = 0
    formula_count: int = 0
    formula_attempted: bool = False
    formula_stage: str = ""
    formula_error_level: str = "none"
    formula_error_code: str = ""
    formula_error_message: str = ""
    formula_recognition_rate: float = 0.0
    seal_count: int = 0
    seal_blocks_total: int = 0
    seal_blocks_recognized: int = 0
    seal_attempted: bool = False
    seal_stage: str = ""
    seal_error_level: str = "none"
    seal_error_code: str = ""
    seal_error_message: str = ""
    seal_recognition_rate: float = 0.0
    # Figure crop export metrics (GLM trial P0-2)
    figure_count: int = 0
    figure_cropped_count: int = 0
    figure_integrity_warning_count: int = 0
    kie_attempted: bool = False
    kie_stage: str = ""
    kie_error_code: str = ""
    kie_error_message: str = ""
    kie_fields_count: int = 0
    kie_production_hit: bool = False
    kie_production_reason: str = ""
    kie_production_keys: List[str] = []
    kie_id_card_precision_hit: bool = False
    kie_id_card_precision_reason: str = ""
    kie_id_card_precision_keys: List[str] = []
    kie_items_count: int = 0
    kie_confidence_avg: float = 0.0
    kie_confidence_source: str = ""
    kie_model_load_ms: int = 0
    kie_items_source: str = "n/a"
    avg_layout_confidence: float = 0.0
    engines_used: List[str] = []  # ["doc_preprocessor", "pp_structure_v3"]
    # v1.8 E2: selective text-layer backfill summary (four-layer funnel counts,
    # per-page verdicts, rates). Optional; omitted for runs without table step.
    table_backfill: Optional[Dict[str, Any]] = None


class JobEnvelope(BaseModel):
    """Phase 1 API response envelope: unified document processing result"""
    job_id: str
    status: str  # "running", "succeeded", "failed", "cancelled"
    version: str = "1.0"
    preprocessing: PreprocessingMetadata = PreprocessingMetadata()
    raw: RawLayer = RawLayer()
    fused: FusedLayer = FusedLayer()
    view: ViewLayer = ViewLayer()
    quality: QualityLayer = QualityLayer()
    # Figure crop exports (GLM trial P0-2): present only when figure regions
    # were detected/cropped or integrity warnings fired; crop files are
    # served by GET /api/v1/tasks/{task_id}/figures/{figure_id}.
    figures: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class JobStatus(BaseModel):
    """Job status response (minimal, returned during processing)"""
    job_id: str
    status: str  # "running", "succeeded", "failed", "cancelled"
    progress: float = 0.0
    message: str = ""
    created_at: datetime = None
    completed_at: Optional[datetime] = None


class ProcessingOptions(BaseModel):
    enable_layout: bool = True
    enable_table: bool = True
    enable_formula: bool = False
    enable_seal: bool = False
    enable_figure_export: bool = True
    enable_kie: bool = False
    document_type: str = "auto"
    language: str = "en"
    ocr_engine: Optional[str] = None
    layout_engine: Optional[str] = None
    table_engine: Optional[str] = None
    table_allow_fullpage_fallback: bool = settings.TABLE_ALLOW_FULLPAGE_FALLBACK
    formula_disable_layout: bool = False
    formula_disable_preprocess: bool = False
    formula_two_stage_threshold_retry: bool = True
    formula_primary_layout_threshold: float = 0.5
    formula_fallback_layout_threshold: float = 0.2
    formula_layout_threshold: Optional[float] = None
    pipeline_formula_batch_size: int = 1
    return_raw: bool = False


class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: float
    message: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None


class BatchCreateModel(BaseModel):
    name: str
    options: Dict[str, Any] = {}


class KieFieldsPatchModel(BaseModel):
    fields: Dict[str, Any]


class HitlResolveModel(BaseModel):
    status: str = "approved"
    corrected_fields: Optional[Dict[str, Any]] = None


class TrialGtDiffModel(BaseModel):
    """Ground-truth payload for the trial diagnostic endpoint (GLM trial P1-4)."""
    fields: Dict[str, Any] = {}
    tables: List[List[List[Any]]] = []  # list of tables; each = rows of cells
    case_sensitive: bool = False

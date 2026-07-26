"""
DocuVision Lite API response models.

Contract: docs/architecture/lite-api.md
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


LITE_API_VERSION = "1.0.0-lite"
LITE_SCHEMA_VERSION = "1.0"


class ExtractMode(str, Enum):
    SMART = "smart"
    ADVANCED = "advanced"


class EngineId(str, Enum):
    AUTO = "auto"
    PDFPLUMBER = "pdfplumber"
    CAMELOT = "camelot"
    TESSERACT = "tesseract"
    EASYOCR = "easyocr"
    TRANSFORMER = "transformer"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DetectedFileType(str, Enum):
    PDF_DIGITAL = "pdf_digital"
    PDF_SCAN = "pdf_scan"
    IMAGE = "image"
    UNSUPPORTED = "unsupported"


class WarningCode(str, Enum):
    SCAN_DETECTED = "scan_detected"
    LOW_CONFIDENCE = "low_confidence"
    NO_TEXT_DETECTED = "no_text_detected"
    OCR_EXTRACTION_FAILED = "ocr_extraction_failed"
    ENGINE_FALLBACK = "engine_fallback"
    TRANSFORMER_UNAVAILABLE = "transformer_unavailable"
    RASTER_TABLE_FROZEN = "raster_table_frozen"
    PAGE_TRUNCATED = "page_truncated"
    PRO_RECOMMENDED = "pro_recommended"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class LiteModel(BaseModel):
    model_config = ConfigDict(use_enum_values=True)


class LiteError(LiteModel):
    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)


class LiteInputMeta(LiteModel):
    filename: str = ""
    file_size_bytes: int = 0
    mime_type: str = ""
    detected_file_type: DetectedFileType = DetectedFileType.UNSUPPORTED
    page_count: int = 0
    sha256: str = ""


class LiteRoutingMeta(LiteModel):
    mode: ExtractMode = ExtractMode.SMART
    requested_engine: str = EngineId.AUTO.value
    engine_used: str = ""
    engine_chain: List[str] = Field(default_factory=list)
    table_type_detected: str = "unknown"
    flavor_used: str = "auto"
    param_mode: str = "auto"
    profile: str = "cpu"
    document_profile: Optional["LiteDocumentProfile"] = None


class LiteQualityMeta(LiteModel):
    overall_confidence: float = 0.0
    tables_found: int = 0
    tables_accepted: int = 0
    pages_processed: int = 0
    pages_with_tables: int = 0
    ocr_blocks: int = 0
    processing_profile: str = "cpu"


class LiteTableDetails(LiteModel):
    domain: str = "unknown"
    empty_cells: int = 0
    merged_cells_detected: bool = False


class LiteTable(LiteModel):
    table_id: str
    page: int = 1
    index_on_page: int = 0
    bbox: List[float] = Field(default_factory=list)
    row_count: int = 0
    col_count: int = 0
    score: float = 0.0
    source: str = ""
    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)
    details: LiteTableDetails = Field(default_factory=LiteTableDetails)


class LiteOcrBlock(LiteModel):
    page: int = 1
    bbox: List[float] = Field(default_factory=list)
    text: str = ""
    confidence: float = 0.0
    engine: str = ""


class LiteExportLinks(LiteModel):
    csv: Optional[str] = None
    markdown: Optional[str] = None
    docx: Optional[str] = None
    json: Optional[str] = None
    xlsx: Optional[str] = None


class LiteWarning(LiteModel):
    code: WarningCode
    message: str
    severity: Severity = Severity.WARNING


class LiteHint(LiteModel):
    code: str
    message: str
    link: Optional[str] = None


class LiteResult(LiteModel):
    schema_version: str = LITE_SCHEMA_VERSION
    api_version: str = LITE_API_VERSION
    job_id: str
    status: JobStatus
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_ms: int = 0
    input: LiteInputMeta = Field(default_factory=LiteInputMeta)
    routing: LiteRoutingMeta = Field(default_factory=LiteRoutingMeta)
    quality: LiteQualityMeta = Field(default_factory=LiteQualityMeta)
    tables: List[LiteTable] = Field(default_factory=list)
    ocr: Optional[List[LiteOcrBlock]] = None
    text_preview: Optional[str] = None
    exports: LiteExportLinks = Field(default_factory=LiteExportLinks)
    warnings: List[LiteWarning] = Field(default_factory=list)
    hints: List[LiteHint] = Field(default_factory=list)
    transactions: List[Dict[str, Any]] = Field(default_factory=list)
    mapped_transactions: List[Dict[str, Any]] = Field(default_factory=list)
    mapped_table_rows: List[Dict[str, Any]] = Field(default_factory=list)
    table_template: Optional[str] = None
    error: Optional[LiteError] = None


class LiteJobProgress(LiteModel):
    pages_total: int = 0
    pages_done: int = 0
    percent: int = 0


class LiteJobStatus(LiteModel):
    job_id: str
    status: JobStatus
    progress: Optional[LiteJobProgress] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LiteJobAccepted(LiteModel):
    job_id: str
    status: JobStatus = JobStatus.PENDING
    poll_url: str
    result_url: str


class LiteEngineAvailability(LiteModel):
    available: bool
    version: Optional[str] = None
    reason: Optional[str] = None


class LiteLimits(LiteModel):
    max_file_size_mb: int = 50
    max_pages: int = 50
    sync_max_pages: int = 10


class LiteHealthResponse(LiteModel):
    status: str = "ok"
    service: str = "docuvision-lite"
    api_version: str = LITE_API_VERSION
    profile: str = "cpu"
    engines: Dict[str, LiteEngineAvailability] = Field(default_factory=dict)
    limits: LiteLimits = Field(default_factory=LiteLimits)


class LiteEngineInfo(LiteModel):
    id: str
    label: str
    file_types: List[str] = Field(default_factory=list)
    description: str = ""
    profile: str = "cpu"
    flavors: List[str] = Field(default_factory=list)


class LiteEnginesResponse(LiteModel):
    engines: List[LiteEngineInfo] = Field(default_factory=list)


class LiteErrorResponse(LiteModel):
    error: LiteError


class LiteClassificationDetail(LiteModel):
    method: str = "quick_filter"
    h_lines: int = 0
    v_lines: int = 0
    line_concentration: Optional[float] = None
    area_ratio: Optional[float] = None
    direction_balance: Optional[float] = None


class LiteTypographySummary(LiteModel):
    mode_char_width_pt: float = 0.0
    mode_char_height_pt: float = 0.0
    mode_line_height_pt: float = 0.0
    mode_line_spacing_pt: float = 0.0
    total_lines: int = 0
    total_chars: int = 0


class LiteSuggestedRouting(LiteModel):
    engine: str = "pdfplumber"
    flavor: str = "text"
    param_mode: str = "auto"


class LiteComputedParams(LiteModel):
    camelot_lattice: Dict[str, Any] = Field(default_factory=dict)
    camelot_stream: Dict[str, Any] = Field(default_factory=dict)
    pdfplumber_bordered: Dict[str, Any] = Field(default_factory=dict)
    pdfplumber_unbordered: Dict[str, Any] = Field(default_factory=dict)


class LitePageProfile(LiteModel):
    page: int = 1
    table_type: str = "none"
    table_type_score: float = 0.0
    classification_detail: LiteClassificationDetail = Field(default_factory=LiteClassificationDetail)
    typography_summary: LiteTypographySummary = Field(default_factory=LiteTypographySummary)
    suggested_routing: LiteSuggestedRouting = Field(default_factory=LiteSuggestedRouting)
    computed_params: LiteComputedParams = Field(default_factory=LiteComputedParams)


class LiteScanProfile(LiteModel):
    recommended_ocr: str = "tesseract"
    transformer_available: bool = False
    message: str = ""


class LitePreviewResponse(LiteModel):
    preview_id: str
    page_count: int = 1
    file_name: str = ""


class LiteDocumentProfile(LiteModel):
    schema_version: str = LITE_SCHEMA_VERSION
    api_version: str = LITE_API_VERSION
    input: LiteInputMeta = Field(default_factory=LiteInputMeta)
    pages: List[LitePageProfile] = Field(default_factory=list)
    scan_profile: Optional[LiteScanProfile] = None
    warnings: List[LiteWarning] = Field(default_factory=list)


LiteRoutingMeta.model_rebuild()

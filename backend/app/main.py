"""
DocuVision - Intelligent Document Processing System
FastAPI Backend Main Entry

Core Features: OCR, Layout Analysis, Table Extraction, Export, Batch Processing
"""

# CRITICAL: Set environment variables FIRST
import os

os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['FLAGS_onednn'] = '0'
os.environ['MKLDNN_ENABLED'] = '0'
os.environ['FLAGS_use_onednn'] = '0'
os.environ['PADDLE_USE_ONEDNN'] = '0'
# Avoid startup/source connectivity probes for model hosters in both local and cloud runs.
os.environ['DISABLE_MODEL_SOURCE_CHECK'] = 'True'
os.environ['PADDLEX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

from app.core.gpu_lib_path import ensure_pro_gpu_lib_path

ensure_pro_gpu_lib_path()

# PaddleX 3.3 使用 snapshot_download；在 import paddlex 前注册 aistudio shim（见 app.core.aistudio_compat）。
from app.core.aistudio_compat import install_aistudio_snapshot_shim_for_paddlex

install_aistudio_snapshot_shim_for_paddlex()

# Fix matplotlib backend issue
import matplotlib
matplotlib.use('Agg')

# Ensure PaddleX is imported only once
#import paddlex  # 显式导入并初始化
paddlex_home = os.environ.get('PADDLEX_HOME', '')
if paddlex_home:
    os.environ['PADDLEX_HOME'] = paddlex_home    # 必须放在这里，确保模型加载前生效
# === Import paddle and paddlex BEFORE any patches ===
import paddle
print(f"[Paddle] Version: {paddle.__version__}, Compiled with CUDA: {paddle.is_compiled_with_cuda()}")

import paddlex

# 验证 PaddleX 实际使用�?home 目录
try:
    # PaddleX 3.x 中可能有 get_home_dir() 方法，如果没有则跳过
    if hasattr(paddlex.utils, 'get_home_dir'):
        actual_home = paddlex.utils.get_home_dir()
        print(f"[PaddleX Home] {actual_home}")
    else:
        print("[PaddleX Home] 无法直接获取，请检查模型下载路径")
except Exception as e:
    print(f"[PaddleX Home] 验证失败: {e}")

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Set
import uuid
import shutil
import hashlib
from datetime import datetime
from loguru import logger
from importlib import metadata as _metadata
from pathlib import Path


def _get_dist_version(dist_names: List[str]) -> str:
    """Get installed package version without importing the package."""
    for name in dist_names:
        try:
            return _metadata.version(name)
        except Exception:
            continue
    return "0.0.0"





def _build_page_image_meta(file_path: str, task_id: str = "", page_num: int = 1) -> Dict[str, Any]:
    """
    Build stable page image metadata for front-end coordinate binding checks.

    Coordinates are declared in original image pixel space (image_abs_px).
    For PDF we render with the same 2x matrix used by /page-image to keep
    dimensions aligned with the preview image endpoint.
    """
    meta: Dict[str, Any] = {
        "page": int(page_num),
        "width_px": 0,
        "height_px": 0,
        "sha256": "",
        "coord_space": "image_abs_px",
        "bbox_to_image_matrix": {
            "src_space": "image_abs_px",
            "dst_space": "image_abs_px",
            "scale_x": 1.0,
            "scale_y": 1.0,
            "offset_x": 0.0,
            "offset_y": 0.0,
        },
    }

    if task_id:
        meta["image_url"] = f"/api/v1/tasks/{task_id}/page-image/{page_num}"

    try:
        if not file_path or not os.path.exists(file_path):
            return meta

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            try:
                if page_num < 1 or page_num > len(doc):
                    return meta

                page = doc[page_num - 1]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                meta["width_px"] = int(pix.width)
                meta["height_px"] = int(pix.height)
                meta["sha256"] = hashlib.sha256(pix.tobytes("png")).hexdigest()

                # Explicit PDF-page-points -> rendered-image-px transform.
                # Useful when a downstream pipeline emits PDF-native coords.
                rect = page.rect
                rect_w = float(getattr(rect, "width", 0.0) or 0.0)
                rect_h = float(getattr(rect, "height", 0.0) or 0.0)
                if rect_w > 0 and rect_h > 0:
                    pdf_to_img_scale_x = float(pix.width) / rect_w
                    pdf_to_img_scale_y = float(pix.height) / rect_h
                else:
                    pdf_to_img_scale_x = 1.0
                    pdf_to_img_scale_y = 1.0

                meta["pdf_page_to_image_matrix"] = {
                    "src_space": "pdf_page_points",
                    "dst_space": "image_abs_px",
                    "scale_x": pdf_to_img_scale_x,
                    "scale_y": pdf_to_img_scale_y,
                    "offset_x": 0.0,
                    "offset_y": 0.0,
                }
                return meta
            finally:
                doc.close()

        from PIL import Image as PILImage
        with PILImage.open(file_path) as img:
            meta["width_px"] = int(img.width)
            meta["height_px"] = int(img.height)
        with open(file_path, "rb") as f:
            meta["sha256"] = hashlib.sha256(f.read()).hexdigest()
    except Exception as e:
        logger.warning(f"Failed to build page image meta for {file_path}: {e}")

    return meta


def _dependency_preflight_check() -> Dict[str, str]:
    """Log installed Paddle/PaddleOCR/PaddleX versions at startup."""
    versions = {
        "paddle": _get_dist_version(["paddlepaddle-gpu", "paddlepaddle"]),
        "paddleocr": _get_dist_version(["paddleocr"]),
        "paddlex": _get_dist_version(["paddlex"]),
    }
    logger.info(
        "[Preflight] Dependency versions | paddle={paddle} | paddleocr={paddleocr} | paddlex={paddlex}",
        paddle=versions["paddle"],
        paddleocr=versions["paddleocr"],
        paddlex=versions["paddlex"],
    )
    return versions


_DEP_VERSIONS = _dependency_preflight_check()


def _short_public_model_id(model_id: str) -> str:
    """Last path segment or trimmed id for health payloads (no full host paths)."""
    s = (model_id or "").strip()
    if not s:
        return ""
    base = os.path.basename(s.rstrip("/\\"))
    return base if base else s[:96]


# 继续导入其他模块
from io import BytesIO
import json
import asyncio
import inspect

from app.services.ocr_service import OCRService
from app.services.layout_service import LayoutService
from app.services.table_service import TableService
from app.services.formula_service import FormulaService
from app.services.seal_service import SealService
from app.services.kie_qwen_service import QwenDocumentKIEService
from app.services.export_service import ExportService
from app.services.batch_service import BatchService, BatchStatus
from app.services.batch_export_service import (
    build_batch_xlsx_bytes,
    build_failure_csv_rows,
    build_json_bundle,
    build_kie_csv_rows,
    build_summary_csv_rows,
    render_csv,
)
from app.services.single_file_pipeline import run_single_file_pipeline
from app.services.kie.kie_pages import validate_kie_pages_for_non_pdf
from app.services.unified_layout_service import UnifiedLayoutService
from app.orchestration.document_pipeline_orchestrator import DocumentPipelineOrchestrator
from app.core.config import settings
from app.core.debug_utils import save_debug_overlay_image

# Single source of truth for /health api_version and OpenAPI version (see config.APP_VERSION).
API_VERSION = settings.APP_VERSION

# Initialize FastAPI application
app = FastAPI(
    title="DocuVision API",
    description="Intelligent Document Processing System - Open Source Alternative to Azure Document Intelligence",
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Trial API-key authentication (GLM trial P0-1).
# MUST be added BEFORE the CORS middleware add_middleware() call below:
# Starlette runs the middleware added LAST as the OUTERMOST layer, so CORS
# sits OUTSIDE the auth middleware — it answers OPTIONS preflights directly
# and decorates 401 responses from the inner auth middleware with CORS
# headers. Empty DOCUVISION_TRIAL_API_KEY keeps the previous open
# local-dev behaviour.
from app.core.trial_auth import TrialAuthMiddleware

app.add_middleware(TrialAuthMiddleware, api_key=settings.TRIAL_API_KEY)

# CORS Configuration (origins configurable via DOCUVISION_CORS_ORIGINS)
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip compression for all responses >= 500 bytes
# Starlette's canonical name is GZipMiddleware (mixed case). Newer starlette/fastapi
# versions also export GZIPMiddleware (all-caps). Try all known spellings in order.
try:
    from starlette.middleware.gzip import GZipMiddleware as _GzipMW  # starlette canonical
except ImportError:
    try:
        from starlette.middleware.gzip import GZIPMiddleware as _GzipMW  # type: ignore[assignment]
    except ImportError:
        from fastapi.middleware.gzip import GZIPMiddleware as _GzipMW  # type: ignore[assignment]
app.add_middleware(_GzipMW, minimum_size=500)

# Frontend static files (served by backend for simple deployments, e.g. AI Studio)
try:
    backend_dir = Path(__file__).resolve().parent.parent
    project_root = backend_dir.parent
    frontend_dir = project_root / "frontend"

    if frontend_dir.exists():
        app.mount(
            "/frontend",
            StaticFiles(directory=str(frontend_dir), html=True),
            name="frontend",
        )
        logger.info(f"[Frontend] Mounted static frontend at /frontend from {frontend_dir}")
    else:
        logger.warning(f"[Frontend] Frontend directory not found, skip mounting: {frontend_dir}")
except Exception as e:
    logger.warning(f"[Frontend] Failed to mount frontend static files: {e}")

# Auto-detect GPU availability
import paddle
use_gpu = paddle.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0
logger.info(f"GPU available: {use_gpu}")

# Test GPU functionality to avoid segmentation faults
if use_gpu:
    try:
        # Quick test to see if GPU can be used without crashing
        import paddle.base.libpaddle as libpaddle
        config = libpaddle.AnalysisConfig()
        # If we get here without crashing, GPU should be usable
        logger.info("GPU initialization test passed")
    except Exception as e:
        logger.warning(f"GPU initialization test failed: {e}, falling back to CPU mode")
        use_gpu = False

# Initialize Services
ocr_service = OCRService(use_gpu=use_gpu, lang=settings.OCR_LANG)
layout_service = LayoutService(use_gpu=use_gpu)
table_service = TableService(
    use_gpu=use_gpu,
    allow_fullpage_fallback=settings.TABLE_ALLOW_FULLPAGE_FALLBACK,
)
formula_service = FormulaService(device="gpu" if use_gpu else "cpu")
seal_service = SealService(device="gpu" if use_gpu else "cpu")
kie_service = QwenDocumentKIEService()


@app.on_event("startup")
async def _kie_optional_warmup_background() -> None:
    """When DOCUVISION_KIE_WARMUP is truthy, load KIE model after startup without blocking readiness."""
    if not settings.KIE_WARMUP:
        return

    async def _run() -> None:
        try:
            await kie_service.warmup_model()
            logger.info("DOCUVISION_KIE_WARMUP: KIE model load finished")
        except Exception as exc:
            logger.warning("DOCUVISION_KIE_WARMUP: warmup failed (non-fatal): {}", exc)

    asyncio.create_task(_run())
export_service = ExportService()
batch_service = BatchService(max_concurrent=3)

# Queue persistence store (SQLite). Attached to batch_service now and to the
# hitl_queue singleton at startup. See docs/architecture/v1.5-roadmap.md.
from app.services.persistence.queue_store import SqliteQueueStore  # noqa: E402

_queue_store = SqliteQueueStore(db_path=Path(settings.SQLITE_DB_PATH))
batch_service.attach_store(_queue_store)


def _raise_query_fields_http(exc: Exception) -> None:
    from app.services.kie.query_fields import QueryFieldsError

    if not isinstance(exc, QueryFieldsError):
        raise exc
    raise HTTPException(
        status_code=400,
        detail={"error_code": exc.error_code, "message": str(exc)},
    )


def _resolve_kie_query_fields_in_options(options: Dict[str, Any]) -> None:
    from app.services.kie.query_fields import QueryFieldsError, attach_kie_query_fields_to_options

    try:
        attach_kie_query_fields_to_options(options)
    except QueryFieldsError as exc:
        _raise_query_fields_http(exc)
unified_layout_service = UnifiedLayoutService()  # 统一的版面分析服
# Task Storage
tasks: Dict[str, Dict[str, Any]] = {}
# Task cancellation flags
task_cancellation_flags: Dict[str, bool] = {}
# WebSocket connections for real-time event streaming
task_websockets: Dict[str, Set[WebSocket]] = {}
# Event history for tasks (to send to late-connecting WebSocket clients)
task_event_history: Dict[str, List[Dict[str, Any]]] = {}
# Per-task event id counters (monotonic incrementing id for each event)
task_event_counters: Dict[str, int] = {}

logger.info(
    "Startup strategy | layout=ppstructure(layout-only optional engines off) | table_mode={} | table_fullpage_fallback={} | formula_mode=independent_lazy_roi | seal_mode=independent_lazy",
    "layout_first",
    settings.TABLE_ALLOW_FULLPAGE_FALLBACK,
)


# ============================================
# Data Models
# ============================================

# ============================================
# Phase 1 API - Response Models (Envelope Structure)
# ============================================

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


# ============================================
# API Routes - Core (P1)
# ============================================

def _enforce_max_upload_size(content: bytes, filename: str = "") -> None:
    """Enforce settings.MAX_FILE_SIZE on in-memory uploads (GLM trial P0-1).

    The limit existed in config but was never wired; this closes the gap for
    every upload endpoint without changing their response contracts.
    """
    limit = int(settings.MAX_FILE_SIZE)
    if limit <= 0:
        return
    if len(content) > limit:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File exceeds maximum upload size "
                f"({len(content) / (1024 * 1024):.1f}MB > {limit / (1024 * 1024):.0f}MB)"
                + (f": {filename}" if filename else "")
            ),
        )


@app.get("/")
async def root():
    return {
        "name": "DocuVision API",
        "version": API_VERSION,
        "status": "running",
        "features": ["OCR/Layout/Table/Export", "Batch Processing"],
        "docs": "/docs"
    }


def _build_health_payload() -> dict:
    deps_extra = {
        "torch": _get_dist_version(["torch"]),
        "transformers": _get_dist_version(["transformers"]),
    }
    return {
        "status": "healthy",
        "api_version": API_VERSION,
        "timestamp": datetime.now().isoformat(),
        "dependencies": dict(_DEP_VERSIONS),
        "dependencies_extra": deps_extra,
        "kie": {
            "model_loaded": kie_service.is_model_loaded(),
            "model_id": _short_public_model_id(settings.KIE_QWEN_MODEL_ID),
        },
        "services": {
            "ocr": {
                "ready": ocr_service.is_ready(),
                "engines": ocr_service.get_available_engines()
            },
            "layout": {
                "ready": layout_service.is_ready(),
                "engines": layout_service.get_available_engines()
            },
            "table": {
                "ready": table_service.is_ready(),
                "engines": table_service.get_available_engines(),
                "strategy": table_service.get_strategy_info(),
            },
            "seal": seal_service.get_status(),
            "batch": {
                "ready": True,
                "active_batches": len([b for b in batch_service.batches.values()
                                      if b.status == BatchStatus.PROCESSING])
            }
        }
    }


@app.get("/health")
async def health_check():
    return _build_health_payload()


@app.get("/api/v1/health")
async def health_check_v1():
    """Same payload as GET /health; use behind reverse proxies that only forward /api/v1/*."""
    return _build_health_payload()


@app.get("/api/v1/engines")
async def list_engines():
    return {
        "ocr": {
            "available": ocr_service.get_available_engines(),
            "default": "paddleocr",
            "engines": {
                "paddleocr": {"name": "PaddleOCR", "is_primary": True},
                "tesseract": {"name": "Tesseract OCR", "is_primary": False},
                "easyocr": {"name": "EasyOCR", "is_primary": False}
            }
        },
        "layout": {
            "available": layout_service.get_available_engines(),
            "default": "ppstructure",
            "engines": {
                "ppstructure": {"name": "PP-StructureV3", "is_primary": True}
            }
        },
        "table": {
            "available": table_service.get_available_engines(),
            "default": "ppstructure",
            "engines": {
                "ppstructure": {"name": "PP-Structure-Table", "is_primary": True}
            }
        },
        "seal": {
            "available": ["seal_recognition"],
            "default": "seal_recognition",
            "engines": {
                "seal_recognition": {"name": "PaddleX Seal Recognition", "is_primary": True}
            }
        }
    }


@app.post("/api/v1/ocr")
async def ocr_recognize(
    file: UploadFile = File(...),
    language: str = Form("en"),
    engine: Optional[str] = Form(None)
):
    """Simple OCR endpoint for quick text extraction"""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Save file temporarily
    task_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.UPLOAD_DIR, task_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        _enforce_max_upload_size(content, file.filename or "")
        f.write(content)

    try:
        ocr_result = await call_maybe_async(
            ocr_service.recognize,
            file_path,
            language=language,
            engine=engine,
            fallback=True
        )

        return {
            "text": ocr_result.get("full_text", ""),
            "text_blocks": ocr_result.get("text_blocks", []),
            "confidence": ocr_result.get("confidence", 0.0),
            "engine": ocr_result.get("engine_used", "unknown"),
            "page_count": ocr_result.get("page_count", 0),
            "processing_time": ocr_result.get("processing_time", 0)
        }
    except Exception as e:
        logger.error(f"OCR error: {e}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")
    finally:
        # Cleanup
        try:
            if os.path.exists(upload_dir):
                shutil.rmtree(upload_dir)
        except:
            pass


@app.post("/api/v1/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file and return task_id for preview purposes.
    This endpoint only uploads the file without processing, allowing immediate preview.
    """
    # Validate file
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Create task_id and save file
    task_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.UPLOAD_DIR, task_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        _enforce_max_upload_size(content, file.filename or "")
        f.write(content)

    # Create minimal task entry for preview purposes
    task = {
        "task_id": task_id,
        "status": "uploaded",
        "progress": 0,
        "message": "File uploaded, ready for preview",
        "created_at": datetime.now(),
        "completed_at": None,
        "file_path": file_path,
        "file_name": file.filename,
        "options": {},
        "result": None
    }
    tasks[task_id] = task

    page_count = 1
    if ext == ".pdf":
        try:
            from app.services.pdf_raster import pdf_page_count

            page_count = max(1, pdf_page_count(file_path))
        except Exception:
            page_count = 1

    return {
        "task_id": task_id,
        "file_name": file.filename,
        "status": "uploaded",
        "message": "File uploaded successfully",
        "page_count": page_count,
    }


@app.post("/api/v1/analyze", response_model=TaskStatus)
async def analyze_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    enable_layout: bool = Form(True),
    enable_table: bool = Form(True),
    enable_formula: bool = Form(False),
    enable_seal: bool = Form(False),
    enable_figure_export: bool = Form(True),
    enable_kie: bool = Form(False),
    document_type: str = Form("auto"),
    language: str = Form("en"),
    ocr_engine: Optional[str] = Form(None),
    layout_engine: Optional[str] = Form(None),
    table_engine: Optional[str] = Form(None),
    table_allow_fullpage_fallback: Optional[bool] = Form(None),
    formula_disable_layout: bool = Form(False),
    formula_disable_preprocess: bool = Form(False),
    formula_two_stage_threshold_retry: bool = Form(True),
    formula_primary_layout_threshold: float = Form(0.5),
    formula_fallback_layout_threshold: float = Form(0.2),
    formula_layout_threshold: Optional[float] = Form(None),
    pipeline_formula_batch_size: int = Form(1),
    return_raw: bool = Form(False),
    kie_query_fields: Optional[str] = Form(None),
    kie_pages: Optional[str] = Form(None),
    table_template: Optional[str] = Form(None),
    enable_hitl: bool = Form(True),
):
    """Upload and analyze a single document"""
    # Validate file
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    is_pdf = ext == ".pdf"
    pages_err = validate_kie_pages_for_non_pdf(kie_pages, is_pdf, enable_kie=enable_kie)
    if pages_err:
        raise HTTPException(status_code=400, detail=pages_err)

    # CRITICAL FIX: FastAPI parses "1"/"0" as True/False for bool Form fields
    # "true"/"false" strings will cause validation errors
    logger.info(
        "Analyze endpoint received - enable_layout={}, enable_table={}, "
        "enable_formula={}, enable_seal={}, enable_kie={}, document_type={}, "
        "table_allow_fullpage_fallback={}, formula_disable_layout={}, formula_disable_preprocess={}, "
        "pipeline_formula_batch_size={}, return_raw={}",
        enable_layout,
        enable_table,
        enable_formula,
        enable_seal,
        enable_kie,
        document_type,
        table_allow_fullpage_fallback,
        formula_disable_layout,
        formula_disable_preprocess,
        pipeline_formula_batch_size,
        return_raw,
    )

    effective_table_allow_fullpage_fallback = (
        settings.TABLE_ALLOW_FULLPAGE_FALLBACK
        if table_allow_fullpage_fallback is None
        else bool(table_allow_fullpage_fallback)
    )

    task_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.UPLOAD_DIR, task_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        _enforce_max_upload_size(content, file.filename or "")
        f.write(content)

    options = {
        "enable_layout": enable_layout,
        "enable_table": enable_table,
        "enable_figure_export": enable_figure_export,
        "enable_formula": enable_formula,
        "enable_seal": enable_seal,
        "enable_kie": enable_kie,
        "document_type": document_type,
        "language": language,
        "ocr_engine": ocr_engine,
        "layout_engine": layout_engine,
        "table_engine": table_engine,
        "table_allow_fullpage_fallback": effective_table_allow_fullpage_fallback,
        "formula_disable_layout": formula_disable_layout,
        "formula_disable_preprocess": formula_disable_preprocess,
        "formula_two_stage_threshold_retry": formula_two_stage_threshold_retry,
        "formula_primary_layout_threshold": formula_primary_layout_threshold,
        "formula_fallback_layout_threshold": formula_fallback_layout_threshold,
        "formula_layout_threshold": formula_layout_threshold,
        "pipeline_formula_batch_size": pipeline_formula_batch_size,
        "return_raw": return_raw,
        "kie_query_fields": kie_query_fields if (kie_query_fields and str(kie_query_fields).strip()) else [],
        "kie_pages": (kie_pages or "").strip() or "1",
    }
    if table_template and str(table_template).strip():
        options["table_template"] = str(table_template).strip().lower()
    options["enable_hitl"] = bool(enable_hitl)

    _resolve_kie_query_fields_in_options(options)

    # Backward-compatible fallback: if user selected a document_type that typically
    # requires KIE (invoice/receipt/id_card) but did not explicitly enable KIE,
    # enable it automatically as a short-term safety net.
    try:
        doc_type_norm = str(document_type or "").strip().lower()
        if doc_type_norm in {"invoice", "receipt", "id_card"} and not options.get("enable_kie", False):
            options["enable_kie"] = True
            logger.info(f"Analyze endpoint compatibility: auto-enabled KIE for document_type={doc_type_norm}")
    except Exception:
        pass

    # Explicitly log the final analyze options so server-side observers
    # (cloud testing / CI logs) can verify whether KIE was enabled without
    # inspecting the browser request payload.
    try:
        logger.info("Analyze options: %s", options)
    except Exception:
        # Logging should never break the request flow
        logger.debug("Failed to log analyze options")

    task = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "Task created",
        "created_at": datetime.now(),
        "completed_at": None,
        "file_path": file_path,
        "file_name": file.filename,
        "options": options,
        "result": None
    }
    tasks[task_id] = task

    # WebSocket connections will be created when client connects
    # No need to pre-create anything

    background_tasks.add_task(process_document, task_id)

    return TaskStatus(**task)


async def _send_event(task_id: str, event_type: str, message: str, progress: Optional[float] = None):
    """Send event to WebSocket clients and store in history"""
    event = {
        "type": event_type,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }
    if progress is not None:
        event["progress"] = progress

    # Store event in history (keep last 100 events)
    if task_id not in task_event_history:
        task_event_history[task_id] = []
    # Assign a monotonic event id for replay filtering
    if task_id not in task_event_counters:
        task_event_counters[task_id] = 0
    task_event_counters[task_id] += 1
    event_id = task_event_counters[task_id]
    event["id"] = event_id
    task_event_history[task_id].append(event)
    # Keep only last 100 events
    if len(task_event_history[task_id]) > 100:
        task_event_history[task_id] = task_event_history[task_id][-100:]

    # Send to all connected WebSocket clients for this task
    if task_id in task_websockets:
        disconnected = set()
        send_tasks = {}

        async def _safe_send(ws, ev):
            try:
                await ws.send_json(ev)
                return True
            except Exception as e:
                logger.warning(f"Task {task_id}: Failed to send event via WebSocket: {e}")
                return False

        # Launch sends concurrently so a slow client won't block processing
        for ws in list(task_websockets[task_id]):
            t = asyncio.create_task(_safe_send(ws, event))
            send_tasks[t] = ws

        # Wait for a short time for sends to complete, but don't block indefinitely
        if send_tasks:
            done, pending = await asyncio.wait(send_tasks.keys(), timeout=1.0)

            # Process completed sends
            for task in done:
                ws = send_tasks.get(task)
                try:
                    ok = task.result()
                    if not ok:
                        disconnected.add(ws)
                except Exception:
                    disconnected.add(ws)

            # Any pending tasks we don't wait for; they will continue in background.
            # Remove disconnected websockets
            for ws in disconnected:
                task_websockets[task_id].discard(ws)
            if not task_websockets.get(task_id):
                task_websockets.pop(task_id, None)
    else:
        logger.debug(f"Task {task_id}: No WebSocket connections, event stored in history - type={event_type}, message={message[:50]}...")


async def call_maybe_async(func, *args, **kwargs):
    """Call `func` which may be sync or async. If sync, run it in thread pool."""
    try:
        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return await asyncio.to_thread(func, *args, **kwargs)
    except Exception:
        # Re-raise to let callers handle logging
        raise


async def process_document(task_id: str):
    """Background document processing delegates execution to orchestrator."""
    task = tasks.get(task_id)
    if not task:
        return

    orchestrator = DocumentPipelineOrchestrator(
        services={
            "ocr_service": ocr_service,
            "layout_service": layout_service,
            "table_service": table_service,
            "formula_service": formula_service,
            "seal_service": seal_service,
            "kie_service": kie_service,
        },
        send_event=_send_event,
        is_cancelled=lambda tid: task_cancellation_flags.get(tid, False),
        call_maybe_async=call_maybe_async,
        build_page_image_meta=_build_page_image_meta,
        save_debug_overlay=save_debug_overlay_image if settings.ENABLE_DEBUG_OVERLAYS else None,
    )

    try:
        await orchestrator.run(task_id, task)
    finally:
        task_cancellation_flags.pop(task_id, None)


# ============================================
# Phase 1 API Routes - Job-Based Endpoints
# ============================================

@app.post("/api/v1/documents:analyze", response_model=JobStatus)
async def analyze_document_v1(
    file: UploadFile = File(...),
    enable_layout: bool = Form(True),
    enable_table: bool = Form(True),
    enable_formula: bool = Form(False),
    enable_seal: bool = Form(False),
    enable_figure_export: bool = Form(True),
    enable_kie: bool = Form(False),
    document_type: str = Form("auto"),
    language: str = Form("en"),
    ocr_engine: Optional[str] = Form(None),
    layout_engine: Optional[str] = Form(None),
    table_engine: Optional[str] = Form(None),
    table_allow_fullpage_fallback: Optional[bool] = Form(None),
    formula_disable_layout: bool = Form(False),
    formula_disable_preprocess: bool = Form(False),
    formula_two_stage_threshold_retry: bool = Form(True),
    formula_primary_layout_threshold: float = Form(0.5),
    formula_fallback_layout_threshold: float = Form(0.2),
    formula_layout_threshold: Optional[float] = Form(None),
    pipeline_formula_batch_size: int = Form(1),
    return_raw: bool = Form(False),
    kie_query_fields: Optional[str] = Form(None),
    kie_pages: Optional[str] = Form(None),
    table_template: Optional[str] = Form(None),
    enable_hitl: bool = Form(True),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Phase 1 API: Submit a document for analysis.
    Returns job_id and status. Use /api/v1/jobs/{job_id} to poll status,
    and /api/v1/jobs/{job_id}/result to fetch the Envelope result.

    Request: multipart/form-data with 'file' field
    Response: JobStatus with job_id

    Form parameters mirror POST /api/v1/analyze (legacy) so the Phase 1
    Job-based endpoint is feature-complete (layout/table/formula/seal/KIE
    toggles, engine overrides, formula thresholds, table_template, HITL).
    """
    # Validate file
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    is_pdf = ext == ".pdf"
    pages_err = validate_kie_pages_for_non_pdf(kie_pages, is_pdf, enable_kie=enable_kie)
    if pages_err:
        raise HTTPException(status_code=400, detail=pages_err)

    effective_table_allow_fullpage_fallback = (
        settings.TABLE_ALLOW_FULLPAGE_FALLBACK
        if table_allow_fullpage_fallback is None
        else bool(table_allow_fullpage_fallback)
    )

    job_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.UPLOAD_DIR, job_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        _enforce_max_upload_size(content, file.filename or "")
        f.write(content)

    options = {
        "enable_layout": enable_layout,
        "enable_table": enable_table,
        "enable_figure_export": enable_figure_export,
        "enable_formula": enable_formula,
        "enable_seal": enable_seal,
        "enable_kie": enable_kie,
        "document_type": document_type,
        "language": language,
        "ocr_engine": ocr_engine,
        "layout_engine": layout_engine,
        "table_engine": table_engine,
        "table_allow_fullpage_fallback": effective_table_allow_fullpage_fallback,
        "formula_disable_layout": formula_disable_layout,
        "formula_disable_preprocess": formula_disable_preprocess,
        "formula_two_stage_threshold_retry": formula_two_stage_threshold_retry,
        "formula_primary_layout_threshold": formula_primary_layout_threshold,
        "formula_fallback_layout_threshold": formula_fallback_layout_threshold,
        "formula_layout_threshold": formula_layout_threshold,
        "pipeline_formula_batch_size": pipeline_formula_batch_size,
        "use_doc_unwarping": settings.USE_DOC_UNWARPING,
        "debug_mode": settings.DEBUG_MODE,
        "return_raw": return_raw,
        "kie_query_fields": kie_query_fields if (kie_query_fields and str(kie_query_fields).strip()) else [],
        "kie_pages": (kie_pages or "").strip() or "1",
    }
    if table_template and str(table_template).strip():
        options["table_template"] = str(table_template).strip().lower()
    options["enable_hitl"] = bool(enable_hitl)

    _resolve_kie_query_fields_in_options(options)

    # Backward-compatible fallback: if user selected a document_type that
    # typically requires KIE (invoice/receipt/id_card) but did not enable KIE,
    # enable it automatically (mirrors legacy /api/v1/analyze behavior).
    try:
        doc_type_norm = str(document_type or "").strip().lower()
        if doc_type_norm in {"invoice", "receipt", "id_card"} and not options.get("enable_kie", False):
            options["enable_kie"] = True
            logger.info(f"Phase1 analyze: auto-enabled KIE for document_type={doc_type_norm}")
    except Exception:
        pass

    try:
        logger.info("Phase1 analyze options: %s", options)
    except Exception:
        logger.debug("Failed to log phase1 analyze options")

    task = {
        "task_id": job_id,
        "status": "pending",
        "progress": 0,
        "message": "Job created",
        "created_at": datetime.now(),
        "completed_at": None,
        "file_path": file_path,
        "file_name": file.filename,
        "options": options,
        "result": None,
        "envelope": None,  # Will be populated by phase1_envelope_step
    }
    tasks[job_id] = task

    background_tasks.add_task(process_document, job_id)

    return JobStatus(
        job_id=job_id,
        status="running",
        progress=0,
        message="Job created",
        created_at=datetime.now(),
    )


@app.get("/api/v1/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """
    Phase 1 API: Get current job status and progress.
    """
    task = tasks.get(job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatus(
        job_id=job_id,
        status=task.get("status"),
        progress=task.get("progress", 0),
        message=task.get("message", ""),
        created_at=task.get("created_at"),
        completed_at=task.get("completed_at"),
    )


@app.get("/api/v1/jobs/{job_id}/result", response_model=JobEnvelope, response_model_exclude_none=True)
async def get_job_result(job_id: str):
    """
    Phase 1 API: Get the completed Envelope result.
    Returns 404 if job not found or not completed.
    Returns JobEnvelope with preprocessing, raw, fused, view, quality layers.
    """
    task = tasks.get(job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    if task.get("status") not in ("succeeded", "completed"):
        raise HTTPException(
            status_code=409,
            detail=f"Job not completed. Current status: {task.get('status')}"
        )

    envelope_dict = task.get("envelope")
    if not envelope_dict:
        raise HTTPException(
            status_code=500,
            detail="Job result envelope not found"
        )

    if not bool(task.get("options", {}).get("return_raw", False)):
        envelope_dict = dict(envelope_dict)
        envelope_dict["raw"] = {}

    # Convert dict to JobEnvelope model
    return JobEnvelope(**envelope_dict)


@app.get("/api/v1/jobs/{job_id}/debug")
async def get_job_debug(job_id: str):
    """
    Phase 1 API: Get debug artifacts (preprocessing, raw, fused, quality JSON + images).

    Returns 404 if:
    - Job not found
    - DEBUG_MODE is disabled
    - Job not completed

    Returns a manifest with debug artifact paths and metadata.
    """
    if not settings.DEBUG_MODE:
        raise HTTPException(
            status_code=404,
            detail="Debug mode is disabled"
        )

    task = tasks.get(job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    if task.get("status") != "succeeded":
        raise HTTPException(
            status_code=409,
            detail=f"Job not completed. Current status: {task.get('status')}"
        )

    debug_dir = os.path.join(settings.DEBUG_OUTPUT_DIR, job_id)
    if not os.path.exists(debug_dir):
        raise HTTPException(
            status_code=404,
            detail="Debug artifacts not found"
        )

    # List debug files
    debug_files = []
    for filename in os.listdir(debug_dir):
        filepath = os.path.join(debug_dir, filename)
        if os.path.isfile(filepath):
            debug_files.append({
                "filename": filename,
                "path": f"/api/v1/jobs/{job_id}/debug/{filename}",
                "size": os.path.getsize(filepath),
            })

    return {
        "job_id": job_id,
        "debug_dir": debug_dir,
        "artifacts": debug_files,
    }


@app.get("/api/v1/jobs/{job_id}/debug/{filename}")
async def get_job_debug_file(job_id: str, filename: str):
    """
    Phase 1 API: Download a specific debug artifact file.
    """
    if not settings.DEBUG_MODE:
        raise HTTPException(status_code=404, detail="Debug mode is disabled")

    task = tasks.get(job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    filepath = os.path.join(settings.DEBUG_OUTPUT_DIR, job_id, filename)

    # Security: prevent directory traversal (use resolved path containment,
    # not startswith, to reject sibling dirs like ./debug2/...)
    base_dir = Path(settings.DEBUG_OUTPUT_DIR).resolve()
    try:
        resolved = Path(filepath).resolve()
        if not resolved.is_relative_to(base_dir):
            raise HTTPException(status_code=403, detail="Access denied")
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(filepath)


# ============================================
# Legacy API Routes (Task-based, deprecated for Phase 1.1)
# ============================================

@app.get("/api/v1/tasks/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatus(**task)


@app.get("/api/v1/tasks/{task_id}/events")
async def get_task_events(task_id: str):
    """Debug endpoint: return stored event history for a task (last 100 events)."""
    events = task_event_history.get(task_id, [])
    return {"events": events}


@app.websocket("/api/v1/tasks/{task_id}/ws")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    WebSocket endpoint for real-time task event streaming.
    Connects to a specific task and receives all events in real-time.
    Sends event history to late-connecting clients.
    """
    await websocket.accept()
    logger.info(f"Task {task_id}: WebSocket connection established")

    # Add WebSocket to task's connection set
    if task_id not in task_websockets:
        task_websockets[task_id] = set()
    task_websockets[task_id].add(websocket)

    # Send event history first (for late-connecting clients)
    # Support `since` or `last_event_id` query parameter to only replay events after a given id
    try:
        query = websocket.query_params
        since_val = query.get('since') or query.get('last_event_id') or '0'
        try:
            since_id = int(since_val)
        except Exception:
            since_id = 0
    except Exception:
        since_id = 0

    history = task_event_history.get(task_id, [])
    # Filter history to events with id > since_id
    to_send = [e for e in history if int(e.get('id', 0)) > int(since_id)]
    if to_send:
        logger.info(f"Task {task_id}: Sending {len(to_send)} historical events to new WebSocket connection (since={since_id})")
        max_sent_id = int(since_id)
        for event in to_send:
            try:
                await websocket.send_json(event)
                try:
                    max_sent_id = max(max_sent_id, int(event.get('id', 0)))
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Task {task_id}: Failed to send historical event: {e}")
                break
    else:
        max_sent_id = int(since_id)

    # Send current task status
    task = tasks.get(task_id)
    if task:
        # Build current event and send only if it's newer than any history we just sent
        current_event_id = task_event_counters.get(task_id, 0)
        current_event = {
            "type": "status",
            "status": task.get('status', 'pending'),
            "progress": task.get('progress', 0),
            "message": task.get('message', ''),
            "timestamp": datetime.now().isoformat(),
            "id": current_event_id
        }
        try:
            # If the server already sent history that includes this id, skip sending the duplicate current_event
            if current_event_id > int(max_sent_id):
                await websocket.send_json(current_event)
            else:
                logger.debug(f"Task {task_id}: Skipping current status send (id={current_event_id} <= max_sent_id={max_sent_id})")
        except Exception as e:
            logger.warning(f"Task {task_id}: Failed to send current status: {e}")

    # Handle incoming messages in background task to avoid blocking
    async def handle_messages():
        try:
            while True:
                try:
                    data = await websocket.receive_text()
                    if data == "ping":
                        await websocket.send_text("pong")
                except WebSocketDisconnect:
                    logger.info(f"Task {task_id}: WebSocket disconnected normally")
                    break
                except Exception as e:
                    logger.error(f"Task {task_id}: WebSocket receive error: {e}")
                    break
        except Exception as e:
            logger.error(f"Task {task_id}: Error in message handler: {e}")

    # Start message handler
    message_task = asyncio.create_task(handle_messages())

    try:
        # Wait for message handler to complete (connection closed)
        await message_task
    finally:
        # Clean up: remove WebSocket from task's connection set
        if task_id in task_websockets:
            task_websockets[task_id].discard(websocket)
            if not task_websockets[task_id]:
                task_websockets.pop(task_id, None)
        logger.info(f"Task {task_id}: WebSocket connection closed")


@app.get("/api/v1/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("status") not in ("succeeded", "completed"):
        raise HTTPException(status_code=400, detail="Task not completed")
    return task["result"]

@app.get("/api/v1/tasks/{task_id}/layout")
async def get_unified_layout_analysis(task_id: str, page_number: int = 1):
    """
    获取统一格式的版面分析结�?    Returns unified layout analysis result in standard format
    """
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    logger.info(f"[Layout API] Fetching layout analysis for task {task_id}")

    # 从task结果中获取原始的layout数据
    result = task.get("result", {})
    file_path = task.get("file_path")

    logger.info(f"[Layout API] Result keys: {list(result.keys())}")

    try:
        # 根据文件类型获取image_info
        image_info = {}
        if file_path:
            from PIL import Image as PILImage
            try:
                with PILImage.open(file_path) as img:
                    image_info = {
                        "width": img.width,
                        "height": img.height,
                        "format": img.format
                    }
                logger.info(f"[Layout API] Image info: {image_info}")
            except Exception as e:
                logger.warning(f"[Layout API] Failed to get image info: {e}")
                image_info = {"width": 0, "height": 0}

        # 检查是否有layout数据
        layout_result = result.get("layout")

        if not layout_result:
            logger.warning(f"[Layout API] No layout data in result for task {task_id}")
            # 返回空结果而不是错�?            from app.models.layout_result import LayoutAnalysisResult
            empty_result = LayoutAnalysisResult()
            return empty_result.to_dict()

        logger.info(f"[Layout API] Layout data type: {type(layout_result)}")

        # 尝试转换layout数据为统一格式
        try:
            unified_result = unified_layout_service.analyze_paddleocr_result(
                layout_result,
                image_info=image_info,
                page_number=page_number
            )

            logger.info(f"[Layout API] �?Successfully analyzed layout with {len(unified_result.elements)} elements")
            return unified_result.to_dict()

        except Exception as e:
            logger.error(f"[Layout API] Error analyzing paddleocr result: {e}", exc_info=True)
            # Return empty result on conversion error
            from app.models.layout_result import LayoutAnalysisResult
            empty_result = LayoutAnalysisResult()
            return empty_result.to_dict()

    except Exception as e:
        logger.error(f"[Layout API] �?Error getting unified layout analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


def _normalize_flat_bbox(raw_bbox: Any) -> List[float]:
    """Normalize heterogeneous bbox formats to [x1, y1, x2, y2]."""
    if isinstance(raw_bbox, dict):
        x = float(raw_bbox.get("x", 0))
        y = float(raw_bbox.get("y", 0))
        w = float(raw_bbox.get("width", 0))
        h = float(raw_bbox.get("height", 0))
        return [x, y, x + w, y + h]
    if isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) >= 4:
        return [
            float(raw_bbox[0]),
            float(raw_bbox[1]),
            float(raw_bbox[2]),
            float(raw_bbox[3]),
        ]
    return [0.0, 0.0, 0.0, 0.0]


@app.get("/api/v1/tasks/{task_id}/blocks")
async def get_task_blocks(task_id: str, page_number: int = 1, content_limit: int = 120):
    """Return frontend-oriented flat blocks payload from the view layer."""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("status") not in ("succeeded", "completed"):
        raise HTTPException(status_code=400, detail="Task not completed")

    # Primary source: view layer from Phase 1 envelope
    envelope = task.get("envelope") or {}
    view_layer = envelope.get("view") or {}
    preprocessing = envelope.get("preprocessing") or {}

    # Derive image dimensions from preprocessing metadata
    coord_space = preprocessing.get("coordinate_space", "preprocessed")
    if coord_space == "original":
        size_dict = preprocessing.get("input_size") or {}
    else:
        size_dict = preprocessing.get("output_size") or preprocessing.get("input_size") or {}
    image_width = int(size_dict.get("width", 0) or 0)
    image_height = int(size_dict.get("height", 0) or 0)

    # Fallback to legacy page_image_meta when envelope not present
    if image_width == 0 or image_height == 0:
        result = task.get("result", {}) or {}
        page_meta = (result.get("document_info", {}) or {}).get("page_image_meta", {}) or {}
        image_width = image_width or int(page_meta.get("width_px", 0) or 0)
        image_height = image_height or int(page_meta.get("height_px", 0) or 0)

    blocks: List[Dict[str, Any]] = []

    # Build blocks from view layer pages
    view_pages = view_layer.get("pages", [])
    view_page = next((p for p in view_pages if p.get("page_num", 1) == page_number), None)

    if view_page is not None:
        # Use page-level dimensions if available
        image_width = image_width or int(view_page.get("width", 0) or 0)
        image_height = image_height or int(view_page.get("height", 0) or 0)
        _elem_count = len(view_page.get("elements", []))
        logger.info(
            f"[Blocks] task={task_id} page={page_number} "
            f"source=envelope_view elements={_elem_count}"
        )
        for elem in view_page.get("elements", []):
            if not isinstance(elem, dict):
                continue
            polygon = elem.get("polygon") or []
            # Convert flat polygon [x0,y0,x1,y0,x1,y1,x0,y1] → bbox [x0,y0,x1,y1]
            if len(polygon) >= 4:
                xs = [polygon[i] for i in range(0, len(polygon), 2)]
                ys = [polygon[i] for i in range(1, len(polygon), 2)]
                bbox = [min(xs), min(ys), max(xs), max(ys)]
            else:
                bbox = [0.0, 0.0, 0.0, 0.0]
            payload = elem.get("payload") or {}
            text = str(payload.get("text") or "")
            confidence_raw = payload.get("confidence", elem.get("confidence", 0))
            confidence = float(confidence_raw or 0)
            role = str(elem.get("kind") or "paragraph")
            blocks.append({
                "id": elem.get("id") or f"block_{len(blocks)}",
                "page": page_number,
                "role": role,
                "type": role,
                "confidence": confidence,
                "score": confidence,
                "bbox": bbox,
                "text": text,
                "content": text,
                "content_truncated": text[:content_limit],
                "processing_status": elem.get("processing_status", "succeeded"),
                # GLM trial P0-B: surface the envelope reading_order so the
                # frontend can render a reading-order overlay for multi-column
                # pages. Non-breaking: absent in legacy fallback below.
                "reading_order": elem.get("reading_order", 0),
            })
    else:
        # Fallback: read from legacy result layout elements
        result = task.get("result", {}) or {}
        source_blocks = (
            result.get("semantic_text_blocks")
            or result.get("layout", {}).get("elements")
            or result.get("text_blocks")
            or []
        )
        _fallback_reason = "envelope_missing" if not envelope else (
            "view_missing" if not view_layer.get("pages") else "page_not_found"
        )
        logger.warning(
            f"[Blocks] task={task_id} page={page_number} "
            f"source=legacy_fallback reason={_fallback_reason} "
            f"source_blocks={len(source_blocks)}"
        )
        for idx, block in enumerate(source_blocks):
            if not isinstance(block, dict):
                continue
            page = int(block.get("page", page_number) or page_number)
            if page != page_number:
                continue
            text = str(block.get("text") or block.get("content") or "")
            bbox = _normalize_flat_bbox(block.get("bbox") or block.get("bounding_box"))
            score = block.get("score")
            confidence = float(block.get("confidence", score if score is not None else 0) or 0)
            role = str(block.get("semantic_role") or block.get("type") or block.get("element_type") or "Paragraph")
            blocks.append({
                "id": block.get("id") or block.get("block_id") or f"block_{idx}",
                "page": page,
                "role": role,
                "type": role,
                "confidence": confidence,
                "score": confidence,
                "bbox": bbox,
                "text": text,
                "content": text,
                "content_truncated": text[:content_limit],
            })

    return {
        "task_id": task_id,
        "page": page_number,
        "image_width": image_width,
        "image_height": image_height,
        "coord_space": coord_space,
        "blocks": blocks,
    }



@app.get("/api/v1/tasks/{task_id}/figures")
async def list_task_figures(task_id: str):
    """List figure crops for a task (GLM trial P0-2)."""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    result = task.get("result") or {}
    figures = result.get("figures")
    if not isinstance(figures, dict):
        figures = {"figure_count": 0, "items": []}
    return figures


@app.get("/api/v1/tasks/{task_id}/figures/{figure_id}")
async def get_task_figure_crop(task_id: str, figure_id: str):
    """Serve a single cropped figure PNG (GLM trial P0-2).

    Figure crops live under OUTPUT_DIR/{task_id}/figures/. figure_id is the
    layout element id (e.g. p1_e3); only a safe basename is accepted to
    prevent path traversal.
    """
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Path-traversal guard: accept [A-Za-z0-9_-] ids only.
    import re as _re

    if not _re.fullmatch(r"[A-Za-z0-9_\-]+", figure_id or ""):
        raise HTTPException(status_code=400, detail="Invalid figure id")

    crop_path = os.path.join(settings.OUTPUT_DIR, task_id, "figures", f"{figure_id}.png")
    if not os.path.isfile(crop_path):
        raise HTTPException(status_code=404, detail="Figure crop not found")
    return FileResponse(crop_path, media_type="image/png")


@app.post("/api/v1/trial/gt-diff/{task_id}")
async def trial_gt_diff(task_id: str, body: TrialGtDiffModel):
    """Run a ground-truth diff against a completed task (GLM trial P1-4).

    The client (or operator) supplies expected values; the endpoint returns
    a field/cell-level accuracy report and persists a self-contained HTML
    report served at GET /api/v1/trial/gt-diff/{task_id}/report.
    """
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("status") not in ("succeeded", "completed"):
        raise HTTPException(status_code=400, detail="Task not completed yet")

    from app.services.trial.gt_diff import run_diff

    report_dir = os.path.join(settings.OUTPUT_DIR, task_id)
    html_path = os.path.join(report_dir, "gt_diff_report.html")
    report = run_diff(
        body.model_dump(),
        task.get("result") or {},
        job_id=task_id,
        output_html_path=html_path,
        case_sensitive=body.case_sensitive,
    )
    report["report_url"] = f"/api/v1/trial/gt-diff/{task_id}/report"
    return report


@app.get("/api/v1/trial/gt-diff/{task_id}/report")
async def trial_gt_diff_report_file(task_id: str):
    """Serve the generated HTML accuracy report (GLM trial P1-4)."""
    import re as _re

    if not _re.fullmatch(r"[A-Za-z0-9_\-]+", task_id or ""):
        raise HTTPException(status_code=400, detail="Invalid task id")
    path = os.path.join(settings.OUTPUT_DIR, task_id, "gt_diff_report.html")
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Report not generated yet")
    return FileResponse(path, media_type="text/html")


@app.get("/api/v1/tasks/{task_id}/page-image/{page_num}")
async def get_page_image(task_id: str, page_num: int = 1):
    """
    Convert PDF page to image for display.
    Returns the first page as PNG image for PDF files, or original image for image files.
    """
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # When PaddleOCR performed unwarping during processing, serve the preprocessed
    # image so that bbox coordinates (which are in output_img space) align with
    # the image visible in the frontend.
    preprocessed_path = task.get("preprocessed_image_path")
    if preprocessed_path and os.path.exists(preprocessed_path):
        return FileResponse(preprocessed_path, media_type="image/png")

    file_path = task.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    file_ext = os.path.splitext(file_path)[1].lower()

    try:
        if file_ext == '.pdf':
            # Convert PDF page to image
            import fitz  # PyMuPDF
            from PIL import Image

            doc = fitz.open(file_path)
            if page_num < 1 or page_num > len(doc):
                doc.close()
                raise HTTPException(status_code=400, detail=f"Page number {page_num} out of range (1-{len(doc)})")

            page = doc[page_num - 1]  # 0-indexed

            # Render page to image with 2x scale for better quality
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            if pix.alpha:
                img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
                img = img.convert("RGB")
            else:
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            doc.close()

            # Convert to bytes
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            return Response(
                content=img_bytes.getvalue(),
                media_type="image/png",
                headers={
                    "Content-Disposition": f"inline; filename=page_{page_num}.png"
                }
            )
        else:
            # For image files, return the original file
            return FileResponse(
                file_path,
                media_type=f"image/{file_ext[1:]}",
                headers={
                    "Content-Disposition": f"inline; filename={os.path.basename(file_path)}"
                }
            )
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="PyMuPDF (fitz) is required for PDF conversion. Please install: pip install PyMuPDF"
        )
    except Exception as e:
        logger.error(f"Error converting page to image: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to convert page to image: {str(e)}")


@app.get("/api/v1/tasks/{task_id}/export/{format}")
async def export_result(task_id: str, format: str):
    """Export results in various formats"""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("status") not in ("succeeded", "completed"):
        raise HTTPException(status_code=400, detail="Task not completed")

    result = task["result"]
    format = format.lower()

    try:
        if format == "json":
            json_path = await export_service.to_json(result, task_id)
            return FileResponse(json_path, filename=f"{task_id}_result.json")
        elif format == "csv":
            csv_path = await export_service.to_csv(result, task_id)
            return FileResponse(csv_path, filename=f"{task_id}_tables.csv")
        elif format in ["markdown", "md"]:
            md_content = await export_service.to_markdown(result)
            return JSONResponse(content={"markdown": md_content})
        elif format in ["docx", "word"]:
            docx_path = await export_service.to_docx(result, task_id)
            return FileResponse(docx_path, filename=f"{task_id}_result.docx")
        elif format in ["xlsx", "excel"]:
            xlsx_path = await export_service.to_excel(result, task_id)
            return FileResponse(xlsx_path, filename=f"{task_id}_tables.xlsx")
        elif format == "azure":
            azure_format = await export_service.to_structured_json(result)
            return JSONResponse(content=azure_format)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    status = task.get("status")

    if status in ["succeeded", "completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel task with status: {status}")

    # Set cancellation flag
    task_cancellation_flags[task_id] = True
    task["status"] = "cancelled"
    task["message"] = "Task cancelled by user"

    logger.info(f"Task cancelled: {task_id}")
    return {"message": "Task cancelled", "task_id": task_id}


def _apply_kie_fields_to_task(task: Dict[str, Any], fields: Dict[str, Any]) -> Dict[str, Any]:
    from app.services.kie_fields_update import apply_kie_fields_to_task

    return apply_kie_fields_to_task(task, fields)


@app.patch("/api/v1/tasks/{task_id}/kie-fields")
async def patch_task_kie_fields(task_id: str, body: KieFieldsPatchModel):
    """Update KIE fields after human review."""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    try:
        validation = _apply_kie_fields_to_task(task, body.fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "task_id": task_id,
        "fields": body.fields,
        "kie_validation": validation,
    }


@app.delete("/api/v1/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task (can delete any task regardless of status)"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]

    # Cancel if still processing
    if task.get("status") in ["pending", "processing"]:
        task_cancellation_flags[task_id] = True
        task["status"] = "cancelled"

    # Clean up files
    upload_dir = os.path.dirname(task.get("file_path", ""))
    if upload_dir and os.path.exists(upload_dir):
        try:
            shutil.rmtree(upload_dir)
        except Exception as e:
            logger.warning(f"Failed to delete upload directory: {e}")

    # Remove from storage
    del tasks[task_id]
    task_cancellation_flags.pop(task_id, None)

    return {"message": "Task deleted", "task_id": task_id}


# ============================================
# API Routes - Batch Processing (P2)
# ============================================

_PIPELINE_SERVICES = None


def _pipeline_services() -> Dict[str, Any]:
    global _PIPELINE_SERVICES
    if _PIPELINE_SERVICES is None:
        _PIPELINE_SERVICES = {
            "ocr_service": ocr_service,
            "layout_service": layout_service,
            "table_service": table_service,
            "formula_service": formula_service,
            "seal_service": seal_service,
            "kie_service": kie_service,
        }
    return _PIPELINE_SERVICES


async def _batch_process_file(file_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """Full orchestrator pipeline for one batch file."""
    opts = dict(options)
    _resolve_kie_query_fields_in_options(opts)
    doc_type_norm = str(opts.get("document_type", "auto") or "auto").strip().lower()
    if doc_type_norm in {"invoice", "receipt", "id_card"} and not opts.get("enable_kie", False):
        opts["enable_kie"] = True

    async def _noop_event(*_args, **_kwargs):
        return None

    return await run_single_file_pipeline(
        file_path,
        opts,
        services=_pipeline_services(),
        call_maybe_async=call_maybe_async,
        send_event=_noop_event,
        build_page_image_meta=_build_page_image_meta,
        save_debug_overlay=save_debug_overlay_image if settings.ENABLE_DEBUG_OVERLAYS else None,
    )


@app.post("/api/v1/batch")
async def create_batch(
    name: str = Form(...),
    files: List[UploadFile] = File(...),
    options: str = Form("{}")
):
    """Create a new batch job"""
    import json

    try:
        opts = json.loads(options)
    except Exception:
        opts = {}

    if not isinstance(opts, dict):
        opts = {}
    _resolve_kie_query_fields_in_options(opts)

    # Save files and create file list
    batch_dir = os.path.join(settings.UPLOAD_DIR, "batch_" + str(uuid.uuid4())[:8])
    os.makedirs(batch_dir, exist_ok=True)

    file_list = []
    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']:
            continue

        file_path = os.path.join(batch_dir, file.filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        file_list.append({
            "file_path": file_path,
            "file_name": file.filename
        })

    if not file_list:
        raise HTTPException(status_code=400, detail="No valid files provided")

    doc_type_norm = str(opts.get("document_type", "auto") or "auto").strip().lower()
    if doc_type_norm in {"invoice", "receipt", "id_card"} and not opts.get("enable_kie", False):
        opts["enable_kie"] = True
    if "kie_pages" not in opts:
        opts["kie_pages"] = "1"

    batch = batch_service.create_batch(name, file_list, opts)
    return batch.to_dict()


@app.get("/api/v1/batch")
async def list_batches(
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """List all batch jobs"""
    batch_status = BatchStatus(status) if status else None
    batches = batch_service.list_batches(batch_status, limit, offset)
    return {"batches": batches, "total": len(batch_service.batches)}


@app.get("/api/v1/batch/{batch_id}")
async def get_batch(batch_id: str):
    """Get batch job details"""
    batch = batch_service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch.to_dict()


@app.post("/api/v1/batch/{batch_id}/start")
async def start_batch(batch_id: str, background_tasks: BackgroundTasks):
    """Start processing a batch job"""
    batch = batch_service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    try:
        await batch_service.start_batch(batch_id, _batch_process_file)
        return {"message": "Batch started", "batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/batch/{batch_id}/pause")
async def pause_batch(batch_id: str):
    """Pause a running batch"""
    try:
        success = await batch_service.pause_batch(batch_id)
        return {"message": "Batch paused" if success else "Cannot pause", "batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/v1/batch/{batch_id}/resume")
async def resume_batch(batch_id: str):
    """Resume a paused batch"""
    try:
        success = await batch_service.resume_batch(batch_id, process_func=_batch_process_file)
        return {"message": "Batch resumed" if success else "Cannot resume", "batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/v1/batch/{batch_id}/cancel")
async def cancel_batch(batch_id: str):
    """Cancel a batch job"""
    try:
        success = await batch_service.cancel_batch(batch_id)
        return {"message": "Batch cancelled" if success else "Cannot cancel", "batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/api/v1/batch/{batch_id}")
async def delete_batch(batch_id: str):
    """Delete a batch job"""
    try:
        success = batch_service.delete_batch(batch_id)
        if not success:
            raise HTTPException(status_code=404, detail="Batch not found")
        return {"message": "Batch deleted", "batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/batch/{batch_id}/summary")
async def get_batch_summary(batch_id: str):
    """Get batch job summary"""
    try:
        return batch_service.get_batch_summary(batch_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/v1/batch/{batch_id}/results")
async def get_batch_results(batch_id: str):
    """Get all results from a batch"""
    try:
        return {"results": batch_service.get_batch_results(batch_id)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/v1/batch/{batch_id}/retry")
async def retry_batch_failed(batch_id: str):
    """Retry failed tasks in a batch"""
    try:
        retried = batch_service.retry_failed_tasks(batch_id)
        return {"message": f"Reset {retried} tasks for retry", "batch_id": batch_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/batch/{batch_id}/export.csv")
async def export_batch_csv(batch_id: str, mode: str = "kie", validation_passed_only: bool = False):
    """Download aggregated batch results as CSV (mode: kie, summary, failures)."""
    batch = batch_service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    mode_norm = (mode or "kie").strip().lower()
    export_opts = dict(batch.options or {})
    if validation_passed_only:
        export_opts["validation_passed_only"] = True
    if mode_norm == "summary":
        header, rows = build_summary_csv_rows(batch)
    elif mode_norm in ("failures", "failure"):
        header, rows = build_failure_csv_rows(batch)
    else:
        header, rows = build_kie_csv_rows(batch, options=export_opts)

    csv_text = render_csv(header, rows)
    filename = f"batch_{batch_id}_{mode_norm}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/batch/{batch_id}/export.xlsx")
async def export_batch_xlsx(batch_id: str, mode: str = "all"):
    """Download aggregated batch results as Excel (mode: all, kie, tables, summary)."""
    batch = batch_service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    mode_norm = (mode or "all").strip().lower()
    if mode_norm not in {"all", "kie", "tables", "summary"}:
        raise HTTPException(status_code=400, detail="Invalid mode; use all, kie, tables, or summary")

    try:
        payload = build_batch_xlsx_bytes(batch, mode=mode_norm)
    except Exception as exc:
        logger.error(f"Batch Excel export failed: {exc}")
        raise HTTPException(status_code=500, detail="Batch Excel export failed") from exc

    filename = f"batch_{batch_id}_{mode_norm}.xlsx"
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/batch/{batch_id}/export.json")
async def export_batch_json(batch_id: str):
    """Download full batch results as JSON bundle."""
    import json

    batch = batch_service.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    payload = json.dumps(build_json_bundle(batch), ensure_ascii=False, indent=2)
    filename = f"batch_{batch_id}.json"
    return Response(
        content=payload,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============================================
# Roadmap APIs (v1.3–v1.5 MVP)
# ============================================

@app.post("/api/v1/document/profile")
async def document_profile_scan(file: UploadFile = File(...)):
    """Pre-scan upload and suggest routing options (Pro Document Profile)."""
    import tempfile

    suffix = os.path.splitext(file.filename or "")[1] or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        from app.services.document_profile import build_document_profile

        return build_document_profile(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@app.get("/api/v1/kie/templates")
async def list_kie_templates():
    from app.services.kie.schema_templates import list_templates

    return {"templates": list_templates()}


@app.get("/api/v1/kie/templates/{template_id}")
async def get_kie_template(template_id: str):
    from app.services.kie.schema_templates import load_template

    schema = load_template(template_id)
    if not schema:
        raise HTTPException(status_code=404, detail="Template not found")
    return schema


@app.post("/api/v1/kie/templates/{template_id}")
async def save_kie_template(template_id: str, body: Dict[str, Any]):
    from app.services.kie.schema_templates import save_template

    try:
        save_template(template_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"template_id": template_id, "saved": True}


@app.get("/api/v1/hitl/reviews")
async def list_hitl_reviews(limit: int = 50, include_payload: bool = False):
    from app.services.hitl_queue import hitl_queue

    return {"reviews": hitl_queue.list_pending(limit=limit, include_payload=include_payload)}


@app.get("/api/v1/hitl/reviews/{review_id}")
async def get_hitl_review(review_id: str):
    from app.services.hitl_queue import hitl_queue

    item = hitl_queue.get(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review not found")
    return {
        "review_id": item.review_id,
        "task_id": item.task_id,
        "file_name": item.file_name,
        "reason": item.reason,
        "status": item.status,
        "created_at": item.created_at.isoformat(),
        "payload": item.payload,
    }


@app.post("/api/v1/hitl/reviews/{review_id}/resolve")
async def resolve_hitl_review(
    review_id: str,
    status: str = "approved",
    body: Optional[HitlResolveModel] = None,
):
    from app.services.hitl_queue import hitl_queue

    item = hitl_queue.get(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review not found")

    resolved_status = (body.status if body and body.status else status).strip().lower()
    if resolved_status not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="status must be approved or rejected")

    if resolved_status == "approved":
        task_id = item.task_id
        if task_id in tasks:
            if body and body.corrected_fields is not None:
                _apply_kie_fields_to_task(tasks[task_id], body.corrected_fields)
            else:
                result = tasks[task_id].get("result")
                if isinstance(result, dict):
                    validation = dict(result.get("kie_validation") or {})
                    validation["manual_reviewed"] = True
                    validation["validation_passed"] = True
                    result["kie_validation"] = validation

    corrected = body.corrected_fields if body and body.corrected_fields is not None else None
    item = await hitl_queue.resolve(review_id, status=resolved_status, edited_fields=corrected)
    if not item:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"review_id": review_id, "status": item.status, "task_id": item.task_id}


def _enforce_webhook_enabled() -> None:
    """Return 404 when the instance has webhooks disabled (process-level switch)."""
    if not settings.WEBHOOK_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")


def _enforce_webhook_admin_token(request: Request) -> None:
    """Validate ``X-DocuVision-Admin-Token`` against ``settings.WEBHOOK_ADMIN_TOKEN``.

    Fail-closed: when an admin token is configured, requests without a
    matching header are rejected with 401. An empty configured token is
    treated as "no auth required" only when webhooks are disabled (already
    gated by ``_enforce_webhook_enabled``); when enabled with an empty token,
    we still require the header to be absent-or-empty to avoid silently
    exposing registration, but log a warning.
    """
    expected = settings.WEBHOOK_ADMIN_TOKEN
    provided = request.headers.get("X-DocuVision-Admin-Token", "")
    if expected:
        if not provided or provided != expected:
            raise HTTPException(status_code=401, detail="Invalid admin token")
    else:
        # Token not configured: fail-closed to avoid open registration.
        logger.warning(
            "WEBHOOK_ENABLED=true but WEBHOOK_ADMIN_TOKEN is empty; "
            "rejecting webhook admin request. Set WEBHOOK_ADMIN_TOKEN to allow registration."
        )
        raise HTTPException(status_code=401, detail="Admin token not configured")


@app.get("/api/v1/webhooks")
async def list_webhooks(request: Request):
    _enforce_webhook_enabled()
    _enforce_webhook_admin_token(request)
    from app.services.webhook_service import webhook_registry

    return {"subscriptions": webhook_registry.list_subscriptions()}


@app.post("/api/v1/webhooks")
async def register_webhook(
    request: Request,
    url: str = Form(...),
    events: str = Form("task.completed,batch.completed"),
    secret: str = Form(""),
):
    _enforce_webhook_enabled()
    _enforce_webhook_admin_token(request)
    from app.services.webhook_service import webhook_registry

    event_list = [e.strip() for e in events.split(",") if e.strip()]
    try:
        sub = webhook_registry.register(url, event_list, secret=secret)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "subscription_id": sub.subscription_id,
        "url": sub.url,
        "events": sub.events,
    }


@app.post("/api/v1/pdf-tools/split")
async def pdf_tools_split(file: UploadFile = File(...), pages: str = Form("")):
    import json
    import tempfile

    from app.services.pdf_tools_service import coerce_page_list, split_pdf

    page_list = None
    if pages.strip():
        try:
            page_list = coerce_page_list(json.loads(pages))
        except Exception:
            page_list = coerce_page_list(
                [int(p.strip()) for p in pages.split(",") if p.strip().isdigit()]
            )

    suffix = os.path.splitext(file.filename or "")[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        in_path = tmp.name
    out_dir = os.path.join(tempfile.gettempdir(), f"split_{uuid.uuid4().hex[:8]}")
    try:
        outputs = split_pdf(in_path, out_dir, pages=page_list)
        if len(outputs) == 1 and os.path.isfile(outputs[0]):
            base = os.path.splitext(file.filename or "document")[0]
            page_num = (page_list or [1])[0]
            return FileResponse(
                outputs[0],
                filename=f"{base}_page_{page_num}.pdf",
                media_type="application/pdf",
            )
        return {"pages": outputs, "count": len(outputs)}
    finally:
        try:
            os.unlink(in_path)
        except OSError:
            pass


@app.post("/api/v1/pdf-tools/merge")
async def pdf_tools_merge(files: List[UploadFile] = File(...)):
    import tempfile

    from app.services.pdf_tools_service import merge_pdfs

    paths = []
    try:
        for upload in files:
            suffix = os.path.splitext(upload.filename or "")[1] or ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await upload.read())
                paths.append(tmp.name)
        out_path = os.path.join(tempfile.gettempdir(), f"merged_{uuid.uuid4().hex[:8]}.pdf")
        merge_pdfs(paths, out_path)
        return FileResponse(out_path, filename="merged.pdf", media_type="application/pdf")
    finally:
        for path in paths:
            try:
                os.unlink(path)
            except OSError:
                pass


@app.post("/api/v1/pdf-tools/metadata")
async def pdf_tools_metadata(file: UploadFile = File(...)):
    import tempfile

    from app.services.pdf_tools_service import read_pdf_metadata

    suffix = os.path.splitext(file.filename or "")[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        return read_pdf_metadata(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@app.post("/api/v1/pdf-tools/searchable")
async def pdf_tools_searchable(file: UploadFile = File(...), text: str = Form("")):
    raise HTTPException(
        status_code=501,
        detail="Not Implemented: searchable PDF OCR text layer not yet supported",
    )


@app.post("/api/v1/pdf-tools/form-fill")
async def pdf_tools_form_fill(
    file: UploadFile = File(...),
    field_values: str = Form("{}"),
):
    import json
    import tempfile

    from app.services.pdf_tools_service import fill_acroform

    try:
        values = json.loads(field_values)
    except Exception:
        values = {}
    if not isinstance(values, dict):
        raise HTTPException(status_code=400, detail="field_values must be a JSON object")

    suffix = os.path.splitext(file.filename or "")[1] or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        in_path = tmp.name
    out_path = os.path.join(tempfile.gettempdir(), f"filled_{uuid.uuid4().hex[:8]}.pdf")
    try:
        fill_acroform(in_path, out_path, {str(k): str(v) for k, v in values.items()})
        return FileResponse(out_path, filename="filled.pdf", media_type="application/pdf")
    finally:
        try:
            os.unlink(in_path)
        except OSError:
            pass


# ============================================
# Application Startup
# ============================================

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info(f"DocuVision - Intelligent Document Processing System v{settings.APP_VERSION}")
    logger.info("=" * 60)
    try:
        logger.info(
            "Dependency versions | paddle={paddle} | paddleocr={paddleocr} | paddlex={paddlex}",
            paddle=_DEP_VERSIONS.get("paddle", "unknown"),
            paddleocr=_DEP_VERSIONS.get("paddleocr", "unknown"),
            paddlex=_DEP_VERSIONS.get("paddlex", "unknown"),
        )
    except Exception:
        # Avoid failing startup due to logging issues
        pass
    logger.info(f"Features: OCR, Layout, Table, Export, Batch")
    logger.info("-" * 60)
    logger.info(f"OCR Engines: {ocr_service.get_available_engines()}")
    logger.info(f"Layout Engines: {layout_service.get_available_engines()}")
    logger.info(f"Table Engines: {table_service.get_available_engines()}")
    try:
        from app.services.kie_qwen_service import preflight_kie_model_path

        kie_pf = preflight_kie_model_path()
        logger.info(
            "KIE model path: {} (configured: {}, hub_id={}, local_ready={})",
            kie_pf["resolved"],
            kie_pf["configured"],
            kie_pf["is_hub_id"],
            kie_pf["local_ready"],
        )
        if not kie_pf["is_hub_id"] and not kie_pf["local_ready"]:
            logger.error(
                "KIE preflight failed: local model weights missing at {}. "
                "Run modelscope snapshot_download('Qwen/Qwen2.5-VL-3B-Instruct') "
                "or set DOCUVISION_KIE_QWEN_MODEL_ID.",
                kie_pf["resolved"],
            )
    except Exception:
        pass
    # Queue persistence: rebuild in-memory batch + HITL indexes from SQLite.
    try:
        from app.services.hitl_queue import hitl_queue

        hitl_queue.attach_store(_queue_store)
        hitl_queue.load_from_db()
        batch_service.load_from_db()
    except Exception as exc:
        logger.warning("Queue persistence load failed (non-fatal): {}", exc)
    logger.info("=" * 60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

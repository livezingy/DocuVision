"""
DocuVision - Intelligent Document Processing System
FastAPI Backend Main Entry

P1 Features: OCR, Layout Analysis, Table Extraction, Export
P2 Features: Template System, Batch Processing, Keyword Extraction (NLP)
"""

# CRITICAL: Set environment variables FIRST
import os
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['FLAGS_onednn'] = '0'
os.environ['MKLDNN_ENABLED'] = '0'
os.environ['FLAGS_use_onednn'] = '0'
os.environ['PADDLE_USE_ONEDNN'] = '0'

# Fix matplotlib backend issue
import matplotlib
matplotlib.use('Agg')

# Ensure PaddleX is imported only once
#import paddlex  # 显式导入并初始化
paddlex_home = os.environ.get('PADDLEX_HOME', '/content/drive/My Drive/DocuVision/DocuVision')
os.environ['PADDLEX_HOME'] = paddlex_home    # 必须放在这里，确保模型加载前生效
# === Import paddle and paddlex BEFORE any patches ===
import paddle
print(f"[Paddle] Version: {paddle.__version__}, Compiled with CUDA: {paddle.is_compiled_with_cuda()}")

import paddlex

# 验证 PaddleX 实际使用的 home 目录
try:
    # PaddleX 3.x 中可能有 get_home_dir() 方法，如果没有则跳过
    if hasattr(paddlex.utils, 'get_home_dir'):
        actual_home = paddlex.utils.get_home_dir()
        print(f"[PaddleX Home] {actual_home}")
    else:
        print("[PaddleX Home] 无法直接获取，请检查模型下载路径")
except Exception as e:
    print(f"[PaddleX Home] 验证失败: {e}")

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form, WebSocket, WebSocketDisconnect
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


def _parse_version_tuple(version_str: str) -> tuple[int, int, int]:
    """Parse 'X.Y.Z...' into (X, Y, Z). Non-numeric suffixes are ignored."""
    core_chars: List[str] = []
    for ch in version_str:
        if ch.isdigit() or ch == ".":
            core_chars.append(ch)
        else:
            break
    core = "".join(core_chars)
    parts = [p for p in core.split(".") if p]
    nums: List[int] = []
    for p in parts:
        try:
            nums.append(int(p))
        except Exception:
            break
    while len(nums) < 3:
        nums.append(0)
    return (nums[0], nums[1], nums[2])





def _truthy_env(name: str, default: bool = False) -> bool:
    """Parse common truthy/falsey environment values."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


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


def _resolve_debug_overlay_dir() -> str:
    """Resolve a cloud-friendly output path for debug overlay images."""
    override = os.environ.get("DOCUVISION_DEBUG_OVERLAY_DIR", "").strip()
    if override:
        return override

    # Prefer mounted cloud drive path when available (e.g., Colab/AI Studio).
    cloud_root = "/content/drive/My Drive/DocuVision/DocuVision"
    if os.path.exists(cloud_root):
        return os.path.join(cloud_root, "outputs", "debug_overlays")

    backend_dir = Path(__file__).resolve().parent.parent
    project_root = backend_dir.parent
    return str(project_root / "outputs" / "debug_overlays")


def _normalize_bbox_like(raw_bbox: Any) -> Optional[Dict[str, float]]:
    """Normalize bbox formats into {x, y, width, height}."""
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


def _save_debug_overlay_image(
    file_path: str,
    task_id: str,
    stage: str,
    elements: List[Dict[str, Any]],
    page_num: int = 1,
) -> Optional[Dict[str, Any]]:
    """
    Render and save a debug overlay image for a specific processing stage.

    Coordinates are treated as image_abs_px for current pipeline.
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

        for idx, el in enumerate(elements or []):
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


def _detect_aistudio_environment() -> bool:
    """
    Best-effort detection for Baidu AI Studio runtime.

    This intentionally avoids importing heavy ML packages.
    """
    # Common home path in AI Studio images
    if os.path.exists("/home/aistudio"):
        return True
    # Explicit opt-in
    if _truthy_env("AISTUDIO", False) or _truthy_env("DOCUVISION_AISTUDIO", False):
        return True
    # Other possible signals (non-exhaustive)
    for key in ("AISTUDIO_PROJECT_NAME", "PADDLE_CLOUD", "PADDLE_PLATFORM"):
        if os.environ.get(key):
            return True
    return False


def _dependency_preflight_check() -> Dict[str, str]:
    """
    Print Paddle/PaddleOCR/PaddleX versions and optionally enforce expected versions.

    Strict mode:
    - Enabled by default on AI Studio.
    - Can be forced on/off by env var DOCUVISION_STRICT_DEP_VERSIONS.

    Expected versions can be overridden by:
    - DOCUVISION_EXPECTED_PADDLE_VERSION
    - DOCUVISION_EXPECTED_PADDLEOCR_VERSION
    - DOCUVISION_EXPECTED_PADDLEX_VERSION
    """
    is_aistudio = _detect_aistudio_environment()
    strict = _truthy_env("DOCUVISION_STRICT_DEP_VERSIONS", default=is_aistudio)

    versions = {
        "paddle": _get_dist_version(["paddlepaddle-gpu", "paddlepaddle"]),
        "paddleocr": _get_dist_version(["paddleocr"]),
        "paddlex": _get_dist_version(["paddlex"]),
    }

    logger.info(
        "[Preflight] Dependency versions | paddle={paddle} | paddleocr={paddleocr} | paddlex={paddlex} | strict={strict} | aistudio={is_aistudio}",
        paddle=versions["paddle"],
        paddleocr=versions["paddleocr"],
        paddlex=versions["paddlex"],
        strict=strict,
        is_aistudio=is_aistudio,
    )

    expected_defaults = {
        "paddle": "3.3.0",
        "paddleocr": "3.3.2",
        "paddlex": "3.3.12",
    }

    expected = {
        "paddle": os.environ.get("DOCUVISION_EXPECTED_PADDLE_VERSION", expected_defaults["paddle"] if is_aistudio else ""),
        "paddleocr": os.environ.get("DOCUVISION_EXPECTED_PADDLEOCR_VERSION", expected_defaults["paddleocr"] if is_aistudio else ""),
        "paddlex": os.environ.get("DOCUVISION_EXPECTED_PADDLEX_VERSION", expected_defaults["paddlex"] if is_aistudio else ""),
    }

    if strict:
        mismatches: List[str] = []
        for k in ("paddle", "paddleocr", "paddlex"):
            exp = expected.get(k, "")
            if not exp:
                continue
            if versions.get(k, "0.0.0") != exp:
                mismatches.append(f"- {k}: expected {exp}, found {versions.get(k)}")

        if mismatches:
            msg = (
                "Dependency version mismatch detected.\n"
                "This project expects the AI Studio preinstalled stack (no venv).\n\n"
                "Mismatches:\n"
                + "\n".join(mismatches)
                + "\n\n"
                "Fix suggestions:\n"
                "- Do NOT `pip install`/downgrade paddle/paddleocr/paddlex into the global environment.\n"
                "- Switch to the correct AI Studio image, or align expected versions via:\n"
                "  DOCUVISION_EXPECTED_PADDLE_VERSION / DOCUVISION_EXPECTED_PADDLEOCR_VERSION / DOCUVISION_EXPECTED_PADDLEX_VERSION\n"
                "- To bypass (not recommended on AI Studio), set DOCUVISION_STRICT_DEP_VERSIONS=0\n"
            )
            logger.error("[Preflight] " + msg)
            raise RuntimeError(msg)
    else:
        # Non-strict mode: still warn if AI Studio defaults don't match.
        if is_aistudio:
            warn_lines: List[str] = []
            for k in ("paddle", "paddleocr", "paddlex"):
                exp = expected_defaults[k]
                if versions.get(k, "0.0.0") != exp:
                    warn_lines.append(f"- {k}: expected {exp}, found {versions.get(k)}")
            if warn_lines:
                logger.warning(
                    "[Preflight] AI Studio default stack differs from expected.\n{details}",
                    details="\n".join(warn_lines),
                )

    return versions


_DEP_VERSIONS = _dependency_preflight_check()




# 继续导入其他模块
from io import BytesIO
import json
import asyncio
import inspect

from app.services.ocr_service import OCRService
from app.services.layout_service import LayoutService
from app.services.table_service import TableService
from app.services.export_service import ExportService
from app.services.nlp_service import NLPService
from app.services.template_service import TemplateService
from app.services.batch_service import BatchService, BatchStatus
from app.services.unified_layout_service import UnifiedLayoutService
from app.orchestration.document_pipeline_orchestrator import DocumentPipelineOrchestrator
from app.core.config import settings

# Initialize FastAPI application
app = FastAPI(
    title="DocuVision API",
    description="Intelligent Document Processing System - Open Source Alternative to Azure Document Intelligence",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
ocr_service = OCRService(use_gpu=use_gpu)
layout_service = LayoutService(use_gpu=use_gpu)
table_service = TableService(use_gpu=use_gpu)
export_service = ExportService()
# PaddleOCR-only version: NLP service disabled (no spaCy/HanLP dependencies)
nlp_service = None  # NLPService(language=settings.OCR_LANG)
template_service = TemplateService(templates_dir=os.path.join(settings.UPLOAD_DIR, "templates"))
batch_service = BatchService(max_concurrent=3)
unified_layout_service = UnifiedLayoutService()  # 统一的版面分析服务

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


# ============================================
# Data Models
# ============================================

class ProcessingOptions(BaseModel):
    enable_layout: bool = True
    enable_ocr: bool = True
    enable_table: bool = True
    enable_formula: bool = False
    enable_barcode: bool = False  # New: Barcode recognition
    enable_stamp: bool = False
    enable_nlp: bool = True
    template_id: Optional[str] = None
    language: str = "en"
    ocr_engine: Optional[str] = None
    layout_engine: Optional[str] = None
    table_engine: Optional[str] = None
    nlp_engine: Optional[str] = None
    barcode_engine: Optional[str] = None  # New: Barcode engine option


class TaskStatus(BaseModel):
    task_id: str
    status: str
    progress: float
    message: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None


class TemplateFieldModel(BaseModel):
    name: str
    label: str
    field_type: str = "text"
    required: bool = False
    patterns: List[str] = []
    description: str = ""


class CreateTemplateModel(BaseModel):
    template_id: str
    name: str
    description: str = ""
    category: str = "custom"
    fields: List[TemplateFieldModel]
    keywords: List[str] = []


class BatchCreateModel(BaseModel):
    name: str
    options: Dict[str, Any] = {}


class NLPAnalysisRequest(BaseModel):
    text: str
    top_k_keywords: int = 10
    engine: Optional[str] = None


# ============================================
# API Routes - Core (P1)
# ============================================

@app.get("/")
async def root():
    return {
        "name": "DocuVision API",
        "version": "1.1.0",
        "status": "running",
        "features": ["P1: OCR/Layout/Table/Export", "P2: Template/Batch/NLP"],
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
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
                "engines": table_service.get_available_engines()
            },
            "nlp": {
                "ready": nlp_service.is_ready() if nlp_service else False,
                "engines": nlp_service.get_available_engines() if nlp_service else []
            },
            "template": {
                "ready": True,
                "template_count": len(template_service.templates)
            },
            "batch": {
                "ready": True,
                "active_batches": len([b for b in batch_service.batches.values()
                                      if b.status == BatchStatus.PROCESSING])
            }
        }
    }


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
                "ppstructure": {"name": "PP-StructureV3", "is_primary": True},
                "layoutparser": {"name": "LayoutParser", "is_primary": False}
            }
        },
        "table": {
            "available": table_service.get_available_engines(),
            "default": "ppstructure",
            "engines": {
                "ppstructure": {"name": "PP-Structure-Table", "is_primary": True},
                "camelot": {"name": "Camelot", "is_primary": False},
                "tabula": {"name": "Tabula", "is_primary": False}
            }
        },
        "nlp": {
            "available": nlp_service.get_available_engines() if nlp_service else [],
            "default": "spacy",
            "engines": {
                "spacy": {"name": "spaCy", "is_primary": True, "features": ["NER", "Keywords"]},
                "hanlp": {"name": "HanLP", "is_primary": False, "features": ["Chinese NLP"]},
                "simple": {"name": "SimpleNLP", "is_primary": False, "features": ["Regex-based"]}
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

    return {
        "task_id": task_id,
        "file_name": file.filename,
        "status": "uploaded",
        "message": "File uploaded successfully"
    }


@app.post("/api/v1/analyze", response_model=TaskStatus)
async def analyze_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    enable_layout: bool = Form(True),
    enable_ocr: bool = Form(True),
    enable_table: bool = Form(True),
    enable_nlp: bool = Form(True),
    template_id: Optional[str] = Form(None),
    language: str = Form("en"),
    ocr_engine: Optional[str] = Form(None),
    layout_engine: Optional[str] = Form(None),
    table_engine: Optional[str] = Form(None),
    nlp_engine: Optional[str] = Form(None)
):
    """Upload and analyze a single document"""
    # Validate file
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # CRITICAL FIX: FastAPI parses "1"/"0" as True/False for bool Form fields
    # "true"/"false" strings will cause validation errors
    logger.info(f"Analyze endpoint received - enable_layout={enable_layout}, enable_ocr={enable_ocr}, enable_table={enable_table}")

    task_id = str(uuid.uuid4())
    upload_dir = os.path.join(settings.UPLOAD_DIR, task_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    options = {
        "enable_layout": enable_layout,
        "enable_ocr": enable_ocr,
        "enable_table": enable_table,
        "enable_nlp": enable_nlp,
        "template_id": template_id,
        "language": language,
        "ocr_engine": ocr_engine,
        "layout_engine": layout_engine,
        "table_engine": table_engine,
        "nlp_engine": nlp_engine
    }

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
            "nlp_service": nlp_service,
            "template_service": template_service,
        },
        send_event=_send_event,
        is_cancelled=lambda tid: task_cancellation_flags.get(tid, False),
        call_maybe_async=call_maybe_async,
        build_page_image_meta=_build_page_image_meta,
        save_debug_overlay=_save_debug_overlay_image,
    )

    try:
        await orchestrator.run(task_id, task)
    finally:
        task_cancellation_flags.pop(task_id, None)


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
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")
    return task["result"]


def _load_canonical_document(canonical_raw: Any):
    """Load CanonicalDocument from either dict (current) or JSON string (legacy)."""
    from app.models.canonical_document import CanonicalDocument

    if isinstance(canonical_raw, dict):
        return CanonicalDocument.from_dict(canonical_raw)
    if isinstance(canonical_raw, str):
        return CanonicalDocument.from_json(canonical_raw)

    raise TypeError(f"Unsupported canonical payload type: {type(canonical_raw).__name__}")


@app.get("/api/v1/tasks/{task_id}/canonical")
async def get_canonical_result(task_id: str, include_raw: bool = False, include_ocr_lines: bool = False):
    """
    Return the CanonicalDocument for a completed task.
    Query params:
      include_raw=true         – embed the full PaddleOCR raw payload
      include_ocr_lines=true   – embed per-block OCR line details
    """
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")

    result = task.get("result", {})
    canonical_raw = result.get("canonical")
    if not canonical_raw:
        raise HTTPException(status_code=404, detail="Canonical document not available for this task")

    # If the caller wants a stripped-down view, rebuild from the stored dict
    try:
        doc = _load_canonical_document(canonical_raw)
        return doc.to_dict(include_raw_payload=include_raw, include_ocr_lines=include_ocr_lines)
    except Exception as e:
        logger.warning(f"Task {task_id}: Failed to deserialise canonical doc, returning raw: {e}")
        return canonical_raw


class RemappingRequest(BaseModel):
    rules_path: str | None = None   # Optional override path to a YAML rules file
    doc_type_hint: str | None = None  # e.g. "invoice", "contract", "unknown"
    invalidate_cache: bool = False   # Force reload of cached rule set


@app.post("/api/v1/tasks/{task_id}/remapping")
async def remap_task_canonical(task_id: str, body: RemappingRequest):
    """
    Re-apply semantic mapping rules to a previously processed task without
    re-running OCR/layout.  Useful after editing semantic_mapping_base.yaml.
    Returns the updated canonical summary.
    """
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed (only completed tasks can be remapped)")

    result = task.get("result", {})
    canonical_raw = result.get("canonical")
    if not canonical_raw:
        raise HTTPException(status_code=404, detail="No canonical document stored for this task — run full analysis first")

    try:
        from app.services.canonical_converter import remap_canonical_doc, invalidate_rule_cache
        if body.invalidate_cache:
            invalidate_rule_cache()

        # remap_canonical_doc currently expects a serialised dict payload and
        # returns (updated_dict, changed_count).
        if isinstance(canonical_raw, dict):
            canonical_dict = canonical_raw
        else:
            canonical_dict = _load_canonical_document(canonical_raw).to_dict(include_raw_payload=True)

        current_taxonomy = str(canonical_dict.get("taxonomy_version", "azure-like-v1"))
        updated_canonical, changed_blocks = remap_canonical_doc(
            canonical_dict=canonical_dict,
            new_taxonomy_version=current_taxonomy,
            doc_type=body.doc_type_hint,
            rules_path=body.rules_path,
        )

        from app.models.canonical_document import CanonicalDocument
        updated_doc = CanonicalDocument.from_dict(updated_canonical)

        result["canonical"] = updated_canonical
        result["canonical_summary"] = updated_doc.summary()
        logger.info(
            f"Task {task_id}: Remapping completed | changed_blocks={changed_blocks} | "
            f"summary={updated_doc.summary()}"
        )
        return {
            "task_id": task_id,
            "status": "ok",
            "changed_blocks": changed_blocks,
            "canonical_summary": updated_doc.summary(),
        }
    except Exception as e:
        logger.error(f"Task {task_id}: Remapping failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Remapping failed: {str(e)}")


@app.get("/api/v1/tasks/{task_id}/layout")
async def get_unified_layout_analysis(task_id: str, page_number: int = 1):
    """
    获取统一格式的版面分析结果
    Returns unified layout analysis result in standard format
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
            # 返回空结果而不是错误
            from app.models.layout_result import LayoutAnalysisResult
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

            logger.info(f"[Layout API] ✓ Successfully analyzed layout with {len(unified_result.elements)} elements")
            return unified_result.to_dict()

        except Exception as e:
            logger.error(f"[Layout API] Error analyzing paddleocr result: {e}", exc_info=True)
            # Return empty result on conversion error
            from app.models.layout_result import LayoutAnalysisResult
            empty_result = LayoutAnalysisResult()
            return empty_result.to_dict()

    except Exception as e:
        logger.error(f"[Layout API] ❌ Error getting unified layout analysis: {e}", exc_info=True)
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
    """Return frontend-oriented flat blocks payload (blocks-only, no lines/words)."""
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")

    result = task.get("result", {}) or {}
    page_meta = (result.get("document_info", {}) or {}).get("page_image_meta", {}) or {}
    image_width = int(page_meta.get("width_px", 0) or 0)
    image_height = int(page_meta.get("height_px", 0) or 0)

    grouped_fields: Dict[str, List[str]] = {}
    entities_grouped = result.get("entities_grouped") or {}
    for key, values in entities_grouped.items():
        grouped_fields[str(key)] = [str(v) for v in values]

    blocks: List[Dict[str, Any]] = []
    semantic_blocks = result.get("semantic_text_blocks") or []
    if semantic_blocks:
        source_blocks = semantic_blocks
    elif result.get("layout", {}).get("elements"):
        source_blocks = result.get("layout", {}).get("elements", [])
    else:
        source_blocks = result.get("text_blocks", [])

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

        blocks.append(
            {
                "id": block.get("id") or block.get("block_id") or f"block_{idx}",
                "page": page,
                "role": role,
                "confidence": confidence,
                "score": confidence,
                "bbox": bbox,
                "text": text,
                "content": text,
                "content_truncated": text[:content_limit],
            }
        )

    return {
        "task_id": task_id,
        "page": page_number,
        "image_width": image_width,
        "image_height": image_height,
        "coord_space": page_meta.get("coord_space", "image_abs_px"),
        "grouped_fields": grouped_fields,
        "blocks": blocks,
    }



@app.get("/api/v1/tasks/{task_id}/page-image/{page_num}")
async def get_page_image(task_id: str, page_num: int = 1):
    """
    Convert PDF page to image for display.
    Returns the first page as PNG image for PDF files, or original image for image files.
    """
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

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
    if task["status"] != "completed":
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

    if status in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel task with status: {status}")

    # Set cancellation flag
    task_cancellation_flags[task_id] = True
    task["status"] = "cancelled"
    task["message"] = "Task cancelled by user"

    logger.info(f"Task cancelled: {task_id}")
    return {"message": "Task cancelled", "task_id": task_id}


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
# API Routes - NLP (P2)
# ============================================

@app.post("/api/v1/nlp/analyze")
async def analyze_text_nlp(request: NLPAnalysisRequest):
    """Analyze text for keywords and entities"""
    try:
        result = await call_maybe_async(
            nlp_service.analyze_text,
            request.text,
            top_k_keywords=request.top_k_keywords,
            engine=request.engine
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/nlp/keywords")
async def extract_keywords(request: NLPAnalysisRequest):
    """Extract keywords from text"""
    if not nlp_service:
        raise HTTPException(status_code=503, detail="NLP service is not available in PaddleOCR-only version")
    try:
        result = await call_maybe_async(
            nlp_service.extract_keywords,
            request.text,
            top_k=request.top_k_keywords,
            engine=request.engine
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/nlp/entities")
async def extract_entities(request: NLPAnalysisRequest):
    """Extract named entities from text"""
    if not nlp_service:
        raise HTTPException(status_code=503, detail="NLP service is not available in PaddleOCR-only version")
    try:
        result = await call_maybe_async(
            nlp_service.extract_entities,
            request.text,
            engine=request.engine
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# API Routes - Templates (P2)
# ============================================

@app.get("/api/v1/templates")
async def list_templates(category: Optional[str] = None):
    """List all available templates"""
    return {
        "templates": template_service.list_templates(category),
        "categories": ["financial", "identity", "contact", "legal", "custom"]
    }


@app.get("/api/v1/templates/{template_id}")
async def get_template(template_id: str):
    """Get template details"""
    template = template_service.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template.to_dict()


@app.post("/api/v1/templates")
async def create_template(template_data: CreateTemplateModel):
    """Create a custom template"""
    try:
        data = template_data.dict()
        data["fields"] = [{"name": f.name, "label": f.label, "field_type": f.field_type,
                          "required": f.required, "patterns": f.patterns,
                          "description": f.description} for f in template_data.fields]
        template = template_service.create_template(data)
        return template.to_dict()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/v1/templates/{template_id}")
async def delete_template(template_id: str):
    """Delete a custom template"""
    try:
        success = template_service.delete_template(template_id)
        if not success:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"message": "Template deleted", "template_id": template_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/templates/{template_id}/extract")
async def extract_with_template(template_id: str, text: str = Form(...)):
    """Extract fields using a specific template"""
    try:
        result = await call_maybe_async(template_service.extract_fields, template_id, text)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/templates/auto-extract")
async def auto_extract_template(text: str = Form(...)):
    """Auto-detect template and extract fields"""
    try:
        result = await call_maybe_async(template_service.auto_extract, text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/templates/match")
async def match_templates(text: str = Form(...)):
    """Match text against templates"""
    matches = template_service.match_template(text)
    return {
        "matches": [
            {"template_id": tid, "score": score}
            for tid, score in matches
        ]
    }


# ============================================
# API Routes - Batch Processing (P2)
# ============================================

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
    except:
        opts = {}

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

    async def process_file(file_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single file in the batch"""
        # Create a temporary task-like structure
        temp_task = {
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "options": options
        }

        result = {
            "document_info": {
                "file_name": temp_task["file_name"],
                "pages": 0,
                "processed_at": datetime.now().isoformat(),
                "page_image_meta": _build_page_image_meta(file_path, page_num=1),
            }
        }

        # OCR
        if options.get("enable_ocr", True):
            ocr_result = await call_maybe_async(
                ocr_service.recognize,
                file_path,
                language=options.get("language", "en"),
                engine=options.get("ocr_engine"),
                fallback=True
            )
            result["text_blocks"] = ocr_result["text_blocks"]
            result["document_info"]["pages"] = ocr_result["page_count"]
            result["full_text"] = ocr_result.get("full_text", "")

        # Layout
        if options.get("enable_layout", True):
            layout_result = await call_maybe_async(
                layout_service.analyze,
                file_path,
                engine=options.get("layout_engine"),
                fallback=True
            )
            result["layout"] = layout_result

        # Tables
        if options.get("enable_table", True):
            table_result = await call_maybe_async(
                table_service.extract,
                file_path,
                engine=options.get("table_engine"),
                fallback=True
            )
            result["tables"] = table_result

        # NLP
        if options.get("enable_nlp", True) and nlp_service:
            full_text = result.get("full_text", "")
            if full_text:
                nlp_result = await call_maybe_async(nlp_service.analyze_text, full_text)
                result["keywords"] = [kw["keyword"] for kw in nlp_result.get("keywords", [])]
                result["entities"] = nlp_result.get("entities", [])

        return result

    try:
        await batch_service.start_batch(batch_id, process_file)
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
        success = await batch_service.resume_batch(batch_id)
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


# ============================================
# Application Startup
# ============================================

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 60)
    logger.info("DocuVision - Intelligent Document Processing System v1.1")
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
    logger.info(f"P1 Features: OCR, Layout, Table, Export")
    logger.info(f"P2 Features: Template, Batch, NLP")
    logger.info("-" * 60)
    logger.info(f"OCR Engines: {ocr_service.get_available_engines()}")
    logger.info(f"Layout Engines: {layout_service.get_available_engines()}")
    logger.info(f"Table Engines: {table_service.get_available_engines()}")
    logger.info(f"NLP Engines: {nlp_service.get_available_engines() if nlp_service else 'N/A (disabled in PaddleOCR-only version)'}")
    logger.info(f"Templates: {len(template_service.templates)} available")
    logger.info("=" * 60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

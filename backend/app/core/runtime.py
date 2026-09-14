"""Shared runtime singletons, task state, and small helpers (v1.8.2 C1a).

Routers must not import ``app.main`` (import cycle), so everything a router
needs that used to live at ``main`` module scope is collected here:

- service singletons (ocr / layout / table / formula / seal / kie / export /
  batch / unified layout)
- task storage and WebSocket/event streaming state
- small helpers used by routes (health payload, KIE query-field bridging,
  model-id shortener)

This module is allowed to carry heavy dependencies (paddle-backed services): it
is the assembly-time runtime, **not** a leaf module. ``init_runtime()`` holds the
former import-time side effects so that ``import app.core.runtime`` itself does
no file/DB writes (SPLIT-U4).
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import os
from datetime import datetime
from importlib import metadata as _metadata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException, WebSocket
from loguru import logger

from app.core.config import settings
from app.core.debug_utils import save_debug_overlay_image
from app.orchestration.document_pipeline_orchestrator import DocumentPipelineOrchestrator
from app.services.batch_service import BatchService, BatchStatus
from app.services.export_service import ExportService
from app.services.formula_service import FormulaService
from app.services.kie_qwen_service import QwenDocumentKIEService
from app.services.layout_service import LayoutService
from app.services.ocr_service import OCRService
from app.services.persistence.analyze_job_store import analyze_job_store
from app.services.persistence.queue_store import SqliteQueueStore
from app.services.seal_service import SealService
from app.services.table_service import TableService
from app.services.unified_layout_service import UnifiedLayoutService


# ---------------------------------------------------------------------------
# Dependency version helpers (read dist metadata; never import the package).
# ---------------------------------------------------------------------------
def _get_dist_version(dist_names: List[str]) -> str:
    """Get installed package version without importing the package."""
    for name in dist_names:
        try:
            return _metadata.version(name)
        except Exception:
            continue
    return "0.0.0"


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

# Single source of truth for /health api_version and OpenAPI version (config.APP_VERSION).
API_VERSION = settings.APP_VERSION


def _short_public_model_id(model_id: str) -> str:
    """Last path segment or trimmed id for health payloads (no full host paths)."""
    s = (model_id or "").strip()
    if not s:
        return ""
    base = os.path.basename(s.rstrip("/\\"))
    return base if base else s[:96]


# ---------------------------------------------------------------------------
# GPU auto-detect + service singletons.
# ---------------------------------------------------------------------------
import paddle  # noqa: E402  (heavy import kept at runtime level by design)

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

export_service = ExportService()
batch_service = BatchService(max_concurrent=3)
unified_layout_service = UnifiedLayoutService()  # 统一的版面分析服务

# ---------------------------------------------------------------------------
# Task storage + WebSocket/event streaming state.
# ---------------------------------------------------------------------------
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


def init_runtime() -> None:
    """Wire the SQLite queue store into the batch / HITL / analyze-job singletons.

    Called from the app startup hook. Collects the former import-time side
    effects (main.py 339-341 + 365) and the second startup's queue rebuild
    (main.py 2627-2638), so that ``import app.core.runtime`` stays write-free
    (SPLIT-U4).
    """
    queue_store = SqliteQueueStore(db_path=Path(settings.SQLITE_DB_PATH))
    batch_service.attach_store(queue_store)
    analyze_job_store.attach_store(queue_store)
    analyze_job_store.bind(tasks)
    # Queue persistence: rebuild in-memory HITL + analyze-job indexes from SQLite.
    from app.services.hitl_queue import hitl_queue

    hitl_queue.attach_store(queue_store)
    hitl_queue.load_from_db()
    batch_service.load_from_db()
    analyze_job_store.load_from_db()


# ---------------------------------------------------------------------------
# Route helpers.
# ---------------------------------------------------------------------------
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

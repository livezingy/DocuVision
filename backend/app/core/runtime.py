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

import os
from datetime import datetime
from importlib import metadata as _metadata
from pathlib import Path
from typing import Any, Dict, List, Set

from fastapi import HTTPException, WebSocket
from loguru import logger

from app.core.config import settings
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

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

from fastapi import Body, FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form, Path as APIPath, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from typing import List, Optional, Dict, Any, Set
import uuid
import shutil
from datetime import datetime
from loguru import logger
from pathlib import Path





# _build_page_image_meta moved to app.core.runtime (v1.8.2 C1c).


# 继续导入其他模块
from io import BytesIO
import json
import asyncio

from app.services.pack_export_service import PackTooLargeError, build_task_pack_zip
from app.services.batch_service import BatchStatus
from app.services.batch_export_service import (
    build_batch_xlsx_bytes,
    build_failure_csv_rows,
    build_json_bundle,
    build_kie_csv_rows,
    build_summary_csv_rows,
    render_csv,
)
from app.services.single_file_pipeline import run_single_file_pipeline
from app.core.config import settings
from app.core.debug_utils import save_debug_overlay_image

# Shared runtime (services / state / helpers) + API models extracted for the
# v1.8.2 main.py split (C1a). Imported here — after env/paddle setup — so the
# heavy service singletons are still built once, at the same point in startup.
from app.core.runtime import (  # noqa: E402
    API_VERSION,
    _DEP_VERSIONS,
    _build_health_payload,
    _build_page_image_meta,
    _enforce_max_upload_size,
    _get_dist_version,
    _raise_query_fields_http,
    _resolve_kie_query_fields_in_options,
    _send_event,
    _short_public_model_id,
    batch_service,
    call_maybe_async,
    export_service,
    formula_service,
    init_runtime,
    kie_service,
    layout_service,
    ocr_service,
    process_document,
    seal_service,
    table_service,
    task_cancellation_flags,
    task_event_counters,
    task_event_history,
    task_websockets,
    tasks,
    unified_layout_service,
    use_gpu,
)
from app.models.api_models import (  # noqa: E402
    BatchCreateModel,
    FusedBlock,
    FusedLayer,
    FusedPage,
    HitlResolveModel,
    KieFieldsPatchModel,
    PreprocessingMetadata,
    ProcessingOptions,
    QualityLayer,
    RawLayer,
    TaskStatus,
    TrialGtDiffModel,
    ViewContent,
    ViewElement,
    ViewLayer,
    ViewPage,
)

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

# Service singletons + GPU detection moved to app.core.runtime (v1.8.2 split).


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
# Module-level state (services / tasks / streaming) moved to app.core.runtime (v1.8.2 split).

logger.info(
    "Startup strategy | layout=ppstructure(layout-only optional engines off) | table_mode={} | table_fullpage_fallback={} | formula_mode=independent_lazy_roi | seal_mode=independent_lazy",
    "layout_first",
    settings.TABLE_ALLOW_FULLPAGE_FALLBACK,
)


# ============================================
# API models moved to app.models.api_models (v1.8.2 split, C1a).
# ============================================





# ============================================
# API Routes - Core (P1)
# ============================================

# _enforce_max_upload_size moved to app.core.runtime (v1.8.2 C1c).


# System routes (/, /health, /api/v1/health, /api/v1/engines) moved to
# app.routers.system (v1.8.2 C1b).


# Analyzer routes (/api/v1/ocr, /api/v1/upload, /api/v1/analyze) moved to
# app.routers.analyzer (v1.8.2 C1c).





# _send_event / call_maybe_async / process_document moved to app.core.runtime (v1.8.2 C1c).


# ============================================
# Phase 1 API Routes - Job-Based Endpoints
# ============================================

# documents:analyze + jobs routes moved to app.routers.documents / app.routers.jobs
# (v1.8.2 C1d/C1e).


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
async def export_result(task_id: str, format: str, include: str = ""):
    """Export results in various formats.

    ``format=zip`` builds a tables + figures artifact pack. Optional
    ``include`` is a comma list: ``tables``, ``figures``, ``json``
    (default ``tables,figures``).
    """
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
        elif format == "zip":
            zip_path = await build_task_pack_zip(result, task_id, include=include)
            return FileResponse(
                zip_path,
                filename=f"{task_id}_pack.zip",
                media_type="application/zip",
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
    except PackTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
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

    from app.services.persistence.analyze_job_store import persist_task_safe

    await persist_task_safe(task)

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
    from app.services.persistence.analyze_job_store import persist_task_safe

    await persist_task_safe(task)
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

    from app.services.persistence.analyze_job_store import delete_task_safe

    delete_task_safe(task_id)
    tasks.pop(task_id, None)
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

# document/profile moved to app.routers.documents (v1.8.2 C1d).


@app.get("/api/v1/kie/templates")
async def list_kie_templates():
    from app.services.kie.schema_templates import list_templates

    return {"templates": list_templates()}


@app.get("/api/v1/kie/templates/{template_id}")
async def get_kie_template(
    template_id: str = APIPath(..., pattern=r"^[A-Za-z0-9_-]+$"),
):
    from app.services.kie.schema_templates import load_template

    schema = load_template(template_id)
    if not schema:
        raise HTTPException(status_code=404, detail="Template not found")
    return schema


@app.post("/api/v1/kie/templates/{template_id}")
async def save_kie_template(
    template_id: str = APIPath(..., pattern=r"^[A-Za-z0-9_-]+$"),
    body: Dict[str, Any] = Body(...),
):
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
# Router registration (v1.8.2 split — include order pinned)
# ============================================
from app.routers.analyzer import router as analyzer_router  # noqa: E402
from app.routers.documents import router as documents_router  # noqa: E402
from app.routers.jobs import router as jobs_router  # noqa: E402
from app.routers.system import router as system_router  # noqa: E402

routers_to_include = [
    system_router,
    analyzer_router,
    documents_router,
    jobs_router,
]
for _router in routers_to_include:
    app.include_router(_router)


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
    # Queue persistence: rebuild in-memory batch + HITL + analyze-job indexes.
    try:
        init_runtime()
    except Exception as exc:
        logger.warning("Queue persistence load failed (non-fatal): {}", exc)
    logger.info("=" * 60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

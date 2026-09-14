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

from fastapi import Body, FastAPI, UploadFile, File, HTTPException, Form, Path as APIPath, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from typing import List, Optional, Dict, Any, Set
import uuid
from datetime import datetime
from loguru import logger
from pathlib import Path





# _build_page_image_meta moved to app.core.runtime (v1.8.2 C1c).


# 继续导入其他模块
from io import BytesIO
import asyncio

from app.core.config import settings

# Shared runtime (services / state / helpers) + API models extracted for the
# v1.8.2 main.py split (C1a). Imported here — after env/paddle setup — so the
# heavy service singletons are still built once, at the same point in startup.
from app.core.runtime import (  # noqa: E402
    API_VERSION,
    _DEP_VERSIONS,
    _apply_kie_fields_to_task,
    _build_page_image_meta,
    _enforce_max_upload_size,
    _raise_query_fields_http,
    _resolve_kie_query_fields_in_options,
    batch_service,
    call_maybe_async,
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
)
from app.models.api_models import (  # noqa: E402
    BatchCreateModel,
    FusedBlock,
    FusedLayer,
    FusedPage,
    HitlResolveModel,
    PreprocessingMetadata,
    ProcessingOptions,
    QualityLayer,
    RawLayer,
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

# Task lifecycle routes (status / events / ws) moved to app.routers.tasks (v1.8.2 C2).


# Task result + layout routes moved to app.routers.tasks_content (v1.8.2 C2).


# _normalize_flat_bbox + blocks route moved to app.routers.tasks_content (v1.8.2 C2).



# Figures + trial routes moved to app.routers.tasks_content / app.routers.trial (v1.8.2 C2).


# page-image + export routes moved to app.routers.tasks_content (v1.8.2 C2).


# cancel / kie-fields / delete routes moved to app.routers.tasks;
# _apply_kie_fields_to_task moved to app.core.runtime (v1.8.2 C2).


# ============================================
# API Routes - Batch Processing (P2)
# ============================================

# Batch management routes + helpers (_pipeline_services / _batch_process_file)
# moved to app.routers.batch; batch export routes moved to
# app.routers.batch_export (v1.8.2 C3).


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
from app.routers.batch import router as batch_router  # noqa: E402
from app.routers.batch_export import router as batch_export_router  # noqa: E402
from app.routers.documents import router as documents_router  # noqa: E402
from app.routers.jobs import router as jobs_router  # noqa: E402
from app.routers.system import router as system_router  # noqa: E402
from app.routers.tasks import router as tasks_router  # noqa: E402
from app.routers.tasks_content import router as tasks_content_router  # noqa: E402
from app.routers.trial import router as trial_router  # noqa: E402

routers_to_include = [
    system_router,
    analyzer_router,
    documents_router,
    jobs_router,
    tasks_router,
    trial_router,
    tasks_content_router,
    batch_router,
    batch_export_router,
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

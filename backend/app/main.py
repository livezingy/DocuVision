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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pathlib import Path





# 继续导入其他模块
import asyncio

from app.core.config import settings

# Shared runtime (services / state / helpers) extracted for the v1.8.2 main.py
# split (C1a). Imported here — after env/paddle setup — so the heavy service
# singletons are still built once, at the same point in startup.
from app.core.runtime import (  # noqa: E402
    API_VERSION,
    _DEP_VERSIONS,
    init_runtime,
    kie_service,
    layout_service,
    ocr_service,
    table_service,
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

# Service singletons / GPU detection / module-level state live in
# app.core.runtime (v1.8.2 split).

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


logger.info(
    "Startup strategy | layout=ppstructure(layout-only optional engines off) | table_mode={} | table_fullpage_fallback={} | formula_mode=independent_lazy_roi | seal_mode=independent_lazy",
    "layout_first",
    settings.TABLE_ALLOW_FULLPAGE_FALLBACK,
)


# ============================================
# API routes
# ============================================
# API models live in app.models.api_models; all 55 routes moved to
# app.routers.* (v1.8.2 C1-C4). Include order is pinned in the router
# registration table below.

# ============================================
# Router registration (v1.8.2 split — include order pinned)
# ============================================
from app.routers.analyzer import router as analyzer_router  # noqa: E402
from app.routers.batch import router as batch_router  # noqa: E402
from app.routers.batch_export import router as batch_export_router  # noqa: E402
from app.routers.documents import router as documents_router  # noqa: E402
from app.routers.hitl import router as hitl_router  # noqa: E402
from app.routers.jobs import router as jobs_router  # noqa: E402
from app.routers.kie import router as kie_router  # noqa: E402
from app.routers.pdftools import router as pdftools_router  # noqa: E402
from app.routers.system import router as system_router  # noqa: E402
from app.routers.tasks import router as tasks_router  # noqa: E402
from app.routers.tasks_content import router as tasks_content_router  # noqa: E402
from app.routers.trial import router as trial_router  # noqa: E402
from app.routers.webhooks import router as webhooks_router  # noqa: E402

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
    kie_router,
    hitl_router,
    webhooks_router,
    pdftools_router,
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

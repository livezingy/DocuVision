"""
DocuVision Lite — FastAPI entry point.

No Paddle / Qwen imports. CPU-friendly table and OCR API.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes_analyze import router as analyze_router
from app.api.routes_extract import router as extract_router
from app.api.routes_health import router as health_router
from app.api.routes_jobs import router as jobs_router
from app.core.config import settings
from app.schemas.lite_result import LITE_API_VERSION

app = FastAPI(
    title="DocuVision Lite API",
    description="CPU-friendly document table extraction and OCR (Lite tier)",
    version=LITE_API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1/lite")
app.include_router(analyze_router, prefix="/api/v1/lite")
app.include_router(extract_router, prefix="/api/v1/lite")
app.include_router(jobs_router, prefix="/api/v1/lite")

_frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
_shared_dir = Path(__file__).resolve().parents[4] / "frontend" / "shared"
if _frontend_dir.exists():
    app.mount("/lite", StaticFiles(directory=str(_frontend_dir), html=True), name="lite-frontend")
if _shared_dir.exists():
    app.mount("/shared", StaticFiles(directory=str(_shared_dir)), name="shared-frontend")


@app.get("/", tags=["root"])
def root() -> dict:
    return {
        "service": "docuvision-lite",
        "api_version": LITE_API_VERSION,
        "docs": "/docs",
        "health": "/api/v1/lite/health",
        "ui": "/lite/lite.html" if _frontend_dir.exists() else None,
    }

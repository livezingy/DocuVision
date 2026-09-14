"""System routes: /, /health, /api/v1/health, /api/v1/engines.

Moved verbatim from main.py (v1.8.2 C1b). No ``prefix`` on the APIRouter —
paths are written in full so the OpenAPI contract is unchanged.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.runtime import (
    API_VERSION,
    _build_health_payload,
    layout_service,
    ocr_service,
    seal_service,
    table_service,
)

router = APIRouter()


@router.get("/")
async def root():
    return {
        "name": "DocuVision API",
        "version": API_VERSION,
        "status": "running",
        "features": ["OCR/Layout/Table/Export", "Batch Processing"],
        "docs": "/docs"
    }


@router.get("/health")
async def health_check():
    return _build_health_payload()


@router.get("/api/v1/health")
async def health_check_v1():
    """Same payload as GET /health; use behind reverse proxies that only forward /api/v1/*."""
    return _build_health_payload()


@router.get("/api/v1/engines")
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

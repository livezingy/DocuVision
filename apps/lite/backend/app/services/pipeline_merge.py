"""Merge Lite pipeline outputs for scan/image documents."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _empty_scan_image_result(detected: Any, page_count: int) -> Dict[str, Any]:
    return {
        "tables": [],
        "ocr": [],
        "text_preview": None,
        "routing": {"engine_used": "none", "mode": "smart"},
        "quality": {
            "overall_confidence": 0.0,
            "tables_found": 0,
            "tables_accepted": 0,
            "ocr_blocks": 0,
            "pages_processed": 0,
        },
        "warnings": [],
        "detected_file_type": detected,
        "page_count": page_count,
    }


def merge_pipeline_outputs(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    merged["tables"] = list(base.get("tables") or []) + list(extra.get("tables") or [])
    merged["ocr"] = list(base.get("ocr") or []) + list(extra.get("ocr") or [])

    if extra.get("text_preview"):
        merged["text_preview"] = extra["text_preview"]
    elif not merged.get("text_preview"):
        merged["text_preview"] = base.get("text_preview")

    merged["warnings"] = list(base.get("warnings") or []) + list(extra.get("warnings") or [])

    for key in ("routing", "quality"):
        if extra.get(key):
            merged[key] = {**(merged.get(key) or {}), **extra[key]}

    if extra.get("detected_file_type"):
        merged["detected_file_type"] = extra["detected_file_type"]
    if extra.get("page_count"):
        merged["page_count"] = extra["page_count"]
    return merged

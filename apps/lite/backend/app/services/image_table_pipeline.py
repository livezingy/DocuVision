"""Image table extraction via Table Transformer (docuvision_core TableParser)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from app.schemas.lite_result import ExtractMode, WarningCode
from app.services.file_detector import detect_file_type


def _transformer_available() -> bool:
    import importlib.util

    return (
        importlib.util.find_spec("torch") is not None
        and importlib.util.find_spec("transformers") is not None
    )


def _parser_tables_to_lite(tables: List[Dict[str, Any]], page: int = 1) -> List[Dict[str, Any]]:
    lite_tables: List[Dict[str, Any]] = []
    for idx, table in enumerate(tables):
        columns = table.get("columns") or []
        data = table.get("data") or []
        headers: List[str] = []
        rows: List[List[str]] = []

        if data and isinstance(data[0], dict):
            headers = [str(c) for c in columns] if columns else [str(k) for k in data[0].keys()]
            rows = [[str(row.get(h, "")) for h in headers] for row in data]
        elif data and isinstance(data[0], (list, tuple)):
            rows = [[str(c) for c in row] for row in data]
            if columns:
                headers = [str(c) for c in columns]

        bbox_raw = table.get("bbox") or []
        bbox = [float(v) for v in bbox_raw] if bbox_raw else []

        lite_tables.append(
            {
                "table_id": f"t{idx}_p{page}",
                "page": page,
                "index_on_page": idx,
                "bbox": bbox,
                "row_count": len(rows),
                "col_count": len(rows[0]) if rows else 0,
                "score": float(table.get("score") or table.get("confidence") or 0.0),
                "source": "transformer",
                "headers": headers,
                "rows": rows,
                "details": {
                    "domain": "image",
                    "empty_cells": 0,
                    "merged_cells_detected": False,
                },
            }
        )
    return lite_tables


async def _run_transformer_parser(image: Image.Image) -> Dict[str, Any]:
    from docuvision_core.models.table_parser import TableParser
    from docuvision_core.utils.config import load_config

    app_config = load_config()
    parser = TableParser(app_config)
    if parser.models is None:
        raise RuntimeError("Table Transformer models failed to initialize")
    return await parser.parser_image(image)


def extract_tables_from_image(
    file_path: Path,
    *,
    mode: ExtractMode = ExtractMode.SMART,
    score_threshold: float = 0.5,
) -> Dict[str, Any]:
    if not _transformer_available():
        raise RuntimeError(
            "Table Transformer requires torch and transformers. "
            "Install: pip install 'docuvision-core[ocr-heavy]'"
        )

    detected_type, page_count = detect_file_type(file_path)
    if detected_type.value not in {"image", "pdf_scan"}:
        raise ValueError("Transformer table extraction requires an image or scanned document")

    image = Image.open(file_path).convert("RGB")
    try:
        parser_result = asyncio.run(_run_transformer_parser(image))
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Transformer table extraction failed: {exc}") from exc

    if not parser_result.get("success"):
        error = parser_result.get("error") or "Transformer table extraction failed"
        raise RuntimeError(str(error))

    raw_tables = parser_result.get("tables") or []
    all_tables = _parser_tables_to_lite(raw_tables, page=1)
    all_tables = [t for t in all_tables if float(t.get("score") or 0.0) >= score_threshold]

    warnings: List[Dict[str, Any]] = []
    if not all_tables:
        warnings.append(
            {
                "code": WarningCode.ENGINE_FALLBACK.value,
                "message": "No tables detected in the image with Table Transformer.",
            }
        )

    scores = [t["score"] for t in all_tables if t.get("score") is not None]
    overall = sum(scores) / len(scores) if scores else 0.0

    return {
        "tables": all_tables,
        "text_preview": None,
        "ocr": [],
        "routing": {
            "mode": mode.value if hasattr(mode, "value") else mode,
            "requested_engine": "transformer",
            "engine_used": "transformer",
            "engine_chain": ["transformer"],
            "table_type_detected": "image",
            "flavor_used": "detection+structure",
            "param_mode": "auto",
            "profile": "cpu",
        },
        "quality": {
            "overall_confidence": overall,
            "tables_found": len(all_tables),
            "tables_accepted": len(all_tables),
            "pages_processed": 1,
            "pages_with_tables": 1 if all_tables else 0,
            "ocr_blocks": 0,
            "processing_profile": "cpu",
        },
        "warnings": warnings,
        "page_count": page_count,
        "detected_file_type": detected_type,
    }

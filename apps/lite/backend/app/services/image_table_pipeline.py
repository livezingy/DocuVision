"""Image table extraction via Table Transformer (docuvision_core TableParser)."""

from __future__ import annotations

import asyncio
import concurrent.futures
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from app.schemas.lite_result import ExtractMode, WarningCode
from app.services.file_detector import detect_file_type
from app.services.page_utils import load_raster_pages


def _transformer_available() -> bool:
    import importlib.util

    return (
        importlib.util.find_spec("torch") is not None
        and importlib.util.find_spec("transformers") is not None
    )


def _parser_tables_to_lite(
    tables: List[Dict[str, Any]],
    *,
    page: int = 1,
    domain: str = "image",
) -> List[Dict[str, Any]]:
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
                    "domain": domain,
                    "empty_cells": 0,
                    "merged_cells_detected": False,
                },
            }
        )
    return lite_tables


async def _run_transformer_parser(
    image: Image.Image,
    *,
    table_ocr_engine: Optional[str] = None,
    table_ocr_languages: Optional[List[str]] = None,
) -> Dict[str, Any]:
    from docuvision_core.models.table_parser import TableParser
    from docuvision_core.utils.config import load_config

    app_config = load_config()
    parser_cfg = dict(app_config.get("table_parser") or {})
    if table_ocr_engine:
        parser_cfg["table_ocr_engine"] = table_ocr_engine
    if table_ocr_languages:
        parser_cfg["table_ocr_languages"] = table_ocr_languages
    app_config = {**app_config, "table_parser": parser_cfg}

    parser = TableParser(app_config)
    if parser.models is None:
        raise RuntimeError("Table Transformer models failed to initialize")
    return await parser.parser_image(image)


def _run_transformer_in_thread(
    image: Image.Image,
    *,
    table_ocr_engine: Optional[str] = None,
    table_ocr_languages: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run async parser in a worker thread (safe when caller has a running event loop)."""
    return asyncio.run(
        _run_transformer_parser(
            image,
            table_ocr_engine=table_ocr_engine,
            table_ocr_languages=table_ocr_languages,
        )
    )


def extract_tables_from_image(
    file_path: Path,
    *,
    mode: ExtractMode = ExtractMode.SMART,
    score_threshold: float = 0.5,
    pages_spec: Optional[str] = None,
    max_pages: int = 10,
    table_ocr_engine: Optional[str] = None,
    table_ocr_languages: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if not _transformer_available():
        raise RuntimeError(
            "Table Transformer requires torch and transformers. "
            "Install: pip install 'docuvision-core[ocr-heavy]'"
        )

    detected_type, page_count = detect_file_type(file_path)
    if detected_type.value not in {"image", "pdf_scan"}:
        raise ValueError("Transformer table extraction requires an image or scanned document")

    domain = "scan" if detected_type.value == "pdf_scan" else "image"
    page_images = load_raster_pages(
        file_path,
        page_count=page_count,
        pages_spec=pages_spec if detected_type.value == "pdf_scan" else None,
        max_pages=max_pages,
    )

    all_tables: List[Dict[str, Any]] = []
    pages_with_tables = 0

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            for page_num, image in page_images:
                parser_result = executor.submit(
                    _run_transformer_in_thread,
                    image,
                    table_ocr_engine=table_ocr_engine,
                    table_ocr_languages=table_ocr_languages,
                ).result()
                if not parser_result.get("success"):
                    error = parser_result.get("error") or "Transformer table extraction failed"
                    raise RuntimeError(str(error))
                raw_tables = parser_result.get("tables") or []
                page_tables = _parser_tables_to_lite(raw_tables, page=page_num, domain=domain)
                page_tables = [t for t in page_tables if float(t.get("score") or 0.0) >= score_threshold]
                if page_tables:
                    pages_with_tables += 1
                all_tables.extend(page_tables)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Transformer table extraction failed: {exc}") from exc

    warnings: List[Dict[str, Any]] = []
    if not all_tables:
        warnings.append(
            {
                "code": WarningCode.ENGINE_FALLBACK.value,
                "message": "No tables detected with Table Transformer.",
            }
        )
    if detected_type.value == "pdf_scan" and len(page_images) >= max_pages:
        warnings.append(
            {
                "code": WarningCode.PAGE_TRUNCATED.value,
                "message": f"Rasterized at most {max_pages} page(s) for Transformer table extraction.",
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
            "table_type_detected": detected_type.value,
            "flavor_used": "detection+structure",
            "param_mode": "auto",
            "profile": "cpu",
        },
        "quality": {
            "overall_confidence": overall,
            "tables_found": len(all_tables),
            "tables_accepted": len(all_tables),
            "pages_processed": len(page_images),
            "pages_with_tables": pages_with_tables,
            "ocr_blocks": 0,
            "processing_profile": "cpu",
        },
        "warnings": warnings,
        "page_count": page_count,
        "detected_file_type": detected_type,
    }

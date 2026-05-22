"""PDF table extraction pipeline using docuvision_core."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber

from docuvision_core.processing.table_processor import TableProcessor

from app.schemas.lite_result import ExtractMode, WarningCode
from app.services.file_detector import detect_file_type
from app.services.result_mapper import raw_results_to_lite_tables


def _parse_pages_spec(pages_spec: Optional[str], page_count: int) -> List[int]:
    if not pages_spec or pages_spec.strip().lower() == "all":
        return list(range(1, page_count + 1))
    selected: List[int] = []
    for part in pages_spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            selected.extend(range(start, end + 1))
        else:
            selected.append(int(part))
    return sorted({p for p in selected if 1 <= p <= page_count})


def _resolve_table_method(mode: ExtractMode, engine: str) -> Tuple[str, str, List[str]]:
    engine = (engine or "auto").lower()
    chain: List[str] = []

    if mode == ExtractMode.SMART or engine == "auto":
        chain = ["pdfplumber", "camelot"]
        return "mixed", "auto", chain

    if engine == "pdfplumber":
        return "pdfplumber", "auto", ["pdfplumber"]
    if engine == "camelot":
        return "camelot", "auto", ["camelot"]
    raise ValueError(f"Unsupported table engine: {engine}")


def extract_tables_from_pdf(
    file_path: Path,
    *,
    mode: ExtractMode = ExtractMode.SMART,
    engine: str = "auto",
    flavor: str = "auto",
    pages_spec: Optional[str] = None,
    score_threshold: float = 0.5,
    max_pages: int = 50,
) -> Dict[str, Any]:
    detected_type, page_count = detect_file_type(file_path)
    if detected_type.value != "pdf_digital":
        raise ValueError("Table extraction requires a digital PDF with extractable text")

    page_count = min(page_count, max_pages)
    page_numbers = _parse_pages_spec(pages_spec, page_count)

    table_method, resolved_flavor, engine_chain = _resolve_table_method(mode, engine)
    if flavor and flavor != "auto":
        resolved_flavor = flavor

    processor_params = {
        "table_method": table_method,
        "table_flavor": None if resolved_flavor == "auto" else resolved_flavor,
        "table_score_threshold": score_threshold,
    }
    processor = TableProcessor(processor_params)

    all_tables: List[Dict[str, Any]] = []
    engine_used = ""
    flavor_used = resolved_flavor
    table_type_detected = "unknown"
    warnings: List[Dict[str, Any]] = []

    with pdfplumber.open(str(file_path)) as pdf:
        for page_num in page_numbers:
            page = pdf.pages[page_num - 1]
            try:
                from docuvision_core.processing.table_processor import PageFeatureAnalyzer

                analyzer = PageFeatureAnalyzer(page, enable_logging=False)
                table_type_detected = analyzer.predict_table_type()
            except Exception:
                pass

            raw = processor.process_pdf_page(str(file_path), page)
            if raw and not engine_used:
                engine_used = str(raw[0].get("source", "")).split("_")[0] or table_method
                if resolved_flavor == "auto":
                    flavor_used = str(raw[0].get("source", "")).split("_")[-1] if raw else "auto"

            mapped = raw_results_to_lite_tables(raw, page=page_num)
            all_tables.extend(mapped)

    if not all_tables and len(engine_chain) > 1:
        warnings.append(
            {
                "code": WarningCode.ENGINE_FALLBACK.value,
                "message": "Primary extraction returned no tables; try advanced engine settings.",
            }
        )

    scores = [t["score"] for t in all_tables if t.get("score") is not None]
    overall = sum(scores) / len(scores) if scores else 0.0
    pages_with_tables = len({t["page"] for t in all_tables})

    return {
        "tables": all_tables,
        "routing": {
            "mode": mode.value if hasattr(mode, "value") else mode,
            "requested_engine": engine,
            "engine_used": engine_used or table_method,
            "engine_chain": engine_chain,
            "table_type_detected": table_type_detected,
            "flavor_used": flavor_used,
            "param_mode": "auto",
            "profile": "cpu",
        },
        "quality": {
            "overall_confidence": overall,
            "tables_found": len(all_tables),
            "tables_accepted": len(all_tables),
            "pages_processed": len(page_numbers),
            "pages_with_tables": pages_with_tables,
            "ocr_blocks": 0,
            "processing_profile": "cpu",
        },
        "warnings": warnings,
        "page_count": page_count,
        "detected_file_type": detected_type,
    }

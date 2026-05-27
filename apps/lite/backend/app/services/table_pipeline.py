"""PDF table extraction pipeline using docuvision_core."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber

from docuvision_core.processing.table_processor import TableProcessor

from app.schemas.lite_result import ExtractMode, WarningCode
from app.services.file_detector import detect_file_type
from app.services.result_mapper import raw_results_to_lite_tables

TEXT_PREVIEW_MAX_CHARS = 8000


def _build_page_text_preview(pages: List[Any]) -> Optional[str]:
    from docuvision_core.utils.pdf_text_utils import sanitize_pdf_text

    parts: List[str] = []
    for page in pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        cleaned = sanitize_pdf_text(text)
        if cleaned:
            parts.append(cleaned)
    if not parts:
        return None
    preview = "\n\n".join(parts)
    if len(preview) > TEXT_PREVIEW_MAX_CHARS:
        return preview[:TEXT_PREVIEW_MAX_CHARS]
    return preview


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


def _parse_custom_params(custom_params: Optional[str]) -> Dict[str, Any]:
    if not custom_params or not custom_params.strip():
        return {}
    try:
        parsed = json.loads(custom_params)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid custom_params JSON: {exc}") from exc


def _build_processor_params(
    table_method: str,
    resolved_flavor: str,
    score_threshold: float,
    param_mode: str,
    custom: Dict[str, Any],
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "table_method": table_method,
        "table_flavor": None if resolved_flavor == "auto" else resolved_flavor,
        "table_score_threshold": score_threshold,
    }
    if param_mode == "custom":
        params["pdfplumber_param_mode"] = "custom"
        params["camelot_lattice_param_mode"] = "custom"
        params["camelot_stream_param_mode"] = "custom"
        if custom.get("pdfplumber"):
            params["pdfplumber_custom_params"] = custom["pdfplumber"]
        elif custom.get("pdfplumber_bordered"):
            params["pdfplumber_custom_params"] = custom["pdfplumber_bordered"]
        if custom.get("pdfplumber_unbordered"):
            params["pdfplumber_unbordered_custom_params"] = custom["pdfplumber_unbordered"]
        if custom.get("camelot_lattice"):
            params["camelot_lattice_custom_params"] = custom["camelot_lattice"]
        if custom.get("camelot_stream"):
            params["camelot_stream_custom_params"] = custom["camelot_stream"]
    return params


def extract_tables_from_pdf(
    file_path: Path,
    *,
    mode: ExtractMode = ExtractMode.SMART,
    engine: str = "auto",
    flavor: str = "auto",
    pages_spec: Optional[str] = None,
    score_threshold: float = 0.5,
    param_mode: str = "auto",
    custom_params: Optional[str] = None,
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

    custom = _parse_custom_params(custom_params)

    processor_params = _build_processor_params(
        table_method, resolved_flavor, score_threshold, param_mode, custom
    )
    processor = TableProcessor(processor_params)

    all_tables: List[Dict[str, Any]] = []
    engine_used = ""
    flavor_used = resolved_flavor
    table_type_detected = "unknown"
    warnings: List[Dict[str, Any]] = []

    text_preview: Optional[str] = None
    with pdfplumber.open(str(file_path)) as pdf:
        preview_pages = [pdf.pages[p - 1] for p in page_numbers]
        text_preview = _build_page_text_preview(preview_pages)
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

    sources_used = sorted({str(t.get("source", "")) for t in all_tables if t.get("source")})
    engines_used = sorted({s.split("_")[0] for s in sources_used if s})
    if table_method == "mixed" and engines_used:
        engine_used_label = f"smart ({'+'.join(engines_used)})"
        flavor_used_label = ", ".join(s.replace("_", " · ") for s in sources_used) or flavor_used
    elif sources_used:
        engine_used_label = sources_used[0].split("_")[0]
        flavor_used_label = sources_used[0].replace("_", " · ")
    else:
        engine_used_label = engine_used or table_method
        flavor_used_label = flavor_used

    return {
        "tables": all_tables,
        "text_preview": text_preview,
        "routing": {
            "mode": mode.value if hasattr(mode, "value") else mode,
            "requested_engine": engine,
            "engine_used": engine_used_label,
            "engine_chain": sources_used if sources_used else engine_chain,
            "table_type_detected": table_type_detected,
            "flavor_used": flavor_used_label,
            "param_mode": param_mode,
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

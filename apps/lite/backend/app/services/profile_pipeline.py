"""Lightweight document profile analysis for Lite UI."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

import pdfplumber

from app.services.engine_probe import probe_engine_availability
from app.core.config import settings
from app.schemas.lite_result import (
    DetectedFileType,
    LiteClassificationDetail,
    LiteComputedParams,
    LiteDocumentProfile,
    LiteInputMeta,
    LitePageProfile,
    LiteScanProfile,
    LiteSuggestedRouting,
    LiteTypographySummary,
    LiteWarning,
    Severity,
    WarningCode,
)
from app.services.file_detector import detect_file_type


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _json_safe_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """Drop non-JSON-serializable values from extractor params."""
    safe: Dict[str, Any] = {}
    for key, value in params.items():
        try:
            json.dumps(value)
            safe[key] = value
        except (TypeError, ValueError):
            continue
    return safe


def _suggested_routing(table_type: str) -> LiteSuggestedRouting:
    if table_type == "bordered":
        return LiteSuggestedRouting(engine="camelot", flavor="lattice", param_mode="auto")
    return LiteSuggestedRouting(engine="pdfplumber", flavor="text", param_mode="auto")


def _analyze_pdf_page(page, page_num: int) -> LitePageProfile:
    from docuvision_core.processing.table_processor import PageFeatureAnalyzer

    analyzer = PageFeatureAnalyzer(page, enable_logging=False)
    classification = analyzer.classify_table_type()

    char = analyzer.char_analysis
    text_lines = analyzer.text_line_analysis

    image_shape = None
    try:
        img = page.to_image(resolution=150)
        image_shape = img.original.size
    except Exception:
        pass

    table_type = classification["table_type"]
    return LitePageProfile(
        page=page_num,
        table_type=table_type,
        table_type_score=round(classification["score"], 4),
        classification_detail=LiteClassificationDetail(
            method=classification["method"],
            h_lines=classification["h_lines"],
            v_lines=classification["v_lines"],
            line_concentration=classification.get("line_concentration"),
            area_ratio=classification.get("area_ratio"),
            direction_balance=classification.get("direction_balance"),
        ),
        typography_summary=LiteTypographySummary(
            mode_char_width_pt=round(float(char.get("mode_width") or 0), 2),
            mode_char_height_pt=round(float(char.get("mode_height") or 0), 2),
            mode_line_height_pt=round(float(text_lines.get("mode_line_height") or 0), 2),
            mode_line_spacing_pt=round(float(text_lines.get("mode_line_spacing") or 0), 2),
            total_lines=int(text_lines.get("total_lines") or 0),
            total_chars=int(char.get("total_chars") or 0),
        ),
        suggested_routing=_suggested_routing(table_type),
        computed_params=LiteComputedParams(
            camelot_lattice=_json_safe_params(analyzer.get_camelot_lattice_params(image_shape)),
            camelot_stream=_json_safe_params(analyzer.get_camelot_stream_params()),
            pdfplumber_bordered=_json_safe_params(analyzer.get_pdfplumber_params("bordered")),
            pdfplumber_unbordered=_json_safe_params(analyzer.get_pdfplumber_params("unbordered")),
        ),
    )


def _build_scan_profile(detected: DetectedFileType) -> LiteScanProfile:
    engines = probe_engine_availability()
    tesseract_ok = engines.get("tesseract") and engines["tesseract"].available
    easyocr_ok = engines.get("easyocr") and engines["easyocr"].available
    transformer_ok = engines.get("transformer") and engines["transformer"].available

    if easyocr_ok:
        recommended = "easyocr"
    elif tesseract_ok:
        recommended = "tesseract"
    else:
        recommended = "tesseract"

    if detected == DetectedFileType.PDF_SCAN:
        message = "Scan PDF detected. OCR recommended for text; use Transformer for table structure if available."
    else:
        message = "Image file detected. OCR recommended for text extraction."

    return LiteScanProfile(
        recommended_ocr=recommended,
        transformer_available=bool(transformer_ok),
        message=message,
    )


def build_document_profile(
    file_path: Path,
    mime_type: str = "",
    *,
    max_pages: int | None = None,
) -> LiteDocumentProfile:
    """Analyze uploaded file and return LiteDocumentProfile."""
    max_pages = max_pages or settings.SYNC_MAX_PAGES
    detected, page_count = detect_file_type(file_path, mime_type)
    warnings: List[LiteWarning] = []

    input_meta = LiteInputMeta(
        filename=file_path.name,
        file_size_bytes=file_path.stat().st_size,
        mime_type=mime_type,
        detected_file_type=detected,
        page_count=page_count,
        sha256=_sha256(file_path),
    )

    if detected == DetectedFileType.UNSUPPORTED:
        raise ValueError(f"Unsupported file type: {file_path.suffix}")

    if detected in (DetectedFileType.PDF_SCAN, DetectedFileType.IMAGE):
        return LiteDocumentProfile(
            input=input_meta,
            pages=[],
            scan_profile=_build_scan_profile(detected),
            warnings=warnings,
        )

    pages: List[LitePageProfile] = []
    analyze_count = min(page_count, max_pages)

    with pdfplumber.open(str(file_path)) as pdf:
        for i in range(analyze_count):
            page = pdf.pages[i]
            pages.append(_analyze_pdf_page(page, i + 1))

    if page_count > max_pages:
        warnings.append(
            LiteWarning(
                code=WarningCode.PAGE_TRUNCATED,
                message=f"Profile analyzed first {max_pages} of {page_count} pages.",
                severity=Severity.WARNING,
            )
        )

    return LiteDocumentProfile(
        input=input_meta,
        pages=pages,
        scan_profile=None,
        warnings=warnings,
    )

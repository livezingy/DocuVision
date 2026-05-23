"""OCR pipeline for images and scanned PDFs."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from app.schemas.lite_result import ExtractMode, WarningCode


def _engine_available(name: str) -> bool:
    if name == "tesseract":
        return shutil.which("tesseract") is not None
    if name == "easyocr":
        return importlib.util.find_spec("easyocr") is not None
    if name == "transformer":
        return importlib.util.find_spec("transformers") is not None and importlib.util.find_spec("torch") is not None
    return False


def _resolve_ocr_engine(mode: ExtractMode, engine: str) -> str:
    engine = (engine or "auto").lower()
    if mode == ExtractMode.SMART or engine == "auto":
        if _engine_available("easyocr"):
            return "easyocr"
        if _engine_available("tesseract"):
            return "tesseract"
        raise RuntimeError("No OCR engine available (install easyocr or tesseract binary)")
    if engine in {"easyocr", "tesseract", "transformer"}:
        if not _engine_available(engine):
            raise RuntimeError(f"Engine unavailable: {engine}")
        return engine
    raise ValueError(f"Unsupported OCR engine: {engine}")


def _normalize_easyocr_bbox(block: Dict[str, Any]) -> List[float]:
    """Map EasyOCR bbox_rect or corner points to LiteOcrBlock [x1, y1, x2, y2]."""
    rect = block.get("bbox_rect")
    if rect and len(rect) >= 4:
        return [float(v) for v in rect[:4]]

    corners = block.get("bbox") or []
    if corners and isinstance(corners[0], (list, tuple)):
        xs = [float(p[0]) for p in corners]
        ys = [float(p[1]) for p in corners]
        return [min(xs), min(ys), max(xs), max(ys)]

    if corners:
        return [float(v) for v in corners[:4]]
    return []


def _run_easyocr(image: Image.Image, languages: List[str], min_confidence: float) -> List[Dict[str, Any]]:
    from docuvision_core.engines.easyocr_engine import EasyOCREngine

    ocr = EasyOCREngine(languages=languages or ["en"], gpu=False)
    ocr.initialize()
    blocks = ocr.recognize_text(image, min_confidence=min_confidence)
    return [
        {
            "page": 1,
            "bbox": _normalize_easyocr_bbox(b),
            "text": str(b.get("text", "")),
            "confidence": float(b.get("confidence", 0.0) or 0.0),
            "engine": "easyocr",
        }
        for b in blocks
    ]


def _run_tesseract(image: Image.Image, min_confidence: float) -> List[Dict[str, Any]]:
    import pytesseract

    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    blocks: List[Dict[str, Any]] = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        conf_raw = data.get("conf", [0])[i]
        try:
            confidence = float(conf_raw) / 100.0
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < min_confidence:
            continue
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        blocks.append(
            {
                "page": 1,
                "bbox": [float(x), float(y), float(x + w), float(y + h)],
                "text": text,
                "confidence": confidence,
                "engine": "tesseract",
            }
        )
    return blocks


def extract_ocr_from_image(
    file_path: Path,
    *,
    mode: ExtractMode = ExtractMode.SMART,
    engine: str = "auto",
    languages: Optional[List[str]] = None,
    min_confidence: float = 0.5,
) -> Dict[str, Any]:
    engine_used = _resolve_ocr_engine(mode, engine)
    image = Image.open(file_path).convert("RGB")

    if engine_used == "easyocr":
        ocr_blocks = _run_easyocr(image, languages or ["en"], min_confidence)
    elif engine_used == "tesseract":
        ocr_blocks = _run_tesseract(image, min_confidence)
    else:
        raise RuntimeError("Transformer OCR is not enabled in Lite Phase C baseline")

    confidences = [b["confidence"] for b in ocr_blocks]
    overall = sum(confidences) / len(confidences) if confidences else 0.0
    text_preview = " ".join(b["text"] for b in ocr_blocks[:20])[:500] or None

    warnings: List[Dict[str, Any]] = []
    if overall < 0.6:
        warnings.append(
            {
                "code": WarningCode.LOW_CONFIDENCE.value,
                "message": "OCR confidence is low; consider DocuVision Pro for scan/layout quality.",
            }
        )

    return {
        "ocr": ocr_blocks,
        "tables": [],
        "text_preview": text_preview,
        "routing": {
            "mode": mode.value if hasattr(mode, "value") else mode,
            "requested_engine": engine,
            "engine_used": engine_used,
            "engine_chain": [engine_used],
            "table_type_detected": "unknown",
            "flavor_used": "n/a",
            "param_mode": "auto",
            "profile": "cpu",
        },
        "quality": {
            "overall_confidence": overall,
            "tables_found": 0,
            "tables_accepted": 0,
            "pages_processed": 1,
            "pages_with_tables": 0,
            "ocr_blocks": len(ocr_blocks),
            "processing_profile": "cpu",
        },
        "warnings": warnings,
    }

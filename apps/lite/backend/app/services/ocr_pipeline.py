"""OCR pipeline for images and scanned PDFs."""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    fitz = None  # type: ignore

from app.schemas.lite_result import ExtractMode, WarningCode

# Short API summary only; full text is in LiteResult.ocr[]
TEXT_PREVIEW_MAX_BLOCKS = 20
TEXT_PREVIEW_MAX_CHARS = 500


def build_text_preview(ocr_blocks: List[Dict[str, Any]]) -> Optional[str]:
    """Build truncated summary for list/card views; UI Text tab should use ocr[] instead."""
    preview = " ".join(b["text"] for b in ocr_blocks[:TEXT_PREVIEW_MAX_BLOCKS])
    preview = preview[:TEXT_PREVIEW_MAX_CHARS]
    return preview or None


def _is_pdf(path: Path) -> bool:
    if path.suffix.lower() == ".pdf":
        return True
    with path.open("rb") as handle:
        return handle.read(4) == b"%PDF"


def _rasterize_pdf_pages(pdf_path: Path, max_pages: int = 10, dpi: int = 200) -> List[Tuple[int, Image.Image]]:
    """Rasterize PDF pages to PIL images using PyMuPDF."""
    if fitz is None:
        raise RuntimeError("PyMuPDF is required for scanned PDF OCR. Install: pip install PyMuPDF")

    images: List[Tuple[int, Image.Image]] = []
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    with fitz.open(pdf_path) as doc:
        for page_index in range(min(len(doc), max_pages)):
            page = doc[page_index]
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            mode = "RGB" if pix.n < 4 else "RGBA"
            image = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
            if mode == "RGBA":
                image = image.convert("RGB")
            images.append((page_index + 1, image))
    return images


def _load_images_from_path(file_path: Path, max_pages: int = 10) -> List[Tuple[int, Image.Image]]:
    if _is_pdf(file_path):
        return _rasterize_pdf_pages(file_path, max_pages=max_pages)
    return [(1, Image.open(file_path).convert("RGB"))]


def _engine_available(name: str) -> bool:
    if name == "tesseract":
        return shutil.which("tesseract") is not None
    if name == "easyocr":
        return importlib.util.find_spec("easyocr") is not None
    if name == "transformer":
        return importlib.util.find_spec("transformers") is not None and importlib.util.find_spec("torch") is not None
    return False


_EASYOCR_LANG_MAP = {
    "eng": "en",
    "en": "en",
    "ch_sim": "ch_sim",
    "ch_tra": "ch_tra",
    "fr": "fr",
    "de": "de",
    "es": "es",
    "ja": "ja",
    "ko": "ko",
}


def _normalize_easyocr_languages(languages: Optional[List[str]]) -> List[str]:
    raw = languages or ["en"]
    mapped: List[str] = []
    for lang in raw:
        key = str(lang or "").strip().lower().replace("-", "_")
        if not key:
            continue
        mapped.append(_EASYOCR_LANG_MAP.get(key, key))
    return mapped or ["en"]


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


def _create_easyocr_engine(languages: List[str], gpu: bool = False):
    from docuvision_core.engines.easyocr_engine import EasyOCREngine

    return EasyOCREngine(languages=languages, gpu=gpu)


def _run_easyocr(image: Image.Image, languages: List[str], min_confidence: float) -> List[Dict[str, Any]]:
    lang_list = _normalize_easyocr_languages(languages)
    ocr = _create_easyocr_engine(lang_list, gpu=False)
    if not ocr.initialize():
        raise RuntimeError("EasyOCR failed to initialize; check language packs and installation.")
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
    min_confidence: float = 0.2,
    max_pages: int = 10,
) -> Dict[str, Any]:
    engine_used = _resolve_ocr_engine(mode, engine)
    page_images = _load_images_from_path(file_path, max_pages=max_pages)
    ocr_blocks: List[Dict[str, Any]] = []
    extraction_errors: List[str] = []

    for page_num, image in page_images:
        try:
            if engine_used == "easyocr":
                page_blocks = _run_easyocr(image, languages, min_confidence)
            elif engine_used == "tesseract":
                page_blocks = _run_tesseract(image, min_confidence)
            else:
                raise RuntimeError("Transformer OCR is not enabled in Lite Phase C baseline")
        except Exception as exc:
            extraction_errors.append(str(exc))
            page_blocks = []
        for block in page_blocks:
            block["page"] = page_num
        ocr_blocks.extend(page_blocks)

    confidences = [b["confidence"] for b in ocr_blocks]
    overall = sum(confidences) / len(confidences) if confidences else 0.0
    text_preview = build_text_preview(ocr_blocks)

    warnings: List[Dict[str, Any]] = []
    if _is_pdf(file_path):
        warnings.append(
            {
                "code": WarningCode.SCAN_DETECTED.value,
                "message": f"Scanned PDF rasterized to {len(page_images)} page(s) for OCR.",
            }
        )
    if extraction_errors:
        warnings.append(
            {
                "code": WarningCode.OCR_EXTRACTION_FAILED.value,
                "message": f"OCR extraction failed ({engine_used}): {extraction_errors[0]}",
            }
        )
    elif not ocr_blocks:
        warnings.append(
            {
                "code": WarningCode.NO_TEXT_DETECTED.value,
                "message": "No text detected in the image. Try Advanced mode, another OCR engine, or higher-resolution input.",
            }
        )
    elif overall < 0.6:
        warnings.append(
            {
                "code": WarningCode.LOW_CONFIDENCE.value,
                "message": "OCR confidence is low; results are shown below. DocuVision Pro may improve scan/layout quality.",
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
            "pages_processed": len(page_images),
            "pages_with_tables": 0,
            "ocr_blocks": len(ocr_blocks),
            "processing_profile": "cpu",
        },
        "warnings": warnings,
    }

"""Page-level text layer trust judgement (E1 gatekeeper).

Determines, per PDF page, whether the text layer is trustworthy for
selective cell backfill. Two primary signals:

  * invisible rendered character ratio (Tr3 via ``Page.get_texttrace()``)
  * full-page image coverage (``Page.get_image_info()``)

Conservative thresholds bias toward false negatives (never backfill when
unsure) because the only catastrophic error is trusting an untrusted layer.

Per v1.8-design §3.1:
    trusted = (invisible_ratio < 0.2) AND (image_coverage < 0.5)
    overlay = invisible_ratio >= 0.5 AND image_coverage >= 0.8 (confidence=1.0)
    otherwise -> untrusted (mixed)

Dependency: PyMuPDF only (backend already depends on it). This module does
NOT live in docuvision-core — Pro is the sole consumer after Lite removal,
so core does not gain a fitz dependency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Tuple

_CID_RE = re.compile(r"\(cid:\d+\)")

# Verdicts (single source of truth; file_type_detector consumes these).
VERDICT_TEXT_LAYER = "text_layer"
VERDICT_OVERLAY = "overlay"
VERDICT_MIXED = "mixed"
VERDICT_NO_TEXT = "no_text"


@dataclass
class PageTrustResult:
    trusted: bool
    confidence: float          # 0.0~1.0
    verdict: str               # "text_layer" | "overlay" | "mixed" | "no_text"
    signals: Dict[str, Any]    # raw signal values (debug log + quality layer)


def _span_char_count(span: Dict[str, Any]) -> int:
    """Return character count of a texttrace span, defensively."""
    chars = span.get("chars")
    if isinstance(chars, (list, tuple)):
        return len(chars)
    text = span.get("text")
    if isinstance(text, str):
        return len(text)
    return 0


def _trace_stats(page: Any) -> Tuple[int, int]:
    """Return ``(total_chars, invisible_chars)`` from ``get_texttrace()``.

    ``get_texttrace()`` returns a flat list of span dicts. A span's ``type``
    field encodes the PDF text rendering mode (Tr); 3 is invisible (render
    mode 3: neither fill nor stroke). Defensive against nested block/line
    shapes seen in some bindings.

    KNOWN UPSTREAM RISK: PyMuPDF's ``get_texttrace()`` has a refcount bug that
    can hard-crash the interpreter (`none_dealloc: deallocating None`) when
    accumulating traces across many pages. It is a C-level fault, so Python
    try/except cannot catch it. Mitigations in place:
      * the analyze path only calls this per table-bearing page
        (see ``table_backfill.backfill_tables``), not per document page;
      * ``requirements.txt`` pins PyMuPDF ``<1.26.0`` — versions above that
        (observed: 1.27.2.3) are known to trigger it.
    Verify with the GATEKEEPER-STABILITY gate before release.
    """
    total = 0
    invisible = 0
    try:
        trace = page.get_texttrace()
    except Exception:
        return 0, 0
    if not isinstance(trace, list):
        return 0, 0

    spans: list = []
    for item in trace:
        if not isinstance(item, dict):
            continue
        if "spans" in item:
            spans.extend(item.get("spans", []) or [])
        elif "lines" in item:
            for line in item.get("lines", []) or []:
                if isinstance(line, dict):
                    spans.extend(line.get("spans", []) or [])
        else:
            spans.append(item)

    for span in spans:
        if not isinstance(span, dict):
            continue
        count = _span_char_count(span)
        total += count
        if span.get("type") == 3:
            invisible += count
    return total, invisible


def _image_coverage(page: Any) -> float:
    """Union area of image bboxes divided by page area."""
    import fitz

    rect = page.rect
    area = float(rect.width * rect.height)
    if area <= 0:
        return 0.0
    try:
        images = page.get_image_info(xrefs=True)
    except Exception:
        return 0.0
    if not isinstance(images, list):
        return 0.0
    union = fitz.Rect()
    for im in images:
        bbox = im.get("bbox") if isinstance(im, dict) else None
        if not bbox:
            continue
        r = fitz.Rect(bbox) & rect
        if r.is_empty or r.get_area() <= 0:
            continue
        union |= r
    return union.get_area() / area


def _font_signals(page: Any) -> Dict[str, Any]:
    """Font diversity and GlyphLessFont (Tesseract OCR) signature hit."""
    try:
        fonts = page.get_fonts(full=True)
    except Exception:
        fonts = []
    if not isinstance(fonts, list):
        fonts = []
    basefonts = set()
    glyphless = False
    for f in fonts:
        basefont = (f[3] if (isinstance(f, (list, tuple)) and len(f) > 3) else "") or ""
        if basefont:
            basefonts.add(basefont)
        combined = " ".join(str(x) for x in (f if isinstance(f, (list, tuple)) else []))
        if "GlyphLessFont" in combined:
            glyphless = True
    return {"font_count": len(basefonts), "glyphless_font": glyphless}


def _cid_rate(page: Any) -> float:
    """Ratio of ``(cid:N)`` placeholder occurrences to total text length."""
    try:
        text = page.get_text("text") or ""
    except Exception:
        text = ""
    if not text:
        return 0.0
    return len(_CID_RE.findall(text)) / len(text)


def judge_page_trust(page: "Any") -> PageTrustResult:
    """Judge whether a page's text layer is trustworthy (E1 gatekeeper).

    Conservative by design: only clearly born-digital pages (near-zero
    invisible rendering AND below-threshold image coverage) are trusted.
    Everything ambiguous falls through to untrusted so backfill is never
    applied to a possibly-untrustworthy layer.
    """
    total_chars, invisible_chars = _trace_stats(page)
    invisible_ratio = (invisible_chars / total_chars) if total_chars else 0.0
    image_coverage = _image_coverage(page)
    font_signals = _font_signals(page)
    cid_rate = _cid_rate(page)

    signals = {
        "invisible_ratio": round(invisible_ratio, 4),
        "image_coverage": round(image_coverage, 4),
        "font_count": font_signals["font_count"],
        "glyphless_font": font_signals["glyphless_font"],
        "cid_rate": round(cid_rate, 5),
        "total_chars": total_chars,
        "invisible_chars": invisible_chars,
    }

    if total_chars == 0:
        return PageTrustResult(
            trusted=False, confidence=0.0, verdict=VERDICT_NO_TEXT, signals=signals
        )

    # Overlay: hard-positive (scanned page + OCR overlay layer).
    if invisible_ratio >= 0.5 and image_coverage >= 0.8:
        return PageTrustResult(
            trusted=False, confidence=1.0, verdict=VERDICT_OVERLAY, signals=signals
        )

    # Trusted: clearly born-digital text layer.
    if invisible_ratio < 0.2 and image_coverage < 0.5:
        confidence = 1.0 - 0.5 * (invisible_ratio / 0.2 + image_coverage / 0.5)
        confidence = max(0.6, min(1.0, confidence))
        return PageTrustResult(
            trusted=True,
            confidence=round(confidence, 3),
            verdict=VERDICT_TEXT_LAYER,
            signals=signals,
        )

    # Intermediate: untrusted (only lose speed, never correctness).
    confidence = 0.5 * (invisible_ratio / 0.5 + image_coverage / 0.8)
    confidence = max(0.0, min(0.5, confidence))
    return PageTrustResult(
        trusted=False,
        confidence=round(confidence, 3),
        verdict=VERDICT_MIXED,
        signals=signals,
    )

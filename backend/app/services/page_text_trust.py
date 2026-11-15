"""Page-level text-layer trust measurement (shared leaf; multi-domain contract).

Measures the physical properties of a PDF page's native text layer —
invisible rendered character ratio (Tr 3 text objects via ``pypdfium2``),
full-page image coverage (image object bounds via ``pypdfium2``), font
signatures (``pypdf`` resource walk) and the ToUnicode-missing font
character rate — and turns them into a conservative verdict plus raw
signals. Each consumer brings its own question to the same public result:

  * table backfill (``table_backfill``): is this layer safe to overwrite
    table cells from? — the E1 gatekeeper question; the thresholds and the
    never-trust-when-unsure bias are calibrated for it, and the E1 narrative
    lives in ``provenance-review.md`` (the owning doc);
  * evidence grounding (``evidence.gate`` / ``evidence.grounding``): does the
    page carry a usable native text layer? — the M5 predicate reads the same
    signals and applies its OWN, deliberately different thresholds;
  * document probing (``file_type_detector`` / ``page_type_probe``): which
    text-layer class does the page belong to? — ``VERDICT_*`` are the shared
    vocabulary (single source of truth).

The module itself is domain-neutral: no service state, stdlib plus deferred
pypdfium2 / pypdf only (fitz surface replaced per R-005 package B; signal
equivalence was probed empirically in
``docs/R&D/runs/R-005/attachments/r005v2_fitz_surface_replacement_probe.py``).
Registered as a shared leaf in ``service_domain_map.json`` (P-038 ruling D,
2026-10-25). Verdict vocabulary, thresholds and signal keys are unchanged —
only the extraction engines underneath moved (see ``_cid_rate`` for the one
registered semantic change).

Per v1.8-design §3.1:
    trusted = (invisible_ratio < 0.2) AND (image_coverage < 0.5)
    overlay = invisible_ratio >= 0.5 AND image_coverage >= 0.8 (confidence=1.0)
    otherwise -> untrusted (mixed)

Dependency: the R-005 package B engine stack — pypdfium2 / pdfplumber /
pypdf (this module imports pypdfium2 + pypdf directly; pdfplumber serves
the words path in ``table_backfill``). PyMuPDF is no longer imported here.
This module does NOT live in docuvision-core — Pro is the sole consumer
after Lite removal.
"""

from __future__ import annotations

import io
import re
import weakref
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

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


# --- pypdf resource cache ---------------------------------------------------
# One ``PdfReader`` per pdfium ``PdfDocument`` (weak-keyed: the entry dies with
# the document). ``pypdf.PdfReader`` pages are needed for the /Resources/Font
# walk and the /ToUnicode presence check, which pdfium cannot express.
_PYPDF_READERS: "weakref.WeakKeyDictionary[Any, Any]" = weakref.WeakKeyDictionary()


def _pypdf_page_of(page: Any, page_index: Any) -> Any:
    """pypdf page for a pdfium page's ``(document, 0-based index)`` pair.

    Reads the source the pdfium document was opened from (``PdfDocument._input``:
    a ``Path``/``str`` path, raw bytes or a file-like object) and caches the
    ``PdfReader`` on the document. Returns ``None`` on any failure — callers
    then degrade to the pdfium text-object font fallback (fail-soft, same
    shape as the previous ``get_fonts`` ``except`` branch)."""
    if page_index is None:
        return None
    try:
        import pypdf

        index = int(page_index)
        if index < 0:
            return None
        doc = getattr(page, "pdf", None) or getattr(page, "parent", None)
        if doc is None:
            return None
        reader = _PYPDF_READERS.get(doc)
        if reader is None:
            source = getattr(doc, "_input", None)
            if isinstance(source, Path):
                reader = pypdf.PdfReader(str(source))
            elif isinstance(source, str):
                reader = pypdf.PdfReader(source)
            elif isinstance(source, (bytes, bytearray)):
                reader = pypdf.PdfReader(io.BytesIO(bytes(source)))
            elif hasattr(source, "read"):
                reader = pypdf.PdfReader(source)
            else:
                return None
            _PYPDF_READERS[doc] = reader
        return reader.pages[index]
    except Exception:
        return None


def _page_font_resources(pypdf_page: Any) -> Dict[str, Any]:
    """Resolved ``/Resources`` dict for a pypdf page, walking ``/Parent`` for
    inherited resources (PDF spec 7.8.3; mirrors fitz page-scoped semantics)."""
    node = pypdf_page
    depth = 0
    while node is not None and depth < 64:
        resources = node.get("/Resources")
        if resources is not None:
            resources = resources.get_object()
            if isinstance(resources, dict):
                return resources
        parent = node.get("/Parent")
        node = parent.get_object() if parent is not None else None
        depth += 1
    return {}


def _normalize_font_name(name: str) -> str:
    """Comparable font-name form for cross-engine matching: drop the leading
    ``/``, the subset tag (``ABCDEF+``) and all whitespace, lowercase."""
    name = name.lstrip("/")
    if "+" in name:
        name = name.split("+", 1)[1]
    return re.sub(r"\s+", "", name).lower()


def _text_obj_stats(page: Any) -> Tuple[int, int, Dict[str, int], List[str]]:
    """``(total_chars, invisible_chars, chars_by_font, obj_font_names)`` from
    the page's text objects (pypdfium2 raw walk).

    Invisible = ``FPDFTextObj_GetTextRenderMode`` ==
    ``FPDF_TEXTRENDERMODE_INVISIBLE`` (render mode 3: neither fill nor
    stroke; measured value 3, probe S1). Char counts come from
    ``PdfTextObj.extract()`` per object — probe S1 verified the fitz
    ``get_texttrace()`` span counts (total 39 / invisible 19 on the Tr3
    fixture) reproduce exactly. Defensive against per-object extraction
    failures (single-object failure counts 0 chars, same as a span without
    ``chars``/``text`` in the previous implementation)."""
    import pypdfium2 as pdfium
    import pypdfium2.raw as pdfium_c

    total = 0
    invisible = 0
    chars_by_font: Dict[str, int] = {}
    obj_fonts: List[str] = []
    try:
        textpage = page.get_textpage()
    except Exception:
        return 0, 0, {}, []
    try:
        try:
            objs = list(
                page.get_objects(
                    filter=[pdfium_c.FPDF_PAGEOBJ_TEXT], max_depth=2, textpage=textpage
                )
            )
        except Exception:
            return 0, 0, {}, []
        for obj in objs:
            try:
                text = obj.extract() or ""
            except Exception:
                text = ""
            try:
                render_mode = int(pdfium_c.FPDFTextObj_GetTextRenderMode(obj))
            except Exception:
                render_mode = None
            try:
                font_name = obj.get_font().get_base_name() or ""
            except Exception:
                font_name = ""
            count = len(text)
            total += count
            if render_mode == int(pdfium_c.FPDF_TEXTRENDERMODE_INVISIBLE):
                invisible += count
            if font_name:
                chars_by_font[font_name] = chars_by_font.get(font_name, 0) + count
                obj_fonts.append(font_name)
        return total, invisible, chars_by_font, obj_fonts
    finally:
        try:
            textpage.close()
        except Exception:
            pass


def _image_coverage(page: Any) -> float:
    """Image coverage: the bounding box of all clipped image bboxes, divided
    by the page area.

    Semantics preserved from the fitz implementation, whose ``fitz.Rect``
    ``|`` chain produced the *bounding box* of the clipped image rects (not
    the exact union area); the probe (S2, single image) cannot distinguish
    the two, so the bounding-box math is kept for value equivalence.

    ``PdfObject.get_bounds()`` returns ``(l, b, r, t)`` bottom-left origin;
    ``page.get_size()`` matches the fitz ``page.rect`` rotation semantics
    (probe S2: equal coverage 0.053 on the f4 fixture; on rotated pages both
    engines clip the unrotated object bounds against the rotated page rect,
    so the value carries the same bias as before).

    REGISTERED GAP (R-005 package B): pdfium's ``FPDF_PAGEOBJ`` enumeration
    covers page content only — images drawn inside annotation appearance
    streams are invisible to it (fitz ``get_image_info`` did include them).
    Measured example: pub_bmc page 1 — fitz 0.6105 (4 content images + 1
    annotation-appearance image stretching the bbox) vs pypdfium2 0.0017
    (content images only); verdict mixed -> text_layer on that page.
    Diagnostic-direction impact only: under-counting coverage biases toward
    ``text_layer`` trust; the E1 consumer (table backfill) still runs the
    per-cell T1/T2/T3 + sanity gates, and the evidence M5 predicate does not
    read ``image_coverage`` at all."""
    import pypdfium2 as pdfium
    import pypdfium2.raw as pdfium_c

    try:
        width, height = page.get_size()
    except Exception:
        return 0.0
    area = float(width) * float(height)
    if area <= 0:
        return 0.0
    try:
        images = list(page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE], max_depth=2))
    except Exception:
        return 0.0
    clipped: List[Tuple[float, float, float, float]] = []
    for obj in images:
        try:
            l, b, r, t = obj.get_bounds()
        except Exception:
            continue
        l = max(float(l), 0.0)
        b = max(float(b), 0.0)
        r = min(float(r), float(width))
        t = min(float(t), float(height))
        if r <= l or t <= b:
            continue
        clipped.append((l, b, r, t))
    if not clipped:
        return 0.0
    u_l = min(rect[0] for rect in clipped)
    u_b = min(rect[1] for rect in clipped)
    u_r = max(rect[2] for rect in clipped)
    u_t = max(rect[3] for rect in clipped)
    return (u_r - u_l) * (u_t - u_b) / area


def _font_signals(page: Any, page_index: Any, fallback_names: List[str]) -> Dict[str, Any]:
    """Font diversity and GlyphLessFont (Tesseract OCR) signature hit.

    Primary: ``pypdf`` walk of the page's ``/Resources/Font`` dictionaries
    (resource-level semantics equal to fitz ``get_fonts(full=True)`` — probe
    S3: both report ``Helvetica`` / ``Segoe UI Symbol Regular``). Fallback:
    the pdfium text-object font names — they only cover fonts actually used
    by text objects (probe S3: ``SegoeUISymbol`` differs from the resource
    ``BaseFont``), so they step in only when the resource walk fails or
    yields nothing.

    REGISTERED GAP (R-005 package B): the walk does not descend into
    annotation appearance streams or form XObject resources, which fitz
    ``get_fonts(full=True)`` did include; ``font_count`` can read lower on
    such pages (measured: pub_bmc pages drop 8->4 .. 10->9). Diagnostic
    signal only — no verdict branch reads ``font_count``."""
    import pypdf

    basefonts = set()
    glyphless = False
    pypdf_page = _pypdf_page_of(page, page_index)
    if pypdf_page is not None:
        try:
            fonts_res = _page_font_resources(pypdf_page).get("/Font")
            fonts_res = fonts_res.get_object() if fonts_res is not None else {}
            if isinstance(fonts_res, dict):
                for _key, value in fonts_res.items():
                    try:
                        font = value.get_object() if value is not None else None
                    except Exception:
                        font = None
                    if not isinstance(font, dict):
                        continue
                    basefont = font.get("/BaseFont") or ""
                    basefont = str(basefont)
                    if basefont:
                        basefonts.add(basefont)
                    if "GlyphLessFont" in basefont:
                        glyphless = True
        except Exception:
            basefonts = set()
            glyphless = False
    if not basefonts:
        for name in fallback_names or []:
            if name:
                basefonts.add(name)
                if "GlyphLessFont" in name:
                    glyphless = True
    return {"font_count": len(basefonts), "glyphless_font": glyphless}


def _cid_rate(page: Any, page_index: Any, chars_by_font: Dict[str, int], total_chars: int) -> float:
    """Ratio of text-object characters rendered with fonts that lack a
    ``/ToUnicode`` CMap.

    SEMANTIC CHANGE (R-005 package B, registered): the fitz implementation
    counted literal ``(cid:N)`` placeholders produced by fitz text
    extraction. pypdfium2 extraction does not emit that placeholder shape,
    so the old computation would silently read ``0.0`` on the new engine.
    The signal key stays ``cid_rate``; the value now compares the pypdf
    ``/Resources/Font`` dicts for missing ``/ToUnicode`` entries against the
    per-font character counts of the page's text objects (cross-engine name
    matching is subset-tag/whitespace/case-insensitive).

    Interpretation note (R-005 low ②): under this new semantics the base-14
    standard fonts (Helvetica, Times, Courier families, Symbol, ZapfDingbats)
    carry no ``/ToUnicode`` by construction per the PDF specification — their
    encodings are predefined — so a healthy born-digital page typeset in
    standard fonts legitimately reads a high value (≈1.0). When using this
    signal for diagnosis, interpret it together with the page's font
    collection (``font_count`` / base fonts from :func:`_font_signals`): a
    high ``cid_rate`` is only anomalous for non-standard embedded fonts, not
    a standalone defect marker.

    Diagnostic signal only — it feeds ``signals`` and no verdict branch.
    Fails soft to ``0.0`` when the pypdf page is unavailable (no
    ``page_index``) or any step raises."""
    pypdf_page = _pypdf_page_of(page, page_index)
    if pypdf_page is None or not chars_by_font or total_chars <= 0:
        return 0.0
    try:
        fonts_res = _page_font_resources(pypdf_page).get("/Font")
        fonts_res = fonts_res.get_object() if fonts_res is not None else {}
        if not isinstance(fonts_res, dict):
            return 0.0
        missing: set = set()
        for _key, value in fonts_res.items():
            try:
                font = value.get_object() if value is not None else None
            except Exception:
                font = None
            if not isinstance(font, dict):
                continue
            if font.get("/ToUnicode") is None:
                basefont = str(font.get("/BaseFont") or "")
                if basefont:
                    missing.add(_normalize_font_name(basefont))
        if not missing:
            return 0.0
        affected = sum(
            count
            for name, count in chars_by_font.items()
            if _normalize_font_name(name) in missing
        )
        return affected / total_chars
    except Exception:
        return 0.0


def judge_page_trust(page: Any, page_index: int | None = None) -> PageTrustResult:
    """Judge whether a page's text layer is trustworthy (E1 gatekeeper).

    Conservative by design: only clearly born-digital pages (near-zero
    invisible rendering AND below-threshold image coverage) are trusted.
    Everything ambiguous falls through to untrusted so backfill is never
    applied to a possibly-untrustworthy layer.

    ``page`` is a ``pypdfium2.PdfPage``. ``page_index`` (0-based) enables the
    pypdf ``/Resources/Font`` walk behind the ``font_count`` / ``glyphless_font``
    / ``cid_rate`` signals; without it those signals degrade to the pdfium
    text-object font fallback (``cid_rate`` then reads ``0.0``). Verdict
    vocabulary, thresholds and signal keys are unchanged from the fitz
    implementation; ``cid_rate`` carries the one registered semantic change
    (see :func:`_cid_rate`).
    """
    total_chars, invisible_chars, chars_by_font, obj_fonts = _text_obj_stats(page)
    invisible_ratio = (invisible_chars / total_chars) if total_chars else 0.0
    image_coverage = _image_coverage(page)
    font_signals = _font_signals(page, page_index, obj_fonts)
    cid_rate = _cid_rate(page, page_index, chars_by_font, total_chars)

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

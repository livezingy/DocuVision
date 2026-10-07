"""P-032 M1/M2 text-first input channel (pico on PDF inputs).

The pico extraction input switches from the page image to the PDF's native
text layer, segmented into blocks and annotated with globally-unique markers
``[p{page}_b{block}]`` (page 1-based, block index 0-based, mirroring the fused
``block_id`` convention). The model cites markers instead of bare block ids;
the evidence gate (P-032 M4) grounds quotes against the SAME text, so a quote
copied from the input can never drift from the grounding text.

Single home of the P-032 adjudicated rules, pinned as code constants:
  * body-page rule (adjudication 2): >= 8 body-type layout elements and
    >= 500 text-element characters per page, calibrated on the 5 pico corpora;
  * sliding windows (adjudication 3): per-page calls; a page longer than the
    model context window is split at block boundaries with a 1-block overlap,
    markers keep absolute page numbers.

This module shares the native text extraction with the evidence gate's
grounding source (``app.services.evidence.grounding``) -- "same source" is
the P-032 contract, not an implementation accident.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# P-032 adjudication 2 constants (C1-calibrated; never runtime-tuned).
BODY_PAGE_MIN_TEXT_ELEMENTS = 8
BODY_PAGE_MIN_TEXT_CHARS = 500

# Layout element types that count as body content (adjudication 2).
BODY_ELEMENT_TYPES = frozenset({"text", "paragraph", "title", "table", "figure_caption"})

# P-032 adjudication 3: sliding-window bound (chars incl. markers), to be
# confirmed against the C1 Cloud token measurements.
TEXT_FIRST_WINDOW_MAX_CHARS = 12000

# Per-page input source tags recorded in debug_input (M1 DoD).
SOURCE_TEXT_LAYER = "text_layer"
SOURCE_FUSED_OCR = "fused_ocr"


def text_first_enabled(document_type: str, is_pdf: bool) -> bool:
    """P-032 feature flag gate: text-first applies to pico on PDFs only."""
    if not is_pdf or str(document_type).lower() != "pico":
        return False
    try:
        from app.core.config import settings

        return bool(getattr(settings, "EVIDENCE_TEXT_FIRST", False))
    except Exception:
        return False


def text_first_from_ctx(ctx: Dict[str, Any]) -> bool:
    """Same-source text-first decision from a pipeline ctx (P-032 review D2).

    Resolves the document type from ``result.kie_meta.resolved_document_type``
    and PDF-ness from ``file_path``, then defers to :func:`text_first_enabled` --
    the same predicate the KIE step uses, so the extraction channel and the
    evidence grounding path cannot diverge (unknown type / non-PDF -> legacy).
    """
    result = ctx.get("result") or {}
    kie_meta = result.get("kie_meta") if isinstance(result.get("kie_meta"), dict) else {}
    doc_type = str(kie_meta.get("resolved_document_type") or "")
    is_pdf = str(ctx.get("file_path") or "").lower().endswith(".pdf")
    return text_first_enabled(doc_type, is_pdf)


def block_marker(page_num: int, block_index: int) -> str:
    """Globally-unique block marker: absolute page number, 0-based block."""
    return f"[p{page_num}_b{block_index}]"


def build_page_payload(
    blocks: List[str],
    page_num: int,
    block_indices: Optional[List[int]] = None,
) -> str:
    """Marker-annotated text for one page (or window): one line per block."""
    indices = list(range(len(blocks))) if block_indices is None else block_indices
    return "\n".join(
        f"{block_marker(page_num, index)} {text}" for index, text in zip(indices, blocks)
    )


def split_windows(blocks: List[str], page_num: int) -> List[str]:
    """Block-boundary sliding windows for one page (adjudication 3).

    Windows carry at least one block even when a single block exceeds the
    char bound (a block cannot be split further); consecutive windows overlap
    by exactly one block so a quote spanning the boundary stays locatable."""
    if not blocks:
        return []
    windows: List[str] = []
    start = 0
    total = len(blocks)
    while start < total:
        size = 0
        last = start
        for index in range(start, total):
            chunk = len(block_marker(page_num, index)) + 1 + len(blocks[index]) + 1
            if size + chunk > TEXT_FIRST_WINDOW_MAX_CHARS and index > start:
                break
            size += chunk
            last = index
        indices = list(range(start, last + 1))
        windows.append(build_page_payload([blocks[i] for i in indices], page_num, indices))
        if last + 1 >= total:
            break
        start = last if last > start else last + 1
    return windows


def select_body_pages(layout: Dict[str, Any], page_count: int) -> List[int]:
    """Body pages per the pinned adjudication-2 rule (M2).

    A page is a body page when it carries >= BODY_PAGE_MIN_TEXT_ELEMENTS
    layout elements of the body types AND >= BODY_PAGE_MIN_TEXT_CHARS
    characters across those elements (skips covers / pure-image pages)."""
    counts: Dict[int, int] = {}
    chars: Dict[int, int] = {}
    for elem in (layout or {}).get("elements", []) or []:
        if not isinstance(elem, dict):
            continue
        if str(elem.get("type", "")).lower() not in BODY_ELEMENT_TYPES:
            continue
        try:
            page_no = int(elem.get("page", elem.get("page_id", 1)))
        except (TypeError, ValueError):
            continue
        counts[page_no] = counts.get(page_no, 0) + 1
        chars[page_no] = chars.get(page_no, 0) + len(str(elem.get("text") or ""))
    return [
        page
        for page in range(1, page_count + 1)
        if counts.get(page, 0) >= BODY_PAGE_MIN_TEXT_ELEMENTS
        and chars.get(page, 0) >= BODY_PAGE_MIN_TEXT_CHARS
    ]


def resolve_pages_text_first(
    pages_spec: Optional[str],
    page_count: int,
    max_pages: int,
    *,
    text_first: bool,
    layout: Optional[Dict[str, Any]] = None,
):
    """Page resolution (M2): under text-first the pico default page set
    becomes the body pages, then ``max_pages`` truncation. Explicit page
    specs are honoured as-is via the legacy parser."""
    from app.services.kie.kie_pages import resolve_kie_pages

    if not text_first:
        return resolve_kie_pages(pages_spec, page_count, max_pages)
    spec = str(pages_spec or "").strip().lower()
    if spec not in {"", "1", "first", "page1"}:
        return resolve_kie_pages(pages_spec, page_count, max_pages)
    pages = select_body_pages(layout, page_count) or [1]
    truncated = False
    if len(pages) > max_pages:
        pages, truncated = pages[:max_pages], True
    return pages, truncated


def _layout_text_by_page(layout: Optional[Dict[str, Any]]) -> Dict[int, List[str]]:
    """Per-page layout element texts (reading order as produced by layout)."""
    by_page: Dict[int, List[str]] = {}
    for elem in (layout or {}).get("elements", []) or []:
        if not isinstance(elem, dict):
            continue
        try:
            page_no = int(elem.get("page", elem.get("page_id", 1)))
        except (TypeError, ValueError):
            continue
        text = str(elem.get("text") or "")
        if text.strip():
            by_page.setdefault(page_no, []).append(text)
    return by_page


def build_text_first_payloads(
    file_path: str,
    layout: Optional[Dict[str, Any]],
    selected_pages: List[int],
) -> Dict[int, Dict[str, Any]]:
    """Per-page text-first payloads (M1): ``{page: {page, source, n_chars, windows}}``.

    ``source`` records which text fed the model: ``text_layer`` when the page
    passes the M5 evidence trust predicate (native layer exists, no OCR
    overlay), else ``fused_ocr`` (layout-element text, explicitly declared --
    the M5 trust gate still fails such pages closed at evidence time, R3).
    Pages with no text on either channel are absent: they fall back to the
    image channel, which the payload map makes visible (nothing is silently
    mixed)."""
    from app.services.evidence.grounding import (
        grounding_source,
        trusted_grounding_page_set,
    )

    source = grounding_source(file_path)
    trusted = trusted_grounding_page_set(file_path)
    layout_text = _layout_text_by_page(layout)
    payloads: Dict[int, Dict[str, Any]] = {}
    for page_num in selected_pages:
        native = source.blocks.get(page_num) or []
        if page_num in trusted and native:
            blocks, tag = native, SOURCE_TEXT_LAYER
        else:
            ocr_blocks = layout_text.get(page_num) or []
            if not ocr_blocks:
                continue  # no text anywhere -> image channel (recorded by absence)
            blocks, tag = ocr_blocks, SOURCE_FUSED_OCR
        windows = split_windows(blocks, page_num)
        payloads[page_num] = {
            "page": page_num,
            "source": tag,
            "n_chars": sum(len(block) for block in blocks),
            "windows": windows,
        }
    return payloads

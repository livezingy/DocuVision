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

The pinned constants, the marker/payload format and the pure decision
predicates live in the shared leaf ``app.services.text_first_contract``
(runs/split batch 2: both the KIE channel and the evidence gate consume the
SAME functions); this module keeps the settings-reading wrappers with the
original signatures plus the payload assembly. "Same source" with the
evidence grounding text remains the P-032 contract: the grounding layer is
injected by the orchestrator (``blocks_by_page`` / ``trusted_pages`` come
from ``evidence.grounding``), not imported here.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from app.services.text_first_contract import (  # noqa: F401 (re-exported contract surface)
    BODY_ELEMENT_TYPES,
    BODY_PAGE_MIN_TEXT_CHARS,
    BODY_PAGE_MIN_TEXT_ELEMENTS,
    SOURCE_FUSED_OCR,
    SOURCE_TEXT_LAYER,
    TEXT_FIRST_WINDOW_MAX_CHARS,
    block_marker,
    build_page_payload,
    select_body_pages,
    split_windows,
)
from app.services.text_first_contract import (
    text_first_enabled as _text_first_enabled_pure,
)
from app.services.text_first_contract import text_first_from_ctx as _from_ctx_pure


def text_first_enabled(document_type: str, is_pdf: bool) -> bool:
    """P-032 feature flag gate (settings-reading wrapper over the shared leaf)."""
    try:
        from app.core.config import settings

        flag = bool(getattr(settings, "EVIDENCE_TEXT_FIRST", False))
    except Exception:
        flag = False
    return _text_first_enabled_pure(document_type, is_pdf, flag)


def text_first_from_ctx(ctx: Dict[str, Any]) -> bool:
    """Same-source text-first decision from a pipeline ctx (settings wrapper)."""
    try:
        from app.core.config import settings

        flag = bool(getattr(settings, "EVIDENCE_TEXT_FIRST", False))
    except Exception:
        flag = False
    return _from_ctx_pure(ctx, flag)


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
    layout: Optional[Dict[str, Any]],
    selected_pages: List[int],
    *,
    blocks_by_page: Dict[int, List[str]],
    trusted_pages: Set[int],
) -> Dict[int, Dict[str, Any]]:
    """Per-page text-first payloads (M1): ``{page: {page, source, n_chars, windows}}``.

    The native text layer and the trusted-page set are INJECTED by the caller
    (the orchestrator's KIE step passes ``evidence.grounding``'s results) —
    the same-source P-032 contract holds without any kie->evidence import
    (dissolved in runs/split batch 3).

    ``source`` records which text fed the model: ``text_layer`` when the page
    passes the M5 evidence trust predicate (native layer exists, no OCR
    overlay), else ``fused_ocr`` (layout-element text, explicitly declared --
    the M5 trust gate still fails such pages closed at evidence time, R3).
    Pages with no text on either channel are absent: they fall back to the
    image channel, which the payload map makes visible (nothing is silently
    mixed)."""
    layout_text = _layout_text_by_page(layout)
    payloads: Dict[int, Dict[str, Any]] = {}
    for page_num in selected_pages:
        native = blocks_by_page.get(page_num) or []
        if page_num in trusted_pages and native:
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

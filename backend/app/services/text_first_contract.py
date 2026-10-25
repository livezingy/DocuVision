"""Text-first contract primitives (shared leaf, I-1/P-038).

The pinned P-032 rules and the pure predicates shared by the KIE extraction
channel (``kie.text_first``) and the evidence gate: both sides must answer
"is text-first active for this ctx?" with the SAME function (P-032 review D2,
same-source contract). Promoted verbatim from ``kie/text_first.py`` in
runs/split batch 2 to break the evidence<->kie cycle (frozen edges #4/#5);
the only tier-B change is flag parameterization — the ``EVIDENCE_TEXT_FIRST``
settings read stays with the callers (a leaf is zero-outbound, L1 strength A),
so ``kie.text_first`` keeps thin settings-reading wrappers with the original
signatures.
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


def text_first_enabled(document_type: str, is_pdf: bool, flag: bool) -> bool:
    """P-032 feature flag gate: text-first applies to pico on PDFs only."""
    if not is_pdf or str(document_type).lower() != "pico":
        return False
    return bool(flag)


def text_first_from_ctx(ctx: Dict[str, Any], flag: bool) -> bool:
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
    return text_first_enabled(doc_type, is_pdf, flag)


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

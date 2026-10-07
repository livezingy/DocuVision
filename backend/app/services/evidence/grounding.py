"""Evidence-specific grounding helpers (P-032 text-first hardening).

M5: evidence-specific page-trust predicate for the text-first path.

The E1 gatekeeper (``page_text_trust.judge_page_trust``) answers the table
backfill question "is this text layer safe to overwrite table cells from?"
and therefore rejects born-digital pages with high image coverage. The
evidence gate answers a different question: "does this page carry a usable
NATIVE text layer to ground quotes against?" -- image coverage is irrelevant
for that (a scanned figure does not corrupt the surrounding text layer), so
the text-first path judges pages by:

    trusted_grounding(page) = total_chars > 0 AND invisible_ratio < 0.5

``page_text_trust`` itself stays read-only (P-032 zero-touch list): the E1
predicate and its other consumers (file_type_detector / table_backfill /
page_type_probe) are untouched; this module reuses its public result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.evidence.normalize import normalize
from app.services.evidence.verifier import (
    VERBATIM_EXACT,
    _ladder_variants,
    classify_quote,
    longest_prefix_words,
)

# P-032 M5 thresholds, pinned at design time (never runtime-tuned).
MIN_TOTAL_CHARS = 1
MAX_INVISIBLE_RATIO = 0.5

# P-032 M1 marker shape: [p{absolute page}_b{block index}], page 1-based,
# block index 0-based (mirrors the fused block_id convention).
_MARKER_RE = re.compile(r"\[\s*p(\d+)_b(\d+)\s*\]")


def trusted_grounding_page_set(file_path: str) -> Set[int]:
    """1-based page numbers whose native text layer the text-first evidence
    gate trusts: ``total_chars > 0`` and ``invisible_ratio < 0.5``.

    Signals come from the E1 extractor via its public result (raw counts in
    ``signals``), so ``page_text_trust.py`` is not modified. Single-page
    failures and unreadable documents are fail-closed (page left out)."""
    trusted: Set[int] = set()
    try:
        import fitz

        from app.services.page_text_trust import judge_page_trust

        with fitz.open(file_path) as doc:
            for index in range(doc.page_count):
                try:
                    signals = judge_page_trust(doc[index]).signals
                except Exception:
                    continue  # single-page failure -> untrusted (fail-closed)
                total = int(signals.get("total_chars") or 0)
                invisible = int(signals.get("invisible_chars") or 0)
                if total >= MIN_TOTAL_CHARS and invisible / total < MAX_INVISIBLE_RATIO:
                    trusted.add(index + 1)
    except Exception:
        return set()  # native text layer unreadable -> nothing is trusted
    return trusted


@dataclass
class GroundingSource:
    """Native text layer of a document (P-032 M4 same-source grounding).

    ``blocks`` carries the raw native block texts (M1 feeds them to the model);
    ``texts`` carries the normalized per-page join (M4 grounds against it) --
    the same extraction, so a model quote copied from its input can never
    drift from the grounding text the way an image-channel quote can."""

    blocks: Dict[int, List[str]]
    texts: Dict[int, str]


def grounding_source(file_path: str) -> GroundingSource:
    """Per-page native text blocks via PyMuPDF (deterministic: the same PDF
    yields the same blocks, so the M1 payload and this grounding source are
    identical by construction). Image blocks are skipped."""
    blocks: Dict[int, List[str]] = {}
    texts: Dict[int, str] = {}
    try:
        import fitz

        with fitz.open(file_path) as doc:
            for index in range(doc.page_count):
                page_blocks: List[str] = []
                for raw in doc[index].get_text("blocks"):
                    if not raw or not isinstance(raw[4], str):
                        continue
                    if len(raw) > 6 and raw[6] != 0:
                        continue  # image block
                    if raw[4].strip():
                        page_blocks.append(raw[4])
                blocks[index + 1] = page_blocks
                texts[index + 1] = normalize("\n".join(page_blocks))
    except Exception:
        return GroundingSource(blocks={}, texts={})  # fail-closed: no grounding
    return GroundingSource(blocks=blocks, texts=texts)


def parse_marker_page(quote_block: object) -> Optional[int]:
    """Page number from a text-first block marker ``[p{page}_b{block}]``.

    Integer ``quote_block`` values are the legacy image-channel shape and are
    deliberately ignored here: P-032 M4 deletes the ``quote_block`` ->
    ``block_id`` attribution heuristic on the text-first path."""
    match = _MARKER_RE.fullmatch(str(quote_block or "").strip())
    return int(match.group(1)) if match else None


def _best_prefix_page(quote: str, texts: Dict[int, str]) -> Optional[int]:
    """Page with the longest V4-quote / V6-haystack word prefix (lowest page
    wins ties); ``None`` when the quote has no words to match."""
    quote_variants = _ladder_variants(quote)
    total = len(quote_variants[4].split())
    if not total:
        return None
    best_page: Optional[int] = None
    best_pref = -1
    for page_no in sorted(texts):
        hay_variants = _ladder_variants(texts[page_no])
        pref = longest_prefix_words(quote_variants[4], hay_variants[6])
        if pref > best_pref:
            best_page, best_pref = page_no, pref
    return best_page


def attribute_candidates(
    candidates: List[Dict[str, Any]],
    source: GroundingSource,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Deterministic page attribution on the same-source grounding text.

    Resolution order per candidate lacking an int ``page`` (P-032 M4; the
    ``kie_pages_processed`` / quote_block-id heuristics are NOT consulted):
      1. marker hint page (``[p{page}_b{block}]``) when the quote verbatim-
         ladder-matches that page's grounding text;
      2. first page (ascending) whose grounding text ladder-matches the quote;
      3. no verbatim hit anywhere: attribute the best word-prefix page so
         Gate A emits the pinned ``N/Mw prefix`` detail instead of
         "grounding unavailable" (fail-closed verdict is unchanged).

    Returns ``(candidates, stats)``; candidates that resolve to no page stay
    untouched and fail closed in the gate."""
    stats = {
        "marker_hint_hits": 0,
        "scan_hits": 0,
        "prefix_only": 0,
        "unresolved": 0,
    }
    out: List[Dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            out.append(candidate)
            continue
        if isinstance(candidate.get("page"), int):
            out.append(candidate)
            continue
        quote = str(candidate.get("quote") or "")
        if not quote.strip():
            stats["unresolved"] += 1
            out.append(candidate)
            continue
        marker_page = parse_marker_page(candidate.get("quote_block"))
        page: Optional[int] = None
        if marker_page is not None and marker_page in source.texts:
            if classify_quote(quote, source.texts[marker_page]).verdict == VERBATIM_EXACT:
                page = marker_page
                stats["marker_hint_hits"] += 1
        if page is None:
            for page_no in sorted(source.texts):
                if page_no == marker_page:
                    continue  # already checked above
                if classify_quote(quote, source.texts[page_no]).verdict == VERBATIM_EXACT:
                    page = page_no
                    stats["scan_hits"] += 1
                    break
        if page is None:
            page = _best_prefix_page(quote, source.texts)
            if page is not None:
                stats["prefix_only"] += 1
        if page is None:
            stats["unresolved"] += 1
            out.append(candidate)
            continue
        candidate = dict(candidate)
        candidate["page"] = page
        out.append(candidate)
    return out, stats

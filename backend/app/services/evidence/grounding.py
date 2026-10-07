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

from typing import Set

# P-032 M5 thresholds, pinned at design time (never runtime-tuned).
MIN_TOTAL_CHARS = 1
MAX_INVISIBLE_RATIO = 0.5


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

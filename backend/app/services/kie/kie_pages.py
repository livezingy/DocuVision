"""Resolve KIE page selection from request options (Lite-compatible spec)."""

from __future__ import annotations

from typing import List, Optional, Tuple


def parse_pages_spec(pages_spec: Optional[str], page_count: int) -> List[int]:
    """Return 1-based page numbers from a pages spec string."""
    if page_count < 1:
        return []
    if not pages_spec or not str(pages_spec).strip():
        return [1]
    spec = str(pages_spec).strip().lower()
    if spec in {"1", "first", "page1"}:
        return [1]
    if spec == "all":
        return list(range(1, page_count + 1))
    selected: List[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            selected.extend(range(start, end + 1))
        else:
            selected.append(int(part))
    return sorted({p for p in selected if 1 <= p <= page_count})


def resolve_kie_pages(
    pages_spec: Optional[str],
    page_count: int,
    max_pages: int,
) -> Tuple[List[int], bool]:
    """
    Resolve pages to process and whether truncation occurred.

    Returns (page_list, truncated).
    """
    if page_count < 1:
        return [1], False
    pages = parse_pages_spec(pages_spec, page_count)
    if not pages:
        pages = [1]
    truncated = False
    if len(pages) > max_pages:
        pages = pages[:max_pages]
        truncated = True
    return pages, truncated


def validate_kie_pages_for_non_pdf(
    pages_spec: Optional[str],
    is_pdf: bool,
) -> Optional[str]:
    """Return error message if invalid; None if OK."""
    if is_pdf:
        return None
    spec = (pages_spec or "").strip()
    if not spec or spec.lower() in {"1", "first", "page1"}:
        return None
    return "kie_pages is only supported for PDF inputs"

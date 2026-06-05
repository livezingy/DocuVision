"""Merge per-page KIE field dicts into one document-level map."""

from __future__ import annotations

from typing import Any, Dict, List


_SKIP_MERGE_KEYS = frozenset({"raw_output"})
_LIST_MERGE_KEYS = frozenset({"items", "line_items"})


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False


def merge_kie_fields(
    fields_by_page: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Merge page dicts in ascending page order.

    Scalars: later non-empty overwrites earlier empty; conflicts favor later page.
    List keys (items): extend in page order.
    raw_output: never merged into top-level.
    """
    merged: Dict[str, Any] = {}
    page_keys = sorted(fields_by_page.keys(), key=lambda k: int(k) if str(k).isdigit() else 0)

    for page_key in page_keys:
        page_fields = fields_by_page.get(page_key)
        if not isinstance(page_fields, dict):
            continue
        for key, value in page_fields.items():
            if key in _SKIP_MERGE_KEYS:
                continue
            if key in _LIST_MERGE_KEYS and isinstance(value, list):
                existing = merged.get(key)
                if isinstance(existing, list):
                    merged[key] = existing + value
                elif existing is None or _is_empty_value(existing):
                    merged[key] = list(value)
                else:
                    merged[key] = [existing] + list(value)
                continue
            if _is_empty_value(value):
                continue
            merged[key] = value

    return merged


def sum_items_count(fields: Dict[str, Any]) -> int:
    items = fields.get("items")
    if isinstance(items, list):
        return len(items)
    line_items = fields.get("line_items")
    if isinstance(line_items, list):
        return len(line_items)
    return 0

"""Merge per-page KIE field dicts into one document-level map."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


_SKIP_MERGE_KEYS = frozenset({"raw_output"})
# "findings" joins the list whitelist in P-032 M3: pico findings accumulate
# per page (extend) instead of later pages silently overwriting earlier ones.
_LIST_MERGE_KEYS = frozenset({"items", "line_items", "findings"})


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
    List keys (items, line_items, findings): extend in page order.
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


def backfill_schema_keys(
    fields: Dict[str, Any],
    schema_keys: Iterable[str],
) -> Dict[str, Any]:
    """
    Backfill missing scalar schema keys with "" (never-omit contract).

    The KIE prompts instruct the model to never omit a key, but Qwen may still
    drop a key it cannot determine (P-034 round 3: carrier/limits omitted).
    Restoring presence with an empty value makes the X2/P1-3 acceptance criteria
    see a present key (carrier == "") instead of a KeyError / "key omitted"
    ambiguity. Empty strings are not "filled" values, so the fill-confidence and
    production-hit metrics are unaffected.

    List keys (items / line_items / findings) are left untouched: their empty
    semantics is ``[]`` and is handled by downstream consumers (e.g. the evidence
    gate treats a missing findings list as "no evidence findings").
    """
    if not isinstance(fields, dict):
        return fields
    for key in schema_keys:
        key = str(key)
        if key in fields:
            continue
        if key in _LIST_MERGE_KEYS:
            continue
        fields[key] = ""
    return fields


def sum_items_count(fields: Dict[str, Any]) -> int:
    items = fields.get("items")
    if isinstance(items, list):
        return len(items)
    line_items = fields.get("line_items")
    if isinstance(line_items, list):
        return len(line_items)
    return 0

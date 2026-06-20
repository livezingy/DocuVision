"""Map extracted table rows to vertical template fields (bank statement, invoice line items)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Set

# Canonical output field -> header aliases (normalized lowercase)
TABLE_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "bank_statement": {
        "output_fields": ["transaction_date", "description", "amount", "balance"],
        "aliases": {
            "transaction_date": (
                "date",
                "transaction date",
                "posting date",
                "value date",
                "txn date",
            ),
            "description": (
                "description",
                "memo",
                "narration",
                "details",
                "payee",
                "merchant",
            ),
            "amount": ("amount", "debit", "credit", "withdrawal", "deposit"),
            "balance": ("balance", "running balance", "available balance"),
        },
    },
    "invoice_line_items": {
        "output_fields": ["line_description", "quantity", "unit_price", "line_total"],
        "aliases": {
            "line_description": (
                "description",
                "item",
                "product",
                "service",
                "line description",
                "name",
            ),
            "quantity": ("qty", "quantity", "units", "count"),
            "unit_price": ("unit price", "price", "rate", "unit cost"),
            "line_total": ("amount", "line total", "total", "extended price", "subtotal"),
        },
    },
}


def list_table_templates() -> List[str]:
    return sorted(TABLE_TEMPLATES.keys())


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _alias_lookup(template: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for field, aliases in (template.get("aliases") or {}).items():
        for alias in aliases:
            out[_normalize_header(alias)] = field
    return out


def _table_data_rows(table: Dict[str, Any]) -> tuple[List[str], List[List[Any]]]:
    data = table.get("data")
    if isinstance(data, list) and data:
        if isinstance(data[0], (list, tuple)):
            header = [str(c) for c in data[0]]
            rows = [list(r) for r in data[1:] if isinstance(r, (list, tuple))]
            return header, rows
    headers = table.get("headers") or []
    rows = table.get("rows") or []
    if headers:
        return [str(h) for h in headers], [list(r) for r in rows]
    return [], []


def _header_map(headers: Sequence[str], alias_lookup: Dict[str, str]) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    for idx, header in enumerate(headers):
        canonical = alias_lookup.get(_normalize_header(str(header)))
        if canonical:
            mapping[idx] = canonical
    return mapping


def _row_looks_like_header(row: Sequence[Any], alias_lookup: Dict[str, str]) -> bool:
    hits = 0
    for cell in row:
        if _normalize_header(str(cell)) in alias_lookup:
            hits += 1
    return hits >= 2


def map_table_rows(
    table: Dict[str, Any],
    template_name: str,
    *,
    table_index: int = 0,
) -> List[Dict[str, Any]]:
    """Map one extracted table to template field dicts."""
    template = TABLE_TEMPLATES.get((template_name or "").strip().lower())
    if not template:
        return []

    alias_lookup = _alias_lookup(template)
    output_fields: List[str] = list(template.get("output_fields") or [])
    headers, rows = _table_data_rows(table)
    header_map = _header_map(headers, alias_lookup)
    data_rows = rows

    if not header_map and rows and _row_looks_like_header(rows[0], alias_lookup):
        header_map = _header_map([str(c) for c in rows[0]], alias_lookup)
        data_rows = rows[1:]
    elif not header_map and rows and template_name == "bank_statement":
        header_map = {0: "transaction_date", 1: "description", 2: "amount", 3: "balance"}
        data_rows = rows[1:] if _row_looks_like_header(rows[0], alias_lookup) else rows

    page = int(table.get("page") or 1)
    mapped: List[Dict[str, Any]] = []
    for row_index, row in enumerate(data_rows):
        record: Dict[str, Any] = {
            "template": template_name,
            "source_table_index": table_index,
            "page": page,
            "row_index": row_index,
        }
        for col_idx, cell in enumerate(row):
            field = header_map.get(col_idx)
            if not field:
                continue
            text = str(cell or "").strip()
            if text:
                record[field] = text
        if any(record.get(f) for f in output_fields):
            for field in output_fields:
                record.setdefault(field, "")
            mapped.append(record)
    return mapped


def apply_table_template(
    tables: List[Dict[str, Any]],
    template_name: str,
) -> List[Dict[str, Any]]:
    """Apply a vertical template across all tables; returns flat mapped row list."""
    if not tables or not template_name:
        return []
    name = template_name.strip().lower()
    if name not in TABLE_TEMPLATES:
        return []

    out: List[Dict[str, Any]] = []
    for idx, table in enumerate(tables):
        if isinstance(table, dict):
            out.extend(map_table_rows(table, name, table_index=idx))
    return out

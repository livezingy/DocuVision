"""Map extracted tables or KIE line items to transaction-like JSON."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

# Header aliases (case-insensitive) → canonical transaction field
_HEADER_ALIASES: Dict[str, str] = {
    "date": "date",
    "transaction date": "date",
    "posting date": "date",
    "value date": "date",
    "description": "description",
    "memo": "description",
    "narration": "description",
    "details": "description",
    "payee": "description",
    "merchant": "description",
    "amount": "amount",
    "debit": "amount",
    "credit": "amount",
    "total": "amount",
    "balance": "balance",
    "running balance": "balance",
    "category": "category",
    "type": "category",
    "reference": "reference",
    "ref": "reference",
    "transaction id": "reference",
    "txn id": "reference",
}


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _map_headers(headers: Sequence[str]) -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    for idx, header in enumerate(headers):
        canonical = _HEADER_ALIASES.get(_normalize_header(str(header)))
        if canonical:
            mapping[idx] = canonical
    return mapping


def _row_to_transaction(
    row: Sequence[Any],
    header_map: Dict[int, str],
    *,
    table_id: str,
    page: int,
    row_index: int,
) -> Optional[Dict[str, Any]]:
    tx: Dict[str, Any] = {
        "source_table": table_id,
        "page": page,
        "row_index": row_index,
    }
    for col_idx, cell in enumerate(row):
        field = header_map.get(col_idx)
        if not field:
            continue
        text = str(cell or "").strip()
        if text:
            tx[field] = text
    if len(tx) <= 3:
        return None
    return tx


def _row_looks_like_header(row: Sequence[Any]) -> bool:
    """True when a row contains multiple known column header labels."""
    hits = 0
    for cell in row:
        if _normalize_header(str(cell)) in _HEADER_ALIASES:
            hits += 1
    return hits >= 2


def extract_transactions_from_tables(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    transactions: List[Dict[str, Any]] = []
    for table in tables or []:
        headers = table.get("headers") or []
        rows = table.get("rows") or []
        header_map = _map_headers(headers)
        data_rows = rows

        if not header_map and rows and _row_looks_like_header(rows[0]):
            header_map = _map_headers([str(c) for c in rows[0]])
            data_rows = rows[1:]
        elif not header_map and rows:
            # Positional fallback when extractors emit numeric column names (0,1,2,3)
            header_map = {0: "date", 1: "description", 2: "amount", 3: "category"}
            data_rows = rows[1:] if _row_looks_like_header(rows[0]) else rows
        elif headers:
            data_rows = rows
        else:
            data_rows = rows[1:] if len(rows) > 1 else rows
            if rows and not headers:
                header_map = _map_headers([str(c) for c in rows[0]])

        for ri, row in enumerate(data_rows):
            tx = _row_to_transaction(
                row,
                header_map,
                table_id=str(table.get("table_id", "")),
                page=int(table.get("page", 1)),
                row_index=ri,
            )
            if tx:
                transactions.append(tx)
    return transactions


def extract_transactions_from_kie_fields(fields: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(fields, dict):
        return []

    report_txs = fields.get("transactions")
    if isinstance(report_txs, list):
        transactions: List[Dict[str, Any]] = []
        for idx, item in enumerate(report_txs):
            if not isinstance(item, dict):
                continue
            tx = {
                "source": "kie",
                "row_index": idx,
                "date": item.get("date") or "",
                "description": item.get("description") or "",
                "amount": item.get("amount") or "",
                "category": item.get("category") or "",
                "reference": item.get("reference") or "",
            }
            if any(v for k, v in tx.items() if k not in ("source", "row_index") and v):
                transactions.append(tx)
        if transactions:
            return transactions

    items = fields.get("items")
    if not isinstance(items, list):
        return []
    transactions: List[Dict[str, Any]] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        tx = {
            "source": "kie",
            "row_index": idx,
            "description": item.get("description") or item.get("name") or "",
            "quantity": item.get("quantity") or "",
            "unit_price": item.get("unit_price") or item.get("price") or "",
            "amount": item.get("amount") or item.get("total") or "",
            "category": item.get("category") or "",
        }
        if any(v for k, v in tx.items() if k not in ("source", "row_index") and v):
            transactions.append(tx)
    return transactions


def extract_transactions_from_result(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build transaction list from Lite tables or Pro KIE fields."""
    tables = result.get("tables") or []
    if tables:
        return extract_transactions_from_tables(tables)

    kie_fields = result.get("kie_fields") or (result.get("view") or {}).get("fields") or {}
    if isinstance(kie_fields, dict) and kie_fields:
        return extract_transactions_from_kie_fields(kie_fields)
    return []

"""Cross-page table stitching (MVP): header match + pandas concat."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def _normalize_header(row: Sequence[Any]) -> tuple:
    return tuple(str(c or "").strip().lower() for c in row)


def _table_rows(table: Dict[str, Any]) -> List[List[Any]]:
    data = table.get("data")
    if not isinstance(data, list) or len(data) < 1:
        return []
    return [list(r) for r in data if isinstance(r, (list, tuple))]


def stitch_tables_by_header(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge consecutive tables with identical first-row headers.

    Returns a new list; tables without matching headers are kept separate.
    """
    if not tables:
        return []

    try:
        import pandas as pd
    except ImportError:
        return tables

    groups: List[List[Dict[str, Any]]] = []
    current_group: List[Dict[str, Any]] = []
    current_header: Optional[tuple] = None

    for table in tables:
        rows = _table_rows(table)
        if not rows:
            groups.append([table])
            continue
        header = _normalize_header(rows[0])
        if current_group and header == current_header:
            current_group.append(table)
        else:
            if current_group:
                groups.append(current_group)
            current_group = [table]
            current_header = header
    if current_group:
        groups.append(current_group)

    stitched: List[Dict[str, Any]] = []
    for group in groups:
        if len(group) == 1:
            stitched.append(group[0])
            continue
        header_row = _table_rows(group[0])[0]
        frames = []
        for tbl in group:
            rows = _table_rows(tbl)
            if len(rows) <= 1:
                continue
            df = pd.DataFrame(rows[1:], columns=header_row)
            frames.append(df)
        if not frames:
            stitched.append(group[0])
            continue
        merged = pd.concat(frames, ignore_index=True)
        merged_data = [header_row] + merged.values.tolist()
        base = dict(group[0])
        base["data"] = merged_data
        base["stitched_from"] = len(group)
        stitched.append(base)

    return stitched

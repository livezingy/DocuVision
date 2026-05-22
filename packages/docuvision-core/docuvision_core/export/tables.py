"""Export Lite-style table dicts to CSV / Excel."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Dict, List, Union


def _normalize_rows(table: Dict[str, Any]) -> List[List[str]]:
    headers = table.get("headers") or []
    rows = table.get("rows") or []
    if headers:
        return [headers] + rows
    return rows


def export_tables_to_csv(tables: List[Dict[str, Any]], merge: bool = False) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if merge:
        for table in tables:
            for row in _normalize_rows(table):
                writer.writerow(row)
            writer.writerow([])
    else:
        for idx, table in enumerate(tables):
            if idx > 0:
                writer.writerow([])
                writer.writerow([f"--- table {idx + 1} ---"])
            for row in _normalize_rows(table):
                writer.writerow(row)
    return buffer.getvalue().encode("utf-8-sig")


def export_tables_to_xlsx(tables: List[Dict[str, Any]], merge: bool = False) -> bytes:
    import pandas as pd

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if merge:
            all_rows: List[List[str]] = []
            for table in tables:
                all_rows.extend(_normalize_rows(table))
                all_rows.append([])
            pd.DataFrame(all_rows).to_excel(writer, sheet_name="tables", index=False, header=False)
        else:
            for idx, table in enumerate(tables):
                sheet = f"table_{idx + 1}"[:31]
                rows = _normalize_rows(table)
                pd.DataFrame(rows[1:], columns=rows[0] if rows else None).to_excel(
                    writer, sheet_name=sheet, index=False
                )
    return output.getvalue()


def write_csv_file(path: Union[str, Path], tables: List[Dict[str, Any]], merge: bool = False) -> None:
    Path(path).write_bytes(export_tables_to_csv(tables, merge=merge))


def write_xlsx_file(path: Union[str, Path], tables: List[Dict[str, Any]], merge: bool = False) -> None:
    Path(path).write_bytes(export_tables_to_xlsx(tables, merge=merge))

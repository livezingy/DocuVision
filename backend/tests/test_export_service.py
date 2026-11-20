"""Unit tests for ExportService table banners (CSV / Markdown / XLSX).

No Paddle / GPU. CSV and Markdown are pure logic; XLSX is skipped when
pandas/openpyxl are unavailable.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest

from app.services.export_service import (
    ExportService,
    excel_safe_cell,
    format_table_csv_banner,
    format_table_export_title,
    table_confidence_pct,
)


def _table(
    *,
    page: Any = 16,
    confidence: Any = None,
    score: Any = None,
    data: List[List[str]] | None = None,
    rows: int = 2,
    columns: int = 2,
) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "page": page,
        "data": data if data is not None else [["H1", "H2"], ["a", "b"]],
        "rows": rows,
        "columns": columns,
    }
    if confidence is not None:
        item["confidence"] = confidence
    if score is not None:
        item["score"] = score
    return item


class TestTableConfidencePct:
    def test_ratio_rounded_to_percent(self):
        assert table_confidence_pct({"confidence": 0.87}) == 87

    def test_one_is_one_hundred(self):
        assert table_confidence_pct({"confidence": 1.0}) == 100

    def test_zero_is_zero_not_fallback(self):
        assert table_confidence_pct({"confidence": 0.0, "score": 0.9}) == 0

    def test_missing_confidence_falls_back_to_score(self):
        assert table_confidence_pct({"score": 0.5}) == 50

    def test_already_percent_score(self):
        assert table_confidence_pct({"score": 92}) == 92

    def test_neither_is_zero(self):
        assert table_confidence_pct({}) == 0

    def test_invalid_is_zero(self):
        assert table_confidence_pct({"confidence": "n/a"}) == 0


class TestTableBannerFormat:
    def test_title_and_csv_banner(self):
        table = _table(page=16, confidence=0.87)
        assert format_table_export_title(7, table) == "Table 7 (Page 16) confidence=87%"
        assert format_table_csv_banner(7, table) == "=== Table 7 (Page 16) confidence=87% ==="

    def test_score_fallback_in_banner(self):
        table = _table(page=3, score=0.5)
        assert format_table_csv_banner(2, table) == "=== Table 2 (Page 3) confidence=50% ==="

    def test_title_appends_caption(self):
        table = _table(page=16, confidence=0.87)
        table["caption"] = "Table 1: Ablation results"
        assert format_table_export_title(1, table) == (
            "Table 1 (Page 16) confidence=87% — Table 1: Ablation results"
        )
        assert format_table_csv_banner(1, table) == "=== Table 1 (Page 16) confidence=87% ==="


class TestExcelSafeCell:
    def test_plus_prefixed_text(self):
        assert excel_safe_cell("+Accuracy") == "'+Accuracy"

    def test_equals_formula(self):
        assert excel_safe_cell("=SUM(1)") == "'=SUM(1)"

    def test_numeric_minus_kept(self):
        assert excel_safe_cell("-0.5") == "-0.5"

    def test_text_minus_prefixed(self):
        assert excel_safe_cell("-Accuracy") == "'-Accuracy"

    def test_plain_unchanged(self):
        assert excel_safe_cell("hello") == "hello"


class TestExportCsvAndMarkdown:
    def test_csv_banner_per_table(self, tmp_path, monkeypatch):
        from app.core.config import settings as _settings

        monkeypatch.setattr(_settings, "OUTPUT_DIR", str(tmp_path))
        svc = ExportService()
        result = {
            "tables": [
                _table(page=16, confidence=0.87),
                _table(page=3, score=0.5, data=[["X"]], rows=1, columns=1),
            ]
        }
        path = asyncio.run(svc.to_csv(result, "t1"))
        text = open(path, encoding="utf-8-sig").read()
        assert "=== Table 1 (Page 16) confidence=87% ===" in text
        assert "=== Table 2 (Page 3) confidence=50% ===" in text
        assert "H1" in text and "a" in text

    def test_csv_escapes_plus_and_writes_caption(self, tmp_path, monkeypatch):
        from app.core.config import settings as _settings

        monkeypatch.setattr(_settings, "OUTPUT_DIR", str(tmp_path))
        svc = ExportService()
        table = _table(page=16, confidence=0.87, data=[["H", "+pos"], ["a", "b"]])
        table["caption"] = "Table 1: Ablation results"
        path = asyncio.run(svc.to_csv({"tables": [table]}, "t-plus"))
        text = open(path, encoding="utf-8-sig").read()
        assert "=== Table 1 (Page 16) confidence=87% ===" in text
        assert "Caption: Table 1: Ablation results" in text
        assert "'+pos" in text
        assert "### " not in text

    def test_markdown_heading_includes_confidence(self, tmp_path, monkeypatch):
        from app.core.config import settings as _settings

        monkeypatch.setattr(_settings, "OUTPUT_DIR", str(tmp_path))
        svc = ExportService()
        md = asyncio.run(svc.to_markdown({"tables": [_table(page=16, confidence=0.87)]}))
        assert "### Table 1 (Page 16) confidence=87%" in md

    def test_markdown_heading_includes_caption(self, tmp_path, monkeypatch):
        from app.core.config import settings as _settings

        monkeypatch.setattr(_settings, "OUTPUT_DIR", str(tmp_path))
        svc = ExportService()
        table = _table(page=16, confidence=0.87)
        table["caption"] = "Table 1: Ablation results"
        md = asyncio.run(svc.to_markdown({"tables": [table]}))
        assert "### Table 1 (Page 16) confidence=87% — Table 1: Ablation results" in md


class TestExportExcel:
    def test_xlsx_title_row(self, tmp_path, monkeypatch):
        pytest.importorskip("pandas")
        pytest.importorskip("openpyxl")
        from openpyxl import load_workbook

        from app.core.config import settings as _settings

        monkeypatch.setattr(_settings, "OUTPUT_DIR", str(tmp_path))
        svc = ExportService()
        result = {"document_info": {}, "tables": [_table(page=16, confidence=0.87)]}
        path = asyncio.run(svc.to_excel(result, "t-xlsx"))
        wb = load_workbook(path)
        ws = wb["Table_1"]
        assert ws.cell(row=1, column=1).value == "Table 1 (Page 16) confidence=87%"
        assert ws.cell(row=2, column=1).value == "H1"
        assert ws.cell(row=3, column=1).value == "a"


class TestSameSourceSameValue:
    """R-003/P-042 T4 (AC3): the batch's mapping result (``mapped_table_rows``
    + the ``mapped_table_fields`` stamp, R-003 T2) is ONE source flowing to
    three export surfaces — the Google Sheets write path (rows captured at the
    service's worksheet seam, mock level, no network), the aggregate xlsx
    MappedRows sheet, and the per-order CSV files (R-003 T5). Field-by-field
    equality across all three. All fixture data is fictional."""

    _FIELDS = ["po_number", "quantity", "unit_price", "line_total"]
    _TASKS = (("ac3-task-1", "a.png"), ("ac3-task-2", "b.png"))

    @staticmethod
    def _batch():
        from datetime import datetime

        from app.services.batch_service import (
            BatchJob,
            BatchStatus,
            BatchTask,
            TaskStatus,
        )

        def _row(idx, po, qty, price, total):
            return {
                "template": "po_line_schema",
                "source_table_index": 0,
                "page": 1,
                "row_index": idx,
                "po_number": po,
                "quantity": qty,
                "unit_price": price,
                "line_total": total,
            }

        batch = BatchJob(
            batch_id="ac3-batch",
            name="same-source",
            status=BatchStatus.COMPLETED,
            options={"table_template": "po_line_schema"},
            created_at=datetime.now(),
        )
        batch.total_tasks = 2
        t1 = BatchTask(
            task_id="ac3-task-1", file_path="/a.png", file_name="a.png", status=TaskStatus.COMPLETED
        )
        t1.result = {
            "mapped_table_fields": list(TestSameSourceSameValue._FIELDS),
            "mapped_table_rows": [
                _row(0, "PO-1001", "2", "10.50", "21.00"),
                _row(1, "PO-1002", "", "5.00", "5.00"),
            ],
        }
        t2 = BatchTask(
            task_id="ac3-task-2", file_path="/b.png", file_name="b.png", status=TaskStatus.COMPLETED
        )
        t2.result = {
            "mapped_table_fields": list(TestSameSourceSameValue._FIELDS),
            "mapped_table_rows": [_row(0, "PO-1003", "1", "7.25", "7.25")],
        }
        batch.tasks = [t1, t2]
        batch.completed_tasks = 2
        batch.failed_tasks = 0
        return batch

    class _CaptureWorksheet:
        """In-memory gspread worksheet double capturing what the service wrote."""

        def __init__(self):
            self.rows = []

        def get_all_values(self):
            return [list(r) for r in self.rows]

        def update(self, values, range_name=None, **kwargs):
            start = 0
            if range_name and range_name.startswith("A"):
                start = max(int(range_name[1:]) - 1, 0)
            while len(self.rows) < start + len(values):
                self.rows.append([])
            for offset, row_values in enumerate(values):
                self.rows[start + offset] = list(row_values)

        def append_rows(self, values, **kwargs):
            self.rows.extend([list(r) for r in values])

        def delete_rows(self, start_index, end_index=None):
            end = end_index if end_index is not None else start_index
            del self.rows[start_index - 1 : end]

    def _capture_sheets_rows(self, batch):
        """Run the real Sheets write path with the client seam stubbed; return
        the matrix the service handed to the worksheet (mock level, no net)."""
        from app.services.sheets_export_service import export_batch_to_sheets

        worksheet = self._CaptureWorksheet()

        class _Spreadsheet:
            def worksheet(self, title):
                return worksheet

        class _Client:
            def open_by_key(self, key):
                return _Spreadsheet()

        summary = export_batch_to_sheets(
            batch,
            credentials_file="C:/fake/ac3-service-account.json",
            spreadsheet_id="fake-ac3-spreadsheet",
            client_builder=lambda credentials_file: _Client(),
        )
        assert summary["appended"] == 3
        return worksheet.rows

    def test_sheets_csv_xlsx_field_by_field(self, tmp_path):
        pytest.importorskip("pandas")
        pytest.importorskip("openpyxl")
        import csv
        import io

        import pandas as pd

        from app.services.batch_export_service import build_batch_xlsx_bytes
        from app.services.per_order_export_service import export_batch_per_order

        batch = self._batch()

        # (1) Sheets — rows captured from the service write path (mock seam)
        sheet_matrix = self._capture_sheets_rows(batch)
        sheets_header = [str(c) for c in sheet_matrix[0]]
        sheets_rows = [
            dict(zip(sheets_header, (str(c) for c in row))) for row in sheet_matrix[1:]
        ]
        sheets_field_cols = [c for c in sheets_header if c not in ("batch_id", "task_id")]
        assert sheets_field_cols[0] == "file_name"
        assert sheets_field_cols[1:5] == self._FIELDS

        # (2) xlsx — aggregate workbook, MappedRows sheet read back
        payload = build_batch_xlsx_bytes(batch, mode="all")
        xlsx_df = pd.ExcelFile(io.BytesIO(payload)).parse("MappedRows")
        xlsx_cols = [str(c) for c in xlsx_df.columns.tolist()]
        assert xlsx_cols == sheets_field_cols  # same columns, same order

        # (3) csv — per-order split files (one CSV per order, T5 surface)
        export_batch_per_order(batch, str(tmp_path))
        csv_tables = {}
        for name, (task_id, _) in zip(("a.csv", "b.csv"), self._TASKS):
            with open(tmp_path / name, "r", encoding="utf-8", newline="") as fh:
                table = list(csv.reader(fh))
            csv_tables[task_id] = table
            assert [str(c) for c in table[0]] == sheets_field_cols  # set format shared

        # field-by-field: rows aligned per task (order preserved on every surface)
        def _norm(value):
            return "" if pd.isna(value) else str(value)

        def _canon(value):
            """Numeric values canonicalize to float: the xlsx round-trip
            numericises text cells ('2' -> 2.0) — a storage artifact, not a
            value change. Everything else compares as exact text."""
            s = _norm(value)
            try:
                return float(s)
            except ValueError:
                return s

        for task_id, file_name in self._TASKS:
            s_rows = [r for r in sheets_rows if r["task_id"] == task_id]
            x_rows = xlsx_df[xlsx_df["file_name"] == file_name]
            c_table = csv_tables[task_id]
            assert len(x_rows) == len(s_rows) == len(c_table) - 1
            x_records = [
                {col: _norm(v) for col, v in zip(xlsx_cols, row)}
                for row in x_rows.values.tolist()
            ]
            for idx, s_row in enumerate(s_rows):
                x_row = x_records[idx]
                c_row = {col: str(v) for col, v in zip(sheets_field_cols, c_table[idx + 1])}
                for col in sheets_field_cols:
                    assert _canon(s_row[col]) == _canon(x_row[col]) == _canon(c_row[col]), (
                        f"{task_id} row {idx} column {col}: "
                        f"sheets={s_row[col]!r} xlsx={x_row[col]!r} csv={c_row[col]!r}"
                    )

    def test_empty_mapping_rows_agrees_across_surfaces(self, tmp_path):
        pytest.importorskip("pandas")
        pytest.importorskip("openpyxl")
        import io

        import pandas as pd

        from app.services.batch_export_service import build_batch_xlsx_bytes
        from app.services.per_order_export_service import export_batch_per_order
        from app.services.sheets_export_service import export_batch_to_sheets

        batch = self._batch()
        for task in batch.tasks:
            task.result.pop("mapped_table_rows")

        # Sheets: the write is skipped, nothing reaches the worksheet
        worksheet = self._CaptureWorksheet()

        class _Spreadsheet:
            def worksheet(self, title):
                return worksheet

        class _Client:
            def open_by_key(self, key):
                return _Spreadsheet()

        summary = export_batch_to_sheets(
            batch,
            credentials_file="C:/fake/ac3-service-account.json",
            spreadsheet_id="fake-ac3-spreadsheet",
            client_builder=lambda credentials_file: _Client(),
        )
        assert summary.get("skipped") == "no mapping rows"
        assert worksheet.rows == []

        # xlsx: no MappedRows sheet
        sheets = pd.ExcelFile(io.BytesIO(build_batch_xlsx_bytes(batch, mode="all"))).sheet_names
        assert "MappedRows" not in sheets

        # csv: no per-order files
        result = export_batch_per_order(batch, str(tmp_path))
        assert result["written"] == 0
        assert list(tmp_path.iterdir()) == []

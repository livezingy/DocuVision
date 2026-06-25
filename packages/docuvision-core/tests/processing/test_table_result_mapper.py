"""Tests for TableProcessor result mapping."""


class _FakeTable:
    def extract(self):
        return [
            ["Date", "Description", "Amount", "Balance"],
            ["02/01", "Deposit", "100.00", "1100.00"],
        ]


def test_processor_results_to_tables_builds_data_grid():
    from docuvision_core.processing.table_result_mapper import processor_results_to_tables

    raw = [{"table": _FakeTable(), "score": 0.9, "source": "pdfplumber_lines", "bbox": (0, 0, 100, 100)}]
    tables = processor_results_to_tables(raw, page=1)
    assert len(tables) == 1
    assert tables[0]["headers"] == ["Date", "Description", "Amount", "Balance"]
    assert len(tables[0]["rows"]) == 1
    assert tables[0]["data"][0][0] == "Date"
    assert tables[0]["data"][1][1] == "Deposit"

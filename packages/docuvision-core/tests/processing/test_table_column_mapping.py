"""Tests for vertical table column mapping templates."""

from docuvision_core.processing.table_column_mapping import (
    apply_table_template,
    list_table_templates,
    map_table_rows,
)


def test_list_table_templates() -> None:
    names = list_table_templates()
    assert "bank_statement" in names
    assert "invoice_line_items" in names


def test_bank_statement_mapping_from_data_grid() -> None:
    table = {
        "page": 1,
        "data": [
            ["Date", "Description", "Amount", "Balance"],
            ["2024-01-01", "Coffee shop", "-5.00", "100.00"],
        ],
    }
    rows = map_table_rows(table, "bank_statement")
    assert len(rows) == 1
    assert rows[0]["transaction_date"] == "2024-01-01"
    assert rows[0]["description"] == "Coffee shop"
    assert rows[0]["amount"] == "-5.00"
    assert rows[0]["balance"] == "100.00"


def test_invoice_line_items_apply_template() -> None:
    tables = [
        {
            "page": 1,
            "data": [
                ["Description", "Qty", "Unit Price", "Amount"],
                ["Widget A", "2", "10.00", "20.00"],
            ],
        }
    ]
    mapped = apply_table_template(tables, "invoice_line_items")
    assert len(mapped) == 1
    assert mapped[0]["line_description"] == "Widget A"
    assert mapped[0]["quantity"] == "2"
    assert mapped[0]["unit_price"] == "10.00"
    assert mapped[0]["line_total"] == "20.00"

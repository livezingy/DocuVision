"""Tests for Lite /extract/auto mapped_table_rows pass-through."""

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
FIXTURES = Path(__file__).parent / "fixtures"


def _make_pipeline_output(template: str, rows):
    return {
        "tables": [],
        "routing": {},
        "quality": {},
        "mapped_table_rows": rows,
        "table_template": template,
    }


def test_extract_auto_returns_mapped_table_rows_and_template():
    pdf_path = FIXTURES / "sample_bordered.pdf"
    if not pdf_path.exists():
        import pytest
        pytest.skip("sample_bordered.pdf fixture missing")

    rows = [{"date": "2026-01-01", "description": "Open", "amount": "100.00"}]
    with patch("app.api.routes_extract._run_pipeline") as mock_run, patch(
        "app.api.routes_extract.detect_file_type", return_value=("pdf_digital", 1)
    ):
        mock_run.return_value = _make_pipeline_output("bank_statement", rows)
        with pdf_path.open("rb") as f:
            response = client.post(
                "/api/v1/lite/extract/auto",
                files={"file": ("sample_bordered.pdf", f, "application/pdf")},
                data={"mode": "smart", "table_template": "bank_statement"},
            )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["table_template"] == "bank_statement"
    assert data["mapped_table_rows"] == rows


def test_build_lite_result_passes_mapped_fields():
    from app.services.lite_builder import build_lite_result

    pipeline_output = {
        "tables": [],
        "routing": {},
        "quality": {},
        "mapped_table_rows": [{"a": 1}],
        "table_template": "invoice_line_items",
    }
    pdf_path = FIXTURES / "sample_bordered.pdf"
    if not pdf_path.exists():
        import pytest
        pytest.skip("sample_bordered.pdf fixture missing")

    result = build_lite_result(
        file_path=pdf_path,
        mime_type="application/pdf",
        pipeline_output=pipeline_output,
    )
    assert result.table_template == "invoice_line_items"
    assert result.mapped_table_rows == [{"a": 1}]


def test_extract_tables_passes_table_template_to_pipeline():
    """/extract/tables must forward table_template to extract_tables_from_pdf."""
    pdf_path = FIXTURES / "sample_bordered.pdf"
    if not pdf_path.exists():
        import pytest
        pytest.skip("sample_bordered.pdf fixture missing")

    rows = [{"date": "2026-01-01", "description": "Open", "amount": "100.00"}]
    captured = {}

    def _fake_extract(file_path, **kwargs):
        captured.update(kwargs)
        return _make_pipeline_output(kwargs.get("table_template"), rows)

    with patch(
        "app.api.routes_extract.extract_tables_from_pdf", side_effect=_fake_extract
    ), patch(
        "app.api.routes_extract.detect_file_type", return_value=("pdf_digital", 1)
    ):
        with pdf_path.open("rb") as f:
            response = client.post(
                "/api/v1/lite/extract/tables",
                files={"file": ("sample_bordered.pdf", f, "application/pdf")},
                data={"mode": "smart", "table_template": "bank_statement"},
            )

    assert response.status_code == 200, response.text
    assert captured.get("table_template") == "bank_statement"
    data = response.json()
    assert data["table_template"] == "bank_statement"
    assert data["mapped_table_rows"] == rows

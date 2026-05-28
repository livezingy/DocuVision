"""Tests for Lite export helpers."""

from app.services.lite_export import export_lite_to_json, export_lite_to_markdown


def test_export_lite_to_markdown_includes_text_and_tables():
    result = {
        "input": {"filename": "sample.pdf", "detected_file_type": "pdf_digital", "page_count": 1},
        "routing": {"engine_used": "smart (pdfplumber)"},
        "quality": {"overall_confidence": 0.9},
        "text_preview": "Para one\n\nPara two",
        "tables": [
            {
                "page": 1,
                "headers": ["A", "B"],
                "rows": [["1", "2"]],
            }
        ],
    }
    md = export_lite_to_markdown(result)
    assert "Para one" in md
    assert "Para two" in md
    assert "| A | B |" in md
    assert export_lite_to_json(result).startswith("{")

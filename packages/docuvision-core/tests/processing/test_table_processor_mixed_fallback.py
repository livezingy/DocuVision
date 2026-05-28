"""Tests for Smart mixed-mode Camelot low-score fallback."""

from unittest.mock import MagicMock, patch

from docuvision_core.processing.table_processor import TableProcessor


def _make_processor(threshold=0.8):
    return TableProcessor(
        {
            "table_method": "mixed",
            "table_score_threshold": 0.5,
            "smart_camelot_fallback_threshold": threshold,
        }
    )


@patch("docuvision_core.processing.table_processor.ExtractorFactory")
def test_mixed_runs_camelot_when_pdfplumber_max_score_below_threshold(mock_factory):
    pdfplumber = MagicMock()
    camelot = MagicMock()
    mock_factory.create.side_effect = lambda name: pdfplumber if name == "pdfplumber" else camelot

    pdfplumber.extract_tables.return_value = [
        {"bbox": (0, 0, 100, 100), "score": 0.4, "source": "pdfplumber_lines"},
    ]
    camelot.extract_tables.return_value = [
        {"bbox": (0, 0, 100, 100), "score": 0.9, "source": "camelot_lattice"},
    ]

    page = MagicMock()
    page.page_number = 1
    analyzer = MagicMock()
    analyzer.predict_table_type.return_value = "bordered"

    processor = _make_processor(threshold=0.8)
    results = processor._process_mixed("/tmp/sample.pdf", page, analyzer, score_threshold=0.5)

    camelot.extract_tables.assert_called_once()
    call_kwargs = camelot.extract_tables.call_args[0][2]
    assert "table_areas" not in call_kwargs
    assert call_kwargs["flavor"] == "lattice"
    assert len(results) == 1
    assert results[0]["score"] == 0.9


@patch("docuvision_core.processing.table_processor.ExtractorFactory")
def test_mixed_skips_camelot_when_pdfplumber_max_score_above_threshold(mock_factory):
    pdfplumber = MagicMock()
    camelot = MagicMock()
    mock_factory.create.side_effect = lambda name: pdfplumber if name == "pdfplumber" else camelot

    pdfplumber.extract_tables.return_value = [
        {"bbox": (0, 0, 100, 100), "score": 0.85, "source": "pdfplumber_lines"},
    ]

    page = MagicMock()
    page.page_number = 1
    analyzer = MagicMock()
    analyzer.predict_table_type.return_value = "bordered"

    processor = _make_processor(threshold=0.8)
    results = processor._process_mixed("/tmp/sample.pdf", page, analyzer, score_threshold=0.5)

    camelot.extract_tables.assert_not_called()
    assert len(results) == 1
    assert results[0]["score"] == 0.85

"""Tests for TableTypeClassifier.classify()."""

from unittest.mock import MagicMock

from docuvision_core.processing.table_type_classifier import TableTypeClassifier


def _make_classifier(h_lines, v_lines, page_width=595.0, page_height=842.0):
    analyzer = MagicMock()
    analyzer.line_analysis = {
        "horizontal_lines": [{"x0": 0, "x1": 100, "y0": i * 20, "y1": i * 20} for i in range(h_lines)],
        "vertical_lines": [{"x0": i * 30, "x1": i * 30, "y0": 0, "y1": 100} for i in range(v_lines)],
    }
    page = MagicMock()
    page.width = page_width
    page.height = page_height
    return TableTypeClassifier(analyzer, page)


def test_classify_quick_filter_unbordered():
    clf = _make_classifier(h_lines=2, v_lines=5)
    result = clf.classify()
    assert result["table_type"] == "unbordered"
    assert result["method"] == "quick_filter"
    assert result["score"] == 0.0
    assert result["h_lines"] == 2
    assert result["v_lines"] == 5


def test_predict_table_type_delegates_to_classify():
    clf = _make_classifier(h_lines=1, v_lines=1)
    assert clf.predict_table_type() == clf.classify()["table_type"]

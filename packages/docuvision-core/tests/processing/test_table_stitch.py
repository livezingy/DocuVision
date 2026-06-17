"""Tests for cross-page table stitch MVP."""

from docuvision_core.processing.table_stitch import stitch_tables_by_header


def test_stitch_same_header_tables() -> None:
    t1 = {"page": 1, "data": [["Date", "Amount"], ["2024-01-01", "10"]]}
    t2 = {"page": 2, "data": [["Date", "Amount"], ["2024-01-02", "20"]]}
    out = stitch_tables_by_header([t1, t2])
    assert len(out) == 1
    assert out[0]["stitched_from"] == 2
    assert len(out[0]["data"]) == 3


def test_stitch_different_headers_kept_separate() -> None:
    t1 = {"data": [["A"], ["1"]]}
    t2 = {"data": [["B"], ["2"]]}
    out = stitch_tables_by_header([t1, t2])
    assert len(out) == 2

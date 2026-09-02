"""Unit tests for the ground-truth diff tool (GLM trial P1-4).

Pure logic — mirrors the contract documented in gt_diff.py.
"""

from __future__ import annotations

from app.services.trial.gt_diff import (
    diff_fields,
    diff_table,
    extract_actual_fields,
    extract_actual_tables,
    normalize,
    run_diff,
)


class TestNormalize:
    def test_basic(self):
        assert normalize("  INV-001 ") == "inv-001"

    def test_collapses_whitespace(self):
        assert normalize("a\n b   c") == "a b c"

    def test_strips_currency(self):
        assert normalize("$1,234.56") == "1,234.56"

    def test_nbsp_normalized(self):
        assert normalize("a" + chr(160) + "b") == "a b"

    def test_case_sensitive(self):
        assert normalize("ABC", case_sensitive=True) == "ABC"
        assert normalize("ABC") == "abc"

    def test_none_and_empty(self):
        assert normalize(None) == ""
        assert normalize("") == ""


class TestDiffFields:
    def test_statuses(self):
        gt = {"invoice_number": "INV-001", "total": "", "date": "2026-01-01", "seller": "ACME"}
        actual = {
            "invoice_number": "INV-001",     # match
            "total": "10.00",                # gt_empty (not expected)
            "date": "",                      # missing
            "seller": "ACME Corp",           # wrong
            "extra": "ignored",              # out of gt scope
        }
        result = diff_fields(gt, actual)
        by_key = {i["key"]: i["status"] for i in result["items"]}
        assert by_key == {
            "invoice_number": "match",
            "total": "gt_empty",
            "date": "missing",
            "seller": "wrong",
        }
        s = result["summary"]
        assert s["evaluable"] == 3 and s["matched"] == 1
        assert s["missing"] == 1 and s["wrong"] == 1
        assert s["accuracy"] == round(1 / 3, 4)

    def test_currency_and_case_insensitive_match(self):
        gt = {"total": "$1234.56"}
        actual = {"total": "1234.56"}
        assert diff_fields(gt, actual)["items"][0]["status"] == "match"

    def test_case_sensitive_mode(self):
        gt = {"ref": "AbC"}
        actual = {"ref": "abc"}
        assert diff_fields(gt, actual, case_sensitive=True)["items"][0]["status"] == "wrong"
        assert diff_fields(gt, actual)["items"][0]["status"] == "match"


class TestDiffTable:
    def test_cell_level_statuses(self):
        gt = [["h1", "h2"], ["✓", "7"]]
        actual = [["h1", "h2"], ["✓", "8"]]
        result = diff_table(gt, actual)
        by_pos = {(i["row"], i["col"]): i["status"] for i in result["items"]}
        assert by_pos[(0, 0)] == "match"
        assert by_pos[(1, 0)] == "match"
        assert by_pos[(1, 1)] == "wrong"
        assert result["shape_match"] is True
        # evaluable = all 4 gt cells (headers included); matched = h1,h2,check
        assert result["summary"]["accuracy"] == round(3 / 4, 4)

    def test_shape_mismatch_missing_rows(self):
        gt = [["a", "b"], ["c", "d"], ["e", "f"]]
        actual = [["a", "b"]]
        result = diff_table(gt, actual)
        assert result["shape_match"] is False
        statuses = {(i["row"], i["col"]): i["status"] for i in result["items"]}
        assert statuses[(2, 0)] == "missing" and statuses[(2, 1)] == "missing"

    def test_shorter_actual_row_marks_missing(self):
        gt = [["a", "b"]]
        actual = [["a"]]
        result = diff_table(gt, actual)
        statuses = {(i["row"], i["col"]): i["status"] for i in result["items"]}
        assert statuses[(0, 0)] == "match"
        assert statuses[(0, 1)] == "missing"

    def test_empty_inputs(self):
        result = diff_table([], [])
        assert result["items"] == []
        assert result["summary"]["accuracy"] is None


class TestExtractActual:
    def test_fields_prefers_kie_fields(self):
        result = {"kie_fields": {"a": "1"}, "view": {"fields": {"a": "2"}}}
        assert extract_actual_fields(result) == {"a": "1"}

    def test_fields_falls_back_to_view(self):
        result = {"view": {"fields": {"a": "2"}}}
        assert extract_actual_fields(result) == {"a": "2"}

    def test_tables_uses_data_grid(self):
        result = {"tables": [{"data": [["x"]], "rows": 1}, {"no_data": True}]}
        assert extract_actual_tables(result) == [[["x"]]]


class TestRunDiff:
    def test_end_to_end_writes_html(self, tmp_path):
        gt = {"fields": {"invoice_number": "INV-001"}, "tables": [[["h1"], ["v1"]]]}
        task_result = {
            "kie_fields": {"invoice_number": "inv-001"},
            "tables": [{"data": [["h1"], ["v1"]]}],
        }
        out = str(tmp_path / "report.html")
        report = run_diff(gt, task_result, job_id="job1", output_html_path=out)
        assert report["fields"]["items"][0]["status"] == "match"
        assert report["tables"][0]["summary"]["matched"] == 2
        assert report["html_path"] == out
        content = open(out, encoding="utf-8").read()
        assert "Ground-Truth Diff Report" in content
        assert "INV-001" in content

    def test_report_without_html_path(self):
        report = run_diff({"fields": {}, "tables": []}, {}, job_id="job2")
        assert "html_path" not in report
        assert report["fields"]["items"] == []

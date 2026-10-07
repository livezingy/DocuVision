"""Phase A tests for multipage KIE field merge."""

from app.services.kie.field_merge import merge_kie_fields, sum_items_count


def test_merge_scalar_later_non_empty_wins() -> None:
    merged = merge_kie_fields({
        "1": {"invoice_number": "A", "total": ""},
        "2": {"invoice_number": "", "total": "99.00"},
    })
    assert merged["invoice_number"] == "A"
    assert merged["total"] == "99.00"


def test_merge_items_extend() -> None:
    merged = merge_kie_fields({
        "1": {"items": [{"name": "a"}]},
        "2": {"items": [{"name": "b"}]},
    })
    assert len(merged["items"]) == 2
    assert sum_items_count(merged) == 2


def test_raw_output_not_merged() -> None:
    merged = merge_kie_fields({
        "1": {"raw_output": "x"},
        "2": {"invoice_number": "B"},
    })
    assert "raw_output" not in merged
    assert merged["invoice_number"] == "B"


def test_merge_findings_accumulate_no_later_page_override() -> None:
    # P-032 M3: pico findings extend per page; a later page must never
    # overwrite an earlier page's findings (the pre-P-032 scalar path did).
    merged = merge_kie_fields({
        "1": {"findings": [{"quote": "q1", "statement": "s1"}]},
        "2": {"findings": [{"quote": "q2", "statement": "s2"}]},
        "3": {"findings": [{"quote": "q3", "statement": "s3"}]},
    })
    assert [f["quote"] for f in merged["findings"]] == ["q1", "q2", "q3"]


def test_merge_findings_skips_empty_pages_keeps_order() -> None:
    merged = merge_kie_fields({
        "1": {"findings": []},  # empty list is skipped, not appended
        "2": {"findings": [{"quote": "q2"}]},
        "3": {},
    })
    assert [f["quote"] for f in merged["findings"]] == ["q2"]


def test_merge_findings_non_list_value_legacy_promotion() -> None:
    # A malformed (non-list) findings value keeps the legacy list-merge
    # semantics: promoted into the list when a later page carries a real list
    # (same rule items/line_items always had).
    merged = merge_kie_fields({
        "1": {"findings": "garbled"},
        "2": {"findings": [{"quote": "q2"}]},
    })
    assert merged["findings"] == ["garbled", {"quote": "q2"}]


def test_merge_other_doc_types_unaffected() -> None:
    # R5: only the findings key changed; invoice/invoice-line semantics intact.
    merged = merge_kie_fields({
        "1": {"items": [{"name": "a"}], "line_items": [{"name": "la"}], "invoice_number": "A"},
        "2": {"items": [{"name": "b"}], "line_items": [{"name": "lb"}], "invoice_number": "B"},
    })
    assert [i["name"] for i in merged["items"]] == ["a", "b"]
    assert [i["name"] for i in merged["line_items"]] == ["la", "lb"]
    assert merged["invoice_number"] == "B"  # scalar conflict still favors later page

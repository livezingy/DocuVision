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

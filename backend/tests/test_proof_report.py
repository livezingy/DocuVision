"""Tests for the Proof Pack report builder (v1.8.1 E3)."""

from __future__ import annotations

import json

from app.services.proof_report import build_report_data, render_report_html, write_report_json

_ANNOTATION = {
    "pages_total": 3,
    "pages_annotated": 2,
    "pages_skipped": {"rotation": 1},
    "document_skipped_reason": None,
    "cells_confirmed": 2,
    "cells_backfilled": 1,
    "cells_mismatch": 2,
    "cells_fallback_table_level": 0,
    "tables_without_bbox": 0,
    "figures_outlined": 1,
}

_DETAILS = [
    {"page": 1, "table_index": 0, "row": 1, "col": 1, "ocr_text": "✗", "text_layer_text": ""},
    {"page": 2, "table_index": 1, "row": 0, "col": 1, "ocr_text": "99", "text_layer_text": "98"},
]


def _result():
    return {
        "preprocessing": {"coordinate_space": "original", "angle_deg": 0.0, "use_doc_unwarping": False},
        "tables": [
            {
                "page": 1,
                "data": [["5678", "Name"], ["2024-01-15", "✓"]],
                # backfilled cell keeps its OCR original for the demo table
                "cell_provenance": [["text_backfilled", "vision"], ["text_confirmed", "text_mismatch"]],
                "cell_ocr_text": [["1234", None], [None, None]],
            },
            {
                "page": 2,
                "data": [["1", "98"]],
                "cell_provenance": [["text_confirmed", "text_mismatch"]],
            },
        ],
        "quality": {
            "table_backfill": {
                "enabled": True,
                "pages_judged": 3,
                "pages_text_layer_trusted": 2,
                "cells_candidates": 5,
                "cells_confirmed": 2,
                "cells_backfilled": 1,
                "cells_mismatch": 2,
                "page_verdicts": ["text_layer", "text_layer", "no_text"],
                "mismatch_details": _DETAILS,
                "mismatch_details_truncated": 0,
            },
            "figure_count": 3,
            "figure_cropped_count": 2,
            "figure_integrity_warning_count": 1,
            "engines_used": ["doc_preprocessor", "pp_structure_v3"],
        },
    }


def _meta():
    return {
        "filename": "bank_statement.pdf",
        "task_id": "task-123",
        "app_version": "1.8.1",
        "generated_at": "2026-09-12 10:00:00",
    }


def test_build_report_data_is_self_consistent() -> None:
    report = build_report_data(_result(), _ANNOTATION, _meta())

    cards = report["metric_cards"]
    assert (cards["cells_confirmed"], cards["cells_backfilled"], cards["cells_mismatch"]) == (2, 1, 2)
    assert cards["text_layer_pages"] == {"trusted": 2, "judged": 3}

    totals = [
        sum(t["confirmed"] for t in report["tables_summary"]),
        sum(t["backfilled"] for t in report["tables_summary"]),
        sum(t["mismatch"] for t in report["tables_summary"]),
    ]
    assert totals == [cards["cells_confirmed"], cards["cells_backfilled"], cards["cells_mismatch"]]
    assert report["annotation_summary"]["counts_match_quality"] is True

    # Page verdicts: four real buckets from page_text_trust.
    assert report["page_verdicts"] == {"text_layer": 2, "overlay": 0, "mixed": 0, "no_text": 1}


def test_review_list_and_demo_rows() -> None:
    report = build_report_data(_result(), _ANNOTATION, _meta())
    assert report["review_list"] == _DETAILS
    assert report["review_truncated_count"] == 0

    # Amber-cell demo: OCR original vs the corrected value now in data.
    assert report["backfill_demo"] == [
        {"page": 1, "table_index": 0, "row": 0, "col": 0, "ocr_text": "1234", "new_text": "5678"}
    ]


def test_html_contains_exact_numbers_and_truncation_note(tmp_path):
    result = _result()
    result["quality"]["table_backfill"]["mismatch_details"] = [
        {"page": 1, "table_index": 0, "row": i, "col": 0, "ocr_text": str(i), "text_layer_text": ""}
        for i in range(50)
    ]
    result["quality"]["table_backfill"]["mismatch_details_truncated"] = 7
    report = build_report_data(result, _ANNOTATION, _meta())

    html = render_report_html(report, lang="en", out_path=str(tmp_path / "report.html"))
    assert "Needs your review" in html
    assert ">2</div>" in html  # mismatch card
    assert "and 7 more mismatches beyond the 50-entry cap" in html
    assert "no aligned text-layer line" in html
    assert (tmp_path / "report.html").read_text(encoding="utf-8") == html
    assert "http://" not in html and "https://" not in html and "<script" not in html


def test_html_bilingual_literals(tmp_path):
    report = build_report_data(_result(), _ANNOTATION, _meta())
    en = render_report_html(report, lang="en")
    zh = render_report_html(report, lang="zh", out_path=str(tmp_path / "zh.html"))
    assert "Verified cells (zero-error)" in en
    assert "已核对格（逐字零错）" in zh
    assert "Processed in a private environment. Files deleted after delivery." in en
    assert "在私有环境中处理，交付后删除文件。" in zh
    assert (tmp_path / "zh.html").exists()


def test_json_is_full_report_data(tmp_path):
    report = build_report_data(_result(), _ANNOTATION, _meta())
    out = str(tmp_path / "report.json")
    write_report_json(report, out)
    assert json.loads(open(out, encoding="utf-8").read()) == report


def test_counts_mismatch_sets_warning(tmp_path):
    result = _result()
    result["quality"]["table_backfill"]["cells_mismatch"] = 99  # legacy/inconsistent file
    report = build_report_data(result, _ANNOTATION, _meta())
    assert report["annotation_summary"]["counts_match_quality"] is False
    html = render_report_html(report, lang="en")
    assert "differ from document totals" in html

"""Tests for document type classifier."""

from pathlib import Path

from app.services.document_type_classifier import classify_document

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parents[1]

_COI_FIXTURES = [
    "coi_acord25_synth_green.pdf",
    "coi_acord25_synth_yellow.pdf",
    "coi_acord25_cornell_sample.pdf",
    "coi_acord25_tampa_sample.pdf",
]


def test_classify_invoice_text() -> None:
    result = classify_document("", text_hint="Invoice Number INV-001 Bill To Customer")
    assert result["document_type"] == "invoice"
    assert result["confidence"] > 0


def test_classify_coi_text() -> None:
    result = classify_document(
        "",
        text_hint=(
            "CERTIFICATE OF LIABILITY INSURANCE. THIS CERTIFICATE IS ISSUED AS "
            "A MATTER OF INFORMATION ONLY AND CONFERS NO RIGHTS UPON THE "
            "CERTIFICATE HOLDER."
        ),
    )
    assert result["document_type"] == "coi"
    assert result["confidence"] > 0


def test_classify_coi_fixtures_file_level() -> None:
    # P-030b X6 bidirectional regression, positive arm: every committed ACORD
    # 25 fixture must classify as coi from its page-1 text layer.
    for name in _COI_FIXTURES:
        path = _PROJECT_ROOT / "test_data" / "testfiles" / "coi" / name
        result = classify_document(str(path))
        assert result["document_type"] == "coi", f"{name}: {result}"


def test_classifier_non_coi_outputs_unchanged_vs_pre_coi_baseline() -> None:
    # P-030b X6 bidirectional regression, negative arm: non-COI documents keep
    # their exact pre-coi outputs (type AND confidence), pinned from the
    # pre-change baseline archived in the P-030 PR record.
    expected = {
        ("coi", "coi_negative_fl_exemption.pdf"): ("id_card", 1.0),
        ("pdf", "cosent-form-test-document.pdf"): ("receipt", 1.0),
        ("pdf", "financial_report.pdf"): ("auto", 0.0),
        ("pdf", "sample-layout.pdf"): ("auto", 0.0),
        ("pdf", "sample_report.pdf"): ("auto", 0.0),
        ("invoices", "invoice_sample_01.pdf"): ("auto", 0.0),
    }
    for (subdir, name), (doc_type, confidence) in expected.items():
        path = _PROJECT_ROOT / "test_data" / "testfiles" / subdir / name
        result = classify_document(str(path))
        assert result["document_type"] == doc_type, f"{name}: {result}"
        assert result["confidence"] == confidence, f"{name}: {result}"

#!/usr/bin/env python3
"""Build multipage PDF fixtures for Pro KIE acceptance (invoices + receipts)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTFILES = REPO_ROOT / "test_data" / "testfiles"


def _require_fitz():
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise SystemExit("PyMuPDF required: pip install PyMuPDF") from exc
    return fitz


def _image_to_pdf_page(doc, fitz, image_path: Path, page_w: float = 595, page_h: float = 842) -> None:
    page = doc.new_page(width=page_w, height=page_h)
    rect = fitz.Rect(36, 36, page_w - 36, page_h - 36)
    page.insert_image(rect, filename=str(image_path))


def _text_page(doc, fitz, lines: list[str], page_w: float = 595, page_h: float = 842) -> None:
    page = doc.new_page(width=page_w, height=page_h)
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 16


def build_invoice_multipage_2p(out_dir: Path) -> Path:
    fitz = _require_fitz()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "invoice_multipage_2p_header_detail.pdf"
    p1 = TESTFILES / "invoices" / "sample-invoice.png"
    if not p1.is_file():
        raise FileNotFoundError(p1)
    doc = fitz.open()
    _image_to_pdf_page(doc, fitz, p1)
    _text_page(
        doc,
        fitz,
        [
            "LINE ITEMS (PAGE 2)",
            "Item A    10.00",
            "Item B    25.50",
            "Item C    8.00",
            "Subtotal page 2: 43.50",
        ],
    )
    doc.save(str(out_path))
    doc.close()
    return out_path


def build_invoice_multipage_3p(out_dir: Path) -> Path:
    fitz = _require_fitz()
    out_path = out_dir / "invoice_multipage_3p_items.pdf"
    p1 = TESTFILES / "invoices" / "receipt-invoice-like.png"
    p2 = TESTFILES / "invoices" / "sample-invoice.png"
    src_pdf = TESTFILES / "invoices" / "invoice_sample_01.pdf"
    if not p1.is_file() or not p2.is_file():
        raise FileNotFoundError("missing invoice source images")
    doc = fitz.open()
    _image_to_pdf_page(doc, fitz, p1)
    _image_to_pdf_page(doc, fitz, p2)
    if src_pdf.is_file():
        src = fitz.open(str(src_pdf))
        doc.insert_pdf(src, from_page=0, to_page=0)
        src.close()
    else:
        _text_page(doc, fitz, ["Notes page 3", "End of document"])
    doc.save(str(out_path))
    doc.close()
    return out_path


def build_receipt_multipage_2p(out_dir: Path) -> Path:
    fitz = _require_fitz()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "receipt_multipage_2p.pdf"
    p1 = TESTFILES / "receipts" / "receipt-with-tips.png"
    p2 = TESTFILES / "receipts" / "contoso-receipt.png"
    if not p1.is_file() or not p2.is_file():
        raise FileNotFoundError("missing receipt source images")
    doc = fitz.open()
    _image_to_pdf_page(doc, fitz, p1)
    _image_to_pdf_page(doc, fitz, p2)
    doc.save(str(out_path))
    doc.close()
    return out_path


def main() -> int:
    invoice_out = TESTFILES / "invoices" / "multipage"
    receipt_out = TESTFILES / "receipts" / "multipage"
    built = []
    built.append(build_invoice_multipage_2p(invoice_out))
    built.append(build_invoice_multipage_3p(invoice_out))
    built.append(build_receipt_multipage_2p(receipt_out))
    for path in built:
        print("wrote", path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())

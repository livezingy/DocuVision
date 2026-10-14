#!/usr/bin/env python3
"""Extract a 1-based, inclusive page range from a fixture into a standalone PDF.

Why a *content* fingerprint and never a byte sha256: PyMuPDF writes a random
``/ID`` on every save, so two runs of the identical command yield different bytes
(same size, different sha256). ``verify_assets.py`` already standardises this
for regenerated derived PDFs - pin them by content (pages / text_sha256 / words /
rotation), never by bytes. This script prints that fingerprint after writing so
the README can carry a reproducible pin.

Usage:
    python test_data/scripts/extract_pdf_pages.py \
        --src test_data/testfiles/pico/pub_bmcpubh_PMC13595506.pdf \
        --first 8 --last 10 \
        --out test_data/testfiles/pdf/pub_bmcpubh_PMC13595506_p8-10.pdf
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _require_fitz():
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise SystemExit("PyMuPDF required: pip install PyMuPDF") from exc
    return fitz


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else (REPO_ROOT / p)


def content_fingerprint(fitz, path: Path) -> dict:
    """Whole-doc + per-page text fingerprint (rotation fixture friendly)."""
    doc = fitz.open(path)
    if doc.page_count < 1:
        doc.close()
        raise SystemExit(f"no pages in {path}")
    pages: list[dict] = []
    doc_text = hashlib.sha256()
    words_total = 0
    for i in range(doc.page_count):
        page = doc[i]
        text = page.get_text("text")
        doc_text.update(text.encode("utf-8"))
        n_words = len(page.get_text("words"))
        words_total += n_words
        pages.append({
            "page": i + 1,
            "rotation": page.rotation,
            "words": n_words,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest().upper(),
        })
    doc.close()
    return {
        "pages": len(pages),
        "words": words_total,
        "text_sha256": doc_text.hexdigest().upper(),
        "per_page": pages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", required=True, help="source fixture (repo-relative or absolute)")
    parser.add_argument("--first", type=int, required=True, help="first page, 1-based inclusive")
    parser.add_argument("--last", type=int, required=True, help="last page, 1-based inclusive")
    parser.add_argument("--out", required=True, help="output PDF (repo-relative or absolute)")
    args = parser.parse_args()

    if args.first < 1 or args.last < args.first:
        raise SystemExit("--first must be >= 1 and --last >= --first")

    fitz = _require_fitz()
    src = _resolve(args.src)
    out = _resolve(args.out)
    if not src.is_file():
        raise SystemExit(f"source not found: {src}")

    doc = fitz.open(src)
    if args.last > doc.page_count:
        doc.close()
        raise SystemExit(f"--last {args.last} exceeds source page count {doc.page_count}")

    derived = fitz.open()
    for p in range(args.first - 1, args.last):
        derived.insert_pdf(doc, from_page=p, to_page=p)
    out.parent.mkdir(parents=True, exist_ok=True)
    derived.save(str(out), garbage=4, deflate=True)
    derived.close()
    doc.close()

    fp = content_fingerprint(fitz, out)
    print(f"wrote {out.relative_to(REPO_ROOT) if out.is_relative_to(REPO_ROOT) else out}")
    print(f"  pages={fp['pages']} words={fp['words']} text_sha256={fp['text_sha256']}")
    for pg in fp["per_page"]:
        print(f"  p{pg['page']}: rot={pg['rotation']} words={pg['words']} text_sha256={pg['text_sha256']}")
    print("  content_fingerprint_json=" + json.dumps(
        {"pages": fp["pages"], "words": fp["words"], "text_sha256": fp["text_sha256"]},
        sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

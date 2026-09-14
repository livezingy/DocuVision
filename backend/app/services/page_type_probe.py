"""Read-only page-type calibration probe (v1.8 §3.4).

Walks a directory of PDFs and emits per-page trust verdicts + top signals
for human review against ground-truth labels. Produces the calibration
report required before enabling ``TABLE_TEXT_BACKFILL=auto`` in production.

Usage (backend venv active, from backend/ cwd):
    python -m app.services.page_type_probe --input test_data/testfiles \
        --out outputs/page_type_calib.json

Read-only: never writes back to inputs. Only PyMuPDF is required.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

from app.services.page_text_trust import judge_page_trust


def _probe_pdf(file_path: str) -> Dict[str, Any]:
    import fitz

    pages: List[Dict[str, Any]] = []
    with fitz.open(file_path) as doc:
        for idx, page in enumerate(doc):
            result = judge_page_trust(page)
            pages.append(
                {
                    "page": idx + 1,
                    "verdict": result.verdict,
                    "trusted": result.trusted,
                    "confidence": result.confidence,
                    "signals": result.signals,
                }
            )
    return {"file": file_path, "pages": pages}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Page-type calibration probe (v1.8 §3.4)")
    parser.add_argument("--input", required=True, help="directory of PDFs")
    parser.add_argument("--out", default="outputs/page_type_calib.json", help="output JSON path")
    args = parser.parse_args(argv)

    in_dir = args.input
    if not os.path.isdir(in_dir):
        print(f"[error] input dir not found: {in_dir}", file=sys.stderr)
        return 2

    pdfs = sorted(
        os.path.join(root, name)
        for root, _dirs, files in os.walk(in_dir)
        for name in files
        if name.lower().endswith(".pdf")
    )
    if not pdfs:
        print(f"[warn] no PDFs found under {in_dir}", file=sys.stderr)

    report: Dict[str, Any] = {"files": [], "summary": {}}
    verdict_counts: Dict[str, int] = {}
    page_total = 0
    for pdf in pdfs:
        entry = _probe_pdf(pdf)
        report["files"].append(entry)
        for p in entry["pages"]:
            verdict_counts[p["verdict"]] = verdict_counts.get(p["verdict"], 0) + 1
            page_total += 1

    report["summary"] = {
        "files": len(pdfs),
        "pages": page_total,
        "verdict_counts": verdict_counts,
    }

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"[done] {len(pdfs)} files / {page_total} pages -> {args.out}")
    print(f"[summary] {verdict_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

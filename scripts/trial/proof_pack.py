"""Proof Pack CLI (v1.8.1 E4) — thin argparse shell over app.services.proof_pack.

Turn a task result JSON + the original PDF into the customer-facing proof
pack (annotated.pdf + report.html + report.json, optionally merged with an
existing pack.zip's tables/figures).

Exit codes: 0 success / 2 contract missing / 3 rendering failure.

Example (from the repo root, after exporting the task result):
    python scripts/trial/proof_pack.py \
        --result outputs/{task_id}/{task_id}_result.json \
        --pdf uploads/original.pdf \
        --out outputs/{task_id}/proof
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "backend"))

from app.services.proof_pack import ProofPackError, build_proof_pack  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the customer-facing proof pack (annotated PDF + report + JSON)."
    )
    parser.add_argument("--result", required=True, help="task result JSON (GET /api/v1/tasks/{id}/result)")
    parser.add_argument("--pdf", required=True, help="original PDF (read-only)")
    parser.add_argument("--out", required=True, help="output directory for proof_pack.zip")
    parser.add_argument("--pack", help="optional existing pack.zip; tables/ and figures/ are merged in")
    parser.add_argument("--lang", default="en", choices=["en", "zh"], help="report language (default: en)")
    parser.add_argument("--title", default="", help="document title shown in the report header")
    parser.add_argument("--client", default="", help="client name shown in the report header")
    parser.add_argument("--no-stamp", action="store_true", help="omit the per-page footer legend")
    args = parser.parse_args(argv)

    app_version = ""
    try:
        from app.core.config import settings as app_settings

        app_version = app_settings.APP_VERSION
    except Exception:  # noqa: BLE001 — report without a version rather than failing
        pass

    try:
        outcome = build_proof_pack(
            result_path=args.result,
            pdf_path=args.pdf,
            out_dir=args.out,
            pack_zip=args.pack,
            lang=args.lang,
            title=args.title,
            client=args.client,
            stamp=not args.no_stamp,
            app_version=app_version,
        )
    except ProofPackError as exc:
        print(f"[FAIL] {exc}")
        return exc.exit_code

    summary = outcome["summary"]
    skipped = sum(summary.get("pages_skipped", {}).values())
    print(f"[OK] proof pack -> {outcome['zip_path']}")
    print(
        "     cells confirmed/backfilled/mismatch: {}/{}/{} | pages annotated: {}/{} | pages skipped: {}".format(
            summary.get("cells_confirmed", 0),
            summary.get("cells_backfilled", 0),
            summary.get("cells_mismatch", 0),
            summary.get("pages_annotated", 0),
            summary.get("pages_total", 0),
            skipped,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

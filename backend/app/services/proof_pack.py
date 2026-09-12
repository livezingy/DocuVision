"""Proof Pack packager (v1.8.1 E4).

Orchestrates the pure post-processing command: task result JSON + original
PDF (+ optional existing pack.zip) -> ``proof_pack.zip`` with
``annotated.pdf`` / ``report.html`` / ``report.json`` (+ ``tables/`` and
``figures/`` copied verbatim from the pack when provided).

Error contract (v1.8.1 §5): never silently produce an empty package —
contract violations raise :class:`ProofPackError` (CLI exit code 2), renderer
failures raise :class:`ProofRenderError` (exit code 3). The original PDF is
only ever opened read-only.

Importable without the GPU stack (renderer/report are fitz+stdlib), so the
CLI logic is testable in-process; ``scripts/trial/proof_pack.py`` is a thin
argparse shell over :func:`build_proof_pack`.
"""

from __future__ import annotations

import json
import os
import zipfile
from datetime import datetime
from typing import Any, Dict, Optional

from app.services.proof_render import render_annotated_pdf
from app.services.proof_report import build_report_data, render_report_html, write_report_json

# Entries copied verbatim from an existing pack.zip (v1.8.1 §5: tables/ +
# figures/ only; the pack's own manifest/result stay out of the proof pack).
_PACK_COPY_PREFIXES = ("tables/", "figures/")


class ProofPackError(Exception):
    """Contract/validation failure → CLI exit code 2."""

    exit_code = 2


class ProofRenderError(ProofPackError):
    """Renderer failure → CLI exit code 3."""

    exit_code = 3


def _load_result(result_path: str) -> Dict[str, Any]:
    if not os.path.isfile(result_path):
        raise ProofPackError(f"result JSON not found: {result_path}")
    try:
        with open(result_path, "r", encoding="utf-8") as f:
            result = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise ProofPackError(f"result JSON unreadable: {exc}") from exc
    if not isinstance(result, dict):
        raise ProofPackError("result JSON must be an object")
    return result


def _validate_contract(result: Dict[str, Any]) -> None:
    quality = result.get("quality")
    if not isinstance(quality, dict) or not isinstance(quality.get("table_backfill"), dict):
        raise ProofPackError(
            "result JSON is missing quality.table_backfill — run analysis with "
            "table_text_backfill=auto (default) and export /api/v1/tasks/{task_id}/result"
        )
    if not isinstance(result.get("tables"), list):
        raise ProofPackError("result JSON is missing the 'tables' list")


def _copy_pack_entries(zip_path: str, pack_zip: str) -> None:
    with zipfile.ZipFile(pack_zip, "r") as src:
        for name in src.namelist():
            if name.endswith("/") or not name.startswith(_PACK_COPY_PREFIXES):
                continue
            zip_path.writestr(name, src.read(name))


def build_proof_pack(
    result_path: str,
    pdf_path: str,
    out_dir: str,
    pack_zip: Optional[str] = None,
    lang: str = "en",
    title: str = "",
    client: str = "",
    stamp: bool = True,
    app_version: str = "",
) -> Dict[str, Any]:
    """Build proof_pack.zip; returns paths + the annotation/report summaries."""
    result = _load_result(result_path)
    _validate_contract(result)

    if not os.path.isfile(pdf_path):
        raise ProofPackError(f"original PDF not found: {pdf_path}")

    os.makedirs(out_dir, exist_ok=True)
    annotated_path = os.path.join(out_dir, "annotated.pdf")
    html_path = os.path.join(out_dir, "report.html")
    json_path = os.path.join(out_dir, "report.json")

    try:
        summary = render_annotated_pdf(pdf_path, result, annotated_path, footer_stamp=stamp)
    except ProofPackError:
        raise
    except Exception as exc:  # noqa: BLE001 — any renderer failure is exit code 3
        raise ProofRenderError(f"annotated PDF rendering failed: {exc}") from exc

    task_id = os.path.splitext(os.path.basename(result_path))[0]
    if task_id.endswith("_result"):
        task_id = task_id[: -len("_result")]
    meta = {
        "filename": os.path.basename(pdf_path),
        "task_id": task_id,
        "app_version": app_version,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "title": title,
        "client": client,
    }
    report_data = build_report_data(result, summary.to_dict(), meta)
    render_report_html(report_data, lang=lang, out_path=html_path)
    write_report_json(report_data, json_path)

    zip_file = os.path.join(out_dir, "proof_pack.zip")
    with zipfile.ZipFile(zip_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(annotated_path, "annotated.pdf")
        zf.write(html_path, "report.html")
        zf.write(json_path, "report.json")
        if pack_zip:
            if not os.path.isfile(pack_zip):
                raise ProofPackError(f"pack zip not found: {pack_zip}")
            _copy_pack_entries(zf, pack_zip)

    return {
        "zip_path": zip_file,
        "annotated_pdf": annotated_path,
        "report_html": html_path,
        "report_json": json_path,
        "summary": summary.to_dict(),
        "report_data": report_data,
    }

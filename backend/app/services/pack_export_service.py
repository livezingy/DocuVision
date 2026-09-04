"""Build a single-task artifact ZIP (tables + figure crops).

Writes the archive to disk with ZIP_DEFLATED so large figure sets are not
buffered as one in-memory blob. Figure files are copied from
OUTPUT_DIR/{task_id}/figures/; tables reuse ExportService CSV/XLSX helpers.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import zipfile
from typing import Any, Dict, List, Optional, Set

from loguru import logger

from app.core.config import settings
from app.services.export_service import (
    ExportService,
    excel_safe_cell,
    format_table_csv_banner,
)

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
ALLOWED_INCLUDE = frozenset({"tables", "figures", "json"})
DEFAULT_INCLUDE = frozenset({"tables", "figures"})
MAX_PACK_BYTES = 256 * 1024 * 1024


class PackTooLargeError(Exception):
    """Raised when the running uncompressed total exceeds MAX_PACK_BYTES."""

    def __init__(self, size: int, limit: int) -> None:
        self.size = size
        self.limit = limit
        super().__init__(f"Artifact pack exceeds {limit} bytes ({size})")


def parse_include(raw: Optional[str]) -> Set[str]:
    """Parse ``include=tables,figures,json``. Empty / None → default set."""
    if raw is None or not str(raw).strip():
        return set(DEFAULT_INCLUDE)
    parts = {p.strip().lower() for p in str(raw).split(",") if p.strip()}
    unknown = parts - ALLOWED_INCLUDE
    if unknown:
        bad = ", ".join(sorted(unknown))
        raise ValueError(f"Invalid include token(s): {bad}")
    return parts


def single_table_csv_filename(index_1based: int, page: Any) -> str:
    """Match the Tables-card client name: table_{nn}_p{page}.csv."""
    n = str(index_1based).zfill(2)
    p = "?" if page is None or page == "" else page
    return f"table_{n}_p{p}.csv"


def render_single_table_csv(index_1based: int, table: Dict[str, Any]) -> str:
    """One table as CSV text (banner + optional caption + data rows)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow([format_table_csv_banner(index_1based, table)])
    caption = str(table.get("caption") or "").strip()
    if caption:
        writer.writerow([excel_safe_cell(f"Caption: {caption}")])
    for row in table.get("data") or []:
        cells = row if isinstance(row, (list, tuple)) else [row]
        writer.writerow([excel_safe_cell(c) for c in cells])
    return buf.getvalue()


def _safe_figure_id(figure_id: Any) -> Optional[str]:
    text = str(figure_id or "")
    if SAFE_ID_RE.fullmatch(text):
        return text
    return None


class _SizeTracker:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.total = 0

    def add(self, nbytes: int) -> None:
        self.total += int(nbytes)
        if self.total > self.limit:
            raise PackTooLargeError(self.total, self.limit)


def _add_bytes(zf: zipfile.ZipFile, name: str, data: bytes, tracker: _SizeTracker) -> None:
    tracker.add(len(data))
    zf.writestr(name, data)


def _add_file(zf: zipfile.ZipFile, name: str, path: str, tracker: _SizeTracker) -> None:
    tracker.add(os.path.getsize(path))
    zf.write(path, arcname=name)


def _figure_arcname(item: Dict[str, Any], figure_id: str) -> str:
    if item.get("is_merged"):
        return f"figures/merged/{figure_id}.png"
    return f"figures/{figure_id}.png"


async def build_task_pack_zip(
    result: Dict[str, Any],
    task_id: str,
    *,
    include: Optional[str] = None,
    output_dir: Optional[str] = None,
    figures_dir: Optional[str] = None,
    max_bytes: int = MAX_PACK_BYTES,
) -> str:
    """Write ``{task_id}_pack.zip`` under ``output_dir`` and return its path."""
    if not SAFE_ID_RE.fullmatch(task_id or ""):
        raise ValueError("Invalid task id")

    selected = parse_include(include)
    out_dir = output_dir or settings.OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, f"{task_id}_pack.zip")
    crop_dir = figures_dir or os.path.join(settings.OUTPUT_DIR, task_id, "figures")

    doc_info = result.get("document_info") if isinstance(result.get("document_info"), dict) else {}
    tables: List[Dict[str, Any]] = result.get("tables") if isinstance(result.get("tables"), list) else []
    figures_block = result.get("figures") if isinstance(result.get("figures"), dict) else {}
    figure_items: List[Dict[str, Any]] = (
        figures_block.get("items") if isinstance(figures_block.get("items"), list) else []
    )
    quality = result.get("quality") if isinstance(result.get("quality"), dict) else {}

    missing_figures: List[str] = []
    tracker = _SizeTracker(max_bytes)
    export_svc = ExportService()
    export_svc.output_dir = out_dir

    try:
        await _write_pack_archive(
            zip_path=zip_path,
            result=result,
            task_id=task_id,
            selected=selected,
            tables=tables,
            figure_items=figure_items,
            figures_block=figures_block,
            quality=quality,
            doc_info=doc_info,
            crop_dir=crop_dir,
            export_svc=export_svc,
            tracker=tracker,
            missing_figures=missing_figures,
        )
    except PackTooLargeError:
        if os.path.isfile(zip_path):
            os.remove(zip_path)
        raise

    logger.info("Wrote artifact pack {} ({} bytes tracked)", zip_path, tracker.total)
    return zip_path


async def _write_pack_archive(
    *,
    zip_path: str,
    result: Dict[str, Any],
    task_id: str,
    selected: Set[str],
    tables: List[Dict[str, Any]],
    figure_items: List[Dict[str, Any]],
    figures_block: Dict[str, Any],
    quality: Dict[str, Any],
    doc_info: Dict[str, Any],
    crop_dir: str,
    export_svc: ExportService,
    tracker: _SizeTracker,
    missing_figures: List[str],
) -> None:
    packed_figure_files = 0
    xlsx_included = False
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if "json" in selected:
            payload = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
            _add_bytes(zf, "result.json", payload, tracker)

        if "tables" in selected:
            csv_path = await export_svc.to_csv(result, task_id)
            _add_file(zf, "tables/tables.csv", csv_path, tracker)
            for idx, table in enumerate(tables, start=1):
                name = single_table_csv_filename(idx, table.get("page"))
                text = render_single_table_csv(idx, table)
                _add_bytes(zf, f"tables/{name}", text.encode("utf-8-sig"), tracker)
            try:
                xlsx_path = await export_svc.to_excel(result, task_id)
                _add_file(zf, "tables/tables.xlsx", xlsx_path, tracker)
                xlsx_included = True
            except Exception as exc:  # noqa: BLE001 — XLSX is optional in the pack
                logger.warning("pack zip: tables.xlsx skipped: {}", exc)

        if "figures" in selected:
            index_rows: List[List[Any]] = [
                ["id", "page", "type", "caption", "confidence", "filename", "is_merged"]
            ]
            for item in figure_items:
                if not isinstance(item, dict):
                    continue
                figure_id = _safe_figure_id(item.get("id"))
                if not figure_id:
                    missing_figures.append(str(item.get("id") or ""))
                    continue
                src = os.path.join(crop_dir, f"{figure_id}.png")
                arc = _figure_arcname(item, figure_id)
                index_rows.append(
                    [
                        figure_id,
                        item.get("page", ""),
                        item.get("type", ""),
                        item.get("caption") or "",
                        item.get("confidence", ""),
                        arc,
                        "true" if item.get("is_merged") else "false",
                    ]
                )
                if os.path.isfile(src):
                    _add_file(zf, arc, src, tracker)
                    packed_figure_files += 1
                else:
                    missing_figures.append(figure_id)
            index_buf = io.StringIO()
            csv.writer(index_buf, lineterminator="\r\n").writerows(index_rows)
            _add_bytes(zf, "figures/index.csv", index_buf.getvalue().encode("utf-8-sig"), tracker)

        manifest = {
            "task_id": task_id,
            "file_name": doc_info.get("file_name") or "",
            "include": sorted(selected),
            "table_count": len(tables),
            "figure_count": int(figures_block.get("figure_count") or len(figure_items) or 0),
            "figure_cropped_count": int(figures_block.get("cropped_count") or 0),
            "packed_figure_files": packed_figure_files,
            "xlsx_included": xlsx_included,
            "missing_figures": [m for m in missing_figures if m],
            "quality": {
                key: quality[key]
                for key in (
                    "figure_count",
                    "figure_cropped_count",
                    "figure_integrity_warning_count",
                )
                if key in quality
            },
        }
        _add_bytes(
            zf,
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
            tracker,
        )

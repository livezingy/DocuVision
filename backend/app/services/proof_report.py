"""Proof Pack one-page report (v1.8.1 E3).

Single data source: ``build_report_data`` computes every number once from the
task result (quality.table_backfill + provenance grids); the HTML renderer
and the JSON writer only format — they never do arithmetic (v1.8.1 §4.2).
HTML is a self-contained file: inline CSS, no external links, no JS; the
customer double-clicks it. ``write_report_json`` is the full machine-readable
version for technical clients.

Page verdicts use the four real values from ``page_text_trust``
(text_layer / overlay / mixed / no_text). Mismatch cells whose text-layer
value could not be aligned show a plain-language note instead of an empty
field.
"""

from __future__ import annotations

import html as _html
import json
from typing import Any, Dict, List, Optional

_PROVENANCE_CONFIRMED = "text_confirmed"
_PROVENANCE_BACKFILLED = "text_backfilled"
_PROVENANCE_MISMATCH = "text_mismatch"

_DEMO_CAP = 10
_REVIEW_DISPLAY_CAP = 50

_PRIVACY_TEXT = "Processed in a private environment. Files deleted after delivery."

# Two literal tables (v1.8.1 D6) — no i18n framework for two languages.
_LITERALS: Dict[str, Dict[str, str]] = {
    "en": {
        "title": "Document Proof Report",
        "pages": "Pages",
        "processed": "Processed at",
        "task": "Task",
        "engines": "Engines",
        "card_confirmed": "Verified cells (zero-error)",
        "card_backfilled": "Corrected cells",
        "card_mismatch": "Needs your review",
        "card_text_layer": "Text-layer trusted pages",
        "tables_title": "Tables",
        "col_page": "Page",
        "col_table": "Table",
        "col_size": "Rows × Cols",
        "col_confirmed": "Verified",
        "col_backfilled": "Corrected",
        "col_mismatch": "Review",
        "col_coverage": "Verified coverage",
        "review_title": "Cells we recommend you review",
        "review_note": "The two layers disagree; the OCR value was kept.",
        "demo_title": "Sample of corrected values (OCR → text layer)",
        "col_ocr": "OCR value",
        "col_new": "Corrected value",
        "figures_title": "Figure exports",
        "verdicts_title": "Page text-layer verdicts",
        "annotation_title": "Annotation coverage",
        "footer_privacy": _PRIVACY_TEXT,
        "no_aligned": "no aligned text-layer line",
        "coverage_none": "—",
        "truncated_note": "…and {n} more mismatches beyond the 50-entry cap (see mismatch_details_truncated in report.json)",
        "consistency_warning": "Note: per-table counts differ from document totals (legacy result file).",
        "doc_skipped": "This document was processed in a transformed coordinate space, so no annotation could be aligned to the original pages. Reason: {reason}",
        "annotated_pages": "{n} of {total} pages carry annotations",
        "skipped_pages": "skipped pages: {detail}",
    },
    "zh": {
        "title": "文档核验报告",
        "pages": "页数",
        "processed": "处理时间",
        "task": "任务",
        "engines": "引擎",
        "card_confirmed": "已核对格（逐字零错）",
        "card_backfilled": "已修正格",
        "card_mismatch": "建议人工复核",
        "card_text_layer": "文本层可信页",
        "tables_title": "表格",
        "col_page": "页码",
        "col_table": "表",
        "col_size": "行 × 列",
        "col_confirmed": "已核对",
        "col_backfilled": "已修正",
        "col_mismatch": "待复核",
        "col_coverage": "核对覆盖率",
        "review_title": "建议人工复核的单元格",
        "review_note": "两个层不一致，已保留 OCR 原值。",
        "demo_title": "修正值抽样（OCR → 文本层）",
        "col_ocr": "OCR 原值",
        "col_new": "修正后值",
        "figures_title": "图片导出",
        "verdicts_title": "页级文本层判定",
        "annotation_title": "标注覆盖",
        "footer_privacy": "在私有环境中处理，交付后删除文件。",
        "no_aligned": "未能对齐文本层",
        "coverage_none": "—",
        "truncated_note": "…另有 {n} 条不匹配超出 50 条上限（见 report.json 的 mismatch_details_truncated）",
        "consistency_warning": "注意：逐表计数与全文档总数不一致（旧版结果文件）。",
        "doc_skipped": "该文档在变换坐标系下处理，无法对齐原始页面标注。原因：{reason}",
        "annotated_pages": "{n} / {total} 页含标注",
        "skipped_pages": "跳过页：{detail}",
    },
}


def build_report_data(
    result: Dict[str, Any],
    annotation: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute every report number once, from the task result JSON.

    ``annotation`` is ``AnnotationSummary.to_dict()`` from the renderer;
    ``meta`` carries filename / task_id / app_version / generated_at.
    """
    meta = meta or {}
    quality = result.get("quality") or {}
    backfill = quality.get("table_backfill") or {}
    tables = [t for t in result.get("tables") or [] if isinstance(t, dict)]

    confirmed = int(backfill.get("cells_confirmed") or 0)
    backfilled = int(backfill.get("cells_backfilled") or 0)
    mismatch = int(backfill.get("cells_mismatch") or 0)

    # Per-table counts straight from the provenance grids (C1 contract).
    tables_summary: List[Dict[str, Any]] = []
    grid_confirmed = grid_backfilled = grid_mismatch = 0
    for idx, table in enumerate(tables):
        grid = table.get("cell_provenance") if isinstance(table.get("cell_provenance"), list) else []
        c = b = m = 0
        for row in grid:
            if not isinstance(row, list):
                continue
            for value in row:
                if value == _PROVENANCE_CONFIRMED:
                    c += 1
                elif value == _PROVENANCE_BACKFILLED:
                    b += 1
                elif value == _PROVENANCE_MISMATCH:
                    m += 1
        data = table.get("data") if isinstance(table.get("data"), list) else []
        rows = len(data)
        cols = max((len(r) for r in data if isinstance(r, list)), default=0)
        denom = c + b + m
        tables_summary.append(
            {
                "page": table.get("page"),
                "table_index": idx,
                "rows": rows,
                "cols": cols,
                "confirmed": c,
                "backfilled": b,
                "mismatch": m,
                "coverage": round(c / denom, 3) if denom else None,
            }
        )
        grid_confirmed += c
        grid_backfilled += b
        grid_mismatch += m

    counts_match = (grid_confirmed, grid_backfilled, grid_mismatch) == (confirmed, backfilled, mismatch)

    verdicts: Dict[str, int] = {"text_layer": 0, "overlay": 0, "mixed": 0, "no_text": 0}
    for verdict in backfill.get("page_verdicts") or []:
        if isinstance(verdict, str) and verdict in verdicts:
            verdicts[verdict] += 1

    review_list = [dict(rec) for rec in backfill.get("mismatch_details") or [] if isinstance(rec, dict)]

    # Amber-cell before/after demo: original OCR (cell_ocr_text) vs the value
    # now in data (the text-layer winner).
    backfill_demo: List[Dict[str, Any]] = []
    for idx, table in enumerate(tables):
        ocr_grid = table.get("cell_ocr_text")
        data = table.get("data") if isinstance(table.get("data"), list) else []
        if not isinstance(ocr_grid, list):
            continue
        for i, ocr_row in enumerate(ocr_grid):
            if not isinstance(ocr_row, list):
                continue
            for j, ocr in enumerate(ocr_row):
                if ocr is None:
                    continue
                new_text = None
                if i < len(data) and isinstance(data[i], list) and j < len(data[i]):
                    new_text = data[i][j]
                backfill_demo.append(
                    {
                        "page": table.get("page"),
                        "table_index": idx,
                        "row": i,
                        "col": j,
                        "ocr_text": ocr,
                        "new_text": new_text,
                    }
                )
                if len(backfill_demo) >= _DEMO_CAP:
                    break
            if len(backfill_demo) >= _DEMO_CAP:
                break
        if len(backfill_demo) >= _DEMO_CAP:
            break

    annotation_summary = dict(annotation or {})
    annotation_summary["counts_match_quality"] = counts_match

    return {
        "header": {
            "filename": meta.get("filename") or "",
            "pages_total": (annotation or {}).get("pages_total"),
            "processed_at": meta.get("generated_at") or "",
            "task_id": meta.get("task_id") or "",
            "app_version": meta.get("app_version") or "",
            "engines": [str(e) for e in quality.get("engines_used") or []],
        },
        "metric_cards": {
            "cells_confirmed": confirmed,
            "cells_backfilled": backfilled,
            "cells_mismatch": mismatch,
            "text_layer_pages": {
                "trusted": int(backfill.get("pages_text_layer_trusted") or 0),
                "judged": int(backfill.get("pages_judged") or 0),
            },
        },
        "page_verdicts": verdicts,
        "tables_summary": tables_summary,
        "review_list": review_list,
        "review_truncated_count": int(backfill.get("mismatch_details_truncated") or 0),
        "backfill_demo": backfill_demo,
        "figures": {
            "figure_count": int(quality.get("figure_count") or 0),
            "figure_cropped_count": int(quality.get("figure_cropped_count") or 0),
            "figure_integrity_warning_count": int(quality.get("figure_integrity_warning_count") or 0),
        },
        "annotation_summary": annotation_summary,
        "footer": {
            "privacy": _PRIVACY_TEXT,
            "app_version": meta.get("app_version") or "",
            "generated_at": meta.get("generated_at") or "",
            "task_id": meta.get("task_id") or "",
        },
    }


def write_report_json(report_data: Dict[str, Any], out_path: str) -> None:
    """Full machine-readable version (review list not truncated)."""
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)


def _esc(value: Any) -> str:
    return _html.escape(str(value), quote=True)


_CSS = """
body{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;margin:24px;color:#1a1a1a;font-size:14px}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:20px 0 6px}
.muted{color:#666;font-size:12px}
.header{margin-bottom:12px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}
.card{border:1px solid #ddd;border-left-width:5px;border-radius:6px;padding:10px 14px;min-width:150px}
.card .num{font-size:24px;font-weight:600}
.card.confirmed{border-left-color:#008033}.card.backfilled{border-left-color:#D98C00}
.card.mismatch{border-left-color:#CC080D}.card.neutral{border-left-color:#3359B3}
table{border-collapse:collapse;margin:6px 0;width:100%}
th,td{border:1px solid #ddd;padding:4px 8px;text-align:left;font-size:13px}
th{background:#f5f5f5}
.banner{background:#fdf6ec;border:1px solid #D98C00;border-radius:6px;padding:8px 12px;margin:10px 0}
.warn{color:#8a5a00;font-size:12px}
footer{margin-top:24px;border-top:1px solid #ddd;padding-top:8px;color:#666;font-size:12px}
@media print{body{margin:8mm}.card,table{break-inside:avoid}}
"""


def _tables_table(summary: List[Dict[str, Any]], t: Dict[str, str]) -> str:
    rows = []
    for entry in summary:
        coverage = entry["coverage"]
        rows.append(
            "<tr><td>{page}</td><td>#{idx}</td><td>{rows} × {cols}</td><td>{c}</td><td>{b}</td><td>{m}</td><td>{cov}</td></tr>".format(
                page=_esc(entry["page"]),
                idx=_esc(entry["table_index"]),
                rows=entry["rows"],
                cols=entry["cols"],
                c=entry["confirmed"],
                b=entry["backfilled"],
                m=entry["mismatch"],
                cov=coverage if coverage is not None else _esc(t["coverage_none"]),
            )
        )
    return (
        "<table><tr><th>{h0}</th><th>{h1}</th><th>{h2}</th><th>{h3}</th><th>{h4}</th><th>{h5}</th><th>{h6}</th></tr>{rows}</table>"
    ).format(h0=t["col_page"], h1=t["col_table"], h2=t["col_size"], h3=t["col_confirmed"], h4=t["col_backfilled"], h5=t["col_mismatch"], h6=t["col_coverage"], rows="".join(rows))


def _review_table(review_list: List[Dict[str, Any]], t: Dict[str, str]) -> str:
    shown = review_list[:_REVIEW_DISPLAY_CAP]
    rows = []
    for rec in shown:
        text_layer = rec.get("text_layer_text") or t["no_aligned"]
        rows.append(
            "<tr><td>{page}</td><td>#{idx}</td><td>r{row}c{col}</td><td>{ocr}</td><td>{tl}</td></tr>".format(
                page=_esc(rec.get("page")),
                idx=_esc(rec.get("table_index")),
                row=_esc(rec.get("row")),
                col=_esc(rec.get("col")),
                ocr=_esc(rec.get("ocr_text")),
                tl=_esc(text_layer),
            )
        )
    note = ""
    if len(review_list) > _REVIEW_DISPLAY_CAP:
        note = "<p class='muted'>{}</p>".format(
            _esc(t["truncated_note"].format(n=len(review_list) - _REVIEW_DISPLAY_CAP))
        )
    return (
        "<p class='muted'>{note}</p><table><tr><th>{h0}</th><th>{h1}</th><th>{h2}</th><th>{h3}</th><th>{h4}</th></tr>{rows}</table>{note2}"
    ).format(
        note=_esc(t["review_note"]),
        h0=t["col_page"],
        h1=t["col_table"],
        h2=t["col_size"],
        h3=t["col_ocr"],
        h4=t["col_new"],
        rows="".join(rows),
        note2=note,
    )


def render_report_html(
    report_data: Dict[str, Any], lang: str = "en", out_path: Optional[str] = None
) -> str:
    """One self-contained HTML page (inline CSS, zero JS, zero external refs)."""
    t = _LITERALS["zh"] if lang == "zh" else _LITERALS["en"]
    header = report_data["header"]
    cards = report_data["metric_cards"]
    tl = cards["text_layer_pages"]
    annotation = report_data["annotation_summary"]
    verdicts = report_data["page_verdicts"]
    figures = report_data["figures"]

    banner = ""
    if annotation.get("document_skipped_reason"):
        banner = "<div class='banner'>{}</div>".format(
            _esc(t["doc_skipped"].format(reason=annotation["document_skipped_reason"]))
        )

    skipped = annotation.get("pages_skipped") or {}
    skipped_detail = ", ".join("{}: {}".format(k, v) for k, v in sorted(skipped.items())) or "0"

    parts: List[str] = [
        "<!DOCTYPE html><html lang='{}'><head><meta charset='utf-8'><title>{}</title><style>{}</style></head><body>".format(
            lang, _esc(t["title"]), _CSS
        ),
        "<div class='header'><h1>{}</h1><div class='muted'>{} · {}: {} · {} {} · {} v{}".format(
            _esc(t["title"]),
            _esc(header["filename"]),
            _esc(t["processed"]),
            _esc(header["processed_at"]),
            _esc(t["task"]),
            _esc(header["task_id"]),
            _esc(t["engines"]),
            _esc(header["app_version"]),
        ),
        " · {} {}</div></div>".format(_esc(t["pages"]), _esc(header["pages_total"] if header["pages_total"] is not None else t["coverage_none"])),
        banner,
        "<div class='cards'>"
        "<div class='card confirmed'><div class='num'>{}</div>{}</div>"
        "<div class='card backfilled'><div class='num'>{}</div>{}</div>"
        "<div class='card mismatch'><div class='num'>{}</div>{}</div>"
        "<div class='card neutral'><div class='num'>{}/{}</div>{}</div>"
        "</div>".format(
            cards["cells_confirmed"], _esc(t["card_confirmed"]),
            cards["cells_backfilled"], _esc(t["card_backfilled"]),
            cards["cells_mismatch"], _esc(t["card_mismatch"]),
            tl["trusted"], tl["judged"], _esc(t["card_text_layer"]),
        ),
        "<h2>{}</h2>".format(_esc(t["tables_title"])),
        _tables_table(report_data["tables_summary"], t),
        "<h2>{}</h2>".format(_esc(t["review_title"])),
        _review_table(report_data["review_list"], t),
    ]
    if report_data["review_truncated_count"]:
        parts.append(
            "<p class='muted'>{}</p>".format(
                _esc(t["truncated_note"].format(n=report_data["review_truncated_count"]))
            )
        )

    if report_data["backfill_demo"]:
        demo_rows = "".join(
            "<tr><td>{page}</td><td>#{idx}</td><td>r{row}c{col}</td><td>{ocr}</td><td>{new}</td></tr>".format(
                page=_esc(d["page"]), idx=_esc(d["table_index"]), row=_esc(d["row"]), col=_esc(d["col"]),
                ocr=_esc(d["ocr_text"]), new=_esc(d["new_text"]),
            )
            for d in report_data["backfill_demo"]
        )
        parts.append(
            "<h2>{}</h2><table><tr><th>{}</th><th>{}</th><th>{}</th><th>{}</th><th>{}</th></tr>{}</table>".format(
                _esc(t["demo_title"]), _esc(t["col_page"]), _esc(t["col_table"]),
                _esc(t["col_size"]), _esc(t["col_ocr"]), _esc(t["col_new"]), demo_rows,
            )
        )

    parts.append(
        "<h2>{}</h2><p>{} — {}: {} · {}: {} · {}: {}</p>".format(
            _esc(t["figures_title"]), _esc(t["figures_title"]),
            _esc(t["col_confirmed"]), figures["figure_count"],
            _esc(t["col_backfilled"]), figures["figure_cropped_count"],
            _esc(t["col_mismatch"]), figures["figure_integrity_warning_count"],
        )
    )
    parts.append(
        "<h2>{}</h2><p>text_layer: {} · overlay: {} · mixed: {} · no_text: {}</p>".format(
            _esc(t["verdicts_title"]),
            verdicts["text_layer"], verdicts["overlay"], verdicts["mixed"], verdicts["no_text"],
        )
    )
    annotation_line = t["annotated_pages"].format(n=annotation.get("pages_annotated", 0), total=annotation.get("pages_total", 0))
    parts.append(
        "<h2>{}</h2><p>{} · {}</p>".format(
            _esc(t["annotation_title"]), _esc(annotation_line), _esc(t["skipped_pages"].format(detail=skipped_detail)),
        )
    )
    if annotation.get("cells_fallback_table_level"):
        parts.append("<p class='muted'>table-level only: {}</p>".format(annotation["cells_fallback_table_level"]))
    if not annotation.get("counts_match_quality", True):
        parts.append("<p class='warn'>{}</p>".format(_esc(t["consistency_warning"])))

    footer = report_data["footer"]
    parts.append(
        "<footer>{} · DocuVision v{} · {} · {} {}</footer></body></html>".format(
            _esc(t["footer_privacy"]), _esc(footer["app_version"]),
            _esc(footer["generated_at"]), _esc(t["task"]), _esc(footer["task_id"]),
        )
    )
    page = "".join(parts)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(page)
    return page

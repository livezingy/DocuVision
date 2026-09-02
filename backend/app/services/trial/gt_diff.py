"""Ground-truth diff and HTML accuracy report (GLM trial P1-4).

Compares operator-provided expected values (fields / table cells) against a
finished task result and renders a self-contained HTML report. This is the
"free diagnostic" deliverable of the 1-hour trial: the client keeps a
measurable accuracy sheet for their own documents whether or not they hire.

Pure logic — no FastAPI / Paddle imports — so it is unit-testable locally
(contract layer, per .cursor/rules/004). The API endpoint lives in main.py.

Input contract
--------------
Ground truth (gt), typically hand-filled by the trial client::

    {
      "fields": {"invoice_number": "INV-001", ...},
      "tables": [                          # list of tables
        [["h1", "h2"], ["a", "b"]],        # each table = rows of cells
        ...
      ]
    }

Task result (subset consumed)::

    {
      "kie_fields": {...},                 # preferred
      "view": {"fields": {...}},           # fallback (finalize merge)
      "tables": [ {"data": [[...]]}, ... ] # table_service contract
    }

Statuses per item: ``match`` | ``missing`` (expected, not extracted) |
``wrong`` (both non-empty, differ) | ``gt_empty`` (nothing expected).
Accuracy denominators count only evaluable items (gt non-empty).
"""

from __future__ import annotations

import argparse
import html as _html
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

_WS = re.compile(r"\s+")
_CURRENCY = re.compile(r"[$€£¥₹]")


def normalize(value: Any, case_sensitive: bool = False) -> str:
    """Canonical form for comparison: trim, collapse whitespace, drop
    currency symbols; case-insensitive by default."""
    if value is None:
        return ""
    s = str(value)
    s = s.replace(chr(160), " ")  # NBSP -> space
    s = _CURRENCY.sub("", s)
    s = _WS.sub(" ", s).strip()
    if not case_sensitive:
        s = s.casefold()
    return s


def _classify(gt_norm: str, actual_norm: str) -> str:
    if not gt_norm:
        return "gt_empty"
    if not actual_norm:
        return "missing"
    if gt_norm == actual_norm:
        return "match"
    return "wrong"


def _summary(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    evaluable = [i for i in items if i["status"] != "gt_empty"]
    matched = [i for i in evaluable if i["status"] == "match"]
    return {
        "total": len(items),
        "evaluable": len(evaluable),
        "matched": len(matched),
        "missing": sum(1 for i in evaluable if i["status"] == "missing"),
        "wrong": sum(1 for i in evaluable if i["status"] == "wrong"),
        "accuracy": round(len(matched) / len(evaluable), 4) if evaluable else None,
    }


def diff_fields(
    gt_fields: Dict[str, Any],
    actual_fields: Dict[str, Any],
    case_sensitive: bool = False,
) -> Dict[str, Any]:
    """Field-level diff. ``actual`` keys not in gt are ignored (scope = gt)."""
    items: List[Dict[str, Any]] = []
    for key, gt_val in (gt_fields or {}).items():
        actual_val = (actual_fields or {}).get(key)
        status = _classify(normalize(gt_val, case_sensitive), normalize(actual_val, case_sensitive))
        items.append(
            {
                "key": str(key),
                "expected": "" if gt_val is None else str(gt_val),
                "actual": "" if actual_val is None else str(actual_val),
                "status": status,
            }
        )
    return {"items": items, "summary": _summary(items)}


def diff_table(
    gt_rows: List[List[Any]],
    actual_rows: List[List[Any]],
    case_sensitive: bool = False,
) -> Dict[str, Any]:
    """Cell-level diff by (row, col) position on the overlapping shape."""
    gt_rows = gt_rows or []
    actual_rows = actual_rows or []
    items: List[Dict[str, Any]] = []
    n_rows = min(len(gt_rows), len(actual_rows))
    for r in range(n_rows):
        gt_row, act_row = gt_rows[r], actual_rows[r]
        n_cols = min(len(gt_row), len(act_row))
        for c in range(n_cols):
            gt_val, act_val = gt_row[c], act_row[c]
            status = _classify(normalize(gt_val, case_sensitive), normalize(act_val, case_sensitive))
            items.append(
                {
                    "row": r,
                    "col": c,
                    "expected": "" if gt_val is None else str(gt_val),
                    "actual": "" if act_val is None else str(act_val),
                    "status": status,
                }
            )
        # gt cells beyond actual row width → missing
        for c in range(n_cols, len(gt_row)):
            gt_val = gt_row[c]
            if normalize(gt_val, case_sensitive):
                items.append(
                    {"row": r, "col": c, "expected": str(gt_val), "actual": "", "status": "missing"}
                )
    # gt rows beyond actual rows → missing
    for r in range(n_rows, len(gt_rows)):
        for c, gt_val in enumerate(gt_rows[r]):
            if normalize(gt_val, case_sensitive):
                items.append(
                    {"row": r, "col": c, "expected": str(gt_val), "actual": "", "status": "missing"}
                )
    return {
        "gt_shape": [len(gt_rows), max((len(r) for r in gt_rows), default=0)],
        "actual_shape": [len(actual_rows), max((len(r) for r in actual_rows), default=0)],
        "shape_match": bool(
            len(gt_rows) == len(actual_rows)
            and all(len(a) == len(b) for a, b in zip(gt_rows, actual_rows))
        ),
        "items": items,
        "summary": _summary(items),
    }


# ---------------------------------------------------------------------------
# Actual-value extraction from a task result
# ---------------------------------------------------------------------------

def extract_actual_fields(task_result: Dict[str, Any]) -> Dict[str, Any]:
    """Prefer result.kie_fields; fall back to result.view.fields."""
    if not isinstance(task_result, dict):
        return {}
    fields = task_result.get("kie_fields")
    if isinstance(fields, dict) and fields:
        return fields
    view = task_result.get("view")
    if isinstance(view, dict) and isinstance(view.get("fields"), dict):
        return view["fields"]
    return {}


def extract_actual_tables(task_result: Dict[str, Any]) -> List[List[List[Any]]]:
    """table_service contract: each table dict has ``data`` = rows of cells."""
    tables = task_result.get("tables") if isinstance(task_result, dict) else None
    out: List[List[List[Any]]] = []
    for t in tables or []:
        if isinstance(t, dict) and isinstance(t.get("data"), list):
            out.append(t["data"])
    return out


# ---------------------------------------------------------------------------
# Report assembly + HTML rendering
# ---------------------------------------------------------------------------

_STATUS_LABEL = {"match": "✓ match", "missing": "missing", "wrong": "✗ wrong", "gt_empty": "— n/a"}


def _render_html(report: Dict[str, Any]) -> str:
    f_sum = report["fields"]["summary"]
    t_all = report["tables"]
    cell_total = sum(t["summary"]["evaluable"] for t in t_all)
    cell_match = sum(t["summary"]["matched"] for t in t_all)
    cell_acc = round(cell_match / cell_total, 4) if cell_total else None

    def kpi(label, value, sub=""):
        v = "—" if value is None else f"{value * 100:.1f}%"
        return (
            f'<div style="flex:1;min-width:150px;border:1px solid #cbd5e1;border-radius:8px;padding:12px;background:#f8fafc;">'
            f'<div style="font-size:12px;color:#475569;">{label}</div>'
            f'<div style="font-size:26px;font-weight:600;color:#0f172a;">{v}</div>'
            f'<div style="font-size:11px;color:#64748b;">{sub}</div></div>'
        )

    parts = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<title>DocuVision GT Diff Report</title></head>",
        "<body style='font-family:Inter,system-ui,sans-serif;color:#0f172a;background:#fff;margin:0;padding:24px;'>",
        f"<h2 style='margin:0 0 4px 0;'>Ground-Truth Diff Report</h2>",
        f"<div style='color:#475569;font-size:13px;margin-bottom:16px;'>job: {_html.escape(str(report['job_id']))} · "
        f"generated: {_html.escape(report['generated_at'])} · source: GLM trial P1-4</div>",
        "<div style='display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px;'>",
        kpi("Field accuracy", f_sum["accuracy"], f"{f_sum['matched']}/{f_sum['evaluable']} evaluable fields"),
        kpi("Table cell accuracy", cell_acc, f"{cell_match}/{cell_total} evaluable cells"),
        kpi("Fields missing", f_sum["missing"] / (f_sum["evaluable"] or 1), f"{f_sum['missing']} not extracted"),
        "</div>",
    ]

    # Fields section
    parts.append("<h3 style='margin:20px 0 8px 0;'>Fields</h3>")
    if not report["fields"]["items"]:
        parts.append("<div style='color:#94a3b8;font-size:13px;'>No ground-truth fields provided.</div>")
    else:
        parts.append(
            "<table style='border-collapse:collapse;width:100%;font-size:13px;'>"
            "<tr style='background:#f1f5f9;'>"
            "<th style='border:1px solid #e2e8f0;padding:6px 10px;text-align:left;'>Field</th>"
            "<th style='border:1px solid #e2e8f0;padding:6px 10px;text-align:left;'>Expected</th>"
            "<th style='border:1px solid #e2e8f0;padding:6px 10px;text-align:left;'>Actual</th>"
            "<th style='border:1px solid #e2e8f0;padding:6px 10px;text-align:left;'>Status</th></tr>"
        )
        for item in report["fields"]["items"]:
            bg = {"match": "#f0fdf4", "wrong": "#fef2f2", "missing": "#fffbeb", "gt_empty": "#f8fafc"}[item["status"]]
            parts.append(
                f"<tr style='background:{bg};'>"
                f"<td style='border:1px solid #e2e8f0;padding:6px 10px;'>{_html.escape(item['key'])}</td>"
                f"<td style='border:1px solid #e2e8f0;padding:6px 10px;'>{_html.escape(item['expected'])}</td>"
                f"<td style='border:1px solid #e2e8f0;padding:6px 10px;'>{_html.escape(item['actual'])}</td>"
                f"<td style='border:1px solid #e2e8f0;padding:6px 10px;'>{_STATUS_LABEL[item['status']]}</td></tr>"
            )
        parts.append("</table>")

    # Tables section
    for idx, t in enumerate(report["tables"], start=1):
        s = t["summary"]
        acc = "—" if s["accuracy"] is None else f"{s['accuracy'] * 100:.1f}%"
        shape = f"gt {t['gt_shape'][0]}×{t['gt_shape'][1]} vs actual {t['actual_shape'][0]}×{t['actual_shape'][1]}"
        parts.append(
            f"<h3 style='margin:20px 0 8px 0;'>Table {idx} <span style='font-weight:400;color:#475569;font-size:12px;'>"
            f"{acc} · {shape}{' · shape mismatch' if not t['shape_match'] else ''}</span></h3>"
        )
        n_rows = max(t["gt_shape"][0], t["actual_shape"][0])
        n_cols = max(t["gt_shape"][1], t["actual_shape"][1])
        cell_map = {(i["row"], i["col"]): i for i in t["items"]}
        parts.append("<table style='border-collapse:collapse;font-size:12px;'>")
        for r in range(n_rows):
            parts.append("<tr>")
            for c in range(n_cols):
                item = cell_map.get((r, c))
                if item is None:
                    parts.append(
                        f"<td style='border:1px solid #eef2f7;padding:5px 9px;background:#ffffff;color:#cbd5e1;'>—</td>"
                    )
                    continue
                bg = {"match": "#f0fdf4", "wrong": "#fef2f2", "missing": "#fffbeb", "gt_empty": "#f8fafc"}[item["status"]]
                tooltip = f"expected: {item['expected']!r} | actual: {item['actual']!r}"
                parts.append(
                    f"<td style='border:1px solid #e2e8f0;padding:5px 9px;background:{bg};' title='{_html.escape(tooltip)}'>"
                    f"{_html.escape(item['actual'] or item['expected'])}</td>"
                )
            parts.append("</tr>")
        parts.append("</table>")

    parts.append(
        "<div style='margin-top:24px;color:#94a3b8;font-size:11px;'>DocuVision · self-hosted document pipeline · "
        "normalization: trim + collapse whitespace + strip currency symbols + case-insensitive</div>"
    )
    parts.append("</body></html>")
    return "".join(parts)


def run_diff(
    gt: Dict[str, Any],
    task_result: Dict[str, Any],
    job_id: str = "",
    output_html_path: Optional[str] = None,
    case_sensitive: bool = False,
) -> Dict[str, Any]:
    """Full diff + report. Writes the HTML when ``output_html_path`` given."""
    fields = diff_fields(gt.get("fields") or {}, extract_actual_fields(task_result), case_sensitive)
    gt_tables = gt.get("tables") or []
    actual_tables = extract_actual_tables(task_result)
    tables = [
        diff_table(gt_t, actual_tables[i] if i < len(actual_tables) else [], case_sensitive)
        for i, gt_t in enumerate(gt_tables)
    ]
    report = {
        "job_id": job_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "case_sensitive": case_sensitive,
        "fields": fields,
        "tables": tables,
    }
    if output_html_path:
        os.makedirs(os.path.dirname(output_html_path) or ".", exist_ok=True)
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(_render_html(report))
        report["html_path"] = output_html_path
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Ground-truth diff (GLM trial P1-4)")
    parser.add_argument("--gt", required=True, help="ground truth JSON path")
    parser.add_argument("--result", required=True, help="task result JSON path (GET /tasks/{id}/result)")
    parser.add_argument("--out", default="gt_diff_report.html", help="HTML output path")
    parser.add_argument("--case-sensitive", action="store_true")
    args = parser.parse_args()

    with open(args.gt, encoding="utf-8") as f:
        gt = json.load(f)
    with open(args.result, encoding="utf-8") as f:
        task_result = json.load(f)

    report = run_diff(gt, task_result, job_id=str(task_result.get("task_id", "")), output_html_path=args.out, case_sensitive=args.case_sensitive)
    slim = {
        "job_id": report["job_id"],
        "fields": report["fields"]["summary"],
        "tables": [t["summary"] | {"shape_match": t["shape_match"]} for t in report["tables"]],
        "html_path": report.get("html_path"),
    }
    print(json.dumps(slim, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

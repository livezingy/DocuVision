"""Pure table-format helpers shared by the export renderers.

Split from the former export_service.py monolith (S1 batch 10): confidence
percenting, export titles/banners and the Excel formula-injection guard.
Re-exported by the export_service facade (pack_export_service and the
tests import them from there).
"""

from __future__ import annotations

from typing import Any, Dict


def table_confidence_pct(table: Dict[str, Any]) -> int:
    """Return table confidence as a 0-100 integer.

    Prefers ``confidence`` (layout detector score mapped by layout_service,
    typically 0-1). Falls back to ``score``. Values in [0, 1] are ratios;
    values greater than 1 are treated as already-percent.
    """
    raw = table.get("confidence")
    if raw is None:
        raw = table.get("score")
    if raw is None:
        return 0
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return 0
    if 0.0 <= val <= 1.0:
        return int(round(val * 100.0))
    return int(round(val))


def format_table_export_title(index_1based: int, table: Dict[str, Any]) -> str:
    """Human-readable table title including page, confidence, and caption."""
    page = table.get("page", "?")
    pct = table_confidence_pct(table)
    base = f"Table {index_1based} (Page {page}) confidence={pct}%"
    caption = str(table.get("caption") or "").strip()
    if not caption:
        return base
    if len(caption) > 160:
        caption = caption[:157] + "..."
    return f"{base} — {caption}"


def format_table_csv_banner(index_1based: int, table: Dict[str, Any]) -> str:
    """CSV separator line placed above each table body (no caption)."""
    page = table.get("page", "?")
    pct = table_confidence_pct(table)
    return f"=== Table {index_1based} (Page {page}) confidence={pct}% ==="


def excel_safe_cell(value: Any) -> Any:
    """Prefix Excel-formula-like text so CSV/XLSX open as literals.

    Excel treats cells starting with ``=``, ``+``, ``@`` (and non-numeric
    ``-``) as formulas. Academic tables often use ``+``/``-`` as class
    labels, which then display as ``#NAME?``. Numbers such as ``-0.5``
    are left unchanged. Markdown/HTML exporters must not call this.
    """
    if value is None:
        return ""
    s = value if isinstance(value, str) else str(value)
    if not s:
        return s
    first = s[0]
    if first in ("=", "+", "@", "\t", "\r"):
        return "'" + s
    if first == "-":
        try:
            float(s.replace(",", ""))
        except ValueError:
            return "'" + s
    return s

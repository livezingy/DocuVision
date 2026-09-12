"""Proof Pack annotated-PDF renderer (v1.8.1 E2).

Burns three-state provenance boxes into the page content stream of the
ORIGINAL PDF (vector ``draw_rect``, not annotation objects — annotations can
be toggled off by the reader; burned content is the evidence).

Pure post-processing: reads the task result JSON (tables + view + quality +
preprocessing) and the original PDF; the pipeline itself is untouched. This
module imports only ``fitz`` and the stdlib so its tests run without the GPU
stack (v1.8.1 §2 constraint).

Coordinate contract (v1.8.1 §3.3, verified against f2ad595):
  * provenance lives in ``result["tables"][i]["cell_provenance"]`` as a 2D
    matrix aligned with ``table["data"]``;
  * per-cell bboxes are NOT persisted anywhere — they are re-derived here
    from the raster-space ``table["bbox"]`` ({x, y, width, height} px) via a
    uniform grid, mirroring ``table_backfill.derive_cell_bbox`` (÷2 to PDF pt
    first, then split evenly; a parity test pins the equivalence);
  * figure outlines come from view-layer elements (kind == "figure",
    flat 8-number polygon, same raster px space);
  * pages whose bboxes do not live in the original page space are skipped,
    never mis-drawn: document-level when preprocessing reports
    "preprocessed" space or a deskew angle, page-level for rotated PDF pages
    and geometry mismatches.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import fitz

# Rasterization uses fitz.Matrix(2, 2): PDF pt = raster px / 2.
RASTER_SCALE = 2.0
# View-page dims vs PDF-page rect sanity check (defensive; 2% per §3.3).
GEOMETRY_TOLERANCE = 0.02

# Provenance values (v1.8.1 §6 contract; unknown values are never drawn).
_PROVENANCE_CONFIRMED = "text_confirmed"
_PROVENANCE_BACKFILLED = "text_backfilled"
_PROVENANCE_MISMATCH = "text_mismatch"


class ProofStyle:
    """Visual encodings (v1.8.1 §3.2). Color + line style double-encode the
    three states so deuteranopia (~5% of male readers) still reads them."""

    CONFIRMED_STROKE = (0.00, 0.50, 0.20)  # deep green #008033, thin solid
    BACKFILLED_STROKE = (0.85, 0.55, 0.00)  # amber #D98C00, thick solid
    MISMATCH_STROKE = (0.80, 0.05, 0.05)  # red #CC080D, dashed
    TABLE_OUTLINE = (0.20, 0.35, 0.70)  # blue #3359B3 (no provenance meaning)
    FIGURE_OUTLINE = (0.55, 0.55, 0.55)  # gray #8C8C8C
    FOOTER_GRAY = (0.45, 0.45, 0.45)

    CONFIRMED_WIDTH = 0.8
    BACKFILLED_WIDTH = 1.4
    MISMATCH_WIDTH = 1.4
    MISMATCH_DASHES = "[4 2] 0"
    TABLE_WIDTH = 0.5
    FIGURE_WIDTH = 0.5

    FOOTER_SIZE = 6.5  # pt, ASCII-only (helv); localized details live in report.html
    FOOTER_TEXT = (
        "Proof: green=verified, amber=backfilled, red=review (details in report.html)"
    )


@dataclass
class AnnotationSummary:
    """Render outcome, fed to the report layer (v1.8.1 §3.1)."""

    pages_total: int = 0
    pages_annotated: int = 0
    pages_skipped: Dict[str, int] = field(default_factory=dict)
    document_skipped_reason: Optional[str] = None  # "preprocessed"|"deskewed"|None
    cells_confirmed: int = 0
    cells_backfilled: int = 0
    cells_mismatch: int = 0
    cells_fallback_table_level: int = 0
    tables_without_bbox: int = 0
    figures_outlined: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _skip(summary: AnnotationSummary, reason: str) -> None:
    summary.pages_skipped[reason] = summary.pages_skipped.get(reason, 0) + 1


def table_rect_pt(bbox: Dict[str, Any]) -> Optional[fitz.Rect]:
    """Raster-px table bbox {x, y, width, height} → PDF pt rect (÷2)."""
    try:
        x = float(bbox.get("x"))
        y = float(bbox.get("y"))
        w = float(bbox.get("width"))
        h = float(bbox.get("height"))
    except (TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    return fitz.Rect(x / RASTER_SCALE, y / RASTER_SCALE, (x + w) / RASTER_SCALE, (y + h) / RASTER_SCALE)


def split_cell_rect(
    rect: fitz.Rect, n_rows: int, n_cols: int, row: int, col: int
) -> Optional[fitz.Rect]:
    """Uniform-grid cell rect inside a pt-space table rect (§3.3)."""
    if n_rows <= 0 or n_cols <= 0 or rect is None or rect.is_empty:
        return None
    col_w = rect.width / n_cols
    row_h = rect.height / n_rows
    return fitz.Rect(
        rect.x0 + col * col_w,
        rect.y0 + row * row_h,
        rect.x0 + (col + 1) * col_w,
        rect.y0 + (row + 1) * row_h,
    )


def derive_cell_rect(
    table_bbox: Dict[str, Any], n_rows: int, n_cols: int, row: int, col: int
) -> Optional[Tuple[float, float, float, float]]:
    """Pt-space cell rect straight from the raster-px table bbox.

    Mirrors ``table_backfill.derive_cell_bbox`` (÷2 first, then uniform
    split); reimplemented here so this module stays fitz+stdlib-only. A test
    pins the equivalence.
    """
    rect = table_rect_pt(table_bbox)
    cell = split_cell_rect(rect, n_rows, n_cols, row, col)
    if cell is None:
        return None
    return (cell.x0, cell.y0, cell.x1, cell.y1)


def _polygon_rect_px(polygon: List[Any]) -> Optional[fitz.Rect]:
    """Flat polygon [x0,y0,x1,y0,x1,y1,x0,y1] in raster px → pt rect."""
    if not isinstance(polygon, (list, tuple)) or len(polygon) < 8:
        return None
    try:
        xs = [float(v) for v in polygon[0::2]]
        ys = [float(v) for v in polygon[1::2]]
    except (TypeError, ValueError):
        return None
    rect = fitz.Rect(min(xs) / RASTER_SCALE, min(ys) / RASTER_SCALE, max(xs) / RASTER_SCALE, max(ys) / RASTER_SCALE)
    if rect.is_empty:
        return None
    return rect


def _table_page_num(table: Dict[str, Any]) -> int:
    try:
        return int(table.get("page", 1) or 1)
    except (TypeError, ValueError):
        return 1


def _view_page_dims_ok(view_page: Dict[str, Any], page_rect: fitz.Rect) -> bool:
    """Defensive check: view px dims must match the PDF page at 2x raster."""
    try:
        width = float(view_page.get("width"))
        height = float(view_page.get("height"))
    except (TypeError, ValueError):
        return True  # nothing to check on legacy results without view dims
    expect_w = page_rect.width * RASTER_SCALE
    expect_h = page_rect.height * RASTER_SCALE
    return (
        abs(width - expect_w) <= GEOMETRY_TOLERANCE * expect_w
        and abs(height - expect_h) <= GEOMETRY_TOLERANCE * expect_h
    )


def _draw_cells(
    page: fitz.Page,
    table: Dict[str, Any],
    table_rect: fitz.Rect,
    style: ProofStyle,
    summary: AnnotationSummary,
) -> bool:
    """Draw three-state cell boxes from the provenance grid. Returns True when
    at least one cell box was drawn (else the table degrades to outline-only)."""
    grid = table.get("cell_provenance")
    if not isinstance(grid, list) or not grid:
        return False
    n_rows = len(grid)
    n_cols = max((len(r) for r in grid if isinstance(r, list)), default=0)
    if n_cols <= 0:
        return False

    drew_any = False
    for i, prov_row in enumerate(grid):
        if not isinstance(prov_row, list):
            continue
        for j, value in enumerate(prov_row):
            if value == _PROVENANCE_CONFIRMED:
                color, width, dashes = style.CONFIRMED_STROKE, style.CONFIRMED_WIDTH, None
            elif value == _PROVENANCE_BACKFILLED:
                color, width, dashes = style.BACKFILLED_STROKE, style.BACKFILLED_WIDTH, None
            elif value == _PROVENANCE_MISMATCH:
                color, width, dashes = style.MISMATCH_STROKE, style.MISMATCH_WIDTH, style.MISMATCH_DASHES
            else:
                continue  # "vision" or unknown → never drawn
            cell = split_cell_rect(table_rect, n_rows, n_cols, i, j)
            if cell is None:
                continue
            kwargs: Dict[str, Any] = {"color": color, "width": width}
            if dashes:
                kwargs["dashes"] = dashes
            page.draw_rect(cell, **kwargs)
            if value == _PROVENANCE_CONFIRMED:
                summary.cells_confirmed += 1
            elif value == _PROVENANCE_BACKFILLED:
                summary.cells_backfilled += 1
            else:
                summary.cells_mismatch += 1
            drew_any = True
    return drew_any


def _draw_footer(page: fitz.Page, style: ProofStyle) -> None:
    """One ASCII legend line inside the bottom 18pt safe area (§3.2)."""
    page.insert_text(
        fitz.Point(36, page.rect.height - 9),
        ProofStyle.FOOTER_TEXT,
        fontsize=style.FOOTER_SIZE,
        fontname="helv",
        color=style.FOOTER_GRAY,
    )


def render_annotated_pdf(
    pdf_path: str,
    result: Dict[str, Any],
    out_path: str,
    style: Optional[ProofStyle] = None,
    footer_stamp: bool = True,
) -> AnnotationSummary:
    """Write ``pdf_path`` + provenance boxes to ``out_path``; original untouched.

    ``result`` is the task result JSON (tables + view + quality +
    preprocessing — D9 merged ``preprocessing`` into task results; legacy
    results without it are treated as "original" space, matching v1.8
    behavior for upright documents).
    """
    style = style or ProofStyle()
    summary = AnnotationSummary()
    doc = fitz.open(pdf_path)
    try:
        summary.pages_total = doc.page_count

        preprocessing = result.get("preprocessing") or {}
        coordinate_space = str(preprocessing.get("coordinate_space") or "original")
        angle_deg = float(preprocessing.get("angle_deg") or 0.0)
        use_unwarping = bool(preprocessing.get("use_doc_unwarping") or False)

        # Document-level gate, same rule as the v1.8.1 funnel gate (D10): when
        # bboxes live in preprocessed space, nothing on this document can be
        # aligned against the original PDF — skip rather than mis-draw.
        if use_unwarping or coordinate_space == "preprocessed":
            summary.document_skipped_reason = "preprocessed"
        elif angle_deg != 0.0:
            summary.document_skipped_reason = "deskewed"

        view_pages: Dict[int, Dict[str, Any]] = {}
        for p in (result.get("view") or {}).get("pages") or []:
            if isinstance(p, dict):
                try:
                    view_pages[int(p.get("page_num") or 0)] = p
                except (TypeError, ValueError):
                    continue
        tables = [t for t in (result.get("tables") or []) if isinstance(t, dict)]

        if summary.document_skipped_reason is not None:
            summary.pages_skipped[summary.document_skipped_reason] = doc.page_count
        else:
            for page in doc:
                page_num = page.number + 1
                if page.rotation != 0:
                    _skip(summary, "rotation")
                    continue
                view_page = view_pages.get(page_num)
                if view_page is not None and not _view_page_dims_ok(view_page, page.rect):
                    _skip(summary, "geometry")
                    continue

                drew_any = False

                # Figure outlines first (they carry no provenance semantics).
                if view_page is not None:
                    for element in view_page.get("elements") or []:
                        if not isinstance(element, dict) or element.get("kind") != "figure":
                            continue
                        rect = _polygon_rect_px(element.get("polygon") or [])
                        if rect is None:
                            continue
                        page.draw_rect(rect, color=style.FIGURE_OUTLINE, width=style.FIGURE_WIDTH)
                        summary.figures_outlined += 1
                        drew_any = True

                for table in tables:
                    if _table_page_num(table) != page_num:
                        continue
                    rect = table_rect_pt(table.get("bbox") or {})
                    if rect is None:
                        summary.tables_without_bbox += 1
                        continue
                    page.draw_rect(rect, color=style.TABLE_OUTLINE, width=style.TABLE_WIDTH)
                    drew_any = True
                    if not _draw_cells(page, table, rect, style, summary):
                        summary.cells_fallback_table_level += 1

                if footer_stamp:
                    _draw_footer(page, style)
                if drew_any:
                    summary.pages_annotated += 1

        doc.save(out_path, garbage=3, deflate=True)
    finally:
        doc.close()
    return summary

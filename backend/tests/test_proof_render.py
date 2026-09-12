"""Tests for the Proof Pack annotated-PDF renderer (v1.8.1 E2).

Synthetic PDFs with known geometry only — no GPU, no app.main import.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from app.services.proof_render import (
    ProofStyle,
    derive_cell_rect,
    render_annotated_pdf,
)

# A4 at 2x raster: view-layer px dims for a 595x842 pt page.
VIEW_DIMS = (1190.0, 1684.0)

# Raster-px table bbox -> pt rect (100, 150, 400, 250); 2x3 grid.
TABLE_BBOX = {"x": 200, "y": 300, "width": 600, "height": 200}
PROV_GRID = [
    ["text_confirmed", "text_backfilled", "text_mismatch"],
    ["vision", "text_confirmed", "vision"],
]


def _base_pdf(tmp_path: Path) -> str:
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    path = tmp_path / "src.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _result(tables=None, elements=None, preprocessing=None, view_dims=VIEW_DIMS):
    return {
        "preprocessing": preprocessing
        if preprocessing is not None
        else {"coordinate_space": "original", "angle_deg": 0.0, "use_doc_unwarping": False},
        "tables": tables if tables is not None else [],
        "view": {
            "pages": [
                {
                    "page_num": 1,
                    "width": view_dims[0],
                    "height": view_dims[1],
                    "elements": elements or [],
                }
            ]
        },
    }


def _standard_table(**overrides):
    table = {
        "id": "t1",
        "page": 1,
        "bbox": TABLE_BBOX,
        "data": [["a", "b", "c"], ["d", "e", "f"]],
        "cell_provenance": [row[:] for row in PROV_GRID],
    }
    table.update(overrides)
    return table


def _rects_by_color(drawings):
    """Collect (rect, width, dashes) per drawing color from get_drawings()."""
    found: dict = {}
    for d in drawings:
        color = d.get("color")
        if color is None:
            continue
        key = tuple(round(float(c), 3) for c in color)
        for item in d.get("items", []):
            if item[0] == "re":
                rect = item[1]
                found.setdefault(key, []).append(
                    ((rect.x0, rect.y0, rect.x1, rect.y1), d.get("width"), d.get("dashes"))
                )
    return found


def test_draws_three_state_cells_and_table_outline(tmp_path) -> None:
    src = _base_pdf(tmp_path)
    out = str(tmp_path / "annotated.pdf")
    summary = render_annotated_pdf(src, _result(tables=[_standard_table()]), out)

    assert summary.pages_annotated == 1
    assert (summary.cells_confirmed, summary.cells_backfilled, summary.cells_mismatch) == (2, 1, 1)
    assert summary.cells_fallback_table_level == 0

    doc = fitz.open(out)
    found = _rects_by_color(doc[0].get_drawings())
    doc.close()

    green = found[tuple(round(c, 3) for c in ProofStyle.CONFIRMED_STROKE)]
    amber = found[tuple(round(c, 3) for c in ProofStyle.BACKFILLED_STROKE)]
    red = found[tuple(round(c, 3) for c in ProofStyle.MISMATCH_STROKE)]
    blue = found[tuple(round(c, 3) for c in ProofStyle.TABLE_OUTLINE)]

    assert len(green) == 2 and len(amber) == 1 and len(red) == 1 and len(blue) == 1
    # Table outline: bbox px / 2 -> (100, 150, 400, 250), 0.5pt.
    assert blue[0][0] == pytest.approx((100, 150, 400, 250), abs=0.5)
    # Amber cell [0][1]: thick solid.
    assert amber[0][0] == pytest.approx((200, 150, 300, 200), abs=0.5)
    assert amber[0][1] == pytest.approx(ProofStyle.BACKFILLED_WIDTH)
    # Red cell [0][2]: dashed 1.4pt — geometry x0+2*cw=300..400, y 150..200.
    assert red[0][0] == pytest.approx((300, 150, 400, 200), abs=0.5)
    assert red[0][1] == pytest.approx(ProofStyle.MISMATCH_WIDTH)
    assert "4" in (red[0][2] or "")


def test_cell_rect_parity_with_table_backfill() -> None:
    from app.services.table_backfill import derive_cell_bbox

    bboxes = [
        {"x": 0, "y": 0, "width": 200, "height": 100},
        {"x": 200.5, "y": 300.25, "width": 600.5, "height": 200.75},
        {"x": 1000, "y": 2000, "width": 480, "height": 640},
        {"x": 0, "y": 0, "width": 0, "height": 10},  # degenerate -> None
        {},  # missing keys -> None
    ]
    grids = [(0, 0, 2, 3), (1, 2, 2, 3), (3, 5, 4, 6)]
    for bbox in bboxes:
        for row, col, n_rows, n_cols in grids:
            expected = derive_cell_bbox(bbox, n_rows, n_cols, row, col)
            actual = derive_cell_rect(bbox, n_rows, n_cols, row, col)
            if expected is None:
                assert actual is None
            else:
                assert actual == pytest.approx(expected, abs=1e-9)


def test_document_skipped_when_preprocessed(tmp_path) -> None:
    src = _base_pdf(tmp_path)
    out = str(tmp_path / "annotated.pdf")
    preprocessing = {"coordinate_space": "preprocessed", "angle_deg": 0.0, "use_doc_unwarping": True}
    summary = render_annotated_pdf(src, _result(tables=[_standard_table()], preprocessing=preprocessing), out)

    assert summary.document_skipped_reason == "preprocessed"
    assert summary.pages_skipped == {"preprocessed": 1}
    assert summary.pages_annotated == 0

    doc = fitz.open(out)
    assert doc[0].get_drawings() == []
    doc.close()


def test_document_skipped_when_deskewed(tmp_path) -> None:
    src = _base_pdf(tmp_path)
    out = str(tmp_path / "annotated.pdf")
    preprocessing = {"coordinate_space": "original", "angle_deg": 7.5, "use_doc_unwarping": False}
    summary = render_annotated_pdf(src, _result(tables=[_standard_table()], preprocessing=preprocessing), out)

    assert summary.document_skipped_reason == "deskewed"
    assert summary.pages_skipped == {"deskewed": 1}


def test_rotated_page_skipped_others_annotated(tmp_path) -> None:
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    rotated = doc.new_page(width=595, height=842)
    rotated.set_rotation(90)
    src = str(tmp_path / "src.pdf")
    doc.save(src)
    doc.close()

    table_rotated = _standard_table(page=2)
    summary = render_annotated_pdf(
        src,
        _result(
            tables=[_standard_table(), table_rotated],
            # view dims apply to page 1 only in this fixture
        ),
        str(tmp_path / "annotated.pdf"),
    )

    assert summary.pages_skipped.get("rotation") == 1
    assert summary.pages_annotated == 1
    assert summary.cells_mismatch == 1  # only page 1's table was drawn


def test_geometry_guard_skips_mismatched_view_dims(tmp_path) -> None:
    src = _base_pdf(tmp_path)
    out = str(tmp_path / "annotated.pdf")
    summary = render_annotated_pdf(
        src, _result(tables=[_standard_table()], view_dims=(3000.0, 4000.0)), out
    )

    assert summary.pages_skipped.get("geometry") == 1
    assert summary.pages_annotated == 0

    doc = fitz.open(out)
    rects = [d for d in doc[0].get_drawings() if d.get("color") is not None]
    doc.close()
    assert rects == []


def test_missing_provenance_falls_back_to_table_outline(tmp_path) -> None:
    src = _base_pdf(tmp_path)
    out = str(tmp_path / "annotated.pdf")
    summary = render_annotated_pdf(src, _result(tables=[_standard_table(cell_provenance=None)]), out)

    assert summary.cells_fallback_table_level == 1
    assert summary.cells_confirmed == 0

    doc = fitz.open(out)
    found = _rects_by_color(doc[0].get_drawings())
    doc.close()
    blue_key = tuple(round(c, 3) for c in ProofStyle.TABLE_OUTLINE)
    assert len(found.get(blue_key, [])) == 1
    assert all(key in {blue_key} for key in found)  # no cell colors at all


def test_table_without_bbox_is_counted_not_drawn(tmp_path) -> None:
    src = _base_pdf(tmp_path)
    out = str(tmp_path / "annotated.pdf")
    summary = render_annotated_pdf(src, _result(tables=[_standard_table(bbox={})]), out)

    assert summary.tables_without_bbox == 1
    doc = fitz.open(out)
    assert [d for d in doc[0].get_drawings() if d.get("color") is not None] == []
    doc.close()


def test_figure_outlines_from_view_layer(tmp_path) -> None:
    src = _base_pdf(tmp_path)
    out = str(tmp_path / "annotated.pdf")
    element = {"kind": "figure", "polygon": [200, 200, 400, 200, 400, 300, 200, 300]}
    summary = render_annotated_pdf(src, _result(elements=[element]), out)

    assert summary.figures_outlined == 1
    doc = fitz.open(out)
    found = _rects_by_color(doc[0].get_drawings())
    doc.close()
    gray_key = tuple(round(c, 3) for c in ProofStyle.FIGURE_OUTLINE)
    assert found[gray_key][0][0] == pytest.approx((100, 100, 200, 150), abs=0.5)


def test_footer_stamp_toggle(tmp_path) -> None:
    src = _base_pdf(tmp_path)

    stamped = str(tmp_path / "stamped.pdf")
    render_annotated_pdf(src, _result(), stamped, footer_stamp=True)
    doc = fitz.open(stamped)
    assert "Proof:" in doc[0].get_text()
    doc.close()

    unstamped = str(tmp_path / "unstamped.pdf")
    render_annotated_pdf(src, _result(), unstamped, footer_stamp=False)
    doc = fitz.open(unstamped)
    assert "Proof:" not in doc[0].get_text()
    doc.close()


def test_original_pdf_left_untouched(tmp_path) -> None:
    src = _base_pdf(tmp_path)
    before = hashlib.sha256(Path(src).read_bytes()).hexdigest()
    render_annotated_pdf(src, _result(tables=[_standard_table()]), str(tmp_path / "annotated.pdf"))
    after = hashlib.sha256(Path(src).read_bytes()).hexdigest()
    assert before == after

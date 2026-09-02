"""Generate trial sample documents for the remote 1-hour diagnostic (GLM P0-3).

Creates ``test_data/testfiles/trial/`` with three deterministic PDFs:

1. ``multi_column_techdoc.pdf`` — two-column technical article with header
   rule, footnote, a bordered table containing merged cells AND the special
   glyphs from the Upwork JD (check mark, tensor product, filled/open dot).
2. ``flowchart_page.pdf``        — vector process-flow diagram (boxes +
   arrows) with a figure caption, designed to exercise figure-region
   detection and crop integrity.
3. ``architecture_diagram.pdf``  — nested-box architecture diagram with
   connector lines and labels.

All content is vector-drawn with PyMuPDF (no external assets), so the
samples regenerate identically anywhere. A symbol-capable font is required
(DejaVu Sans on Linux/Cloud Studio, Segoe UI Symbol on Windows).

Usage:
    python scripts/trial/generate_trial_samples.py [--out DIR] [--font PATH]

Run locally or in Cloud Studio; outputs land in
test_data/testfiles/trial/ (tracked dir, .gitignore does not exclude it).
"""

from __future__ import annotations

import argparse
import os
import sys

import fitz  # PyMuPDF

SYMBOLS = ["✓", "⊗", "●", "○"]
SYMBOL_NAMES = {
    "✓": "check",
    "⊗": "tensor/cross",
    "●": "filled circle",
    "○": "open circle",
}

FONT_CANDIDATES = [
    # Linux / Cloud Studio
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    # Windows
    "C:/Windows/Fonts/seguisym.ttf",
    "C:/Windows/Fonts/consola.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]

A4 = (595, 842)  # pt
INK = (0.1, 0.12, 0.16)
ACCENT = (0.13, 0.4, 0.76)
GRAY = (0.45, 0.5, 0.58)


def find_font(explicit=None):
    if explicit:
        if os.path.isfile(explicit):
            return explicit
        print(f"[error] font not found: {explicit}", file=sys.stderr)
        sys.exit(2)
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            return path
    print(
        "[error] no symbol-capable font found. Pass --font /path/to/font.ttf "
        "(DejaVu Sans on Linux, Segoe UI Symbol on Windows).",
        file=sys.stderr,
    )
    sys.exit(2)


def _register_font(page, fontfile):
    """Register the font on the page and return its refname."""
    fname = "trialfont"
    page.insert_font(fontname=fname, fontfile=fontfile)
    return fname


def _textbox(page, fname, rect, text, size=9, color=INK, align=fitz.TEXT_ALIGN_LEFT):
    page.insert_textbox(rect, text, fontname=fname, fontsize=size, color=color, align=align)


def _grid_table(page, fname, top, left, col_widths, row_h, rows):
    """Draw a bordered table. A row entry of ("__span__", n, text) draws a
    cell merged across n columns (no inner vertical separators)."""
    total_w = sum(col_widths)

    # Horizontal lines
    y = top
    for _ in range(len(rows) + 1):
        page.draw_line(fitz.Point(left, y), fitz.Point(left + total_w, y), color=(0.7, 0.72, 0.75), width=0.8)
        y += row_h

    # Column edges (verticals with span gaps)
    col_edges = [left]
    for w in col_widths[:-1]:
        col_edges.append(col_edges[-1] + w)
    col_edges.append(left + total_w)

    for col in range(len(col_widths)):
        x0 = col_edges[col]
        for r, row in enumerate(rows):
            cell = row[col] if col < len(row) else ""
            if isinstance(cell, tuple) and cell[0] == "__span__":
                continue  # merged cell: no vertical separator at its left edge
            y0, y1 = top + r * row_h, top + (r + 1) * row_h
            page.draw_line(fitz.Point(x0, y0), fitz.Point(x0, y1), color=(0.7, 0.72, 0.75), width=0.8)

    # Cell text
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            if isinstance(cell, tuple) and cell[0] == "__span__":
                _, n, text = cell
                x0 = col_edges[c]
                width = sum(col_widths[c:c + n])
            else:
                x0 = col_edges[c]
                width = col_widths[c]
                text = str(cell)
            page.insert_textbox(
                fitz.Rect(x0 + 4, top + r * row_h + 2, x0 + width - 4, top + (r + 1) * row_h - 2),
                text, fontname=fname, fontsize=9, color=INK,
            )


def build_multi_column_techdoc(fontfile):
    doc = fitz.open()
    page = doc.new_page(width=A4[0], height=A4[1])
    fname = _register_font(page, fontfile)

    # Header + rule
    _textbox(page, fname, fitz.Rect(40, 30, 555, 48), "DocuVision Trial Sample — Technical Digest Vol.7", size=13, color=ACCENT)
    page.draw_line(fitz.Point(40, 52), fitz.Point(555, 52), color=ACCENT, width=1.2)

    # Two text columns
    left_col = (
        "1. System overview\n"
        "The ingestion stage accepts born-digital PDFs and raster scans. A "
        "router inspects the file signature and dispatches either the native "
        "text path or the OCR path.\n\n"
        "2. Layout analysis\n"
        "Region detection groups paragraphs, titles, tables and figures. "
        "Reading order is derived per column before fusion."
    )
    right_col = (
        "3. Table extraction\n"
        "Structure recovery preserves merged cells and header relationships. "
        "Special glyphs survive only when the OCR charset covers them.\n\n"
        "4. Diagnostics\n"
        "Per-region confidence feeds the quality layer; failures are graded "
        "with explicit error codes for replay."
    )
    _textbox(page, fname, fitz.Rect(40, 64, 290, 300), left_col, size=9.5)
    _textbox(page, fname, fitz.Rect(305, 64, 555, 300), right_col, size=9.5)

    # Symbols table with a merged cell (first body row spans 2 columns)
    rows = [
        ["Symbol", "Name", "Unicode", "Pipeline status"],
        [("__span__", 2, "Glyph survival matrix (merged header)"), "—", "see rows"],
        ["✓", SYMBOL_NAMES["✓"], "U+2713", "expected: pass"],
        ["⊗", SYMBOL_NAMES["⊗"], "U+2297", "expected: at risk"],
        ["●", SYMBOL_NAMES["●"], "U+25CF", "expected: pass"],
        ["○", SYMBOL_NAMES["○"], "U+25CB", "expected: at risk"],
    ]
    _grid_table(page, fname, top=330, left=40, col_widths=[70, 150, 90, 205], row_h=22, rows=rows)

    # Footnote
    page.insert_textbox(
        fitz.Rect(40, 640, 555, 700),
        "Footnote 1 — this document is generated deterministically by scripts/trial/generate_trial_samples.py. "
        "Any extraction regression is a pipeline change, not a sample drift.",
        fontname=fname, fontsize=8, color=GRAY,
    )
    return doc


def build_flowchart_page(fontfile):
    doc = fitz.open()
    page = doc.new_page(width=A4[0], height=A4[1])
    fname = _register_font(page, fontfile)

    _textbox(page, fname, fitz.Rect(40, 30, 555, 46), "Pipeline failure diagnosis — process flow", size=12, color=ACCENT)
    _textbox(
        page, fname, fitz.Rect(40, 56, 555, 76),
        "The diagram below is drawn as pure vector shapes so layout detection must classify it as one figure region.",
        size=9,
    )

    import math

    def box(x, y, w, h, label):
        page.draw_rect(fitz.Rect(x, y, x + w, y + h), color=ACCENT, width=1.4, fill=(0.93, 0.95, 0.99))
        page.insert_textbox(fitz.Rect(x + 4, y + 6, x + w - 4, y + h - 4), label, fontname=fname, fontsize=9, color=INK, align=fitz.TEXT_ALIGN_CENTER)

    def arrow(x0, y0, x1, y1):
        page.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1), color=INK, width=1.2)
        ang = math.atan2(y1 - y0, x1 - x0)
        L, spread = 7, 0.45
        p1 = fitz.Point(x1 - L * math.cos(ang - spread), y1 - L * math.sin(ang - spread))
        p2 = fitz.Point(x1 - L * math.cos(ang + spread), y1 - L * math.sin(ang + spread))
        page.draw_polyline([p1, fitz.Point(x1, y1), p2], color=INK, width=1.2)

    box(200, 110, 180, 40, "Upload")
    arrow(290, 150, 290, 180)
    box(200, 180, 180, 40, "Type router")
    arrow(290, 220, 290, 250)
    box(120, 250, 140, 40, "OCR path")
    box(330, 250, 140, 40, "Native path")
    arrow(260, 270, 330, 270)
    arrow(320, 290, 190, 290)
    box(200, 330, 180, 40, "Fusion")
    arrow(290, 370, 290, 400)
    box(200, 400, 180, 40, "Export / quality")

    page.insert_textbox(
        fitz.Rect(40, 470, 555, 492),
        "Figure 1: Two-path document ingestion flow with fusion stage.",
        fontname=fname, fontsize=9, color=GRAY,
    )
    return doc


def build_architecture_diagram(fontfile):
    doc = fitz.open()
    page = doc.new_page(width=A4[0], height=A4[1])
    fname = _register_font(page, fontfile)

    _textbox(page, fname, fitz.Rect(40, 30, 555, 46), "Deployment architecture — nested regions", size=12, color=ACCENT)

    # Outer container
    page.draw_rect(fitz.Rect(60, 70, 535, 380), color=(0.3, 0.34, 0.4), width=1.2)
    page.insert_textbox(fitz.Rect(70, 74, 300, 92), "GPU host (Cloud Studio)", fontname=fname, fontsize=9, color=GRAY)

    # Inner services
    for label, x, y in [
        ("FastAPI :8000", 90, 120),
        ("PaddleX layout", 300, 120),
        ("Qwen2.5-VL KIE", 90, 200),
        ("SQLite queue", 300, 200),
    ]:
        page.draw_rect(fitz.Rect(x, y, x + 190, y + 60), color=ACCENT, width=1.1, fill=(0.96, 0.97, 0.99))
        page.insert_textbox(fitz.Rect(x + 6, y + 8, x + 184, y + 52), label, fontname=fname, fontsize=10, color=INK, align=fitz.TEXT_ALIGN_CENTER)

    # Connectors
    for x0, y0, x1, y1 in [(280, 150, 300, 150), (185, 180, 185, 200), (395, 180, 395, 200), (280, 230, 300, 230)]:
        page.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1), color=(0.55, 0.58, 0.62), width=1.0)

    # Client outside the host box
    page.draw_rect(fitz.Rect(200, 430, 395, 480), color=(0.2, 0.6, 0.35), width=1.2, fill=(0.94, 0.98, 0.95))
    page.insert_textbox(fitz.Rect(206, 438, 389, 474), "Trial client (browser)", fontname=fname, fontsize=10, color=INK, align=fitz.TEXT_ALIGN_CENTER)
    page.draw_line(fitz.Point(297, 380), fitz.Point(297, 430), color=(0.2, 0.6, 0.35), width=1.4)

    page.insert_textbox(
        fitz.Rect(40, 500, 555, 522),
        "Figure 2: Trial deployment topology. Cropping must keep each container intact.",
        fontname=fname, fontsize=9, color=GRAY,
    )
    return doc


README = """# Trial sample pack (GLM trial P0-3)

Deterministic, vector-drawn PDFs for the 1-hour remote diagnostic demo.

| File | Exercises |
|------|-----------|
| `multi_column_techdoc.pdf` | two-column reading order, header rule, footnote, bordered table with a merged cell, special glyphs (✓ ⊗ ● ○) |
| `flowchart_page.pdf` | figure-region detection + complete crop (boxes/arrows must not split) |
| `architecture_diagram.pdf` | nested figure regions + caption |

Regenerate with:
```bash
python scripts/trial/generate_trial_samples.py
```

Glyph row expectations (for the P1-5 symbol benchmark and GT diff):
✓ U+2713 low risk · ⊗ U+2297 at-risk · ● U+25CF low risk · ○ U+25CB at-risk.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=None, help="output dir (default: test_data/testfiles/trial)")
    parser.add_argument("--font", default=None, help="symbol-capable .ttf path")
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_dir = args.out or os.path.join(root, "test_data", "testfiles", "trial")
    os.makedirs(out_dir, exist_ok=True)
    fontfile = find_font(args.font)

    builders = {
        "multi_column_techdoc.pdf": build_multi_column_techdoc,
        "flowchart_page.pdf": build_flowchart_page,
        "architecture_diagram.pdf": build_architecture_diagram,
    }
    for name, builder in builders.items():
        doc = builder(fontfile)
        path = os.path.join(out_dir, name)
        doc.save(path, garbage=3, deflate=True)
        doc.close()
        size = os.path.getsize(path)
        print(f"[ok] {name} ({size / 1024:.1f} KB, font={os.path.basename(fontfile)})")

    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(README)
    print(f"[done] samples written to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

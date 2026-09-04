#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a ground-truth baseline JSON for an arXiv born-digital paper PDF.

Pipeline (local, one-time, per paper):

    SOURCE MODE html         SOURCE MODE official-pdf
    arXiv HTML (LaTeXML)     official arXiv PDF for the pinned version
        |                        |
        v                        v
    captions/tables/sections printed-layer extraction
    (Tier A: author source)  (Tier A-: verbatim printed text, pdfTeX
                             ToUnicode -- deterministic, no OCR; still
                             needs first-use human spot-check)
        |                        |
        +-----------+------------+
                    v
        align captions onto the LOCAL sample PDF pages (Tier B)
        cluster vector drawings as figure regions  (Tier C)
                    v
        gt/<slug>.gt.json  (pinned: pdf_sha256 + arxiv_version +
                           source url/sha)

When to use which mode (check FIRST, before building):
    html         sample PDF has a matching arXiv HTML version. Verify by
                 comparing caption numbering (Figure/Table counts) between
                 the HTML and the sample; a major revision renumbers
                 everything (e.g. Mamba 2312.00752: v2 HTML has Tables 1-7,
                 the v1 sample has Tables 1-15 -- v2 HTML is UNUSABLE for
                 the v1 sample).
    official-pdf sample is an arXiv paper whose version has NO HTML
                 (404) and no LaTeX e-print (PDF-only submission). The
                 official author-submitted PDF printed layer is then the
                 closest thing to the authoring source. Table cell grids
                 are reconstructed geometrically from word positions ->
                 always Tier B + human queue.

Applicable document types (MUST read before reuse on another file):
    OK:
        born-digital PDF with an embedded text layer produced from LaTeX
        (arXiv pdfTeX papers). Printed-text truth is read live from the
        text layer, never re-OCR'd.
    DEGRADED (Tier-C only + text recall):
        born-digital PDF WITHOUT an arXiv twin (datasheets, reports).
        Captions/tables lack an authoring source; cell-level table truth
        must come from somewhere else.
    NOT APPLICABLE:
        scanned / image-only PDFs (e.g. 01_patent_us8582..., full-page
        bitmaps). The text layer there is itself OCR output and is NOT
        ground truth; use an OCR-centric eval instead.

Trust tiers (each baseline item carries "trust"):
    A - verbatim authoring source (arXiv HTML). Mismatch vs engine =>
        likely pipeline bug.
    A- (recorded as "A" with source "official_pdf_textlayer") - verbatim
        printed caption text extracted from the official arXiv PDF.
        Deterministic, but not the authoring source; spot-check once.
    B - aligned onto the sample PDF (page/bbox) or geometrically
        reconstructed (table grids, section headings). MUST be human-
        locked on first use (see gt/README.md).
    C - heuristic only (drawing-cluster figure regions). Advisory;
        always routed to the human queue, never a hard failure.

Usage:
    python gt_build_arxiv.py --pdf <sample.pdf> --arxiv 2312.00752 \
        --version v1 --slug 03_mamba --source official-pdf
    python gt_build_arxiv.py --pdf <sample.pdf> --arxiv <id> \
        --version <v> --slug <slug> --source html

    Output:  ../testfiles/PDF_Parsing/gt/<slug>.gt.json
    Cache:   ../../TestResult/gt_cache/  (gitignored, re-run friendly)

Encoding discipline: explicit utf-8 everywhere; stdout reconfigured to
utf-8 (Windows GBK consoles crash on U+2713 etc.). Run with the
workspace Python D:\\USERS\\livez\\Python\\python.exe (fitz installed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GT_DIR = REPO_ROOT / "test_data" / "testfiles" / "PDF_Parsing" / "gt"
DEFAULT_CACHE_DIR = REPO_ROOT / "test_data" / "TestResult" / "gt_cache"

HEADING_TAGS = {"h1", "h2", "h3", "h4"}
# Captions in this corpus always print as "Table N:" / "Figure N:"; the
# separator is MANDATORY so body-text references ("Table 3 shows ...")
# cannot be captured as captions.
CAPTION_RE = re.compile(r"^(Figure|Table|Algorithm)\s+(\d+)\s*:", re.IGNORECASE)
WS_RE = re.compile(r"\s+")
ARXIV_FETCH_DELAY_S = 3  # memory 2026-09-02: consecutive arXiv hits throttle (http=000)
ROW_Y_TOL = 4.0          # pt, line clustering tolerance for table rows
CELL_X_GAP = 12.0        # pt, min x-gap to split words into separate cells
COL_SNAP = 10.0          # pt, column x0 snapping tolerance
HEADING_TEXT_RE = re.compile(r"^(\d+(\.\d+)*|[A-Z](\.\d+)*)\s+[A-Z]")


# ---------------------------------------------------------------------------
# arXiv fetching
# ---------------------------------------------------------------------------

def _arxiv_get(url: str, binary: bool = False, attempts: int = 3):
    last_err = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DocuVision-GT-Builder/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            return data if binary else data.decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError) as exc:
            last_err = exc
            print(f"[fetch] attempt {attempt + 1} failed: {exc}; sleeping {ARXIV_FETCH_DELAY_S}s")
            time.sleep(ARXIV_FETCH_DELAY_S)
    raise SystemExit(f"ERROR: could not fetch {url}: {last_err}")


def fetch_arxiv_html(arxiv_id: str, version: str, cache_dir: Path) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{arxiv_id}{version}.html"
    if cache_file.exists() and cache_file.stat().st_size > 10_000:
        print(f"[cache] using {cache_file}")
        return cache_file.read_text(encoding="utf-8", errors="replace")
    url = f"https://arxiv.org/html/{arxiv_id}{version}"
    html = _arxiv_get(url)
    if len(html) < 10_000 or "not available" in html[:2000].lower():
        raise SystemExit(f"ERROR: arXiv has no usable HTML for {url} (len={len(html)}); use --source official-pdf")
    cache_file.write_text(html, encoding="utf-8")
    print(f"[fetch] saved {len(html)} chars -> {cache_file}")
    return html


def fetch_official_pdf(arxiv_id: str, version: str, cache_dir: Path) -> tuple[Path, str]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{arxiv_id}{version}_official.pdf"
    if not (out.exists() and out.stat().st_size > 100_000):
        data = _arxiv_get(f"https://arxiv.org/pdf/{arxiv_id}{version}", binary=True)
        if data[:5] != b"%PDF-":
            raise SystemExit(f"ERROR: {arxiv_id}{version} did not return a PDF")
        out.write_bytes(data)
        print(f"[fetch] saved {len(data)} bytes -> {out}")
    return out, sha256_file(out)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# HTML parsing mode (papers whose arXiv version HAS an HTML twin)
# ---------------------------------------------------------------------------

class _Cell:
    def __init__(self, attrs: dict, in_thead: bool) -> None:
        self.texts: list[str] = []
        self.rowspan = max(1, int(attrs.get("rowspan", 1) or 1))
        self.colspan = max(1, int(attrs.get("colspan", 1) or 1))
        self.is_header = in_thead


class _Table:
    def __init__(self, attrs: dict) -> None:
        self.css_class = (attrs.get("class") or "").lower()
        self.rows: list[list[_Cell]] = []
        self.current_row: list[_Cell] | None = None
        self.thead_depth = 0
        self.in_figure = False


class _Caption:
    def __init__(self) -> None:
        self.texts: list[str] = []
        self.kind = ""
        self.no = 0


class _Heading:
    def __init__(self, tag: str) -> None:
        self.level = int(tag[1])
        self.texts: list[str] = []


class _FigureBox:
    def __init__(self, attrs: dict) -> None:
        self.tables: list[_Table] = []
        self.captions: list[_Caption] = []


class ArxivHTMLParser(HTMLParser):
    """Extract numbered captions, span-expanded data tables and section
    headings from LaTeXML HTML. Equation/layout tables are dropped;
    figcaption/cell text excludes nested tables; <math> contributes
    alttext (author LaTeX) which norm_for_search flattens later."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.captions: list[_Caption] = []
        self.tables: list[_Table] = []
        self.headings: list[_Heading] = []
        self.figure_boxes: list[_FigureBox] = []
        self._figure_stack: list[_FigureBox] = []
        self._table_stack: list[_Table] = []
        self._cell_stack: list[_Cell] = []
        self._caption_stack: list[_Caption] = []
        self._heading_stack: list[_Heading] = []
        self._math_alt: list[str | None] = []
        self._math_texts: list[list[str]] = []
        self._free_tables: list[_Table] = []
        self.warnings: list[str] = []

    def _collector(self) -> list[str] | None:
        if self._math_texts:
            return self._math_texts[-1]
        if self._cell_stack:
            return self._cell_stack[-1].texts
        if self._caption_stack:
            return self._caption_stack[-1].texts
        if self._heading_stack:
            return self._heading_stack[-1].texts
        return None

    def _register_table(self, table: _Table) -> None:
        if "equation" in table.css_class or "eqn" in table.css_class:
            return
        if not any(len(r) > 1 or (r and r[0].texts) for r in table.rows):
            return
        if self._figure_stack:
            self._figure_stack[-1].tables.append(table)
        else:
            self._free_tables.append(table)
        self.tables.append(table)

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "figure":
            box = _FigureBox(a)
            self.figure_boxes.append(box)
            self._figure_stack.append(box)
        elif tag == "table":
            t = _Table(a)
            t.in_figure = bool(self._figure_stack)
            self._table_stack.append(t)
        elif tag == "thead" and self._table_stack:
            self._table_stack[-1].thead_depth += 1
        elif tag == "tr" and self._table_stack:
            self._table_stack[-1].current_row = []
        elif tag in ("td", "th") and self._table_stack:
            t = self._table_stack[-1]
            cell = _Cell(a, in_thead=(t.thead_depth > 0 or tag == "th"))
            if t.current_row is None:
                t.current_row = []
            t.current_row.append(cell)
            self._cell_stack.append(cell)
        elif tag == "figcaption":
            self._caption_stack.append(_Caption())
        elif tag in HEADING_TAGS:
            self._heading_stack.append(_Heading(tag))
        elif tag == "math":
            self._math_alt.append(a.get("alttext") or None)
            self._math_texts.append([])

    def handle_endtag(self, tag):
        if tag == "figure" and self._figure_stack:
            self._figure_stack.pop()
        elif tag == "table" and self._table_stack:
            t = self._table_stack.pop()
            if t.current_row:
                t.rows.append(t.current_row)
                t.current_row = None
            self._register_table(t)
        elif tag == "thead" and self._table_stack:
            self._table_stack[-1].thead_depth = max(0, self._table_stack[-1].thead_depth - 1)
        elif tag == "tr" and self._table_stack:
            t = self._table_stack[-1]
            if t.current_row:
                t.rows.append(t.current_row)
            t.current_row = None
        elif tag in ("td", "th") and self._cell_stack:
            self._cell_stack.pop()
        elif tag == "figcaption" and self._caption_stack:
            cap = self._caption_stack.pop()
            # prefer collected math alttexts inside the caption
            text = WS_RE.sub(" ", "".join(cap.texts)).strip()
            m = CAPTION_RE.match(text)
            if m:
                cap.kind = m.group(1).lower()
                cap.no = int(m.group(2))
                cap.texts = [text]
                self.captions.append(cap)
                if self._figure_stack:
                    self._figure_stack[-1].captions.append(cap)
        elif tag in HEADING_TAGS and self._heading_stack:
            h = self._heading_stack.pop()
            text = WS_RE.sub(" ", "".join(h.texts)).strip()
            if text:
                h.texts = [text]
                self.headings.append(h)
        elif tag == "math" and self._math_texts:
            alt = self._math_alt.pop()
            inner = self._math_texts.pop()
            target = self._collector()
            if target is not None:
                target.append(alt if alt else "".join(inner))

    def handle_data(self, data):
        target = self._collector()
        if target is not None:
            target.append(data)


def expand_rows(rows: list[list[_Cell]]) -> tuple[list[list[str]], int]:
    grid: dict[tuple[int, int], str] = {}
    header_row_idx: set[int] = set()
    for ri, row in enumerate(rows):
        ci = 0
        for cell in row:
            while (ri, ci) in grid:
                ci += 1
            text = WS_RE.sub(" ", "".join(cell.texts)).strip()
            for dr in range(cell.rowspan):
                for dc in range(cell.colspan):
                    grid[(ri + dr, ci + dc)] = text if (dr == 0 and dc == 0) else ""
            if cell.is_header and text:
                header_row_idx.add(ri)
    if not grid:
        return [], 0
    max_r = max(k[0] for k in grid) + 1
    max_c = max(k[1] for k in grid) + 1
    out = [[grid.get((r, c), "") for c in range(max_c)] for r in range(max_r)]
    header_rows = 0
    for ri in range(max_r):
        if ri in header_row_idx:
            header_rows = ri + 1
        else:
            break
    return out, header_rows


def parse_html_source(html: str) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    parser = ArxivHTMLParser()
    parser.feed(html)
    parser.close()

    paired: set[int] = set()
    tables: list[dict] = []
    for cap in parser.captions:
        if cap.kind != "table":
            continue
        owner = None
        for box in parser.figure_boxes:
            if cap in box.captions and box.tables:
                owner = box.tables[0]
                break
        if owner is None:
            for t in reversed(parser._free_tables):
                if id(t) not in paired:
                    owner = t
                    paired.add(id(t))
                    break
        if owner is None:
            parser.warnings.append(f"Table {cap.no}: no data table paired; caption-only entry")
        cells, header_rows = expand_rows(owner.rows) if owner else ([], 0)
        tables.append(
            {
                "table_no": cap.no,
                "caption": cap.texts[0],
                "cells": cells,
                "header_rows": header_rows,
                "n_rows": len(cells),
                "n_cols": max((len(r) for r in cells), default=0),
                "trust": "A",
                "source": "html_table",
            }
        )
    tables.sort(key=lambda t: t["table_no"])
    orphan = sum(1 for t in parser.tables if id(t) not in paired)
    if orphan:
        parser.warnings.append(f"{orphan} data table(s) had no 'Table N' caption (kept out of baseline)")

    figures = [
        {"fig_no": c.no, "caption": c.texts[0], "trust": "A", "source": "html_figcaption"}
        for c in parser.captions
        if c.kind == "figure"
    ]
    sections = [
        {"level": h.level, "text": h.texts[0], "trust": "A", "source": "html_heading"}
        for h in parser.headings
    ]
    return tables, figures, sections, parser.warnings


# ---------------------------------------------------------------------------
# Official-PDF mode (PDF-only arXiv submissions; e.g. Mamba v1)
# ---------------------------------------------------------------------------

def _block_text(b) -> str:
    return WS_RE.sub(" ", b[4] or "").strip()


def extract_printed_captions(doc) -> tuple[list[dict], list[dict]]:
    """Caption blocks from the printed layer. booktabs prints each caption
    as its own text block starting with 'Table N:' / 'Figure N:'."""
    tables: dict[int, dict] = {}
    figures: dict[int, dict] = {}
    for pno in range(doc.page_count):
        for b in doc[pno].get_text("blocks"):
            if b[6] != 0:
                continue
            text = _block_text(b)
            m = CAPTION_RE.match(text)
            if not m:
                continue
            kind, no = m.group(1).lower(), int(m.group(2))
            store = tables if kind == "table" else figures
            if no in store:
                continue
            store[no] = {
                ("table_no" if kind == "table" else "fig_no"): no,
                "caption": text,
                "src_page": pno + 1,
                "src_bbox": [round(v, 2) for v in b[:4]],
                "trust": "A",
                "source": "official_pdf_textlayer",
            }
    return (
        [tables[k] for k in sorted(tables)],
        [figures[k] for k in sorted(figures)],
    )


def extract_printed_sections(doc) -> list[dict]:
    """Headings via bold spans + numbering prefix (or unnumbered majors).

    Bold = font name contains 'TB' (LinLibertine bold) or 'Bold'. Level 1:
    size >= 11.5 (\\section) or unnumbered majors (References, Appendix,
    Acknowledg*). Level >= 2: numbered, size in [9.9, 11.5)."""
    UNNUMBERED = ("references", "appendix", "acknowledg")
    out: list[dict] = []
    seen: set[str] = set()
    for pno in range(doc.page_count):
        d = doc[pno].get_text("dict")
        for blk in d.get("blocks", []):
            for line in blk.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = WS_RE.sub(" ", "".join(s.get("text", "") for s in spans)).strip()
                if not text or len(text) > 90 or text.lower() in seen:
                    continue
                size = max(s.get("size", 0) for s in spans)
                bold = all(
                    "TB" in (s.get("font") or "") or "Bold" in (s.get("font") or "")
                    for s in spans
                    if s.get("text", "").strip()
                )
                if not bold or size < 9.9 or text[0].isdigit() is False and not text.lower().startswith(UNNUMBERED):
                    continue
                if text[0].isdigit():
                    level = text.split()[0].count(".") + 1
                    if level > 1 and size >= 11.5:
                        continue  # numbered subsections are never section-size
                else:
                    if size < 11.5:
                        continue  # unnumbered majors must be section-size
                    level = 1
                seen.add(text.lower())
                out.append(
                    {
                        "level": level,
                        "text": text,
                        "pdf_page": pno + 1,
                        "trust": "B",
                        "source": "pdf_bold_span",
                    }
                )
    return out


def _grid_from_words(words: list[tuple]) -> list[list[str]]:
    """Cluster words into rows (y-centre) and cells (x-gap), snap to a
    global column grid, return the rectangular text grid."""
    rows: list[list[tuple]] = []
    for w in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        yc = (w[1] + w[3]) / 2
        if rows and abs(yc - (rows[-1][-1][1] + rows[-1][-1][3]) / 2) <= ROW_Y_TOL:
            rows[-1].append(w)
        else:
            rows.append([w])
    for r in rows:
        r.sort(key=lambda w: w[0])

    cell_rows: list[list[tuple[str, float]]] = []
    for r in rows:
        cells: list[tuple[str, float]] = []
        buf = [r[0]]
        for prev, cur in zip(r, r[1:]):
            if cur[0] - prev[2] >= CELL_X_GAP:
                cells.append((WS_RE.sub(" ", " ".join(x[4] for x in buf)).strip(), buf[0][0]))
                buf = [cur]
            else:
                buf.append(cur)
        cells.append((WS_RE.sub(" ", " ".join(x[4] for x in buf)).strip(), buf[0][0]))
        cell_rows.append(cells)

    xs = sorted(c[1] for r in cell_rows for c in r)
    col_starts: list[float] = []
    for x in xs:
        if not col_starts or x - col_starts[-1] > COL_SNAP:
            col_starts.append(x)
    grid: list[list[str]] = []
    for r in cell_rows:
        row = [""] * len(col_starts)
        for text, x0 in r:
            col = min(range(len(col_starts)), key=lambda i: abs(col_starts[i] - x0))
            row[col] = (row[col] + " " + text).strip() if row[col] else text
        grid.append(row)
    return grid


def _word_fonts(page) -> dict[tuple, list]:
    """Map word origin (x0,y0 rounded) -> font names, for glyph repair."""
    out: dict[tuple, list] = {}
    d = page.get_text("dict")
    for blk in d.get("blocks", []):
        for line in blk.get("lines", []):
            for s in line.get("spans", []):
                out.setdefault((round(s["bbox"][0], 2), round(s["bbox"][1], 2)), []).append(
                    s.get("font")
                )
    return out


def _looks_like_table_block(page, b) -> bool:
    """Heuristic: a text block whose lines contain >= 3 consecutive word
    gaps >= 10.5pt is a table body, not prose (measured on this corpus:
    prose gaps < 8pt, table column gaps >= 12pt)."""
    words = [
        w for w in page.get_text("words")
        if b[0] - 1 <= w[0] and w[2] <= b[2] + 1 and b[1] - 1 <= w[1] and w[3] <= b[3] + 1
    ]
    if len(words) < 4:
        return False
    rows: list[list[tuple]] = []
    for w in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        yc = (w[1] + w[3]) / 2
        if rows and abs(yc - (rows[-1][-1][1] + rows[-1][-1][3]) / 2) <= ROW_Y_TOL:
            rows[-1].append(w)
        else:
            rows.append([w])
    for r in rows:
        gaps = [cur[0] - prev[2] for prev, cur in zip(r, r[1:])]
        if sum(1 for g in gaps if g >= 10.5) >= 3:
            return True
    return False


def extract_table_grids(doc, tables: list[dict]) -> list[str]:
    """Geometric cell-grid reconstruction for each printed table (Tier B).

    Region = caption bottom .. next flush-left body/heading/caption block.
    Rows = y-clusters of words; cells = x-gap splits snapped to a global
    column grid. Borderless multi-level headers come out as plain rows --
    spans are NOT recovered (recorded in warnings; human lock required).
    """
    warnings: list[str] = []
    for t in tables:
        page = doc[t["src_page"] - 1]
        blocks = [b for b in page.get_text("blocks") if b[6] == 0]
        cap_x0, _, cap_x1, _ = t["src_bbox"]
        # column band: tables live in the caption's column (+ margin); this
        # excludes the neighbouring column on two-column pages
        x_lo, x_hi = cap_x0 - 25, cap_x1 + 25

        def in_band(w) -> bool:
            return x_lo <= w[0] and w[2] <= x_hi + 10

        # figure-style floats: caption BELOW table -> try region ABOVE first
        y_low_bound = 0.0
        y_high_bound = t["src_bbox"][1] - 2
        for b in sorted(blocks, key=lambda x: -x[3]):
            text = _block_text(b)
            if b[3] >= t["src_bbox"][1] - 2:
                continue
            flush_left = b[0] <= cap_x0 + 5
            is_marker = HEADING_TEXT_RE.match(text) or CAPTION_RE.match(text)
            tall_body = (b[3] - b[1] >= 25) and flush_left and not is_marker
            if tall_body and _looks_like_table_block(page, b):
                tall_body = False  # table body, not prose: keep extending
            if is_marker or tall_body:
                y_low_bound = b[3] + 2
                break
        words_above = [
            w for w in page.get_text("words")
            if y_low_bound < (w[1] + w[3]) / 2 < y_high_bound and in_band(w)
        ]
        # mainmatter style: caption ABOVE grid -> region below caption
        y_top = t["src_bbox"][3]
        y_bottom = page.rect.height
        for b in sorted(blocks, key=lambda x: x[1]):
            text = _block_text(b)
            if b[1] <= y_top + 2:
                continue
            flush_left = b[0] <= cap_x0 + 5
            is_marker = HEADING_TEXT_RE.match(text) or CAPTION_RE.match(text)
            tall_body = (b[3] - b[1] >= 20) and flush_left and not is_marker
            if tall_body and _looks_like_table_block(page, b):
                tall_body = False
            if is_marker or tall_body:
                y_bottom = b[1] - 2
                break
        words_below = [
            w for w in page.get_text("words")
            if y_top + 2 < (w[1] + w[3]) / 2 < y_bottom and in_band(w)
        ]
        words = words_above if len(words_above) >= len(words_below) else words_below
        region = "above" if words is words_above else "below"
        t["region"] = region

        if not words:
            warnings.append(f"Table {t['table_no']}: no words found near caption (p{t['src_page']})")
            t["cells"], t["header_rows"] = [], 0
            t["n_rows"] = t["n_cols"] = 0
            continue

        # Glyph repair: official arXiv PDFs may embed Dingbats without
        # ToUnicode; raw codes (0x13/0x17...) are mapped back to real
        # glyphs so the baseline keeps the paper's actual symbols.
        DINGBAT_FIX = {0x31: "\u2713", 0x32: "\u2714", 0x33: "\u2715",
                       0x34: "\u2716", 0x35: "\u2717", 0x36: "\u2718",
                       0x37: "\u2719", 0x38: "\u271a"}
        fonts_by_word = _word_fonts(page)
        repaired = []
        for w in words:
            fonts = fonts_by_word.get((round(w[0], 2), round(w[1], 2)), [])
            has_dingbats = any("dingbat" in (f or "").lower() for f in fonts if f)
            text = w[4]
            if has_dingbats:
                text = "".join(DINGBAT_FIX.get(ord(c), c) if ord(c) < 0x80 else c for c in text)
            repaired.append((w[0], w[1], w[2], w[3], text))

        # cluster words into rows (y-centre) and cells (x-gap), snap to
        # a global column grid
        grid = _grid_from_words(repaired)

        t["cells"] = grid
        t["header_rows"] = 0  # spans unrecoverable from printed layer alone
        t["n_rows"] = len(grid)
        t["n_cols"] = len(grid[0]) if grid else 0
        # caption content stays trust A- (top-level "trust"); the GRID is
        # geometric and only Tier B -- recorded separately so the diff
        # script can hard-fail caption mismatches while queueing grids.
        t["grid_trust"] = "B"
        t["grid_source"] = "pdf_word_geometry"
        if len(grid) < 2 or (grid and len(grid[0]) < 2):
            warnings.append(f"Table {t['table_no']}: degenerate grid (p{t['src_page']}); verify region manually")
        elif any(not any(c for c in r if c) for r in grid):
            warnings.append(f"Table {t['table_no']}: empty row inside grid (p{t['src_page']}); verify manually")
    return warnings


# ---------------------------------------------------------------------------
# Sample alignment (Tier B) + drawing clusters (Tier C)
# ---------------------------------------------------------------------------

def align_captions(doc, items: list[dict], no_key: str, kind: str) -> None:
    for item in items:
        prefix = f"{kind} {item[no_key]}:"
        found_page, bbox, score = None, None, 0.0
        for pno in range(doc.page_count):
            page = doc[pno]
            rects = page.search_for(prefix)
            if rects:
                r = rects[0]
                found_page, score = pno + 1, 1.0
                # expand to the containing text block: captions span multiple
                # lines and the grid region must start after the WHOLE caption
                for b in page.get_text("blocks"):
                    if b[6] == 0 and b[0] - 2 <= r.x0 and b[1] - 2 <= r.y0 and b[3] + 2 >= r.y1 and b[2] + 2 >= r.x1:
                        bbox = [round(v, 2) for v in b[:4]]
                        break
                if bbox is None:
                    bbox = [round(v, 2) for v in (r.x0, r.y0, r.x1, r.y1)]
                break
        align = item.setdefault("align", {})
        align["pdf_page"] = found_page
        align["match_score"] = score
        if bbox:
            align["bbox"] = bbox
        if item.get("trust") == "A" and item.get("source") == "official_pdf_textlayer":
            # Content stays Tier A- (verbatim printed caption from the
            # official PDF); only the sample PAGE/BBOX alignment is Tier B.
            # Keep trust=A (content) and record alignment trust separately.
            item["align"]["trust"] = "B"


def cluster_drawings(page, min_items: int = 20, min_area: float = 9000.0) -> list[list[float]]:
    """Tier C: union-find clustering of vector drawing rects (advisory)."""
    try:
        rects = [d["rect"] for d in page.get_drawings()]
    except Exception:
        return []
    rects = [r for r in rects if r.width > 0.5 and r.height > 0.5]
    if len(rects) < min_items:
        return []
    n = len(rects)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            a, b = rects[i], rects[j]
            gap_x = max(a.x0 - b.x1, b.x0 - a.x1, 0)
            gap_y = max(a.y0 - b.y1, b.y0 - a.y1, 0)
            if gap_x < 12 and gap_y < 12:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[ri] = rj
    groups: dict[int, list] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(rects[i])
    out = []
    for members in groups.values():
        if len(members) < min_items:
            continue
        x0 = min(r.x0 for r in members)
        y0 = min(r.y0 for r in members)
        x1 = max(r.x1 for r in members)
        y1 = max(r.y1 for r in members)
        if (x1 - x0) * (y1 - y0) >= min_area:
            out.append([round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)])
    out.sort(key=lambda b: (b[1], b[0]))
    return out


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build(pdf: Path, arxiv_id: str, version: str, slug: str, source: str, out_dir: Path, cache_dir: Path) -> Path:
    import fitz  # local workspace Python only; Cloud does not need this script

    if source == "html":
        html = fetch_arxiv_html(arxiv_id, version, cache_dir)
        tables, figures, sections, warnings = parse_html_source(html)
        prov_source = {"arxiv_html_url": f"https://arxiv.org/html/{arxiv_id}{version}"}
    else:
        official_pdf, official_sha = fetch_official_pdf(arxiv_id, version, cache_dir)
        odoc = fitz.open(official_pdf)
        tables, figures = extract_printed_captions(odoc)
        sections = extract_printed_sections(odoc)
        odoc.close()
        prov_source = {
            "official_pdf_url": f"https://arxiv.org/pdf/{arxiv_id}{version}",
            "official_pdf_sha256": official_sha,
            "html_twin_available": False,
        }
        warnings = []

    doc = fitz.open(pdf)
    align_captions(doc, tables, "table_no", "Table")
    align_captions(doc, figures, "fig_no", "Figure")

    if source == "official-pdf":
        # Rebuild table grids on the SAMPLE (not the official PDF):
        # - the sample is the pinned parsing target;
        # - official arXiv PDFs may embed Dingbats WITHOUT ToUnicode, which
        #   get_text() drops entirely (verified on 2312.00752v1: glyphs
        #   vanish from words), while the sample's ToUnicode is intact.
        # Sections likewise get sample pages via heading re-scan; official
        # pages stay in src_page for cross-checking.
        for t in tables:
            if t.get("align", {}).get("pdf_page") is None:
                t["cells"], t["n_rows"], t["n_cols"] = [], 0, 0
                t["header_rows"] = 0
                warnings.append(f"Table {t['table_no']}: not found in sample; caption-only entry")
                continue
            page = doc[t["align"]["pdf_page"] - 1]
            cap_bbox = t["align"].get("bbox")
            if not cap_bbox:
                t["cells"], t["n_rows"], t["n_cols"] = [], 0, 0
                t["header_rows"] = 0
                continue
            t["src_bbox"] = cap_bbox
            t["src_page"] = t["align"]["pdf_page"]
        warnings.extend(extract_table_grids(doc, tables))
        sample_sections = extract_printed_sections(doc)
        if sample_sections:
            sections = sample_sections
        warnings.append(
            "PDF-only arXiv submission: table grids are geometric reconstructions "
            "on the SAMPLE printed layer (Tier B); multi-level header spans are NOT "
            "recovered; human lock required before first scored diff."
        )

    figure_regions = []
    for pno in range(doc.page_count):
        for bbox in cluster_drawings(doc[pno]):
            figure_regions.append(
                {"pdf_page": pno + 1, "bbox": bbox, "trust": "C", "source": "drawing_cluster"}
            )

    baseline = {
        "schema": "docuvision.gt/1.0",
        "provenance": {
            "arxiv_id": arxiv_id,
            "arxiv_version": version,
            "pdf_file": pdf.name,
            "pdf_sha256": sha256_file(pdf),
            "pdf_pages": doc.page_count,
            "generated": time.strftime("%Y-%m-%d"),
            "generator": "test_data/scripts/gt_build_arxiv.py",
            **prov_source,
            "notes": [
                "Tier A: verbatim authoring source (arXiv HTML).",
                "Tier A- (stored as A, source=official_pdf_textlayer): verbatim",
                "  printed caption text from the official arXiv PDF -- deterministic",
                "  pdfTeX text layer, no OCR; still spot-check once.",
                "Tier B: page/bbox alignment on the sample, or geometrically",
                "  reconstructed table grids -- MUST be human-locked on first use.",
                "Tier C: drawing-cluster heuristics -- advisory only.",
                "Body paragraph text is NOT stored; printed truth is read live",
                "from the sample PDF text layer at diff time.",
            ],
        },
        "tables": tables,
        "figures": figures,
        "sections": sections,
        "figure_regions": figure_regions,
        "build_warnings": warnings,
    }
    doc.close()

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{slug}.gt.json"
    out_file.write_text(json.dumps(baseline, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"[ok] {out_file}: tables={len(tables)} figures={len(figures)} "
        f"sections={len(sections)} figure_regions={len(figure_regions)} warnings={len(warnings)}"
    )
    for w in warnings[:12]:
        print(f"     warn: {w}")
    return out_file


def main() -> int:
    ap = argparse.ArgumentParser(description="Build arXiv paper GT baseline JSON")
    ap.add_argument("--pdf", required=True, type=Path, help="local sample PDF")
    ap.add_argument("--arxiv", required=True, help="arXiv id, e.g. 2312.00752")
    ap.add_argument("--version", required=True, help="arXiv version tag to pin (e.g. v1)")
    ap.add_argument("--slug", default=None, help="baseline filename slug (default: pdf stem)")
    ap.add_argument("--source", choices=["html", "official-pdf"], default="html",
                    help="html: arXiv HTML twin (Tier A). official-pdf: printed layer of the "
                         "official arXiv PDF for papers without HTML (Tier A-/B).")
    ap.add_argument("--out-dir", default=DEFAULT_GT_DIR, type=Path)
    ap.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR, type=Path)
    args = ap.parse_args()

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    slug = args.slug or args.pdf.stem
    build(args.pdf, args.arxiv, args.version, slug, args.source, args.out_dir, args.cache_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# GT baselines for PDF_Parsing test files

Ground-truth baselines used by `test_data/scripts/gt_diff_report.py` to score
DocuVision parsing results without manual cell-by-cell checking.

## Current baselines

| slug | sample | arXiv | version | source mode | generated |
|---|---|---|---|---|---|
| `03_mamba` | `../03_paper_arxiv-mamba_multicolumn_glyph-tables.pdf` | [2312.00752](https://arxiv.org/abs/2312.00752) | v1 | official-pdf | 2026-09-04 |

## 03_mamba provenance notes (read before trusting the data)

- The sample PDF **is arXiv v1**, NOT v2:
  - v1 printed layer: Tables 1-15, Figures 1-10 (verified; Table 11 on p29).
  - v2 HTML: Tables 1-7, Figures 1-18 — a major revision; the v2 HTML twin is
    **unusable** as GT for this sample (renumbered everything).
  - `https://arxiv.org/html/2312.00752v1` → 404 (no HTML conversion kept for
    v1); the v1 e-print is PDF-only (no LaTeX source available).
- Therefore the baseline uses the **official author-submitted v1 PDF printed
  layer** (`https://arxiv.org/pdf/2312.00752v1`, sha256 pinned in the JSON) as
  the closest thing to the authoring source.
- The sample PDF and the official v1 PDF have **different sha256** (37 vs 36
  pages — arXiv regenerates PDFs) but identical caption numbering; caption
  text is cross-verified between the two before it enters the baseline.
- The official v1 PDF embeds Dingbats **without ToUnicode** (✓/✗ drop out of
  `get_text()` there); the sample has a correct ToUnicode map. Table grids are
  therefore reconstructed on the **sample** printed layer so glyphs survive
  (T11: 23 ✓ / 18 ✗ verified).

## Trust tiers

| tier | meaning | action |
|---|---|---|
| A | verbatim authoring source (arXiv HTML) | mismatch vs engine ⇒ likely pipeline bug |
| A- (stored `A`, `source: official_pdf_textlayer`) | verbatim printed caption text from the official arXiv PDF | deterministic text layer, no OCR; spot-check once |
| B | page/bbox alignment on the sample, or geometrically reconstructed table grids | **human-lock on first use** |
| C | drawing-cluster figure regions (advisory) | human queue, never a hard failure |

All 15 table grids in `03_mamba` are Tier B (`pdf_word_geometry`): built from
sample word geometry; multi-level header **spans are not recovered** and
merged-cell columns can fuse (e.g. T11 dense numeric columns share a cell
when intra-cell word gaps reach the split threshold). Before the first
scored diff, eyeball each grid once against the PDF (see build_warnings
inside the JSON).

## Regenerate / reuse for another paper

```bash
# this file (v1, PDF-only submission):
D:\USERS\livez\Python\python.exe test_data\scripts\gt_build_arxiv.py `
  --pdf test_data\testfiles\PDF_Parsing\03_paper_arxiv-mamba_multicolumn_glyph-tables.pdf `
  --arxiv 2312.00752 --version v1 --slug 03_mamba --source official-pdf

# a paper WITH an arXiv HTML twin (Tier A cells):
D:\USERS\livez\Python\python.exe test_data\scripts\gt_build_arxiv.py `
  --pdf <sample.pdf> --arxiv <id> --version <vN> --slug <slug> --source html
```

Pre-flight check for `--source html`: compare Figure/Table caption numbering
between the HTML and the sample PDF; a major revision renumbers everything
and silently invalidates the baseline. The script pins `pdf_sha256` +
`arxiv_version` + source URL/sha into `provenance`; the diff script refuses
mismatched PDFs.

Applicable document types (see script docstring for the full contract):
born-digital arXiv-style PDFs OK (html or official-pdf mode); non-arXiv
born-digital DEGRADED (Tier-C + recall only); scanned/image-only NOT
APPLICABLE (text layer is OCR output, not truth).

## Human queue (open items in 03_mamba.gt.json)

- Table 9 (p17): caption float separated from the table body by interleaved
  body text → grid left empty, caption-only entry. Fill manually if T9 needs
  scoring.
- All Tier B grids need a one-time eyeball lock before first scored diff.

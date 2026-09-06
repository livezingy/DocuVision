# Trial sample pack (GLM trial P0-3)

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

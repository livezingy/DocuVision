# Architecture media

## Pro (in repo)

- `docuvision-ui.png` — hero screenshot for the root README.
- `DocVision_table.gif`, `DocVision_receipt.gif`, `DocVision_Invoice.gif` — recorded UI walkthroughs for the README **Examples** section (Layout + KIE paths).

### v1.4 (record before tag; link from README)

| File | Scenario | Duration | Key frames |
|------|----------|----------|------------|
| `M1_pro_map_bank_statement.gif` | Table mapping — bank statement | 25–35s | Upload → Options **Table mapping** → Template **Bank statement** → Run → **Mapped rows** → Result JSON |
| `M2_pro_map_invoice_line_items.gif` | Table mapping — invoice lines | 20–30s | Same with `invoice_line_items_sample.pdf` |
| `M3_pro_batch_mapped_excel.gif` | Batch MappedRows XLSX | 30–40s | Batch tab → 3 PDFs → Excel → **MappedRows** sheet |

Recording checklist (Pro): resolution 1280×720; Cloud GPU or CPU for table mapping; sample `test_data/testfiles/GeneralFiles/bank_statement_sample.pdf`; `DEBUG=false python run.py`; ffmpeg target **under 5 MB**. Do **not** imply HITL reviews table-mapping rows.

**API preflight (before recording)** — auto-detects Tencent Cloud Studio / Baidu AI Studio:

```bash
cd ~/DocuVision && bash test_data/scripts/run_m1_table_mapping_acceptance.sh
# Tencent: cd /workspace/DocuVision && bash test_data/scripts/run_m1_table_mapping_acceptance.sh
# Non-standard path: export DOCUVISION_ROOT=/path/to/DocuVision
```

Pass = `MAP-TEMPLATE-001 pass` + `M1 acceptance PASSED` (artifacts under `test_data/TestResult/PhaseV14/M1/`).

After adding GIFs, update root [README.md](../../README.md) **Examples** and [RELEASE_1.4_NOTES.md](../release/RELEASE_1.4_NOTES.md) post-release row.

## Lite (record locally; add to repo when ready)

Target files for Release 1.0.1+ marketing (not yet committed):

| File | Scenario | Duration | Key frames |
|------|----------|----------|------------|
| `DocVision_Lite_table.gif` | Born-digital PDF with bordered table | 20–30s | Upload → Profile (`bordered`) → Run Analysis → Content/Tables → Export JSON |
| `DocVision_Lite_ocr.gif` | Scan/image OCR | 15–25s | Upload PNG → Analysis Options (no Tables) → Run Analysis → Content/Text → Quality hint |

### Recording checklist

- Resolution: 1280×720 (or 1440w); browser zoom 100%; hide bookmarks bar.
- Environment: Cloud Studio CPU; `cd apps/lite/backend && python run_lite.py`; open `http://{host}:8001/lite/lite.html`.
- Samples: `apps/lite/backend/tests/fixtures/sample_bordered.pdf`; OCR from `test_data/testfiles/images/scanned/` (no PII).
- Tooling: OBS → MP4 → ffmpeg or ScreenToGif; target **under 5 MB** (10–15 fps, width 960 if needed).
- On-screen title (optional): **Self-hosted · CPU · No cloud API keys**.
- Do **not** show: raster Transformer tables, Fields tab (Lite has no KIE).
- End card: status bar with `processing_ms` and engine (`easyocr` / `pdfplumber`).

### ffmpeg example (after OBS export)

```bash
ffmpeg -i lite_table.mp4 -vf "fps=12,scale=960:-1:flags=lanczos" -loop 0 DocVision_Lite_table.gif
```

After adding GIFs, link them from the root [README.md](../../README.md) **Lite** subsection.

# Architecture media

> Marketing GIF plan for **v1.5.0**. Root [README.md](../../README.md) **Examples** links committed files only; pending rows stay commented there until recorded.

## Status overview

| ID | File | Scenario | Status |
|----|------|----------|--------|
| G1 | `DocVision_table.gif` | Layout → Tables | **In repo** (README) |
| G2 | `DocVision_receipt.gif` | Receipt KIE → Fields | **In repo** (README) |
| G3 | `DocVision_Invoice.gif` | Invoice KIE → Fields | **In repo** (README) |
| G4 | `DocVision_Lite.gif` | Lite CPU table / OCR | **In repo** (README) |
| G5 | `M1_pro_map_bank_statement.gif` | Table mapping — bank statement | **Pending record** |
| G6 | `M2_pro_map_invoice_line_items.gif` | Table mapping — invoice lines | **Pending record** |
| G7 | `M3_pro_batch_mapped_excel.gif` | Batch MappedRows XLSX | **Pending record** |
| G8 | `M4_pro_hitl_review.gif` | HITL Reviews edit → Save → Approve | **Pending record** |
| G9 | `M5_pro_pdf_tools_merge.gif` | PDF Tools merge | Optional (P2) |

Also in repo: `docuvision-ui.png` — hero screenshot for the root README.

Do **not** record: Settings (disabled), Transactions / Mapped demo tabs (feature flags off), searchable PDF API (`501`).

---

## Pro — in repo (G1–G3)

| File | Scenario | Notes |
|------|----------|-------|
| `DocVision_table.gif` | Layout analysis + tables | Existing walkthrough |
| `DocVision_receipt.gif` | Receipt KIE | Prefer &lt;5 MB if re-encoded |
| `DocVision_Invoice.gif` | Invoice KIE | Prefer &lt;5 MB if re-encoded |

---

## Pro — pending record (G5–G8, optional G9)

| File | Scenario | Duration | Key frames |
|------|----------|----------|------------|
| `M1_pro_map_bank_statement.gif` | Table mapping — bank statement | 25–35s | Upload → eligibility *Ready for table mapping* → Options **Table mapping** → Template **Bank statement** → Run → **Mapped rows** → Result JSON |
| `M2_pro_map_invoice_line_items.gif` | Table mapping — invoice lines | 20–30s | Same with `invoice_line_items_sample.pdf` / Template **Invoice line items** |
| `M3_pro_batch_mapped_excel.gif` | Batch MappedRows XLSX | 30–40s | Batch tab → 3 PDFs (`mapped_bank_statement_3`) → Start → **Download Excel** → **MappedRows** sheet |
| `M4_pro_hitl_review.gif` | HITL Reviews | 25–35s | Reviews tab → edit field → **Save fields** → **Approve** → confirm updated fields (optional subtitle: queue survives restart, v1.5 SQLite) |
| `M5_pro_pdf_tools_merge.gif` | PDF Tools merge | 15–25s | PDF Tools → select ≥2 PDFs → **Merge & Download** → open merged file |

### Recording checklist (Pro)

- Resolution 1280×720; browser zoom 100%; hide bookmarks bar.
- `DEBUG=false python run.py` from `backend/`; for KIE/HITL set `DOCUVISION_KIE_WARMUP=1` and wait until `/health` reports KIE ready.
- Samples: `test_data/testfiles/GeneralFiles/bank_statement_sample.pdf`; `test_data/testfiles/invoices/invoice_line_items_sample.pdf`.
- ffmpeg target **under 5 MB** (10–15 fps, width 960 if needed).
- Do **not** imply HITL reviews table-mapping rows (table mapping path does not enqueue HITL).

### API preflight (before G5–G7)

```bash
cd ~/DocuVision && bash test_data/scripts/run_m1_table_mapping_acceptance.sh
# Tencent: cd /workspace/DocuVision && bash test_data/scripts/run_m1_table_mapping_acceptance.sh
# Non-standard path: export DOCUVISION_ROOT=/path/to/DocuVision

pwsh -File test_data/scripts/run_batch_mapped_acceptance.ps1
```

Pass = `MAP-TEMPLATE-001 pass` + `M1 acceptance PASSED` + `MAPPED-BATCH-001` (artifacts under `test_data/TestResult/`).

### After recording

1. Copy GIFs into this directory.
2. Uncomment the matching image lines in root [README.md](../../README.md) **Examples**.
3. Flip the Status column above from **Pending record** → **In repo**.
4. Optional: note in [RELEASE_1.5_NOTES.md](../../release/RELEASE_1.5_NOTES.md) or next patch notes that marketing media landed.

---

## Lite (G4 in repo; split variants optional)

| File | Scenario | Status |
|------|----------|--------|
| `DocVision_Lite.gif` | Combined Lite table / OCR walkthrough | **In repo** |
| `DocVision_Lite_table.gif` | Born-digital bordered table only | Optional re-record |
| `DocVision_Lite_ocr.gif` | Scan/image OCR only | Optional re-record |

### Recording checklist (Lite split, if needed)

- Environment: `cd apps/lite/backend && python run_lite.py`; open `http://{host}:8001/lite/lite.html`.
- Samples: `apps/lite/backend/tests/fixtures/sample_bordered.pdf`; OCR from `test_data/testfiles/images/scanned/` (no PII).
- Do **not** show: raster Transformer tables, Fields tab (Lite has no KIE).
- End card: status bar with `processing_ms` and engine (`easyocr` / `pdfplumber`).

### ffmpeg example

```bash
ffmpeg -i lite_table.mp4 -vf "fps=12,scale=960:-1:flags=lanczos" -loop 0 DocVision_Lite_table.gif
```

---

## README hang-link snippet (copy after files exist)

```markdown
**Table mapping — bank statement**

![Table mapping bank statement](docs/architecture/media/M1_pro_map_bank_statement.gif)

**Table mapping — invoice line items**

![Table mapping invoice line items](docs/architecture/media/M2_pro_map_invoice_line_items.gif)

**Batch → Excel MappedRows**

![Batch MappedRows Excel](docs/architecture/media/M3_pro_batch_mapped_excel.gif)

**HITL Reviews**

![HITL review edit and approve](docs/architecture/media/M4_pro_hitl_review.gif)

**PDF Tools — merge** (optional)

![PDF Tools merge](docs/architecture/media/M5_pro_pdf_tools_merge.gif)
```

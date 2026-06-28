# DocuVision 30-Minute Trial Demo Guide

Dual-track demo: **Lite (CPU tables)** + **Pro (GPU KIE)** for financial PDF pipeline prospects.

## Prerequisites

| Track | Port | Start command | Requirements |
|-------|------|---------------|--------------|
| **Lite** | 8001 | `cd apps/lite/backend && python run_lite.py` | pdfplumber, camelot, PyMuPDF; optional EasyOCR/Tesseract for scan PDFs |
| **Pro** | 8000 | `cd backend && python run.py` | GPU recommended; set `DOCUVISION_KIE_WARMUP=1` in `.env` |

### Warmup (Pro — avoid live cold start)

```bash
# In backend/.env
DOCUVISION_KIE_WARMUP=1
```

Wait until `/health` reports KIE ready before the trial call.

## Demo URLs

| UI | URL |
|----|-----|
| Lite | http://127.0.0.1:8001/lite/lite.html |
| Pro | http://127.0.0.1:8000/ (serve `frontend/index.html` or static mount) |
| Validation dashboard (Lite PoC) | http://127.0.0.1:8001/lite/validation.html |
| Lite API docs | http://127.0.0.1:8001/docs |

## Recommended sample PDFs

| Track | Sample | Location / notes |
|-------|--------|------------------|
| Lite (bordered table) | `sample_bordered.pdf` | `apps/lite/backend/tests/fixtures/sample_bordered.pdf` |
| Lite (second vendor) | Any born-digital statement/ledger PDF | Bring 1–2 client samples |
| Pro (invoice) | Invoice PDF | `test_data/testfiles/invoices/` (place per acceptance guide) |
| Pro (receipt) | Receipt PDF | `test_data/testfiles/receipts/` |

Pre-run each sample once and note `processing_ms` before the live session.

## 30-minute script

1. **Lite (5 min)** — Upload born-digital PDF → 右栏 **Profile** Tab（自动切换）→ Run Analysis → **Tables** + **Quality** panel → Export CSV/JSON。
2. **Pro (15 min)** — Upload invoice/receipt → Analysis Options → **Invoice** or **Receipt** mode → **Fields** + Result JSON → **Export** (real API).
3. **Persistence (10 min)** — **Save to validation** → open `validation.html`.

## Unified schema demo (v1.4 trial — T2/T3 / ETL)

**Story**: Multiple vendor PDFs → same four-column schema → Batch Excel **MappedRows** sheet.

### Single-file golden paths (Pro)

| Template | Sample | Analysis Options |
|----------|--------|------------------|
| `bank_statement` | `test_data/testfiles/GeneralFiles/bank_statement_sample.pdf` | Processing → **Table mapping** → Template **Bank statement** → Run Analysis |
| `invoice_line_items` | `test_data/testfiles/invoices/invoice_line_items_sample.pdf` | Same with Template **Invoice line items** |

Upload triggers document profile pre-scan; eligibility hint shows *Ready for table mapping* on digital PDFs. Scanned PDFs/images are blocked in v1.4 (use **Layout Analysis**).

After Run Analysis → **Content → Mapped rows** tab shows unified columns (not raw table headers).

### Batch demo (MAPPED-BATCH-001)

```powershell
pwsh -File test_data/scripts/run_batch_mapped_acceptance.ps1
```

Manifest set: `mapped_bank_statement_3` (3 PDFs, `table_template=bank_statement`). Open exported `.xlsx` → **MappedRows** sheet.

**Deferred** (post-trial): custom alias API, debit/credit split columns, deep stitch integration.

## Supabase PoC (post-trial / Assessment)

1. Create Supabase project; run [`supabase/migrations/001_trial_schema.sql`](../../supabase/migrations/001_trial_schema.sql).
2. Set in `apps/lite/backend/.env`:

```env
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
```

3. Without credentials, persistence falls back to `data/demo_validation/*.json` (still works for demo).

## Quick health checks

```bash
curl http://127.0.0.1:8001/api/v1/lite/health
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8001/api/v1/lite/demo/supabase/status
```

## Windows one-liner (Lite)

```powershell
cd d:\3_PROJECTS\DocuVision\apps\lite\backend; python run_lite.py
```

# DocuVision 30-Minute Trial Demo Guide

Single-track demo: **Pro (GPU KIE)** for financial PDF pipeline prospects.

> **Lite 已随 v1.8 退役**（`apps/lite/**` 已删除，`CHANGELOG.md` §v1.8）。本文档只描述 Pro 轨。

## Prerequisites

| Port | Start command | Requirements |
|------|---------------|--------------|
| 8000 | `cd backend && python run.py` | GPU recommended; set `DOCUVISION_KIE_WARMUP=1` in `.env` |

### Warmup (avoid live cold start)

```bash
# In backend/.env
DOCUVISION_KIE_WARMUP=1
```

Wait until `/health` reports KIE ready before the trial call.

## Demo URLs

| UI | URL |
|----|-----|
| Pro | http://127.0.0.1:8000/ (serve `frontend/index.html` or static mount) |

## Recommended sample PDFs

| Sample | Location / notes |
|--------|------------------|
| Invoice | `test_data/testfiles/invoices/` (place per acceptance guide) |
| Receipt | `test_data/testfiles/receipts/` |

Pre-run each sample once and note `processing_ms` before the live session.

## 30-minute script

1. **KIE (20 min)** — Upload invoice/receipt → Analysis Options → **Invoice** or **Receipt** mode → **Fields** + Result JSON → **Export** (real API).
2. **Table mapping (10 min)** — Upload the bank statement sample → Processing **Table mapping** → **Mapped rows** (details in §Unified schema demo).

## Unified schema demo (v1.4 trial — T2/T3 / ETL)

**Story**: Multiple vendor PDFs → same four-column schema → Batch Excel **MappedRows** sheet.

### Single-file golden paths

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

## Quick health checks

```bash
curl http://127.0.0.1:8000/api/v1/health
```

## Windows one-liner

```powershell
cd backend; python run.py
```

## Quality evidence

For a worked example of how pipeline changes are measured before/after — a silent
coordinate bug found by measurement, fixed, and locked by contract tests — see
[QUALITY_CASE_STUDY.md](QUALITY_CASE_STUDY.md).

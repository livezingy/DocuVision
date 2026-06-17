# Release 1.3.0 — PDF Core Routing + IDP Validation (Roadmap P0)

**Date:** 2026-06-17  
**Tag:** `v1.3.0`  
**Baseline:** `v1.2.1` (includes v1.2.x maintenance on the same commit)

## Highlights

### PDF track (P0-A / C / D)

- Pro **born-digital PDF** routes to `docuvision-core.TableProcessor` (Lite-equivalent Smart path).
- **Cross-page table stitch** MVP (`table_stitch.py`); PyMuPDF `find_tables` fallback.
- **Lite Batch API**: `POST /api/v1/lite/batch` (table-only PDF) + `export.csv` / `export.xlsx`.
- `document_info.detected_file_type` on Pro analyze results.

### IDP track (P0-E / F)

- **KIE field validation** (`kie_validation`, date/currency/regex); batch CSV validation columns.
- **Custom templates**: `bank_statement`, `invoice_line_items`; `/api/v1/kie/templates`.
- `document_type=custom` supported in query-fields allowlist.

### v1.4 / v1.5 MVP APIs (stub or heuristic)

- `/api/v1/classify`, `/document/profile`, HITL reviews, webhooks, PDF tools (merge/split/metadata/searchable/form-fill).

## Dependencies

Pro GPU env after pull:

```bash
cd backend
pip install -r requirements.txt   # includes -e ../packages/docuvision-core[lite], pdfplumber, pymupdf
```

## Cloud acceptance

Full gate: [MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md).

Minimum: Phase A **45+** pass, H-Batch regression, **CORE-PDF-001**, **LITE-BATCH-001**, **BATCH-XLSX-001**.

## Upgrade

- `APP_VERSION` / `/health` `api_version` → `1.3.0`; restart `python run.py` and Lite `run_lite.py`.
- Re-run [CLOUD_VALIDATION.md](../architecture/CLOUD_VALIDATION.md) Phase A + v1.3 sections.

## Known MVP limits

- HITL / webhooks / PDF tools: in-memory or heuristic; not production workflow engine.
- Custom schema: YAML templates + runtime save; not full UI template editor.
- Stitch: header-match only; no complex bank-statement column mapping yet (v1.4 P1-1).

See [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md).

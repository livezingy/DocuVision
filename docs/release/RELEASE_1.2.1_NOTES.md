# Release 1.2.1 — Batch Excel + UI E2E + Shared Shell PR2

**Date:** 2026-06-17  
**Tag:** `v1.2.1`  
**Baseline:** `v1.2.0`

## Highlights

- **Batch Excel export**: `GET /api/v1/batch/{id}/export.xlsx?mode=all|kie|tables|summary`; Pro UI **Download Excel**.
- **Playwright E2E P0**: `frontend/tests/e2e/` (UI-S smoke + UI-Q queue/preview) with API mocks; reports under `test_data/TestResult/PhaseUI/`.
- **Shared UI Shell PR2**: Pro loads `shared/components.css` + `pro-only.css` (Export toolbar aligned with Lite).

## Cloud acceptance

See [MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md) — Phase A regression + **BATCH-XLSX-001** + optional Playwright on Cloud.

## Upgrade

- Pull `main` at tag `v1.2.1` (same commit as `v1.3.0` if co-released).
- Re-run Phase A + H-Batch regression; verify Batch Excel download in UI or curl.
- Pro `requirements.txt` adds `docuvision-core[lite]`, `pdfplumber`, `pymupdf` when upgrading to v1.3.0 on same tree.

## Not in this patch alone

Full v1.3 P0 (Pro core PDF routing, Lite batch, KIE validation) — see [RELEASE_1.3.0_NOTES.md](./RELEASE_1.3.0_NOTES.md).

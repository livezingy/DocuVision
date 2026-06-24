# Release 1.3.1 notes

**Tag**: `v1.3.1`  
**Date**: 2026-06-23  
**Train**: maintenance on v1.3.0 P0 baseline — scope trim + Lite preview hardening

## Summary

v1.3.1 removes unused Lite/Pro surface area introduced or planned in v1.3.0, replaces Lite client-side PDF rendering with a **server-side preview API** (aligned with Pro page-image flow), and fixes Pro Playwright E2E mocks after UI/API deletions.

## Removed

| Area | Detail |
|------|--------|
| Pro **Auto-detect** | Document-type auto UI and `/api/v1/classify` analyze shortcut removed; profile API remains for manual type selection. |
| Lite **Batch** | `POST /api/v1/lite/batch` and Batch UI tab removed. **Pro** batch at `/api/v1/batch` unchanged. |
| Lite **Table ROI** | Interactive table region UI removed; table extraction uses full-page / pipeline defaults. |
| Lite **pdf.js** | Browser CDN pdf.js removed; PDF preview uses backend PyMuPDF rasterization. |

## Added

- Lite preview API: `POST /api/v1/lite/preview`, `GET /api/v1/lite/preview/{id}/page-image/{n}`.
- Contract tests: `apps/lite/backend/tests/test_lite_preview.py`.
- Playwright: `frontend/tests/e2e/lite/lite-preview.e2e.js` (`LITE-PREVIEW-01`); CI via `npm run test:e2e:lite`.

## Changed

- `APP_VERSION` default **1.3.1**.
- Pro E2E mock server: `/health`, WebSocket, task routes for queue/options flows.
- Cloud merge gate: [MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md) (**LITE-BATCH-001 N/A**).

## Upgrade / migration

- **Lite integrators**: remove calls to `/api/v1/lite/batch`; use single-file analyze + export, or Pro batch for multi-file KIE.
- **Saved Lite sessions**: legacy `tableAreas` in session storage is ignored on restore (harmless).
- **Cloud validation**: run v1.3.1 checklist instead of LITE-BATCH section in v1.3.0 doc (v1.3.0 checklist remains frozen historical record).

## Verification minimum

| Layer | Command |
|-------|---------|
| Lite API | `cd apps/lite/backend && pytest tests/ -q` |
| Lite preview E2E | `cd frontend && npm run test:e2e:lite` |
| Pro UI | `cd frontend && npm run test:unit && npm run test:e2e` |
| Pro KIE contract | Phase A file set in [CLOUD_VALIDATION.md](../architecture/CLOUD_VALIDATION.md) |

Full gate: [MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md).

## Related (unchanged from v1.3.0)

- Pro pdf_digital → docuvision-core table path (**CORE-PDF-001**).
- KIE field validation (**KIE-VAL-001**).
- Table stitch MVP (**STITCH-001**).

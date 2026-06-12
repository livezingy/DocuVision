# Release 1.2.0 — Multipage KIE + Batch Processing UI

**Date:** 2026-06-12  
**Tag:** `v1.2.0`  
**Baseline:** `v1.1.0` (Pro KIE query fields on `main`)

## Highlights

- **`kie_pages`** (PDF): `1`, ranges, or `all` (max 5 pages). Per-page VL + document-level merge; `kie_fields_by_page` and `quality.kie_pages_*`.
- **Batch API**: full orchestrator pipeline; `GET /batch/{id}/export.csv` (`kie` / `summary` / `failures`) and `export.json`.
- **Pro UI**: **Batch Processing** tab — multi-file upload, progress, pause/resume/retry, CSV/JSON download. Options snapshot from Process tab Analysis Options.
- **Queue fixes**: run selected queue item first; multipage preview page count; layout + `kie_pages=all` on raster no longer 400.

## Cloud acceptance

Merge gate (2026-06-12): Phase A **37/37**, MP-002, H-Batch **6/6** `kie_production_hit`, layout batch, pause/resume, UI smoke — see [MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md) and [KIE_TEST_RUN_TRACKER.md](../architecture/KIE_TEST_RUN_TRACKER.md).

## Not in this release

- Batch Excel export; Lite batch API.
- Generic field validation engine; `document_type=custom`; field bbox overlay.
- Playwright UI E2E (planned in `test_data/AutoTest/PRO_UI_E2E_PLAN.md`).

## Upgrade

- Pull `main` at tag `v1.2.0` or merge `feature/batch-ui`.
- `APP_VERSION` / `/health` `api_version` → `1.2.0`; restart `python run.py` after deploy.
- Batch `options` must include `document_type` when KIE is enabled (not `auto`).
- Re-run [CLOUD_VALIDATION.md](../architecture/CLOUD_VALIDATION.md) Phase A + MP + H-Batch if you customize KIE or batch locally.

## Next (post-1.2)

Field validation (`feature/kie-field-validation`), Playwright E2E P0, optional MP 3p standalone — see [RELEASE_1.1_CHECKLIST.md](./RELEASE_1.1_CHECKLIST.md) §6.

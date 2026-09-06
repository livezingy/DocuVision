# Release 1.6.0 notes

**Tag**: `v1.6.0`
**Date**: 2026-09-06
**Train**: Figure/layout baseline + Pro artifact pack (Download ZIP)

> Frozen snapshot at tag `v1.6.0`. Do not edit after release.

## Summary

v1.6.0 is a SemVer **minor**. It ships figure crop export, layout-first PP-StructureV3 tables, caption binding, trial hardening, and a single-task **artifact pack** (`GET /api/v1/tasks/{id}/export/zip` + sidebar ZIP button) from `feature/v1.6-artifact-pack`.

See [v1.6-roadmap.md](../architecture/v1.6-roadmap.md).

## Already on the train (baseline)

- Figure crop export: `figure_step`, `result.figures` / `envelope.figures`, `GET /tasks/{id}/figures[/{figure_id}]`, `enable_figure_export`. Crops use detection boxes (no pad). Split-figure merge + false-merge veto. Caption binding (F3).
- Layout-first tables via PP-StructureV3; reading order from `block_order`; 23 layout classes; multi-level table headers (F1/F2/F4). Per-page layout timeout with bad-page skip.
- Table CSV/Excel: confidence banner, caption line, Excel-formula cell prefix (`=`/`+`/`@` / non-numeric `-`).
- Trial hardening: API-key middleware, CORS allowlist, `MAX_FILE_SIZE` enforced; GT diff; trial samples / ops scripts.

## Added (this tag)

- Pro single-task ZIP pack: `GET /api/v1/tasks/{id}/export/zip` (`include=tables,figures,json`, default `tables,figures`). `manifest.json` + `tables/` + `figures/` (merged crops under `figures/merged/`). Oversize → 413 (`MAX_PACK_BYTES` 256MB).
- Sidebar **ZIP** button in right-panel Export Results (same row as JSON / CSV / Markdown / Word).
- Tests: `backend/tests/test_pack_export_service.py` (local, no paddle). Cloud gate **PACK-ZIP-001**.

## Changed

- `APP_VERSION` default **1.6.0** (`GET /health` `api_version`). Restart `python run.py` after pull.

## Out of scope (v1.6)

- Lite ZIP / Lite figure crops
- Batch ZIP of all tasks
- Table-region screenshots, formula/seal image export
- Redis / multi-replica (still post-1.6)
- Searchable PDF, AcroForm, mail bridge (remain on [v1.5-roadmap.md](../architecture/v1.5-roadmap.md))
- Single-task `tasks` dict persistence (still in-memory; ZIP/figures 404 after restart)

## Verification (hard gate passed 2026-09-06)

| Layer | Status |
|-------|--------|
| Version identity | `APP_VERSION` = `1.6.0` |
| Local mock | `pytest backend/tests/test_pack_export_service.py` — **11 passed** |
| Cloud **PACK-ZIP-001** | passed (operator confirmed 2026-09-06) |
| Cloud gate | [MERGE_MAIN_v1.6_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.6_CLOUD_CHECKLIST.md) |

## Upgrade / migration

- Non-breaking additive train. Restart `python run.py` after pull so `/health` `api_version` is `1.6.0`.
- Trial auth still off unless `DOCUVISION_TRIAL_API_KEY` is set.

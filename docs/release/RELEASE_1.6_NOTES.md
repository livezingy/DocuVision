# Release 1.6.0 notes

**Tag**: `v1.6.0` (pending — train opened 2026-09-05, not tagged)
**Date opened**: 2026-09-05
**Train**: Figure/layout baseline (already on `fix/pp-structurev3-layout-first-tables-figures`) + Pro artifact pack (Download ZIP)

> This file is **in progress**, not a frozen release snapshot. Do not treat it as shipped until the tag exists.

## Summary

v1.6.0 is a SemVer **minor**. The baseline already on this train includes figure crop export, layout-first PP-StructureV3 tables, caption binding, and trial hardening. The remaining product increment is a single-task **artifact pack** (`GET /api/v1/tasks/{id}/export/zip` + sidebar ZIP button) developed on `feature/v1.6-artifact-pack`.

See [v1.6-roadmap.md](../architecture/v1.6-roadmap.md).

## Already on the train (baseline)

- Figure crop export: `figure_step`, `result.figures` / `envelope.figures`, `GET /tasks/{id}/figures[/{figure_id}]`, `enable_figure_export`. Crops use detection boxes (no pad). Split-figure merge + false-merge veto. Caption binding (F3).
- Layout-first tables via PP-StructureV3; reading order from `block_order`; 23 layout classes; multi-level table headers (F1/F2/F4). Per-page layout timeout with bad-page skip.
- Table CSV/Excel: confidence banner, caption line, Excel-formula cell prefix (`=`/`+`/`@` / non-numeric `-`).
- Trial hardening: API-key middleware, CORS allowlist, `MAX_FILE_SIZE` enforced; GT diff; trial samples / ops scripts.

## Planned (this tag, not in the open commit)

- Pro single-task ZIP pack of tables + figure PNGs + `manifest.json`.
- Sidebar **ZIP** button next to JSON / CSV / Markdown / Word.
- Local mock tests for the pack builder; Cloud gate **PACK-ZIP-001**.

## Changed

- `APP_VERSION` default **1.6.0** (`GET /health` `api_version`). Restart `python run.py` after pull.

## Out of scope (v1.6)

- Lite ZIP / Lite figure crops
- Batch ZIP of all tasks
- Table-region screenshots, formula/seal image export
- Redis / multi-replica (still post-1.6)
- Searchable PDF, AcroForm, mail bridge (remain on [v1.5-roadmap.md](../architecture/v1.5-roadmap.md))
- Git tag `v1.6.0` and GitHub Release — cut after ZIP lands and the Cloud gate passes

## Verification

| Layer | Status |
|-------|--------|
| Version identity | `APP_VERSION` = `1.6.0` |
| ZIP pack | pending `feature/v1.6-artifact-pack` |
| Cloud gate | [MERGE_MAIN_v1.6_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.6_CLOUD_CHECKLIST.md) |

## Upgrade / migration

- Non-breaking additive train. Integrators that parse `/health` `api_version` will see `1.6.0` before ZIP exists if they deploy the open commit.
- Trial auth still off unless `DOCUVISION_TRIAL_API_KEY` is set.

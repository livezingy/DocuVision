# Batch Processing UI — feature/batch-ui

> Delivered in **v1.2.0** on `main` (2026-06-12). See [CHANGELOG.md](../../CHANGELOG.md) `[1.2.0]` and [RELEASE_1.2_NOTES.md](../release/RELEASE_1.2_NOTES.md).

## Goal

Productize Pro batch API in the static SPA (`frontend/`): job list, progress, failure retry, aggregated CSV/Excel export.

## Backend (v1.2)

- Full pipeline via `run_single_file_pipeline` / `_batch_process_file`
- `GET /api/v1/batch/{id}/export.csv?mode=kie|summary|failures`
- `GET /api/v1/batch/{id}/export.json`
- Batch `options`: `enable_kie`, `kie_query_fields`, `kie_pages` (v1.1 + v1.2)

## MVP scope (shipped)

1. **Batch Processing** nav tab enabled (`frontend/index.html`, `app.js`).
2. Upload multiple files + `getProcessingOptions()` (layout/kie/query/kie_pages).
3. Poll batch status; per-file table with KIE hit / error.
4. Download CSV (KIE) and JSON bundle; retry failed + resume.
5. English UI copy only (`007-code-language.mdc`).

## Out of scope (this feature)

- Lite batch API
- Email/webhook integration
- New backend batch engine (use existing `batch_service`)

## References

- Pro batch curl/Python: [CLOUD_VALIDATION.md](./CLOUD_VALIDATION.md), root README
- Upwork ETL narrative: **local only, gitignored** — `test_data/TestResult/PLAN/` (`*Upwork*` files; never commit)

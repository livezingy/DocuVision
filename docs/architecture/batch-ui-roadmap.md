# Batch Processing UI — feature/batch-ui

> Branch: `feature/batch-ui` (from `main` @ v1.1.0)  
> Priority: P0 post-1.1 — see [RELEASE_1.1_CHECKLIST.md](../release/RELEASE_1.1_CHECKLIST.md) §6

## Goal

Productize Pro batch API in the static SPA (`frontend/`): job list, progress, failure retry, aggregated CSV/Excel export.

## Backend (existing)

- `POST /api/v1/batch`, `POST .../start`, `GET .../status`, `GET .../results`
- Batch `options` may include `kie_query_fields` (v1.1)

## MVP scope (draft)

1. Enable **Batch Processing** nav tab (replace disabled placeholder).
2. Upload multiple files + options mirror Analysis Options (layout/table/kie).
3. Poll batch status; per-file success/fail table.
4. Download merged results (CSV or JSON bundle).
5. English UI copy only (`007-code-language.mdc`).

## Out of scope (this feature)

- Lite batch API
- Email/webhook integration
- New backend batch engine (use existing `batch_service`)

## References

- Pro batch curl/Python: [CLOUD_VALIDATION.md](./CLOUD_VALIDATION.md), root README
- Upwork ETL narrative: local `test_data/TestResult/PLAN/` (gitignored)

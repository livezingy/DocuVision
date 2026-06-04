# Release 1.1.0 — Pro KIE query fields

**Date:** 2026-06-04  
**Tag:** `v1.1.0`  
**Baseline:** `v1.0.1` (Pro + Lite on `main`)

## Highlights

- **`kie_query_fields`**: extend built-in KIE YAML schema at runtime (Azure Query Fields style, max 20 fields, extend-only).
- **API**: `POST /api/v1/analyze`, `POST /api/v1/documents:analyze`, batch `options`.
- **Pro UI**: Analysis Options → Advanced → Additional KIE fields.
- **Quality**: `kie_query_fields_requested` / `kie_query_fields_filled` (query fill rate does **not** affect KIE-ACCEPT-002).

## Cloud acceptance

- Phase F: `testfiles/invoices/sample-invoice.png` with `CustomerName`, `OurReference` — 001/002 pass.
- See [KIE_TEST_RUN_TRACKER.md](../architecture/KIE_TEST_RUN_TRACKER.md) and [kie-custom-fields.md](../architecture/kie-custom-fields.md).

## Not in this release

- Full `document_type=custom`, template persistence, field bbox overlay.
- Batch Processing product UI, multi-page PDF KIE, generic validation engine.

## Upgrade

- Pull `main` at tag `v1.1.0` or merge PR from `feature/pro-v1.1-custom-fields`.
- No breaking change to fixed 5-type KIE without `kie_query_fields`.
- Re-run [CLOUD_VALIDATION.md](../architecture/CLOUD_VALIDATION.md) Phase A–F if you customize KIE prompts locally.

## Next (post-1.1)

See [RELEASE_1.1_CHECKLIST.md](./RELEASE_1.1_CHECKLIST.md) §6 — Batch UI, field validation, multi-page KIE.

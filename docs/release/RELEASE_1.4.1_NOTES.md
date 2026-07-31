# Release 1.4.1 notes

**Tag**: `v1.4.1`
**Date**: 2026-07-31
**Train**: maintenance patch on v1.4.0 — Lite `/extract/tables` parity + test constant drift fix

## Summary

v1.4.1 closes a Lite API parity gap: `POST /api/v1/lite/extract/tables` now accepts the same `table_template` parameter as `POST /extract/auto`, and fixes a pre-existing test-constant drift that was failing `lite-contract` CI on `main`.

## Added

- Lite `POST /api/v1/lite/extract/tables`: optional `table_template` Form param (`bank_statement` / `invoice_line_items`), forwarded to `extract_tables_from_pdf` (service layer already supported). Results return in `mapped_table_rows` + `table_template`. Non-breaking; all new params optional with legacy-matching defaults. See [lite-api.md §7.4](../architecture/lite-api.md).
- Contract test: `apps/lite/backend/tests/test_table_template_extract.py::test_extract_tables_passes_table_template_to_pipeline` (mocks pipeline, verifies passthrough + mapped rows).

## Fixed

- `apps/lite/backend/tests/test_lite_health.py`: `LITE_RESULT_TOP_KEYS` constant was missing `mapped_table_rows` and `table_template` (added to `LiteResult` schema in v1.4.0 but not reflected in the test constant), so `test_lite_result_schema_keys` asserted a 19-key set against a 21-key model. Test-only contract alignment; no schema change.

## Changed

- `APP_VERSION` default **1.4.1**.

## Verification (Cloud, hard gate passed 2026-07-31)

| Layer | Command | Result |
|-------|---------|--------|
| Lite contract | `pytest apps/lite/backend/tests/test_table_template_extract.py -v` | 3 passed |
| Lite live smoke | `curl -X POST :8001/api/v1/lite/extract/tables -F file=@bank_statement_sample.pdf -F mode=smart -F table_template=bank_statement` | HTTP 200; `table_template=bank_statement`; `mapped_table_rows` 4 rows |
| Lite contract (drift fix) | `pytest apps/lite/backend/tests/test_lite_health.py::test_lite_result_schema_keys` | passed |

Full v1.4.0 merge gate still applies: [MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md). v1.4.1 adds no new merge gate.

## Upgrade / migration

- None. Non-breaking additive param; integrators may optionally send `table_template` to `/extract/tables`.

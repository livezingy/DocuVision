# Main — Tracked Issues (post-merge baseline)

This document lists issues and short remediation notes to track on `main` after the recent merge baseline.

## High Priority
- KIE engine implementation
  - Description: `backend/app/services/kie_service.py` currently wraps a worker that returns placeholder/empty `fields`.
  - Impact: KIE API responses are non-functional for invoice/receipt/id extraction.
  - Suggested action: implement a real worker (cloud adapter or local inference) and integration tests.
  - Owner: TBD

- Verify KIE input source
  - Description: Ensure `kie_step()` consumes `preprocessed_image_path` (when available) rather than raw file for better OCR/layout alignment.
  - Acceptance: KIE worker receives `preprocessed_image_path` in at least one sample API call; end-to-end test validates non-empty `fields` for sample invoice.

## Medium Priority
- Orchestrator ordering confirmation
  - Description: Confirm pipeline ordering (KIE after table, before formula/chart) and add a regression test ensuring KIE runs in the expected position when `enable_kie=true`.
  - Acceptance: Unit test asserting that `kie_step` is invoked before `formula_step` for a sample task.

- Table fallback behaviour
  - Description: Validate `TABLE_ALLOW_FULLPAGE_FALLBACK` behavior and `table_service.extract_with_meta()` metadata correctness.
  - Acceptance: Tests cover both fallback disabled/enabled modes and verify `meta.fallback_activated` flags.

## Low Priority
- Documentation naming alignment
  - Description: Update design docs to use `envelope_builder` naming and reflect normalized `element['text']` fields.
  - Acceptance: Design docs and README match code references.

- Debug flags and production behavior
  - Description: Confirm `use_doc_unwarping=false` is acceptable for all pipelines or make it configurable per-request.
  - Acceptance: Config update or per-request toggle with documentation.

## Tests to Run
- `backend/tests/test_kie_*` (if present) and `backend/tests/test_table_strategy_meta.py`.
- Add sample fixture for an invoice/receipt and run `pytest tests/...` to validate KIE after implementation.

## Notes
- Branches created during baseline merge:
  - `merge/feature-main-followup-into-main` (merge artifact)
  - `feature/prioritize-kie` (new working branch)


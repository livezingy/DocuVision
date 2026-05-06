# feature/prioritize-kie — Plan & Acceptance Criteria

Goal: Implement and validate KIE (invoice/receipt/id_card) priority work while deferring formula/chart heavy tasks.

## Scope
- Implement a working KIE adaptor (worker) that extracts structured fields from invoices/receipts/IDs.
- Ensure KIE uses preprocessed images and layout outputs for robust field extraction.
- Move/instrument orchestrator so `kie_step` runs after `table_step` and before `formula/chart` steps.
- Add unit/integration tests and sample fixtures.

## Tasks
1. Implement KIE worker
   - Deliverable: `backend/app/services/kie_service.py` worker replaced with real adapter.
   - Acceptance: For sample invoice fixture `tests/fixtures/invoice_sample.json`, API returns non-empty `fields` matching expected keys (invoice_number, date, total) in at least 80% of test assertions.

2. KIE input stabilization
   - Deliverable: `kie_step()` accepts `preprocessed_image_path` when present; fallback to raw file otherwise.
   - Acceptance: Integration test asserts worker invoked with `preprocessed_image_path` for sample job.

3. Orchestrator ordering and lazy formula/chart init
   - Deliverable: Orchestrator updated in `document_pipeline_orchestrator.py` to run `kie_step` immediately after `table_step`. Formula and chart engines must be lazily initialized only when `enable_formula|enable_chart` are true.
   - Acceptance: Unit test verifies `kie_step` occurs before `formula_step` and `chart_step` when `enable_kie=true` and `enable_formula=false`.

4. Tests and CI
   - Deliverable: Add tests under `backend/tests/` covering KIE end-to-end happy path and failure modes.
   - Acceptance: `pytest` passes for new tests in CI environment (or locally using provided fixtures).

5. Documentation & PR
   - Deliverable: Update `docs/architecture/*` and include a PR description template highlighting risk areas and validation steps.
   - Acceptance: PR includes test results and a short migration note describing the orchestrator ordering change.

## Acceptance Criteria Summary
- KIE returns meaningful structured fields for sample invoices/receipts in automated tests.
- Orchestrator ordering guarantees KIE runs before formula/chart when prioritized.
- Table extraction meta flags are present and correct in outputs used by KIE.
- New tests added and pass locally/CI.


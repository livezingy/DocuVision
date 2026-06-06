# Batch KIE acceptance (Pro)

Requires batch pipeline to use full `DocumentPipelineOrchestrator` (KIE enabled).

| Rule ID | Check |
|---------|--------|
| **BATCH-001** | `kie_invoice_6` manifest: 6/6 tasks `completed` after `POST .../start` |
| **BATCH-002** | Each completed task: `result.quality.kie_production_hit == true` (invoice types) |
| **BATCH-003** | `GET /api/v1/batch/{id}/export.csv?mode=kie` returns header with `file_name`, `status`, `kie_production_hit` |
| **BATCH-004** | Failed tasks appear in `export.csv?mode=failures` or failure columns |

## Prerequisites

- Batch `options` JSON sent to `POST /api/v1/batch` **must** include `document_type` (e.g. `invoice`).  
  `auto` causes `kie_stage=skipped_doc_type` and `kie_production_hit=false` even when `enable_kie=true`.
- Manifest may declare `document_type` at set level **and** inside `options`; the acceptance script merges set-level into `options` before upload.

Manifest: `test_data/testfiles/batch/manifest.json`.  
Script: `test_data/scripts/run_batch_kie_acceptance.ps1` (outputs under `test_data/TestResult/PhaseBatch/`, gitignored; exits non-zero if BATCH-002 fails).

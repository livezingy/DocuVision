# Batch KIE acceptance (Pro)

Requires batch pipeline to use full `DocumentPipelineOrchestrator` (KIE enabled).

| Rule ID | Check |
|---------|--------|
| **BATCH-001** | `kie_invoice_6` manifest: 6/6 tasks `completed` after `POST .../start` |
| **BATCH-002** | Each completed task: `result.quality.kie_production_hit == true` (invoice types) |
| **BATCH-003** | `GET /api/v1/batch/{id}/export.csv?mode=kie` returns header with `file_name`, `status`, `kie_production_hit` |
| **BATCH-004** | Failed tasks appear in `export.csv?mode=failures` or failure columns |

Manifest: `test_data/testfiles/batch/manifest.json`.  
Script: `test_data/scripts/run_batch_kie_acceptance.ps1` (outputs under `test_data/TestResult/PhaseBatch/`, gitignored).

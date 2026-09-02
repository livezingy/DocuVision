# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added (GLM trial — `feat/glm-trial`)
- Trial hardening: API-key middleware (`DOCUVISION_TRIAL_API_KEY`, HTTP `X-API-Key` / WS `?key=`), configurable CORS allowlist (`DOCUVISION_CORS_ORIGINS`), enforced `MAX_FILE_SIZE` (413) on all four upload endpoints, frontend key bridge (`shared/trial-key.js`). See [TRIAL_REMOTE_60MIN.md](docs/demo/TRIAL_REMOTE_60MIN.md) §3 P0-1.
- Figure crop export + integrity checks: `figure_service.py`, pipeline `figure_step`, `result.figures` / `envelope.figures` + `quality.figure_*`, routes `GET /tasks/{id}/figures[/{figure_id}]`, option `enable_figure_export`. §3 P0-2.
- Trial sample generator (`scripts/trial/generate_trial_samples.py`): multi-column techdoc with merged-cell symbol table, flowchart and architecture diagram PDFs into `test_data/testfiles/trial/`.
- Ground-truth diff: `app/services/trial/gt_diff.py` (CLI + HTML report), routes `POST /api/v1/trial/gt-diff/{task_id}` + `GET .../report`. §3 P1-4.
- Symbol survival benchmark (`scripts/trial/symbol_benchmark.py`, GPU): PP-OCR vs Qwen2.5-VL. §3 P1-5.
- Trial ops scripts: `trial_preflight.py` (readiness gate), `trial_reset.py` (data wipe between prospects); `.GLM/` assistant rules.

### Fixed
- `MAX_FILE_SIZE` was configured but never enforced; now wired into `/ocr`, `/upload`, `/analyze`, `/documents:analyze`.

## [1.5.0] — 2026-08-05

### Added
- Pro Queue persistence (Batch + HITL): single-file SQLite (`backend/data/docuvision.sqlite`), `queue_store.py`, `BatchService` / `HitlReviewQueue` `load_from_db` + `_persist`, HITL `edited_fields` / `resolved_at`. See [RELEASE_1.5_NOTES.md](docs/release/RELEASE_1.5_NOTES.md) and [MERGE_MAIN_v1.5_CLOUD_CHECKLIST.md](test_data/acceptance/MERGE_MAIN_v1.5_CLOUD_CHECKLIST.md).

### Fixed
- `resume_batch` finalizes when no pending tasks remain after restart demotion (avoids stuck `PROCESSING`).

### Changed
- `APP_VERSION` default **1.5.0**; `hitl_queue.enqueue` / `resolve` are async.

## [1.4.1] — 2026-07-31

### Added
- Lite `POST /api/v1/lite/extract/tables` now accepts `table_template` (`bank_statement` / `invoice_line_items`), forwarding it to `extract_tables_from_pdf`; results return in `mapped_table_rows` + `table_template`. Parity with `POST /extract/auto` (non-breaking, optional param). See [lite-api.md §7.4](docs/architecture/lite-api.md).

### Fixed
- `apps/lite/backend/tests/test_lite_health.py`: `LITE_RESULT_TOP_KEYS` constant drifted from `LiteResult` schema (missing `mapped_table_rows`, `table_template` added in v1.4.0); `test_lite_result_schema_keys` now passes. Test-only contract alignment.

## [1.4.0] — 2026-06-30

Table mapping productization, HITL editable review, PDF Tools nav tab, batch mapped-row Excel export, and backend hardening (webhook auth/SSRF, Phase1 form parity, dead-config cleanup). See [RELEASE_1.4_NOTES.md](docs/release/RELEASE_1.4_NOTES.md) and [MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md](test_data/acceptance/MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md).

### Added

- Pro **Table mapping** processing mode: `processingMode=table_mapping` + `table_template` (`bank_statement`, `invoice_line_items`) → `mapped_table_rows` UI tab.
- Document profile **eligibility** hint on upload (`Ready for table mapping` for `pdf_digital`).
- Pro **Reviews** tab: editable KIE fields, Save (`PATCH /tasks/{id}/kie-fields`), Approve/Reject; **`hitl_policy`** profiles (`full` / `lite` / `off`).
- Pro **PDF Tools** tab: merge, split, metadata (UI); API stubs remain for searchable / form-fill.
- Batch manifest set **`mapped_bank_statement_3`**; XLSX **MappedRows** sheet; script `run_batch_mapped_acceptance.ps1` (**MAPPED-BATCH-001**).
- `POST /api/v1/documents:analyze` (Phase1 Job endpoint) now accepts the full Form parameter set previously only on legacy `POST /api/v1/analyze`: `enable_layout`/`enable_table`/`enable_formula`/`enable_seal`/`enable_kie`, `language`, `ocr_engine`/`layout_engine`/`table_engine`, `table_allow_fullpage_fallback`, formula thresholds (`formula_disable_layout`/`formula_disable_preprocess`/`formula_two_stage_threshold_retry`/`formula_primary_layout_threshold`/`formula_fallback_layout_threshold`/`formula_layout_threshold`/`pipeline_formula_batch_size`), `table_template`, `enable_hitl`. Defaults mirror legacy; `document_type=invoice/receipt/id_card` auto-enables KIE. Non-breaking (all new params optional with legacy-matching defaults).
- Contract tests: `test_table_template_analyze.py`, `test_hitl_policy.py`, `test_task_kie_fields_patch.py`, `test_pdf_tools_service.py`, `test_phase1_analyze_form.py`, `test_webhook_service.py`; core `test_table_column_mapping.py`, `test_table_result_mapper.py`.
- `accelerate` dependency for KIE `device_map=auto`; multi-cloud KIE model path discovery; `GET /api/v1/health` for AI Studio `api_serving`.

### Changed

- `APP_VERSION` default **1.4.0**; Phase A CI extended with v1.4 contract files.
- Table mapping routes born-digital PDF via `enable_layout=false` + docuvision-core TableProcessor (no KIE / no HITL enqueue on this path).
- `batch_export_service._task_kie_fields`: removed dead `quality` branch (`if isinstance(quality, dict): pass` had no effect).
- Debug artifact download endpoint (`GET /api/v1/jobs/{job_id}/debug/{filename}`): replaced `os.path.abspath(...).startswith(...)` with `Path.is_relative_to` to block sibling-directory traversal (e.g. `./debug2/...`).

### Security

- Webhook registration hardened (breaking). Two-layer gating:
  - `DOCUVISION_WEBHOOK_ENABLED` (default `false`): when disabled, `GET/POST /api/v1/webhooks` return `404` and `dispatch_event_async` returns `[]` (no outbound POST even for previously registered subscriptions).
  - `DOCUVISION_WEBHOOK_ADMIN_TOKEN`: when enabled, `GET/POST /api/v1/webhooks` require `X-DocuVision-Admin-Token` header to match. Fail-closed: empty configured token rejects registration with `401` (no open registration when enabled without a token).
- SSRF guard on webhook registration: URLs whose host resolves to private/loopback ranges (`127.0.0.0/8`, `10.0.0.0/8`, `169.254.0.0/16`, `192.168.0.0/16`, `172.16.0.0/12`, `::1`, `fc00::/7`, `fe80::/10`) are rejected with `400`. Does not defend against DNS rebinding (v1.5+ roadmap).

### Removed

- `enable_ocr` per-block OCR dead config removed from `ProcessingOptions`, `/api/v1/analyze` Form, frontend payload, and tests. Standalone `/api/v1/ocr` endpoint and `OCRService` are unchanged.
- `chart_step` and `enable_chart` removed from orchestrator pipeline and Pro UI. `ChartService` deleted (no remaining callers).
- `financial_report` document type removed from KIE registry, orchestrator allow-list, frontend `KIE_DOC_TYPES`, and docs. API callers passing `document_type=financial_report` now hit `unsupported_document_type` (breaking).
- `table_areas` ROI removed across Pro/Lite/core: orchestrator, `table_service`, `core_table_extractor`, Lite `/extract/auto` Form field, Lite `table_pipeline`, core `TableProcessor`/`CamelotExtractor` params, and dead methods `extract_camelot_lattice`/`extract_camelot_stream`. Lite `/extract/auto` no longer accepts `table_areas` (breaking API change).
- `POST /api/v1/pdf-tools/searchable` now returns `501 Not Implemented`. The previous `make_searchable_pdf` was a placeholder that inserted the supplied text into a fixed rectangle (not a real OCR text layer) and has been deleted. Searchable PDF remains on the v1.5+ roadmap (breaking).

### Fixed

- PDF Tools split page list coercion and file-selection hints.
- Pro tab typography; Quality panel gated on KIE-enabled runs.
- Queue reprocess prefers selected completed item; API probe fallback to `/engines` on AI Studio.

## [1.3.1] — 2026-06-23

Maintenance release: remove unused Lite/Pro UI scope, add Lite server-side PDF preview. See [RELEASE_1.3.1_NOTES.md](docs/release/RELEASE_1.3.1_NOTES.md) and [MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md](test_data/acceptance/MERGE_MAIN_v1.3.1_CLOUD_CHECKLIST.md).

### Added

- Lite **server-side preview** API (`POST /preview`, `GET .../page-image/{n}`) with PyMuPDF rasterization.
- Lite contract tests `test_lite_preview.py`; Playwright **LITE-PREVIEW-01** (`npm run test:e2e:lite`).

### Removed

- Pro **Auto-detect** UI and analyze classify shortcut.
- Lite **Batch API/UI** (`/api/v1/lite/batch`).
- Lite **Table ROI** UI; client-side **pdf.js** in Lite frontend.

### Changed

- `APP_VERSION` default **1.3.1**; Pro E2E mock routes extended for queue/options regression.
- Cloud merge gate v1.3.1 replaces **LITE-BATCH-001** with **LITE-PREVIEW-001**.

## [1.3.0] — 2026-06-17

Roadmap **P0** (PDF core routing + IDP validation + Lite batch). See [RELEASE_1.3.0_NOTES.md](docs/release/RELEASE_1.3.0_NOTES.md) and [MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md](test_data/acceptance/MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md).

### Added

- Pro **pdf_digital** → `docuvision-core` TableProcessor; **table stitch** MVP; PyMuPDF `find_tables` fallback.
- **KIE field validation** (`kie_validation`); batch CSV validation columns; custom templates API.
- Lite **Batch API** (`/api/v1/lite/batch`) with CSV/XLSX export.
- Pro MVP APIs: classify, document profile, HITL, webhooks, PDF tools.
- Cloud checklist [MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md](test_data/acceptance/MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md).

### Changed

- `APP_VERSION` default `1.3.0`; Pro `requirements.txt` adds `docuvision-core[lite]`, `pdfplumber`, `pymupdf`.

## [1.2.1] — 2026-06-17

Maintenance patch (deferred from v1.2.0). See [RELEASE_1.2.1_NOTES.md](docs/release/RELEASE_1.2.1_NOTES.md).

### Added

- Batch **Excel** export: `GET /batch/{id}/export.xlsx` + UI **Download Excel**.
- Playwright E2E P0 (UI-S + UI-Q); Shared UI Shell PR2 (`shared/components.css`, `pro-only.css`).

### Changed

- [KNOWN_LIMITATIONS.md](docs/release/KNOWN_LIMITATIONS.md): Batch Excel delivered; Playwright P0 spec added.

## [1.2.0] — 2026-06-12

Pro **multipage PDF KIE** (`kie_pages`) and **Batch Processing** productization (API export + UI tab). Cloud merge gate passed; see [RELEASE_1.2_NOTES.md](docs/release/RELEASE_1.2_NOTES.md) and [KIE_TEST_RUN_TRACKER.md](docs/architecture/KIE_TEST_RUN_TRACKER.md).

### Added

- **Multipage PDF KIE**: `kie_pages` on analyze / jobs (`1`, `1-3`, `all`; max 5 pages). Per-page VL + document-level field merge; `kie_fields_by_page` + `quality.kie_pages_*`.
- **Batch productization**: batch jobs use full document orchestrator (KIE + envelope); `GET /batch/{id}/export.csv` (kie/summary/failures) and `export.json`; Pro UI Batch tab wired.
- Test fixtures script `test_data/scripts/build_multipage_kie_fixtures.py`; batch manifest `test_data/testfiles/batch/manifest.json`; acceptance `multipage_kie.md`, `batch_kie.md`.
- Merge gate checklist `test_data/acceptance/MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md` (Cloud Studio zsh/bash).

### Changed

- `APP_VERSION` default `1.2.0`; batch KIE concurrency defaults to 1 (`BATCH_MAX_CONCURRENT_KIE`).
- Batch `resume` re-schedules pending tasks when `process_func` is provided.

### Fixed

- Batch KIE acceptance script: merge manifest set-level `document_type` into `options` before `POST /batch` (fixes `skipped_doc_type` / 0/6 `kie_production_hit`).
- Batch manifest: duplicate `document_type` inside each set `options` for API clarity.
- Acceptance script: print `export BATCH_ID=...`, validate CSV `kie_production_hit`, exit non-zero on BATCH-002 failure.
- `pdf_page_count`: return `0` when PDF cannot be opened so `resolve_document_page_count` can fall back to `view.pages` / layout (fixes Phase A `test_document_page_count_from_view_pages`).
- Pro UI: queue processes selected item only (no auto-run of other pending); multipage preview page count; batch JSON download as file.

## [1.1.0] — 2026-06-04

Pro **KIE query fields** (extend-only runtime schema). Cloud Phase F accepted; see [RELEASE_1.1_NOTES.md](docs/release/RELEASE_1.1_NOTES.md) and [KIE_TEST_RUN_TRACKER.md](docs/architecture/KIE_TEST_RUN_TRACKER.md).

### Added

- **Pro KIE query fields** (`kie_query_fields`): extend built-in YAML schema at runtime (Azure Query Fields aligned, max 20 fields). API: `POST /api/v1/analyze`, `POST /api/v1/documents:analyze`, batch `options`. See [kie-custom-fields.md](docs/architecture/kie-custom-fields.md).
- Pro UI: Analysis Options → Advanced → Additional KIE fields (comma-separated or JSON).
- `quality.kie_query_fields_requested` / `kie_query_fields_filled`.

### Changed

- `KieManager` / `QwenDocumentKIEService` accept merged schema for VL prompts.
- `APP_VERSION` default `1.1.0`.

## [1.0.1] — 2026-06-02

Maintenance release: **DocuVision Lite** on `main`, dead-code cleanup, CI/docs alignment. Pro KIE scope unchanged from 1.0.

### Added

- **DocuVision Lite** (CPU): [`apps/lite/`](apps/lite/), [`packages/docuvision-core/`](packages/docuvision-core/), [`docs/architecture/lite-api.md`](docs/architecture/lite-api.md).
- Lite: digital PDF tables (Camelot / pdfplumber), Document Profile, scan/image Text OCR (EasyOCR / Tesseract), JSON / CSV / Markdown / Word export.
- Shared UI shell [`frontend/shared/`](frontend/shared/); GitHub Actions **CI Lite**.
- Pro: `install_pro_gpu.sh`, `gpu_lib_path`, live API tests skip when `:8000` is down.

### Fixed

- Lite EasyOCR Reader process cache and multi-page reuse.
- Lite Analysis Options: hide Tables for raster documents.
- Phase A CI: lazy-import `requests` in `conftest.py`.

### Removed

- Dead code: `page_processor`, `base_processor`, broken `file_utils`, `paddleocr_model_preloader`, core `paddleocr_engine`, `generate_kie_card_samples.py`, `test-canvas-display.html`.

### Pro vs Lite (summary)

| Area | Pro (`:8000`) | Lite (`:8001`) |
|------|---------------|----------------|
| Engines | PP-StructureV3 + Qwen KIE | pdfplumber / Camelot + EasyOCR / Tesseract |
| KIE | 5 fixed document types | None |
| GPU | Recommended | CPU |
| Tables | Layout + complex PDF | Born-digital PDF; raster tables frozen by default |
| Batch | Backend API | Not available |

See [Known limitations](docs/release/KNOWN_LIMITATIONS.md) and [RELEASE_1.0.1_NOTES.md](docs/release/RELEASE_1.0.1_NOTES.md).

## [1.0.0] — 2026-05-21

First self-hosted release: Azure Layout–style analysis (PP-StructureV3) plus optional Qwen2.5-VL KIE for five fixed document types.

### Added

- FastAPI pipeline: layout, table, optional formula/seal, envelope (`raw` / `fused` / `view` / `quality`).
- **Qwen KIE** via `QwenDocumentKIEService` + `kie_configs/*.yaml` for `invoice`, `receipt`, `id_card`, `passport`, `bank_card`.
- KIE acceptance rules **KIE-ACCEPT-001/002/003** and `quality.kie_*` / `kie_id_card_precision_*` metrics.
- Synthetic Chinese ID card samples `id_card_sample_02~04.jpg` with layout self-check scripts under `test_data/scripts/`.
- GitHub Actions workflow **KIE Phase A** (CPU contract tests, no Paddle / no Qwen weights).
- Root **MIT License**; release notes and [Known limitations](docs/release/KNOWN_LIMITATIONS.md).

### Fixed

- PDF invoice KIE: rasterize page 1 instead of passing `.pdf` to PIL (`e7dc4ab`).
- Phase A CI: remove eager Paddle imports from `app/services/__init__.py`; slim CI dependencies.

### Changed

- Strengthened `id_card.yaml` prompt and **KIE-ACCEPT-003** (18-digit `id_number` + `name` for Chinese ID regression).
- Cloud validation docs, Tracker, and architecture doc **Release 1.0** / **v1.1 custom fields** roadmap (v1.12).

### Verified (Cloud Studio GPU, see [KIE_TEST_RUN_TRACKER.md](docs/architecture/KIE_TEST_RUN_TRACKER.md))

- **Phase C** (invoices): 3/3 — 001 + 002.
- **Phase D** (`images/kie/`): 6/6 — 001 + 002; id_card **02~04** — 003.
- **Phase E** (receipt): 1/1 — 001 + 002.
- **Phase A** (GitHub Actions): contract pytest green on `main`.

### Known limitations (1.0)

See [docs/release/KNOWN_LIMITATIONS.md](docs/release/KNOWN_LIMITATIONS.md). Summary:

- `id_card_sample_01.jpg` is a legacy non–Chinese-ID layout; **003 may fail** while 002 still passes.
- No user-defined KIE schema, Batch UI productization, multi-page PDF KIE, or field bbox overlay.
- Full `pytest tests/` green not required; live `:8000` integration tests remain manual.

### Out of scope for 1.0

- Custom fields MVP (planned v1.1).
- `PP-DocTranslation`, PaddleOCR-VL long-document QA.

---

## Pre-1.0 history (high level)

| Period | Highlights |
|--------|------------|
| Phase 1–2 | PP-StructureV3 layout, envelope layers, formula/seal, table layout-first. |
| KIE migration | Qwen2.5-VL replaces PaddleNLP UIE; `kie_step` + `view.fields`. |
| 2026-05-20 | Cloud 7-sample KIE baseline; PDF KIE fix (`e7dc4ab`). |
| 2026-05-21 | id_card samples 02–04, ACCEPT-003, Phase A CI, Release 1.0 prep (`2c9c58b`). |

[Unreleased]: https://github.com/livezingy/DocuVision/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/livezingy/DocuVision/releases/tag/v1.1.0
[1.0.1]: https://github.com/livezingy/DocuVision/releases/tag/v1.0.1
[1.0.0]: https://github.com/livezingy/DocuVision/releases/tag/v1.0.0

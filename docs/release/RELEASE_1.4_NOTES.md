# Release 1.4.0 notes

**Tag**: `v1.4.0`  
**Date**: 2026-06-30  
**Train**: table mapping productization + HITL editable review + PDF Tools UI + backend hardening (webhook auth/SSRF, Phase1 form parity, dead-config cleanup)

## Summary

v1.4 delivers **vertical table column mapping** for born-digital PDFs (`table_template` → `mapped_table_rows`), a **Table mapping** processing mode in Analysis Options with document-profile eligibility, an editable **Reviews** (HITL) tab for KIE validation failures, a **PDF Tools** nav tab (merge / split / metadata), and batch **MappedRows** Excel export. Backend hardening: webhook registration gated by `DOCUVISION_WEBHOOK_ENABLED` + admin token + SSRF guard; Phase1 `/api/v1/documents:analyze` Form parity with legacy `/analyze`; dead config removed (chart/ocr/financial_report/table_areas); debug directory traversal hardened; fake `make_searchable_pdf` replaced with 501.

## Added

| Area | Detail |
|------|--------|
| **Table mapping** | Processing mode `table_mapping` + templates `bank_statement`, `invoice_line_items`; analyze with `enable_layout=false`, `table_template`; UI **Mapped rows** tab. |
| **Document profile** | Upload pre-scan via `POST /document/profile`; eligibility hint (*Ready for table mapping* / scan blocked). |
| **HITL Reviews UI** | Editable field grid, Save (`PATCH /api/v1/tasks/{id}/kie-fields`), Approve/Reject; `hitl_policy` (`full` / `lite` / `off`). |
| **PDF Tools UI** | Top nav tab: merge (≥2 PDF), split, metadata JSON. |
| **Batch mapped export** | XLSX **MappedRows** sheet; manifest `mapped_bank_statement_3`; **MAPPED-BATCH-001** script. |
| **Phase1 form parity** | `POST /api/v1/documents:analyze` now accepts full Form set (layout/table/formula/seal/KIE toggles, engine overrides, formula thresholds, `table_template`, `enable_hitl`) — matches legacy `/api/v1/analyze`. |
| **Tests / CI** | Backend/core contract tests; Phase A workflow extended; Playwright `process-table-mapping.e2e.js` (UI-TM-*), `process-pdf-tools.e2e.js` (UI-PT-*); `test_phase1_analyze_form.py`, `test_webhook_service.py` extended. |
| **Ops** | `accelerate` for KIE `device_map=auto`; KIE model path discovery; `GET /api/v1/health` for AI Studio. |

## Changed

- `APP_VERSION` default **1.4.0**.
- Table mapping analyze path: `document_type=general`, no KIE — **does not enqueue HITL** (Reviews tab serves KIE validation failures only).
- `batch_export_service._task_kie_fields`: removed dead `quality` branch.
- Debug artifact download (`GET /api/v1/jobs/{job_id}/debug/{filename}`): `Path.is_relative_to` replaces `startswith` to block sibling-directory traversal.
- Cloud merge gate: [MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md).

## Security

- **Webhook registration hardened (breaking)**. Two-layer gating:
  - `DOCUVISION_WEBHOOK_ENABLED` (default `false`): disabled → `GET/POST /api/v1/webhooks` return `404`, `dispatch_event_async` returns `[]`.
  - `DOCUVISION_WEBHOOK_ADMIN_TOKEN`: enabled → `X-DocuVision-Admin-Token` header required; fail-closed when token empty.
- **SSRF guard**: webhook URL host resolved and rejected if private/loopback (`127/10/169.254/192.168/172.16/::1/fc00::/7/fe80::/10`). Does not defend DNS rebinding (v1.5+).

## Removed

- `enable_ocr` per-block OCR dead config (standalone `/api/v1/ocr` unchanged).
- `chart_step` / `enable_chart` / `ChartService` (no callers).
- `financial_report` document type (breaking: `unsupported_document_type`).
- `table_areas` ROI across Pro/Lite/core (breaking: Lite `/extract/auto` no longer accepts `table_areas`).
- `POST /api/v1/pdf-tools/searchable` → `501` (fake `make_searchable_pdf` deleted; searchable PDF deferred to v1.5+).

## Not in v1.4.0 (explicit deferrals)

| Item | Target |
|------|--------|
| `table_areas` ROI UI | v1.5+ |
| Custom column alias API | post-v1.4 |
| Webhook subscription UI | v1.5+ |
| Webhook DNS-rebinding defense | v1.5+ |
| PDF searchable / form-fill productization | v1.5+ ([v1.5-roadmap.md](../architecture/v1.5-roadmap.md)) |
| Batch / HITL / Webhook persistence | v1.5+ |

## Upgrade / migration

- **Integrators**: optional analyze form field `table_template=bank_statement|invoice_line_items` with `enable_layout=0`, `enable_table=1`, `enable_kie=0` for ETL-style mapped rows.
- **Webhook users (breaking)**: set `DOCUVISION_WEBHOOK_ENABLED=true` + `DOCUVISION_WEBHOOK_ADMIN_TOKEN=<secret>` to register; pass `X-DocuVision-Admin-Token` header.
- **Batch**: use manifest `mapped_bank_statement_3` or set `options.table_template` in batch `options` JSON.
- **HITL**: queue remains in-memory; restart clears pending reviews.
- **Cloud validation**: run v1.4 checklist (extends v1.3.1 gate with **MAP-TEMPLATE-001** + **MAPPED-BATCH-001** + webhook/Phase1/traversal hardening).

## Verification minimum

| Layer | Command |
|-------|---------|
| Phase A v1.4 | Pro + core file set in [CLOUD_VALIDATION.md](../architecture/CLOUD_VALIDATION.md) §阶段 A (incl. `test_phase1_analyze_form.py`, `test_webhook_service.py`) |
| Pro UI (no GPU) | `cd frontend && npm run test:unit && npm run test:e2e` (includes UI-TM-* / UI-PT-*) |
| Lite | `cd apps/lite/backend && pytest tests/ -q`; `npm run test:e2e:lite` |
| Table mapping (GPU/CPU) | **MAP-TEMPLATE-001** in [MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md) |
| Batch mapped | `pwsh -File test_data/scripts/run_batch_mapped_acceptance.ps1` |
| Webhook hardening | `pytest tests/test_webhook_service.py -q`; manual 404/401/400/200 chain (see checklist §9) |

Full gate: [MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.4_CLOUD_CHECKLIST.md).

## Related (unchanged from v1.3.x)

- Pro pdf_digital → docuvision-core table path (**CORE-PDF-001**).
- Lite server-side preview (**LITE-PREVIEW-001**).
- KIE field validation (**KIE-VAL-001**).

See [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md) for MVP bounds (English headers, memory queues, scan PDF blocked for table mapping).

# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — v1.1.0 (Pro custom KIE fields)

### Added

- **Pro KIE query fields** (`kie_query_fields`): extend built-in YAML schema at runtime (Azure Query Fields aligned, max 20 fields). API: `POST /api/v1/analyze`, `POST /api/v1/documents:analyze`, batch `options`. See [kie-custom-fields.md](docs/architecture/kie-custom-fields.md).
- Pro UI: Analysis Options → Advanced → Additional KIE fields (comma-separated or JSON).
- `quality.kie_query_fields_requested` / `kie_query_fields_filled`.

### Changed

- `KieManager` / `QwenDocumentKIEService` accept merged schema for VL prompts.

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

[1.0.1]: https://github.com/livezingy/DocuVision/releases/tag/v1.0.1
[1.0.0]: https://github.com/livezingy/DocuVision/releases/tag/v1.0.0

# DocuVision Core

Shared helpers consumed by the DocuVision **Pro** backend.

## What is in here

| Module | Consumer |
|--------|----------|
| `docuvision_core.processing.table_column_mapping` | `backend/app/orchestration/document_pipeline_orchestrator.py` — `table_template` 列映射 |
| `docuvision_core.utils.pdf_text_utils` | `backend/app/services/table_backfill.py` — `normalize_for_compare` |
| `docuvision_core.utils.logger` / `docuvision_core.utils.path_utils` | Pro 通用工具 |

> **Lite 已随 v1.8 退役**：本包原先的表格/OCR 引擎家族（`extractors/`、`engines/`、`models/`、`export/`、`demo/` 及自适应处理家族）已移除，
> extras 现仅剩 `dev`（`pyproject.toml`）。`CHANGELOG.md` §1.8 记录了移除范围。

## Install

```bash
pip install -e ".[dev]"   # pytest
```

The Pro backend consumes it as an editable path dependency — see `backend/requirements.txt` (`-e ../packages/docuvision-core`).

## Tests

```bash
cd packages/docuvision-core
pytest -q
```

Local (no GPU / no Paddle) — the four surviving test modules cover `normalize_for_compare`, `table_column_mapping`, `pdf_text_utils` and `path_utils`.

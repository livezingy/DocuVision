# DocuVision Lite — 测试与云端验收

> **本地职责**：仅修改代码与测试文件，**不在本地执行 Python/pytest**。  
> **验证职责**：GitHub Actions（`CI Lite` workflow）或 Cloud Studio CPU 环境执行本节命令。

## 0. 测试文件说明（合并前审计）

| 文件 | 保留原因 |
|------|----------|
| `test_*.py`（13 个） | 均在 CI 或文档中引用；**无冗余删除** |
| `test_lite_preview.py` | `POST /preview` + `GET .../page-image` 契约（PDF/PNG 魔数） |
| `test_image_table_pipeline.py` | 覆盖冻结后的 `image_table_pipeline`（含 `RASTER_TABLE_EXTRACTION_ENABLED=true` 时的 mock 路径） |
| `test_raster_transformer_frozen.py` | 默认冻结下 `/extract/auto` 不调用 Transformer |
| `fixtures/sample_bordered.pdf` | 数字 PDF 表格/Profile 集成测试 |
| `LITE_UI_TEST_CHECKLIST.md` | 手工 UI 验收（非 pytest）；对照 [UI_VERIFICATION_MATRIX.md](../../../../test_data/acceptance/UI_VERIFICATION_MATRIX.md) §3 |

后端 `image_table_pipeline.py` 在默认配置下**运行时不用**，但保留供 `RASTER_TABLE_EXTRACTION_ENABLED=true` 开发/回归，**不是死代码**。

## 1. 自动化

| 触发方式 | 何时运行 `CI Lite` |
|----------|-------------------|
| **PR → `main`** | 变更含 `apps/lite/**`、`packages/docuvision-core/**` 等路径时 **自动** |
| **手动** | GitHub → Actions → **CI Lite** → Run workflow |
| **Push（可选）** | 仅当 commit message 含 **`[run ci]`** 时执行（日常 push **不加** 此标记） |

Workflow 定义：[`.github/workflows/ci-lite.yml`](../../../../.github/workflows/ci-lite.yml)

**通过标准**：workflow 全绿。日常开发优先 §2 云端 pytest；合并前以 PR 上 Actions 为准。

## 2. 云端手动命令

### 2.1 强制同步远程（丢弃云端本地改动）

若云端曾手动改过测试文件（如 `test_lite_ocr_messaging.py` 里的路径），`git pull` 可能冲突或无法覆盖。在仓库根目录执行：

```bash
cd /workspace/DocuVision   # 按实际路径调整
git fetch origin
git checkout feature/docuvision-lite
git reset --hard origin/feature/docuvision-lite
git clean -fd   # 可选：删除未跟踪文件；慎用，会删掉未提交的本地新文件
```

**说明**：`reset --hard` 会永久丢弃该分支上所有未提交修改，与远程完全一致。仅用于测试机同步，勿在有需保留的本地实验时使用。

较温和备选（想保留改动到 stash）：

```bash
git stash push -u -m "cloud-local"
git pull origin feature/docuvision-lite
```

### 2.2 环境与 pytest

> **zsh**：extras 方括号会被 shell 展开，以下 `pip install -e '...'` 请保留单引号。

```bash
cd apps/lite/backend
python3 -m venv ~/docuvision_lite_env
source ~/docuvision_lite_env/bin/activate
pip install -r requirements-lite.txt
pip install -e '../../../packages/docuvision-core[lite,dev]'

# Optional: image Table Transformer + matplotlib viz (see apps/lite/backend/README.md)
# sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
# pip install -r requirements-lite-ocr-heavy.txt
python -m pytest tests/ -q

# docuvision-core（含 classify 单元测试）
cd ../../../packages/docuvision-core
python -m pytest tests/utils/test_pdf_text_utils.py tests/extractors/test_factory.py tests/processing/test_table_type_classifier.py tests/utils/test_config.py -q

# Transformer image tables (cloud GPU env with ocr-heavy deps):
# Disabled by default in Lite (RASTER_TABLE_EXTRACTION_ENABLED=false).
# pip install -e '../../../packages/docuvision-core[ocr-heavy]'
# RASTER_TABLE_EXTRACTION_ENABLED=true python -m pytest tests/test_image_table_pipeline.py -q
```

## 3. Document Profile + 三栏 UI 验收标准

### 3.1 API — `POST /api/v1/lite/analyze/profile`

| 规则 ID | 测试文件 | 通过标准 |
|---------|----------|----------|
| **LITE-PROFILE-001** | `test_lite_analyze_profile.py::test_analyze_profile_digital_pdf` | 200；`detected_file_type=pdf_digital`；`pages[0].table_type` 为 `bordered`/`unbordered`/`none` |
| **LITE-PROFILE-002** | `test_lite_analyze_profile.py::test_analyze_profile_file_too_large` | 413 |
| **LITE-PROFILE-003** | `test_lite_analyze_profile.py::test_analyze_profile_png_scan` | 200；`pages=[]`；`scan_profile.message` 非空 |

### 3.2 Core — `TableTypeClassifier.classify()`

| 规则 ID | 测试文件 | 通过标准 |
|---------|----------|----------|
| **LITE-CORE-001** | `test_table_type_classifier.py::test_classify_quick_filter_unbordered` | `method=quick_filter`，`table_type=unbordered` |
| **LITE-CORE-002** | `test_table_type_classifier.py::test_predict_table_type_delegates_to_classify` | `predict_table_type()` 与 `classify()['table_type']` 一致 |

### 3.3 Extract — `param_mode` / `custom_params`

| 规则 ID | 测试文件 | 通过标准 |
|---------|----------|----------|
| **LITE-EXTRACT-001** | `test_lite_extract.py::test_extract_auto_digital_pdf` | 200；`status=succeeded` |
| **LITE-EXTRACT-002** | `test_lite_extract.py::test_extract_file_too_large` | 413 |

### 3.4 前端冒烟（云端启动后人工）

```bash
cd apps/lite/backend && python run_lite.py
# 浏览器打开 http://{host}:8001/lite/lite.html
```

| 检查项 | 通过标准 |
|--------|----------|
| 三栏 resize | 左/右 `panel-resize-handle` 拖动有效，中栏 `flex:1` 自适应 |
| 按钮文案 | **Run Analysis** / **Analysis Options**（含 SVG，风格对齐 Pro） |
| Text 全量 | 多 block 图片 OCR 后 Content/Text 字符数与 Result JSON 中 `ocr[]` 拼接一致（非 `text_preview` 截断） |
| Fields | Content 子 Tab 仅有 Text / Tables / Figures，**无 Fields** |
| Figures | 固定 Pro 空态文案 |
| Document Profile | digital PDF 显示 table_type / routing；PNG 显示 scan_profile |
| Analysis Options | 三 Tab；Advanced 可预填 custom params |
| 本地 docs | `apps/lite/backend/docs/` 可存在本地；`git ls-files apps/lite/backend/docs/` 为空 |

### 3.5 OCR messaging

| Rule ID | Test file | Pass standard |
|---------|-----------|---------------|
| **LITE-OCR-001** | `test_lite_ocr_messaging.py::test_normalize_easyocr_languages_maps_eng_to_en` | `eng` maps to `en` for EasyOCR |
| **LITE-OCR-002** | `test_lite_ocr_messaging.py::test_low_confidence_still_returns_ocr_blocks` | Low confidence still returns OCR text + `low_confidence` warning |
| **LITE-OCR-003** | `test_lite_ocr_messaging.py::test_empty_ocr_emits_no_text_detected` | Empty OCR emits `no_text_detected` |
| **LITE-OCR-004** | `test_lite_ocr_messaging.py::test_ocr_runtime_error_emits_extraction_failed` | Runtime error emits `ocr_extraction_failed` |

### 3.6 Bordered table extract

| Rule ID | Test file | Pass standard |
|---------|-----------|---------------|
| **LITE-TBL-001** | `test_lite_bordered_tables.py::test_extract_auto_bordered_pdf_returns_tables` | Smart extract returns >=1 table with rows |
| **LITE-TBL-002** | `test_lite_bordered_tables.py::test_analyze_profile_bordered_type` | Profile returns bordered/unbordered |

### 3.7 UI manual checklist

See [`tests/LITE_UI_TEST_CHECKLIST.md`](LITE_UI_TEST_CHECKLIST.md) — queue remove, Content tabs, OCR messaging, bordered tables.

## 4. Fixture 说明

- `tests/fixtures/sample_bordered.pdf` — digital PDF 样例（缺失时 `test_analyze_profile_digital_pdf` 自动 skip）
- PNG 测试内嵌最小 1×1 PNG，不依赖 fixture 文件

## 5. 相关文档

- [lite-api.md](../../../docs/architecture/lite-api.md) — API 契约
- [CLOUD_VALIDATION.md](../../../docs/architecture/CLOUD_VALIDATION.md) — 全局云验证顺序

# DocuVision Lite — 测试与云端验收

> **本地职责**：仅修改代码与测试文件，**不在本地执行 Python/pytest**。  
> **验证职责**：GitHub Actions（`CI Lite` workflow）或 Cloud Studio CPU 环境执行本节命令。

## 1. 自动化（推荐）

Push 至 `main` 或 `feature/docuvision-lite` 且变更路径含 `apps/lite/**`、`packages/docuvision-core/**` 时，GitHub Actions [`.github/workflows/ci-lite.yml`](../../../../.github/workflows/ci-lite.yml) 自动运行。

**通过标准**：workflow 全绿。

## 2. 云端手动命令

```bash
cd apps/lite/backend
python3 -m venv ~/docuvision_lite_env
source ~/docuvision_lite_env/bin/activate
pip install -r requirements-lite.txt
pip install -e ../../../packages/docuvision-core[lite,dev]

# Lite API 契约
python -m pytest tests/ -q

# docuvision-core（含 classify 单元测试）
cd ../../../packages/docuvision-core
python -m pytest tests/extractors/test_factory.py tests/processing/test_table_type_classifier.py -q
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
| 三栏布局 | 左 Upload/Queue、中 Preview+Profile、右 Content/Result |
| 上传 digital PDF | Document Profile 显示 table_type、score、routing |
| Analysis Options | 三 Tab；Advanced 可预填参数 |
| Run Extraction | Tables/Text 有结果；Figures 固定 Pro 空态；无 Fields Tab |
| 上传 PNG | scan_profile 文案显示 |

## 4. Fixture 说明

- `tests/fixtures/sample_bordered.pdf` — digital PDF 样例（缺失时 `test_analyze_profile_digital_pdf` 自动 skip）
- PNG 测试内嵌最小 1×1 PNG，不依赖 fixture 文件

## 5. 相关文档

- [lite-api.md](../../../docs/architecture/lite-api.md) — API 契约
- [CLOUD_VALIDATION.md](../../../docs/architecture/CLOUD_VALIDATION.md) — 全局云验证顺序

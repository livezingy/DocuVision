# DocuVision Lite API 规范

> **版本**：v0.1  
> **日期**：2026-05-22  
> **状态**：Phase A — health/engines 已实现；extract 路由待 core 迁移（阶段 B/C）  
> **适用范围**：`apps/lite/backend` + `apps/lite/frontend`（前端阶段 D）  
> **关联**：Pro API 见 `backend/app/main.py`（`/api/v1/analyze` 等）

---

## 1. 文档目的

定义 DocuVision Lite 的 REST API：路由、请求/响应契约、错误码、核心数据结构 **LiteResult**，以及与 Pro Envelope 的边界。

Lite 面向 **CPU 友好** 场景：born-digital PDF 表格（pdfplumber/camelot）、轻量 OCR（Tesseract/EasyOCR）、可选 Transformer（heavy profile）。

---

## 2. 基本信息

| 项 | 值 |
|----|-----|
| **Base URL** | `http://{host}:{port}/api/v1/lite` |
| **默认端口** | `8001`（Pro 为 `8000`） |
| **OpenAPI** | `/docs`、`/openapi.json` |
| **认证（v0.1）** | 无 |

### 2.1 版本策略

- URL 含 `/v1/`；破坏性变更升 `/v2/`
- 响应体含 `api_version: "1.0.0-lite"`
- `schema_version` 当前为 `"1.0"`

---

## 3. 设计原则

1. **简单优先**：默认 `mode=smart`
2. **显式引擎**：`mode=advanced` 时可指定 `engine`
3. **同步 + 可选异步**：小文件同步；大文件走 Job
4. **不伪装 Pro**：无 KIE、无 Layout Envelope
5. **可升级提示**：`hints[]` 引导 Pro

---

## 4. 路由总览

| 方法 | 路径 | 说明 | 阶段 |
|------|------|------|------|
| `GET` | `/health` | 健康检查、引擎就绪 | A ✅ |
| `GET` | `/engines` | 可用引擎列表 | A ✅ |
| `POST` | `/analyze/profile` | 上传后轻量预扫描，返回 LiteDocumentProfile | D ✅ |
| `POST` | `/extract/tables` | PDF 表格提取 | C |
| `POST` | `/extract/ocr` | 图片/扫描 OCR | C |
| `POST` | `/extract/auto` | 自动路由统一入口 | C |
| `POST` | `/jobs` | 创建异步任务 | C |
| `GET` | `/jobs/{job_id}` | 任务状态 | C |
| `GET` | `/jobs/{job_id}/result` | 获取 LiteResult | C |
| `GET` | `/export/{job_id}.csv` | 导出 CSV | C |
| `GET` | `/export/{job_id}.xlsx` | 导出 Excel | C |
| `DELETE` | `/jobs/{job_id}` | 删除任务 | C |

---

## 5. 枚举

```yaml
ExtractMode: [smart, advanced]
EngineId: [auto, pdfplumber, camelot, tesseract, easyocr, transformer]
JobStatus: [pending, running, succeeded, failed, cancelled]
DetectedFileType: [pdf_digital, pdf_scan, image, unsupported]
WarningCode: [scan_detected, low_confidence, engine_fallback, transformer_unavailable, page_truncated, pro_recommended]
```

### 5.1 默认限制

| 参数 | 默认值 |
|------|--------|
| `max_file_size_mb` | 50 |
| `max_pages` | 50 |
| `sync_max_pages` | 10 |
| `job_ttl_hours` | 24 |

---

## 6. LiteResult Schema

### 6.1 顶层结构

```json
{
  "schema_version": "1.0",
  "api_version": "1.0.0-lite",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "succeeded",
  "created_at": "2026-05-22T10:30:00Z",
  "completed_at": "2026-05-22T10:30:02Z",
  "processing_ms": 1842,
  "input": {},
  "routing": {},
  "quality": {},
  "tables": [],
  "ocr": null,
  "text_preview": null,
  "exports": {},
  "warnings": [],
  "hints": [],
  "error": null
}
```

### 6.2 子结构

**LiteInputMeta**：`filename`, `file_size_bytes`, `mime_type`, `detected_file_type`, `page_count`, `sha256`

**LiteRoutingMeta**：`mode`, `requested_engine`, `engine_used`, `engine_chain`, `table_type_detected`, `flavor_used`, `param_mode`, `profile`, `document_profile`（可选，extract 完成后回显）

**LiteDocumentProfile**：`schema_version`, `api_version`, `input`, `pages[]`, `scan_profile`, `warnings[]`

**LitePageProfile**：`page`, `table_type`, `table_type_score`, `classification_detail`, `typography_summary`, `suggested_routing`, `computed_params`

**LiteScanProfile**：`recommended_ocr`, `transformer_available`, `message`

**LiteQualityMeta**：`overall_confidence`, `tables_found`, `tables_accepted`, `pages_processed`, `pages_with_tables`, `ocr_blocks`, `processing_profile`

**LiteTable**：`table_id`, `page`, `index_on_page`, `bbox`, `row_count`, `col_count`, `score`, `source`, `headers`, `rows`, `details`

**LiteOcrBlock**：`page`, `bbox`, `text`, `confidence`, `engine`

**LiteExportLinks**：`csv`, `xlsx`, `json`

**LiteWarning / LiteHint**：`code`, `message`, `severity`（warning）；hint 可含 `link`

**LiteError**（失败时）：`code`, `message`, `details`

---

## 7. 路由详细说明

### 7.1 GET /health

**响应 200**

```json
{
  "status": "ok",
  "service": "docuvision-lite",
  "api_version": "1.0.0-lite",
  "profile": "cpu",
  "engines": {
    "pdfplumber": { "available": true, "version": "0.11.0" },
    "camelot": { "available": true, "version": "0.11.0" },
    "tesseract": { "available": false, "reason": "binary not found" },
    "easyocr": { "available": false, "reason": "not installed" },
    "transformer": { "available": false, "reason": "heavy profile not installed" }
  },
  "limits": {
    "max_file_size_mb": 50,
    "max_pages": 50,
    "sync_max_pages": 10
  }
}
```

### 7.2 GET /engines

返回引擎 metadata，供 Lite 前端 Advanced 面板使用（见实现 `routes_health.py`）。

| Engine | `file_types` | UI section |
|--------|--------------|------------|
| `pdfplumber`, `camelot` | `pdf_digital` | Engines — digital table extraction |
| `tesseract`, `easyocr` | `image`, `pdf_scan` | Engines — text OCR |
| `transformer` | `image`, `pdf_scan` | Engines — raster table extraction (includes scanned PDF after rasterize) |

模型权重路径与换主机流程见 [packages/docuvision-core/models/README.md](../../packages/docuvision-core/models/README.md)。

### 7.3 POST /analyze/profile

**Request** `multipart/form-data`：`file`

轻量预扫描：分析页面特征、表格类型预判、推荐引擎与自动计算参数。**不执行**完整表格/OCR 提取。

**响应 200** — `LiteDocumentProfile`：

```json
{
  "schema_version": "1.0",
  "api_version": "1.0.0-lite",
  "input": {
    "filename": "invoice.pdf",
    "detected_file_type": "pdf_digital",
    "page_count": 3
  },
  "pages": [
    {
      "page": 1,
      "table_type": "bordered",
      "table_type_score": 0.91,
      "classification_detail": {
        "method": "mad",
        "h_lines": 20,
        "v_lines": 18,
        "line_concentration": 0.95,
        "area_ratio": 0.15,
        "direction_balance": 0.90
      },
      "typography_summary": {
        "mode_char_width_pt": 6.0,
        "mode_char_height_pt": 8.0,
        "mode_line_height_pt": 10.0,
        "mode_line_spacing_pt": 3.0,
        "total_lines": 47,
        "total_chars": 1284
      },
      "suggested_routing": {
        "engine": "smart",
        "flavor": "bordered",
        "param_mode": "auto"
      },
      "computed_params": {
        "camelot_lattice": { "flavor": "lattice", "line_scale": 40 },
        "camelot_stream": { "flavor": "stream", "edge_tol": 29 },
        "pdfplumber_bordered": { "snap_tolerance": 1.2 },
        "pdfplumber_unbordered": { "text_x_tolerance": 9.0 }
      }
    }
  ],
  "scan_profile": null,
  "warnings": []
}
```

- `pdf_digital`：返回 `pages[]`（最多 `sync_max_pages` 页）
- `pdf_scan` / `image`：`pages=[]`，填充 `scan_profile`
- 超出页数限制时 `warnings` 含 `page_truncated`

### 7.4 POST /extract/tables（阶段 C）

**Request** `multipart/form-data`：`file`, `mode`, `engine`, `flavor`, `pages`, `param_mode`, `custom_params`, `score_threshold`, `async`

**Smart 路由**：

```
pdf_digital → table_type_classifier
  ├─ bordered    → pdfplumber (lines) first; camelot (lattice) full-page fallback when max score < threshold
  └─ unbordered  → pdfplumber (text) first; camelot (stream) full-page fallback when max score < threshold
失败 → engine_fallback + 备选引擎
```

### 7.3.1 Flavor 语义（Lite UI / API）

Lite 面向用户的 **flavor** 为统一的三档值，Advanced 模式下由前端或 API 映射到引擎原生 flavor：

| UI / API flavor | 含义 | pdfplumber | camelot |
|-----------------|------|------------|---------|
| `auto` | 由 Smart 路由与页面特征决定 | — | — |
| `bordered` | 有边框/网格线表格 | `lines` | `lattice` |
| `unbordered` | 无边框、文本对齐表格 | `text` | `stream` |

- `GET /engines` 与 Advanced 面板下拉框均暴露 `auto` / `bordered` / `unbordered`
- `POST /analyze/profile` 的 `suggested_routing.flavor` 使用同一套值（如 `bordered`、`unbordered`）
- Smart 模式下请求仍传 `flavor=auto`；Camelot 仅在 pdfplumber 最高分低于阈值时作为整页兜底

### 7.3.2 Smart Camelot 兜底策略

Smart（`table_method=mixed`）处理流程：

1. 按页面 `table_type` 用 pdfplumber 提取（bordered→lines，unbordered→text），必要时 flavor 互换重试
2. 计算 pdfplumber 结果的最高 `score`
3. 若 `max_score < smart_camelot_fallback_threshold`（默认 **0.8**，可通过 processor params 配置），对该页运行 **整页** Camelot（bordered→lattice，unbordered→stream）
4. 合并 pdfplumber 与 Camelot 结果，按 bbox 去重（保留较高 score），再按 `score_threshold` 过滤

与旧版「高置信 bbox 局部 Camelot 精修」不同，新版在 pdfplumber 整体质量偏低时触发全页 Camelot，以提高弱线框/扫描类数字 PDF 的召回。

### 7.5 POST /extract/ocr（阶段 C）

字段：`file`, `mode`, `engine`, `languages`, `with_tables`, `min_confidence`, `async`

### 7.6 POST /extract/auto（阶段 C）

统一入口；按文件类型路由至 tables 或 ocr pipeline。

### 7.7 Jobs / Export（阶段 C）

- `POST /jobs` → 202 + `job_id`
- `GET /jobs/{id}/result` → 完整 LiteResult
- `GET /export/{id}.csv|.xlsx` → 附件下载

---

## 8. 错误响应

```json
{
  "error": {
    "code": "file_too_large",
    "message": "File exceeds maximum size of 50 MB",
    "details": { "max_file_size_mb": 50 }
  }
}
```

| HTTP | code |
|------|------|
| 400 | `unsupported_file_type`, `invalid_pages_spec` |
| 413 | `file_too_large` |
| 422 | `validation_error` |
| 404 | `job_not_found` |
| 409 | `job_not_ready` |
| 410 | `job_expired` |
| 503 | `engine_unavailable` |
| 500 | `engine_runtime_error`, `internal_error` |

---

## 9. 与 Pro 的边界

| 能力 | Lite | Pro |
|------|------|-----|
| 路径 | `/api/v1/lite` | `/api/v1` |
| 响应 | LiteResult | Envelope |
| KIE | 否 | 是 |
| Layout 画布 | 否 | 是 |
| UI | `lite.html` :8001 | `index.html` :8000 |

Pro 与 Lite **不在同一 UI 内切换**；通过顶栏外链或产品落地页互相引导。

---

## 10. Lite 前端 UI 布局

Lite 采用与 Pro 一致的三栏结构：

| 区域 | 内容 |
|------|------|
| 左栏 | Upload Document、Processing Queue（最多 3 个文件） |
| 中栏 | 文档预览（`preview-header` → `preview-container` → `preview-pagination`），**不含** Document Profile |
| 右栏 | Processing Results |

### 10.1 右栏主 Tab

| Tab | 说明 | 数据来源 |
|-----|------|----------|
| **Profile** | Lite 独有；上传后预扫描结果 | `POST /analyze/profile` → `LiteDocumentProfile` |
| **Content** | 提取结果（Text / Tables / Figures） | `LiteResult` |
| **Result** | 完整 JSON | `LiteResult` |

**默认 Tab 行为：**

- 上传并完成 profile 分析后 → 自动切换到 **Profile**
- Run Analysis 完成后 → 自动切换到 **Content**（优先 Tables，否则 Text）
- 中间预览翻页与 Profile 页选择器双向同步

### 10.2 可选 Content 子 Tab（Transactions / Mapped）

Lite 与 Pro 共用 [`frontend/shared/ui-features.js`](../../frontend/shared/ui-features.js) 控制 **Transactions**、**Mapped** 子 Tab 的显示。当前默认隐藏；用途与启用步骤见 [`智能文档处理系统设计方案.md`](./智能文档处理系统设计方案.md) §9.2。

---

## 11. 实现检查清单

- [x] Phase A：`LiteResult` Pydantic models
- [x] Phase A：`GET /health`, `GET /engines`
- [x] Phase B：`packages/docuvision-core` 迁移
- [x] Phase C：`/extract/*`, jobs, export（baseline）
- [x] Phase D：`lite.html` 前端（baseline）
- [x] Phase D+：`POST /analyze/profile` + 三栏 UI + Document Profile
- [x] Phase D++：Document Profile 迁至右栏 Profile Tab；中栏预览与 Pro 对齐

---

## 12. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-05-22 | 初版；Phase A health/engines 落地 |
| v0.2 | 2026-05-26 | 新增 LiteDocumentProfile、`POST /analyze/profile` |
| v0.3 | 2026-05-27 | Document Profile 移至右栏 Profile Tab；Transactions/Mapped 默认隐藏（ui-features.js） |
| v0.4 | 2026-05-27 | 统一 flavor 语义（auto/bordered/unbordered）；Smart Camelot 低分兜底策略 |

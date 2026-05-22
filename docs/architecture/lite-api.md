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

**LiteRoutingMeta**：`mode`, `requested_engine`, `engine_used`, `engine_chain`, `table_type_detected`, `flavor_used`, `param_mode`, `profile`

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

### 7.3 POST /extract/tables（阶段 C）

**Request** `multipart/form-data`：`file`, `mode`, `engine`, `flavor`, `pages`, `param_mode`, `custom_params`, `score_threshold`, `async`

**Smart 路由**：

```
pdf_digital → table_type_classifier
  ├─ bordered    → camelot (auto)
  └─ unbordered  → pdfplumber (auto)
失败 → engine_fallback + 备选引擎
```

### 7.4 POST /extract/ocr（阶段 C）

字段：`file`, `mode`, `engine`, `languages`, `with_tables`, `min_confidence`, `async`

### 7.5 POST /extract/auto（阶段 C）

统一入口；按文件类型路由至 tables 或 ocr pipeline。

### 7.6 Jobs / Export（阶段 C）

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

## 10. 实现检查清单

- [x] Phase A：`LiteResult` Pydantic models
- [x] Phase A：`GET /health`, `GET /engines`
- [x] Phase B：`packages/docuvision-core` 迁移
- [x] Phase C：`/extract/*`, jobs, export（baseline）
- [x] Phase D：`lite.html` 前端（baseline）

---

## 11. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v0.1 | 2026-05-22 | 初版；Phase A health/engines 落地 |

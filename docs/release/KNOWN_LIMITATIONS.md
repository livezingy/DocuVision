# Known limitations

> Applies through **v1.7.0 train** (tag pending). Queue persistence is v1.5; figure crops + artifact pack are v1.6; single-task result persistence is v1.7.  
> Release notes: [v1.7-roadmap.md](../architecture/v1.7-roadmap.md) · [RELEASE_1.6_NOTES.md](./RELEASE_1.6_NOTES.md) · [RELEASE_1.5_NOTES.md](./RELEASE_1.5_NOTES.md)  
> Acceptance rules: [KIE_ACCEPTANCE_CRITERIA.md](../../backend/tests/KIE_ACCEPTANCE_CRITERIA.md).

## DocuVision Lite (since 1.0.1)

| Limit | Detail |
|-------|--------|
| No KIE | Lite does not run Qwen KIE or `view.fields`; use **Pro** for invoice / receipt / ID documents. |
| Raster tables | Image and scan PDF **Table Transformer** extraction is **frozen** by default (`RASTER_TABLES_FROZEN`); text OCR only on raster docs. |
| Born-digital PDF | Table extraction via pdfplumber / Camelot; see [lite-api.md](../architecture/lite-api.md). |
| PDF preview | **v1.3.1+**: server-side PyMuPDF rasterization (`POST /preview`, `GET .../page-image/{n}`); preview sessions are in-memory and expire. |
| Models | EasyOCR / optional Transformer weights under `packages/docuvision-core/models/` — bootstrap required on new hosts ([models/README.md](../../packages/docuvision-core/models/README.md)). |
| Batch | **Pro** batch at `/api/v1/batch` with CSV/JSON/**Excel** export. **v1.5+**: job list survives restart (SQLite). **Lite batch API removed in v1.3.1** — use Pro batch or single-file Lite analyze. No Batch ZIP (v1.6 out of scope). |
| GPU | Lite targets CPU; Pro remains GPU-recommended for layout + KIE latency. |

## KIE / 证件票据 (Pro)

### `id_card_sample_01.jpg` 与 KIE-ACCEPT-003

| 项 | 说明 |
|----|------|
| 样例性质 | 历史验收图（美国驾照风格），**不是**标准中华人民共和国居民身份证版式。 |
| **002** | 通常 **通过**（`name` 或 `id_number` 任一项非空即可，例如 `CHRIS SMITH` + `034568`）。 |
| **003** | 通常 **不通过**（`id_number` 非 18 位中国证号 → `id_number_missing_or_invalid`）。 |
| 1.0 判定 | **不将 01 的 003 失败视为回归退步**；003 回归以 **`id_card_sample_02~04`** 为准。 |

### 合成 vs 真实扫描

- 仓库内 `id_card_sample_02~04` 为**虚构合成**图，用于固定回归；真实扫描件、复杂反光/遮挡未全面覆盖。
- Cloud 验收通过 **不保证** 所有真实身份证场景达到相同精度。

### 多页 PDF

- **v1.2+**：可选 `kie_pages`（默认第 1 页，与 v1.1 一致）；`all` / 范围对 PDF 按页推理后合并字段（见 [kie.md](../architecture/kie.md)）。
- 单图/raster 上传不支持 `kie_pages` 非 `1`；页数上限 `KIE_MAX_PAGES`（默认 5）。
- 跨页同名字段冲突：**后页优先**；无 `kie_merge_policy` 配置项。

### 字段精度

- **003** 仅校验 `name` + 18 位 `id_number` 格式，**不**验证校验位算法或与 ground-truth 逐字匹配。
- 住址、签发机关等长字段在复杂版式下可能漏抽或格式不一致。

## 产品 / 架构

| 限制 | 说明 |
|------|------|
| Pro document type | **v1.3.1**: no Auto-detect UI; users pick type via Analysis Options / document profile. Classifier module remains for `/document/profile` hints only. |
| KIE query fields（v1.1） | `kie_query_fields` **仅追加**内置 schema（最多 20 字段）。**v1.3** 起支持 `document_type=custom` 与 YAML 模板库（MVP）；无字段 bbox 联动。见 [kie-custom-fields.md](../architecture/kie-custom-fields.md)。 |
| KIE validation（v1.3） | 启发式 date/currency 规则 + `kie_validation`；非 ground-truth 逐字校验。 |
| Batch Processing UI | v1.2+ Pro Batch tab with aggregated CSV/JSON/**Excel**. **v1.5**: queue persisted (`batch_jobs`). Lite has no batch UI/API since v1.3.1. |
| Single-task results (v1.7) | Completed Pro tasks persist via `analyze_jobs` + `OUTPUT_DIR/{task_id}/result.json`. Restart hydrates the in-memory `tasks` dict. In-flight jobs become `interrupted` (no auto GPU resume). Missing `result.json` → `missing_artifacts` (not 500). FIFO `TASK_KEEP_LAST_N` (default 50) deletes DB row and output dir together. SPA still only holds `currentTaskId` in the current session (no Recent-tasks UI). |
| Figure crops (v1.6) | `figure_step` writes `OUTPUT_DIR/{task_id}/figures/*.png`. Split-figure merge is best-effort; `is_merged` crops are not in the default Figures carousel. Lite has no figure export. |
| Artifact pack (v1.6) | Pro `GET /tasks/{id}/export/zip` packs tables + figure PNGs. Oversize → 413 (`MAX_PACK_BYTES` 256MB). No Lite ZIP, no Batch multi-task ZIP, no table-region screenshots. |
| Table column mapping (v1.4) | `table_template` maps born-digital PDF tables to unified schema (`mapped_table_rows`). **Scanned PDFs/images blocked** in UI (use Layout Analysis). **Debit/Credit split columns, Chinese headers, and complex merged cells** extensible; aliases target **English headers** primarily. Positional fallback when headers unmatched. Custom alias API deferred. **No HITL** on table-mapping analyze path (`document_type=general`, `enable_kie=false`). |
| HITL Reviews UI (v1.4+) | Editable KIE fields + Save/Approve; **`hitl_policy`** (`full`/`lite`/`off`). **v1.5**: review items persisted (`hitl_reviews`, `edited_fields`). **KIE validation failures only** — not table-mapping row review. |
| PDF Tools UI (v1.4) | Nav tab: merge / split / metadata. **`searchable` / `form-fill` API stubs** — not in UI; still post-v1.6 ([v1.5-roadmap.md](../architecture/v1.5-roadmap.md)). |
| 字段 bbox | KIE 字段与画布标注框 **未** 联动。 |
| 翻译 / 长文档 VL 问答 | 明确不在 1.0 / 1.0.1 范围。 |

## 运行与环境

| 限制 | 说明 |
|------|------|
| GPU | 生产级延迟建议 GPU；PP-StructureV3 + Qwen 串行占用显存，避免并行多 Job 抢 GPU。 |
| KIE 冷启动 | 首次 KIE 或 warmup 前 `kie.model_load_ms` 可达数十秒（视模型缓存路径而定）。 |
| 测试 | **Phase A** CI 不加载 Qwen/Paddle；端到端 KIE 效果依赖 **Cloud 手册** 回归，非全量 pytest。 |
| Live API tests | `test_live_api.py` skips when `:8000` is down; do not run full pytest alongside a live GPU server. Run KIE live test alone: `pytest tests/test_live_api.py::TestLiveInvoiceKie -s`. |

## 样例与文档

- `test_data/TestResult/` 为本地/云端导出目录（gitignore），**不**随仓库分发。
- 部分 `test_data/testfiles/` 样例仅供验收，使用时注意版权与隐私（勿提交真实证件）。

## 后续版本方向（post-v1.7.0）

- **v1.5 leftovers**：可搜索 PDF、AcroForm、Webhook 持久化、邮件 IMAP 独立服务 — [v1.5-roadmap.md](../architecture/v1.5-roadmap.md)。
- **Batch ZIP / Lite ZIP / 表格截图**：v1.6 明确不做；Batch ZIP 需单独体积/异步设计。
- **Recent-tasks UI**：后端可恢复，刷新页仍会丢 `currentTaskId`。
- **维护**：Playwright E2E P1/P2；文档漂移审计脚本（`004-doc-sync` 机制 5，暂不建）。

Cloud 验收：[MERGE_MAIN_v1.7_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.7_CLOUD_CHECKLIST.md)、[MERGE_MAIN_v1.6_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.6_CLOUD_CHECKLIST.md)、[MERGE_MAIN_v1.5_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.5_CLOUD_CHECKLIST.md)。

路线图：[v1.7-roadmap.md](../architecture/v1.7-roadmap.md)、[RELEASE_1.6_NOTES.md](./RELEASE_1.6_NOTES.md)、[v1.6-roadmap.md](../architecture/v1.6-roadmap.md)。

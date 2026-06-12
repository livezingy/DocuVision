# Known limitations

> Applies through **`main` @ v1.2.0** (multipage KIE + batch UI; Lite since `v1.0.1`).  
> Release notes: [RELEASE_1.1_NOTES.md](./RELEASE_1.1_NOTES.md) · Tracker: [KIE_TEST_RUN_TRACKER.md](../architecture/KIE_TEST_RUN_TRACKER.md)  
> Acceptance rules: [KIE_ACCEPTANCE_CRITERIA.md](../../backend/tests/KIE_ACCEPTANCE_CRITERIA.md).

## DocuVision Lite (since 1.0.1)

| Limit | Detail |
|-------|--------|
| No KIE | Lite does not run Qwen KIE or `view.fields`; use **Pro** for invoice / receipt / ID documents. |
| Raster tables | Image and scan PDF **Table Transformer** extraction is **frozen** by default (`RASTER_TABLES_FROZEN`); text OCR only on raster docs. |
| Born-digital PDF | Table extraction via pdfplumber / Camelot; see [lite-api.md](../architecture/lite-api.md). |
| Models | EasyOCR / optional Transformer weights under `packages/docuvision-core/models/` — bootstrap required on new hosts ([models/README.md](../../packages/docuvision-core/models/README.md)). |
| Batch | No batch API on Lite (`:8001`); use Pro batch API on `:8000` if needed. |
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
| KIE query fields（v1.1） | `kie_query_fields` **仅追加**内置 schema（最多 20 字段）；**002 不含 query 命中**；空 query 值非契约失败。无模板库、无 `document_type=custom` 全量 schema。见 [kie-custom-fields.md](../architecture/kie-custom-fields.md)。 |
| Batch Processing UI | v1.2+ Batch 标签页与汇总 CSV/JSON；仍为内存 batch，重启丢失。 |
| 字段 bbox | KIE 字段与画布标注框 **未** 联动。 |
| 翻译 / 长文档 VL 问答 | 明确不在 1.0 / 1.0.1 范围。 |

## 运行与环境

| 限制 | 说明 |
|------|------|
| GPU | 生产级延迟建议 GPU；PP-StructureV3 + Qwen 串行占用显存，避免并行多 Job 抢 GPU。 |
| KIE 冷启动 | 首次 KIE 或 warmup 前 `kie.model_load_ms` 可达数十秒（视模型缓存路径而定）。 |
| 测试 | **Phase A** CI 不加载 Qwen/Paddle；端到端 KIE 效果依赖 **Cloud 手册** 回归，非全量 pytest。 |
| Live API tests | `test_api.py` / `test_e2e.py` skip when `:8000` is down; do not run full pytest alongside a live GPU server. |

## 样例与文档

- `test_data/TestResult/` 为本地/云端导出目录（gitignore），**不**随仓库分发。
- 部分 `test_data/testfiles/` 样例仅供验收，使用时注意版权与隐私（勿提交真实证件）。

## 后续版本方向（post-v1.2.0）

- **v1.2.x / 维护**：Batch Excel 导出、Playwright E2E P0、CI Phase A 纳入 v1.2 pytest 列表（workflow 变更需维护者同意）。
- **v1.3 主线（P0）**：通用字段校验、`document_type=custom` / 模板持久化 — 见 [RELEASE_1.2_NOTES.md](./RELEASE_1.2_NOTES.md)。
- **P1**：自动 `document_type`、HITL、可搜索 PDF、邮件/webhook。
- **Lite**：无 KIE/query fields/Batch；仍仅 Pro。

路线图：[RELEASE_1.1_CHECKLIST.md](./RELEASE_1.1_CHECKLIST.md) §6、[RELEASE_1.2_CHECKLIST.md](./RELEASE_1.2_CHECKLIST.md)。

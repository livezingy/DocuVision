# Known limitations

> Applies through **`main` @ v1.3.0** (v1.2.1 maintenance + v1.3 P0 on same release train).  
> Release notes: [RELEASE_1.3.0_NOTES.md](./RELEASE_1.3.0_NOTES.md) · [RELEASE_1.2.1_NOTES.md](./RELEASE_1.2.1_NOTES.md)  
> Acceptance rules: [KIE_ACCEPTANCE_CRITERIA.md](../../backend/tests/KIE_ACCEPTANCE_CRITERIA.md).

## DocuVision Lite (since 1.0.1)

| Limit | Detail |
|-------|--------|
| No KIE | Lite does not run Qwen KIE or `view.fields`; use **Pro** for invoice / receipt / ID documents. |
| Raster tables | Image and scan PDF **Table Transformer** extraction is **frozen** by default (`RASTER_TABLES_FROZEN`); text OCR only on raster docs. |
| Born-digital PDF | Table extraction via pdfplumber / Camelot; see [lite-api.md](../architecture/lite-api.md). |
| Models | EasyOCR / optional Transformer weights under `packages/docuvision-core/models/` — bootstrap required on new hosts ([models/README.md](../../packages/docuvision-core/models/README.md)). |
| Batch | Lite batch API at `/api/v1/lite/batch` (table-only PDF, in-memory). Pro batch adds **Excel** export (v1.2.1+). |
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
| KIE query fields（v1.1） | `kie_query_fields` **仅追加**内置 schema（最多 20 字段）。**v1.3** 起支持 `document_type=custom` 与 YAML 模板库（MVP）；无字段 bbox 联动。见 [kie-custom-fields.md](../architecture/kie-custom-fields.md)。 |
| KIE validation（v1.3） | 启发式 date/currency 规则 + `kie_validation`；非 ground-truth 逐字校验；HITL 队列为内存 MVP。 |
| Batch Processing UI | v1.2+ Batch tab with aggregated CSV/JSON/**Excel**; in-memory batch, lost on restart. |
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

## 后续版本方向（post-v1.3.0）

- **v1.4（P1）**：table_areas ROI UI、完整 HITL 工作流、邮件/IMAP、垂直列映射模板。
- **v1.5+**：PDF 工具箱产品化、可搜索 PDF 质量、Batch 持久化。
- **维护**：Playwright E2E P1/P2（Batch tab）；CI Phase A 扩展测项（workflow 变更需维护者同意）。

Cloud 验收：[MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.2.1_CLOUD_CHECKLIST.md)、[MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.3.0_CLOUD_CHECKLIST.md)。

路线图：[RELEASE_1.3.0_NOTES.md](./RELEASE_1.3.0_NOTES.md)。

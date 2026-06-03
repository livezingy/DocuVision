# Release 1.0 — Known limitations

> Applies through tag **`v1.0.1`** (`v1.0.0` Pro baseline + Lite on `main`).  
> For acceptance rules see [KIE_ACCEPTANCE_CRITERIA.md](../../backend/tests/KIE_ACCEPTANCE_CRITERIA.md).

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

- KIE 对 PDF 默认 **栅格化第 1 页**；多页票据/证件策略未产品化（见 [kie.md](../architecture/kie.md) §6）。

### 字段精度

- **003** 仅校验 `name` + 18 位 `id_number` 格式，**不**验证校验位算法或与 ground-truth 逐字匹配。
- 住址、签发机关等长字段在复杂版式下可能漏抽或格式不一致。

## 产品 / 架构

| 限制 | 说明 |
|------|------|
| 自定义 fields | **未实现**；仅固定 5 类 YAML schema（**v1.1** 规划）。 |
| Batch Processing UI | 前端 placeholder，与后端 batch API 未完整产品化。 |
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

## 后续版本方向（非 1.0.1 承诺）

- v1.0.x：Lite polish, id_card sample / precision tweaks.
- **v1.1**：自定义 fields MVP（见总纲 §10） — **not** Lite-only releases.
- 并行低优：Batch UI、字段 bbox、多页 PDF KIE.

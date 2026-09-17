# Main — 轻量跟踪清单

> **注意**：本文档仅作备忘。若与仓库代码或 [docuvision-system-design.md](./docuvision-system-design.md) 冲突，**以代码与总纲为准**。  
> KIE 主线为 **Qwen2.5-VL**（`QwenDocumentKIEService`）；详见 [kie.md](./kie.md)。

## 仍值得跟进的主题（非阻塞）

- **KIE 增量质量**：复杂版式、id_card 精度；见 [KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md) 与 [KNOWN_LIMITATIONS.md](../release/KNOWN_LIMITATIONS.md)。
- **字段校验引擎**（post-v1.2 P0）：date/currency/regex + `quality` 扩展 — 建议 `feature/kie-field-validation`。
- **custom schema / 模板持久化**：超越 v1.1 extend-only `kie_query_fields`。
- **字段 bbox / 画布联动**：见 [kie.md](./kie.md) §1「不在本文」。
- **Playwright UI E2E**：规划见 [PRO_UI_E2E_PLAN.md](../../test_data/AutoTest/PRO_UI_E2E_PLAN.md)；脚手架见 [frontend/tests/e2e/](../../frontend/tests/e2e/)（`process-smoke.e2e.js`、`process-queue.e2e.js`）。

**v1.2.0 已交付（不再跟进为缺口）**：多页 PDF `kie_pages`、Batch Processing UI、`export.csv` / `export.json`。

**文档阅读顺序**：仓库实现 → [docuvision-system-design.md](./docuvision-system-design.md) → [kie.md](./kie.md) → [CLOUD_VALIDATION.md](./CLOUD_VALIDATION.md)（回归时）。

## v1.9 前端候选：巨函数切分（2026-09-17 保底摘录）

> 来源：v1.8.3 前端拆分设计稿 §12「附 B — 巨函数切分建议图」（local-only 草稿，已按 kernel
> 「用完即删」清理）。**行区间是 v1.8.1.0 快照、拆分后已失效且不可再复现**，故此处只保留
> 「函数 → 现归属模块 → 建议切分线」三项；动用前先用 `scripts/lint_file_size.py` 与模块文件重测。
> 本版（v1.8.3）明确**禁执行**巨函数切分——本表是 v1.9 输入，不是待办。

| 函数 | 现归属模块（2026-09-17 实测行数） | 建议切分线 |
|---|---|---|
| `pollTaskStatus` | `frontend/modules/pipeline/run.js`（474） | 轮询循环体 / 超时与错误分支 / 完成回调（`completeProcessing` 调用点）三段 |
| `startProcessing` | `frontend/modules/pipeline/run.js`（474） | 参数组装（options 合并）/ API 调用与错误处理 / 入队与 UI 渲染三段 |
| `updateContentFigures` | `frontend/modules/result-panels/figures.js`（305） | 数据遍历 / 卡片 DOM 构建（`renderFigureCard` 交界）/ 缩放与下载绑定 |
| `renderTableCard` | `frontend/modules/result-panels/tables.js`（347） | 表头 / 表体行循环 / 置信度徽章 / CSV 导出绑定四段 |
| `updateContentText` | `frontend/modules/result-panels/text.js`（226） | 按页分组（原分组注释所在处）/ 段落渲染 / 折叠判定三段 |
| `renderDocumentWithAnnotations` | `frontend/modules/overlay-render.js`（390） | SVG 构建 / 类型过滤与开关 / 交互绑定三段（`utils/geometry.js` 已在 B0 出仓） |

## 测试入口

```bash
cd backend
pytest tests/test_kie_pages_parse.py tests/test_kie_field_merge.py \
  tests/test_batch_export_service.py tests/test_document_page_count.py \
  tests/test_kie_field_metrics.py tests/test_kie_service.py \
  tests/test_kie_return_raw_contract.py tests/test_orchestrator_order.py -q
```

- 验收矩阵：[test_data/acceptance/doc_types.md](../../test_data/acceptance/doc_types.md)
- 合 main 门禁：[MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md](../../test_data/acceptance/MERGE_MAIN_v1.2_CLOUD_CHECKLIST.md)
- 云测步骤：[CLOUD_VALIDATION.md](./CLOUD_VALIDATION.md)（阶段 A 另见 GitHub Actions `kie-phase-a.yml`）
- 批次记录：[KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md)

## 历史

- 旧版本文曾描述「KIE 为 placeholder」「Batch UI 为 placeholder」「仅 PaddleNLP UIE」——均已过期。
- 2026-06-12：**v1.2.0** — 多页 KIE + Batch UI 已合并 `main`；合 main 门禁全通过。

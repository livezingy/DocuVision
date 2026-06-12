# Main — 轻量跟踪清单

> **注意**：本文档仅作备忘。若与仓库代码或 [智能文档处理系统设计方案.md](./智能文档处理系统设计方案.md) 冲突，**以代码与总纲为准**。  
> KIE 主线为 **Qwen2.5-VL**（`QwenDocumentKIEService`）；详见 [kie.md](./kie.md)。

## 仍值得跟进的主题（非阻塞）

- **KIE 增量质量**：复杂版式、id_card 精度；见 [KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md) 与 [KNOWN_LIMITATIONS.md](../release/KNOWN_LIMITATIONS.md)。
- **字段校验引擎**（post-v1.2 P0）：date/currency/regex + `quality` 扩展 — 建议 `feature/kie-field-validation`。
- **custom schema / 模板持久化**：超越 v1.1 extend-only `kie_query_fields`。
- **字段 bbox / 画布联动**：见 [kie.md](./kie.md) §1「不在本文」。
- **Playwright UI E2E**：规划见 [PRO_UI_E2E_PLAN.md](../../test_data/AutoTest/PRO_UI_E2E_PLAN.md)（脚手架已移除，待落地 P0 spec）。

**v1.2.0 已交付（不再跟进为缺口）**：多页 PDF `kie_pages`、Batch Processing UI、`export.csv` / `export.json`。

**文档阅读顺序**：仓库实现 → [智能文档处理系统设计方案.md](./智能文档处理系统设计方案.md) → [kie.md](./kie.md) → [CLOUD_VALIDATION.md](./CLOUD_VALIDATION.md)（回归时）。

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

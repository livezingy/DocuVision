# Main — 轻量跟踪清单

> **注意**：本文档仅作备忘。若与仓库代码或 [智能文档处理系统设计方案.md](./智能文档处理系统设计方案.md) 冲突，**以代码与总纲为准**。  
> KIE 主线为 **Qwen2.5-VL**（`QwenDocumentKIEService`）；详见 [kie.md](./kie.md)。

## 仍值得跟进的主题（非阻塞）

- **KIE 增量质量**：多页 PDF、复杂版式；Release 1.0 卡证 D 已测（2026-05-21）；见 [KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md) 与 [KNOWN_LIMITATIONS.md](../release/KNOWN_LIMITATIONS.md)。
- **Batch Processing UI**：仍为 placeholder，与后端 batch API 未完整打通。
- **字段 bbox / 画布联动**：见 [kie.md](./kie.md) §1「不在本文」。

**文档阅读顺序**：仓库实现 → [智能文档处理系统设计方案.md](./智能文档处理系统设计方案.md) → [kie.md](./kie.md) → [CLOUD_VALIDATION.md](./CLOUD_VALIDATION.md)（回归时）。

## 测试入口

```bash
cd backend
pytest tests/test_kie_field_metrics.py tests/test_kie_service.py \
  tests/test_kie_return_raw_contract.py tests/test_orchestrator_order.py -q
```

- 验收矩阵：[test_data/acceptance/doc_types.md](../../test_data/acceptance/doc_types.md)
- 云测步骤：[CLOUD_VALIDATION.md](./CLOUD_VALIDATION.md)（阶段 A 另见 GitHub Actions `kie-phase-a.yml`）
- 批次记录：[KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md)

## 历史

- 旧版本文曾描述「KIE 为 placeholder」或「仅 PaddleNLP UIE」——均已过期；当前以 Qwen 主线为准（2026-05 同步）。
- 2026-05-20：`e7dc4ab` 修复 PDF 发票 KIE；Cloud 7/7 KIE-ACCEPT-001/002 基线建立。

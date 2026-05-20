# Main — 轻量跟踪清单

> **注意**：本文档仅作备忘。若与仓库代码或 [智能文档处理系统设计方案.md](./智能文档处理系统设计方案.md) 冲突，**以代码与总纲为准**。  
> KIE 主线为 **Qwen2.5-VL**（`QwenDocumentKIEService`）；详见 [kie.md](./kie.md)。

## 仍值得跟进的主题（非阻塞）

- **KIE 效果**：整页图像 + VL 在复杂版式上的局限；主攻 Qwen prompt/schema 与云测 hit 率，见 [kie.md](./kie.md)、[KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md)。
- **`kie_confidence_source`**：成功路径取自 `kie_meta.engine`（默认 `qwen2.5-vl`）。

**文档阅读顺序（避免与过期备忘冲突）**：仓库实现 → [智能文档处理系统设计方案.md](./智能文档处理系统设计方案.md) → [kie.md](./kie.md)。

## 测试入口

- `pytest backend/tests/test_kie_service.py backend/tests/test_kie_return_raw_contract.py backend/tests/test_orchestrator_order.py`
- 验收矩阵：[test_data/acceptance/doc_types.md](../../test_data/acceptance/doc_types.md)
- 云测矩阵：[KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md)

## 历史

- 旧版本文曾描述「KIE 为 placeholder」或「仅 PaddleNLP UIE」——均已过期；当前以 Qwen 主线为准（2026-05 同步）。

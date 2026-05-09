# Main — 轻量跟踪清单

> **注意**：本文档仅作备忘。若与仓库代码或 [智能文档处理系统设计方案.md](./智能文档处理系统设计方案.md) 冲突，**以代码与总纲为准**。  
> KIE 已从占位实现升级为 **PaddleNLP UIE（`uie-m-base`）**；详见 [kie.md](./kie.md)。

## 仍值得跟进的主题（非阻塞）

- **KIE 效果**：整页 OCR 文本 + UIE 在复杂版式上的局限；可选第二引擎（Qwen2.5-VL、`uie-x-base` 等）见 [kie.md](./kie.md) §8。
- **`kie_confidence_source`**：当前 orchestrator 硬编码 `uie-m-base`；换引擎时需改为配置或枚举。
- **文档**：根目录 [DATA_FLOW_DIAGRAM.md](../DATA_FLOW_DIAGRAM.md) 为历史示意图，非当前实现权威来源。

## 测试入口

- `pytest backend/tests/test_kie_service.py backend/tests/test_orchestrator_order.py`
- 云测矩阵：[KIE_TEST_RUN_TRACKER.md](./KIE_TEST_RUN_TRACKER.md)

## 历史

- 旧版本文曾描述「KIE 为 placeholder」——该状态已过期（2026-05 同步）。

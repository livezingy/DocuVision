# 测试与验证（Testing）

> 唯一真源（kernel）。各 Agent 副本由 `scripts/sync_agent_rules.py` 生成，勿手改副本。
> 吸收原 Cursor `004-project` 的测试验证/测试落点/死代码/手工测试/交付 footer。Cloud 命令速查见 `006-cloud-testing.mdc`。

## pytest 边界
判据：**是否需要运行中的服务器或 GPU 推理**。不需 → 本机可跑；需 → Cloud。

| 范围 | 需服务器/GPU? | 在哪跑 | 助手本地能否 pytest |
|------|---------------|--------|---------------------|
| Pro 契约 mock（`test_kie_*.py` 等不加载 Paddle/Qwen） | 否 | 本机或 Cloud | **允许** |
| Pro live API（`test_live_api.py` 需 :8000） | 是 | Cloud | **禁止** |
| Core 契约 mock / 纯逻辑单测（不加载 Paddle） | 否 | 本机或 Cloud | **允许** |
| 前端 Vitest | 否 | 本机或 Cloud | 允许 |

- 本机 pytest 用 `D:\USERS\livez\Python\` 解释器；先确认测试不触发 `import paddle` / `import torch` / 连 :8000。
- 改后端/KIE/编排须给**可复制 Cloud 命令 + 期望**（针对需服务器/GPU 的部分）。
- **硬门槛**（须 Cloud 通过再继续）：KIE/编排/契约字段变更、发版合 main、用户明确要求。
- **Pro e2e 防遗忘**：新增/修改 Pro e2e 须挂进 CI 或登记到 `UI_VERIFICATION_MATRIX.md` 手工桶并标注"CI 不覆盖"。

## 测试落点（新建/扩展测试前）
1. 先搜后建：在对应 `tests/` 搜同模块是否已有 `test_*.py`。
2. 优先扩展同域文件；新建文件当：新契约域、独立 env gate、CI 已按文件名登记。
3. 分层：契约 mock（`backend/tests/test_kie_*.py`）/ Live GPU（`test_live_api.py`）/ 手动脚本 / Core。
4. Canonical 真源：逻辑断言以 pytest 为准；`kie/_smoke_check.py` 仅薄封装不重复断言。
5. 交付附建议 pytest 范围；本机跑过的 mock 可声称通过，**不得**声称本地 live API / GPU 已通过。

## 死代码检查
- 仅扫 touched 文件：未用 import、不可达分支、注释遗留块、已移除调用方但仍定义的符号。
- 移除符号/文件前全库搜索（code+tests+docs+`.github`），列出每处引用。
- 不删文件除非本轮明确授权（红线）；默认带证据报告候选。
- 刻意保留：Legacy Task API、Feature-flag 路径、Cloud 手动脚本。
- 本地静态检查：`ruff check backend/ packages/docuvision-core/ --select F401,F841`。

## 手工测试提醒
手动测试**仅含需云端启动服务器的测试**。每次改动应用代码或 UI 须附 Manual test scope：
1. 查 `UI_VERIFICATION_MATRIX.md` §4 列仍需手工项。
2. 写清：建议先跑的自动化（命令，区分本机 vs Cloud）/ 仍需云端手工测什么 / 验收标准。
3. E2E 绿仅缩小 Pro 已映射手工项；真实 GPU/KIE 不得因 E2E 绿省略。
4. 发版/合 main 提醒最小手工集。

## 交付 footer
diff 触及应用逻辑/UI/API 时并列五项：
**Adversarial check** | **Dead code check** | **Test placement** | **Manual test scope** | **Doc sync**

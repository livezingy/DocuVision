# 项目事实与测试验证

> 生成自 kernel `docs/agent-ops/core/`（environment, testing）。勿手改副本；改共享约束请编辑 kernel 后重跑 `scripts/sync_agent_rules.py`。
<!-- kernel-ref: environment.md:dc45a8094b72d500; testing.md:60cc84330c3588d5 -->

## 项目目标
DocuVision 旨在**可运行于云端服务器**，提供**试用/演示**，展示主要能力，可直接**投标 Upwork 部分工作**或符合用户基本需求并**接受定制**。开发优先级以"能否上云演示 + 能否投标/定制"为衡量。

## 关于项目
使用 Paddle 组件的仿 Azure 智能文档处理系统。`test_data/Azure/` 下为 Azure 风格参考 JSON；样例与验收矩阵见 `test_data/testfiles/`、`test_data/acceptance/`。

## 技术栈
- paddlepaddle-gpu 3.3.0 / paddleocr 3.3.2 / paddlex 3.3.12 / Qwen2.5-VL

## 开发环境
- 本地**未装** Paddle 及 Qwen2.5-VL 栈；本地以改代码、静态检查/审查为主，不跑 GPU/推理链。
- 本机 Python：`D:\USERS\livez\Python\python.exe`（3.11.6），可跑不需服务器/GPU 的 pytest（契约 mock、纯逻辑单测）。
- 工作流：本地改代码 → Git → 腾讯 Cloud Studio GPU 拉取验证；**Git 为真源**，云端不改业务代码。

## 项目结构
```
DocuVision/
├── backend/              # Pro FastAPI (:8000)
├── frontend/             # Pro SPA
├── packages/docuvision-core/
├── docs/                 # 索引见 docs/README.md
└── test_data/            # acceptance/testfiles/Azure/TestResult(gitignore)
```

## 目录卫生
- `.cursor/` 只放 `rules/*.mdc` 与 `skills/*.md`。禁止一次性脚本、临时产物、数据/权重/日志。
- 正确归属：一次性脚本 → `scripts/`；R&D 临时片段 → `docs/R&D/upwork/`（local only）；临时输出 → `test_data/TestResult/`（gitignore）。
- 发现遗留产物**带证据报告**，不擅删（删除属红线）。

## 按任务选读文档（勿全量通读）
| 任务 | 先读 |
|------|------|
| 总览/编排 | docuvision-system-design.md |
| KIE 契约/验收 | kie.md → CLOUD_VALIDATION.md |
| 发版/合 main | docs/release/README.md → MERGE_MAIN_v*.md |
| 样例/Batch | test_data/acceptance/README.md |
| UI 自动化 vs 手工 | UI_VERIFICATION_MATRIX.md |
| Trial 演示 | docs/demo/TRIAL_DEMO.md |

## pytest 边界
判据：**是否需要运行中的服务器或 GPU 推理**。不需 → 本机可跑；需 → Cloud。

| 范围 | 需服务器/GPU? | 在哪跑 | 助手本地能否 pytest |
|------|---------------|--------|---------------------|
| Pro 契约 mock（`test_kie_*.py` 等不加载 Paddle/Qwen） | 否 | 本机或 Cloud | **允许** |
| Pro live API（`test_live_api.py` 需 :8000） | 是 | Cloud | **禁止** |
| Core 契约 mock / 纯逻辑单测（不加载 Paddle） | 否 | 本机或 Cloud | **允许** |
| 前端 Vitest | 否 | 本机或 Cloud | 允许 |

- 本机 pytest 用 `D:\USERS\livez\Python\` 解释器；先确认测试不触发 `import paddle` / `import torch` / 连 :8000。
- **stub 的作用域（P-023）**：测试需要 stub 重依赖（`paddle` / `cv2` / `torch`）时，**按该文件是否在 Phase A CI
  清单**决定：**清单内必须作用域化**——fixture 用 `monkeypatch.setitem`，模块加载期用 `unittest.mock.patch.dict`；
  **禁止**在模块级写 `sys.modules[...]`。清单外（`kind: full`）可用模块级，但仍推荐作用域化。
  理由：pytest 在**收集期**就 import 全部测试模块，而 Phase A 是**单进程共享会话**，模块级 stub 会让邻居的
  `pytest.importorskip("paddle")` 环境闸门误判"本机已装 Paddle"——轻则误红（撞上闸门间接保护的 import），
  重则**静默少跑**（覆盖消失而无人报警）。机检：`scripts/test_registry_audit.py` 的 `check_stub_scope()`
  （覆盖全部 `backend/tests/**`，模块级 `sys.modules[...]` 赋值 = ERROR）。
- 改后端/KIE/编排须给**可复制 Cloud 命令 + 期望**（针对需服务器/GPU 的部分）。
- **硬门槛**（须 Cloud 通过再继续）：KIE/编排/契约字段变更、发版合 main、用户明确要求。
- **Pro e2e 防遗忘**：新增/修改 Pro e2e 须挂进 CI 或登记到 `UI_VERIFICATION_MATRIX.md` 手工桶并标注"CI 不覆盖"。

## 测试落点（新建/扩展测试前）
1. 先搜后建：在对应 `tests/` 搜同模块是否已有 `test_*.py`。
2. 优先扩展同域文件；新建文件当：新契约域、独立 env gate、CI 已按文件名登记。
3. 分层：契约 mock（`backend/tests/test_kie_*.py`）/ Live GPU（`test_live_api.py`）/ 手动脚本 / Core。
4. Canonical 真源：逻辑断言以 pytest 为准；`kie/_smoke_check.py` 仅薄封装不重复断言。
5. 交付附建议 pytest 范围；本机跑过的 mock 可声称通过，**不得**声称本地 live API / GPU 已通过。

## 测试登记口径（新测试必登记）
- 新增 `backend/tests/**/test_*.py` **必须**同步在 `backend/tests/test_registry.json` 登记一条：`kind` ∈
  `phase-a-ci`（Phase A CI 列表在跑）/ `live-gpu`（需 :8000 活服务器）/ `manual-script`（REPL 手动）/
  `full`（本机或云端全量）。**删除测试文件时一并删除条目**（无 `retired` 态，历史由 git 承担）。
- 登记表是机检唯一真源：`scripts/audit_agent_ops.py` **check 4** 双向对账（未登记文件 / 幽灵条目 /
  与 `kie-phase-a.yml` Phase A 列表不一致，见 `scripts/test_registry_audit.py`）。漏登记 = audit 红。
- 全量 pytest 走 `backend/pytest.ini` 的 `--continue-on-collection-errors`：单个 collection error 不再
  中断其余用例（P-008：曾致 430 用例全灭），但仍以非零码退出——容错不掩盖错误。
- **把测试加进 Phase A CI 清单时的验证义务（P-023）**：本机验证必须跑**该命令的完整文件清单**，不许只跑单文件
  ——跨文件污染（stub 作用域、`sys.modules` 污染）**只在整表运行时暴露**（P-023：首版只跑单文件全绿，CI 才炸）。

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

# 环境事实（Environment）

> 唯一真源（kernel）。各 Agent 副本由 `scripts/sync_agent_rules.py` 生成，勿手改副本。
> 吸收原 Cursor `004-project` 的项目目标/技术栈/环境/结构/目录卫生/选读部分。

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

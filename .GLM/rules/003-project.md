# 项目事实与测试分层（GLM）

> 同步自 `.cursor/rules/004-project.mdc` + `004-delivery.mdc` + `004-doc-sync.mdc`。
> 冲突时以 `.cursor/rules/` 为准；本文件仅 GLM 沙箱用。
<!-- sync: 2026-09-06 -->

## 环境
- 本地（GLM 沙箱与用户本机）**无 GPU**：只改代码 + 跑纯逻辑/契约 pytest。
- GPU 栈在腾讯 Cloud Studio；工作流：本地改 → git → 云拉取验证。**Git 为真源**。
- 技术栈：paddlepaddle-gpu 3.3.0 / paddleocr 3.3.2 / paddlex 3.3.12 / Qwen2.5-VL。
- 本机唯一可信 Python：`D:\USERS\livez\Python\python.exe`（3.11.6）。

## 测试分层（先搜后建）
| 层 | 位置 | 本地可跑 |
|----|------|----------|
| 纯逻辑/契约 mock | backend/tests/test_*.py | ✅（GLM 必须全绿） |
| 引擎/GPU 集成 | test_live_api.py、云 checklist | ❌ Cloud Studio |
| UI E2E | frontend/tests/e2e（Playwright） | ❌ 云/本机浏览器 |

- 改后端/KIE/编排须给可复制 Cloud 命令 + 期望（见 006-cloud-testing）。
- 硬门槛（须 Cloud 通过再继续）：KIE/编排/契约字段变更、发版合 main、用户明确要求。
- Pro e2e 防遗忘：新增/修改 Pro e2e 须挂进 CI 或登记到 UI_VERIFICATION_MATRIX.md 手工桶。

## 交付 footer（diff 触及应用逻辑/UI/API 时必须）
并列五项：**Adversarial check | Dead code check | Test placement | Manual test scope | Doc sync**
- Adversarial check：方案何时不成立（至少 1 条反例）
- Dead code check：touched 文件未用 import / 不可达分支 / 遗留符号
- Test placement：先搜后建，落点同域文件还是新建，本机可跑 vs Cloud
- Manual test scope：本机自动化命令 + Cloud 手工项 + 验收标准
- Doc sync：见下方文档同步机制 1

## 文档同步（强制，防漂移）
- 机制 1：改契约/编排/API 时 footer 必须声明 Doc sync，三选一：
  - `updated <doc> §<节>` —— 已同步
  - `N/A（未触及任何 living 契约）` —— 显式声明
  - `drift: <doc> 仍写旧 <字段/端点>，待修` —— 记录漂移
- 机制 2：文档归属表（改哪个模块→同步哪个文档），见 `.cursor/rules/004-doc-sync.mdc`
- 机制 3：有 pytest 的契约，测试是权威，`.md` 是派生视图
- 机制 4：living doc 顶部标"最近对照"行，发版/合 main 时刷新
- 新增/重命名 docs/ 文档时更新 docs/README.md 索引

## 目录卫生
- 运行时目录（uploads/ outputs/ debug/ backend/data/）不进 git。
- docs/R&D/** 除 README 外 local only。
- `.cursor/` 只放 rules/*.mdc 与 skills/*.md，不放入一次性脚本/临时产物。

## 规则文件结构（.cursor/rules/，2026-09-04 拆分后）
| 文件 | 触发 | 内容 |
|------|------|------|
| 001-general.mdc | always | 通用约束、红线、对抗审查 |
| 002-python.mdc | globs *.py | Python 规范 |
| 003-git.mdc | 按需 | Git/Actions 规范 |
| 004-project.mdc | always | 项目目标、技术栈、环境、结构、目录卫生、按任务选读文档、pytest 边界 |
| 004-delivery.mdc | globs 代码 | 测试落点、死代码、手工测试、交付 footer |
| 004-doc-sync.mdc | globs docs/代码 | 文档同步机制 1-5、生命周期、README 格式 |
| 005-code-language.mdc | always | 代码语言编码 |
| 006-cloud-testing.mdc | 按需 | Cloud 验证速查 |
| 007-official-source-first.mdc | always | 官方依据优先 |

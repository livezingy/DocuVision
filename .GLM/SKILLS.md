# GLM 会话技能（DocuVision）

## 启动检查表（每次会话）
1. 读 `.GLM/rules/001` 与 `003`（通用 + 项目事实）
2. `git status` + `git branch --show-current`：确认在正确分支、了解未提交改动
3. `git log --oneline -5`：了解最近脉络
4. 按任务分流（下表）

## 任务分流
| 任务 | 动作 |
|------|------|
| 纯逻辑/契约改动 | 本地改 + 本地 pytest 全绿 + 小步 commit |
| GPU 依赖改动 | 本地改 + mock 单测 + 在交付文档写 Cloud 验证步骤与验收标准 |
| 前端改动 | node --check + 契约不变则不跑 E2E；改动触及 UI 时列入云手测清单 |
| 试用/演示 | 读 rules/004-trial.md 与 docs/demo/TRIAL_REMOTE_60MIN.md |

## 交付动作（每轮改动收尾）
1. 本地测试全绿（能跑的范围）
2. series commit（conventional 格式）
3. 交付说明含 footer 五项（见 rules/003）
4. patch 包：git format-patch 基线..HEAD + APPLY.md（见 rules/002 交付协议）

## 禁止
- 未经确认 push / 改 workflow / 改 .env
- 在 Cloud Studio 以外宣称 GPU 功能"已验证"

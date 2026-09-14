# GLM 会话技能（DocuVision）

## 启动检查表（每次会话）
1. 读 `.GLM/rules/001-general.md`（通用约束）+ `003-project.md`（项目事实，kernel 生成）
2. `git status` + `git branch --show-current`：确认分支与未提交改动
3. `git log --oneline -5`：了解最近脉络
4. 按任务分流（下表）

## 任务分流
| 任务 | 读 / 做 |
|------|---------|
| 纯逻辑/契约改动 | rules/003（测试分层）+ 本地 pytest 全绿 + 小步 commit |
| GPU 依赖改动 | rules/003 + mock 单测 + 交付文档写 Cloud 验证步骤 |
| 前端改动 | node --check + 触及 UI 时列云手测清单 |
| 试用/演示 | rules/004-trial.md + docs/demo/TRIAL_REMOTE_60MIN.md |
| 审查任务 | rules/005-review.md（产出分级/证据/依据三要素） |

## 交付与红线
- footer 五项见 rules/003；patch 交付协议见 rules/002。
- 红线（push / workflow / .env / 宣称 GPU 已验证）见 rules/001。

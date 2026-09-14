# .GLM — GLM 助手工作规则（DocuVision 试用开发）

> 适用于 GLM 在本仓库的会话。共享约束唯一真源在 `docs/agent-ops/core/`；
> `001-general.md` 与 `003-project.md` 由 `scripts/sync_agent_rules.py` 生成（勿手改）；
> `002-git.md`、`004-trial.md`、`005-review.md` 为 GLM 专属。

## rules/

| 文件 | 何时读 | 内容 |
|------|--------|------|
| [001-general.md](rules/001-general.md) | 每次会话 | 通用约束（kernel: constraints，生成） |
| [002-git.md](rules/002-git.md) | 改代码前 | 分支、提交、patch 交付协议（GLM 专属） |
| [003-project.md](rules/003-project.md) | 每次会话 | 环境事实、测试分层、文档同步（kernel: environment/testing/doc-sync，生成） |
| [004-trial.md](rules/004-trial.md) | 试用相关任务 | 试用资产（auth/figures/gt-diff/bench/reset）（GLM 专属） |
| [005-review.md](rules/005-review.md) | 审查任务 | 审查产出三要素（分级/证据/依据）+ 审查红线（GLM 专属） |

## SKILLS.md

会话启动流程见 [SKILLS.md](SKILLS.md)。

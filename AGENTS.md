# AGENTS.md — 多 Agent 规则体系入口

> 本仓库由多个 AI 助手（Cursor / GLM / Codebuddy / VSCode）协作开发。
> 共享约束的唯一真源在 `docs/agent-ops/core/`；各 Agent 目录为**生成式薄壳**，勿手改。

## 快速导航
| 目标 | 路径 |
|------|------|
| 唯一真源（kernel） | `docs/agent-ops/core/constraints.md` / `environment.md` / `testing.md` / `doc-sync.md` |
| Agent 花名册 | `docs/agent-ops/core/agents.md` |
| 生成各 Agent 薄壳 | `python scripts/sync_agent_rules.py` |
| 审计漂移（kernel-ref + doc） | `python scripts/audit_agent_ops.py` |
| 稳态运维（巡检 + KPI） | `docs/agent-ops/operations.md` |
| 待决决策清单 | `docs/R&D/PENDING.md` |

## 规则层次
1. **共享约束（唯一真源）** → `docs/agent-ops/core/`（4 文件，约 60 行/个软上限）。
2. **各 Agent 副本（生成）** → `.cursor/rules/`、`.GLM/rules/`、`.workbuddy/rules/`，由 sync 脚本派生并写 `kernel-ref` 哈希。
3. **Agent 特有（本地，不参与 sync）** → 各目录的非生成文件（如 GLM `002-git` patch 协议、`004-trial`；Cursor `002-python`/`003-git`）。

## 修改规则的正确姿势
- 改共享约束 → 改 `docs/agent-ops/core/` 对应文件 → 跑 `python scripts/sync_agent_rules.py` 派生副本 → 同时 commit kernel 与副本。
- **勿手改**各 Agent 的生成副本：会被 sync 覆盖，且 `audit_agent_ops.py` 会报 DRIFT。
- 新 Agent 加入 → 在 `agents.md` 登记角色，并在 `sync_agent_rules.py` 映射表补一条。

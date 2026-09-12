# Agent 花名册（Agent roster）

> 唯一真源（kernel）。数据化描述各 Agent 在本仓库的角色、目录与规则归属。

## 角色矩阵
| Agent | 目录 | 角色 | 规则形态 |
|-------|------|------|----------|
| Cursor | `.cursor/rules/` | 主力（开发） | 生成式薄壳 + 专属细则 |
| ZCode | `AGENTS.md`（仓库根）+ kernel 直读 | 审查（review / trial） | 无副本（AGENTS.md 原生加载） |
| Codebuddy | `.codebuddy/` | 低频（回顾 / PENDING 跟踪） | 生成式薄壳 |
| VSCode | `.vscode/` | 编辑器（非规则 Agent） | 配置（settings/tasks） |

## 职责边界
- **Cursor**：主力开发。规则最全，含专属细则 `002-python`（PEP8/类型/单测）、`003-git`（GitHub Actions 策略）、`005`/`007`/`008`（已并入 kernel，文件留索引）。
- **ZCode**：审查 + trial 开发。规则经 AGENTS.md → kernel 直读，无生成副本；审查规范见 `docs/agent-ops/review.md`。GLM 沙箱 patch 协议已退役，存档于 `docs/agent-ops/glm-sandbox-patch.md`。
- **Codebuddy**：低频辅助。会话回顾 + 跟踪 `docs/R&D/PENDING.md` 待决结论。
- **VSCode**：编辑器配置（解释器指向 `D:\USERS\livez\Python\python.exe`、tasks），不承载规则。

## kernel 映射
| core 文件 | Cursor | Codebuddy |
|-----------|--------|-----------|
| `constraints.md` | `001-general.mdc` | `001-general.md` |
| `environment.md` | `004-project.mdc` | `004-project.md` |
| `testing.md` | `004-project.mdc` | `004-project.md` |
| `doc-sync.md` | `009-doc-sync.mdc` | `009-doc-sync.md` |

## 生成与审计
- 生成薄壳：`python scripts/sync_agent_rules.py`（写 kernel-ref 哈希，幂等）。
- 审计漂移：`python scripts/audit_agent_ops.py`（校验 kernel-ref + doc drift，挂 PR→main CI）。

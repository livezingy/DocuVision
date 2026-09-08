# Agent 花名册（Agent roster）

> 唯一真源（kernel）。数据化描述各 Agent 在本仓库的角色、目录与规则归属。

## 角色矩阵
| Agent | 目录 | 角色 | 规则形态 |
|-------|------|------|----------|
| Cursor | `.cursor/rules/` | 主力（开发） | 生成式薄壳 + 专属细则 |
| GLM (ZCode) | `.GLM/rules/` | 审查（patch 交付 / trial） | 生成式薄壳 + 专属协议 |
| Codebuddy | `.workbuddy/` | 低频（记忆 / 回顾） | 生成式薄壳 + memory |
| VSCode | `.vscode/` | 编辑器（非规则 Agent） | 配置（settings/tasks） |

## 职责边界
- **Cursor**：主力开发。规则最全，含专属细则 `002-python`（PEP8/类型/单测）、`003-git`（GitHub Actions 策略）、`005`/`007`/`008`（已并入 kernel，文件留索引）。
- **GLM**：审查 + trial 开发。专属 `002-git`（沙箱→patch→本机 `git am` 协议）、`004-trial`（试用资产）。
- **Codebuddy**：低频辅助。长期记忆 `.workbuddy/memory/`（含 R&D 结论）+ 会话回顾。
- **VSCode**：编辑器配置（解释器指向 `D:\USERS\livez\Python\python.exe`、tasks），不承载规则。

## kernel 映射
| core 文件 | Cursor | GLM | Workbuddy |
|-----------|--------|-----|-----------|
| `constraints.md` | `001-general.mdc` | `001-general.md` | `001-general.md` |
| `environment.md` | `004-project.mdc` | `003-project.md` | `004-project.md` |
| `testing.md` | `004-project.mdc` | `003-project.md` | `004-project.md` |
| `doc-sync.md` | `009-doc-sync.mdc` | `003-project.md` | `009-doc-sync.md` |

## 生成与审计
- 生成薄壳：`python scripts/sync_agent_rules.py`（写 kernel-ref 哈希，幂等）。
- 审计漂移：`python scripts/audit_agent_ops.py`（校验 kernel-ref + doc drift，挂 PR→main CI）。

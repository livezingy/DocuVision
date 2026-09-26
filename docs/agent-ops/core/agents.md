# Agent 花名册（Agent roster）

> 唯一真源（kernel）。数据化描述各 Agent 在本仓库的角色、目录与规则归属。

## 角色矩阵
| Agent | 目录 | 角色 | 规则形态 |
|-------|------|------|----------|
| Cursor | `.cursor/rules/` | 主力（开发） | 生成式薄壳 + 专属细则 |
| Codebuddy | `.codebuddy/` | 低频（回顾 / PENDING 跟踪） | 生成式薄壳 |
| VSCode | `.vscode/` | 编辑器（非规则 Agent） | 配置（settings/tasks） |

## 职责边界
- **Cursor**：主力开发。规则最全，含专属细则 `002-python`（PEP8/类型/单测）、`003-git`（GitHub Actions 策略）。
- **ZCode：已退役（2026-09-26，用户裁决）**——预计半年内不使用。同批清理：工作目录 `.zcode/` 与 `.gitignore` 规则删除、PENDING P-006 移除（去向见 PENDING 历史行）。审查职责**改为"当轮承接者按 `docs/agent-ops/review.md` 执行"**，不再绑定某个 Agent；GLM 沙箱 patch 协议存档仍在 `docs/agent-ops/glm-sandbox-patch.md`（不再有活跃引用）。回归方式：在「角色矩阵」补一行，按其规则形态接入并在本文件登记。
- **Codebuddy**：低频辅助。会话回顾 + 跟踪 `docs/R&D/PENDING.md` 待决结论。
- **VSCode**：编辑器配置（解释器指向 `D:\USERS\livez\Python\python.exe`、tasks），不承载规则。

## kernel 映射
| core 文件 | Cursor | Codebuddy |
|-----------|--------|-----------|
| `constraints.md` | `001-general.mdc` | `001-general.md` |
| `environment.md` | `004-project.mdc` | `004-project.md` |
| `testing.md` | `004-project.mdc` | `004-project.md` |
| `doc-sync.md` | `009-doc-sync.mdc` | `009-doc-sync.md` |
| `routing.md` | `010-routing.mdc` | `010-routing.md` |
| `frontend.md` | `011-frontend.mdc` | `011-frontend.md` |

## 生成与审计
- 生成薄壳：`python scripts/sync_agent_rules.py`（写 kernel-ref 哈希，幂等）。
- 审计漂移：`python scripts/audit_agent_ops.py`（kernel-ref + doc drift + 墓碑门禁 + PENDING 滞留 **DOC-3** + module-map 对账 check 3 + 测试登记 check 4/5 + 单测 pin **E2**；`--selftest` 解析回归；挂 PR→main CI，**每个 PR 必跑**——`pull_request.paths` 已于 2026-09-20 移除）。

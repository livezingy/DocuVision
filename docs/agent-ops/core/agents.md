# Agent 花名册（Agent roster）

> 唯一真源（kernel）。数据化描述各 Agent 在本仓库的角色、目录与规则归属。

## 角色矩阵
| Agent | 目录 | 角色 | 规则形态 |
|-------|------|------|----------|
| Cursor | `.cursor/rules/` | 主力（开发） | 生成式薄壳 + 专属细则 |
| Codebuddy | `.codebuddy/` | 低频（回顾 / PENDING 跟踪） | 生成式薄壳 |
| VSCode | `.vscode/` | 编辑器（非规则 Agent） | 配置（settings/tasks） |
| ZCode | `.zcode/rules/` | 验证（回归 2026-10-28） | 生成式薄壳 |

## 职责边界
- **Cursor**：主力开发。规则最全，含专属细则 `002-python`（PEP8/类型/单测）、`003-git`（GitHub Actions 策略）。
- **ZCode**：验证角色（2026-10-28 回归，用户裁决「按ZCode已回归执行」）：门禁编排执行、verdict 唯一持有、观测与报告（运行时三角色，声明见本区末尾）。2026-09-26 曾退役（同批清理史见 git 历史）；GLM 沙箱 patch 协议存档仍在 `docs/agent-ops/glm-sandbox-patch.md`（不再有活跃引用）。审查职责仍按 `docs/agent-ops/review.md` 由当轮承接者执行，不绑定具体 Agent。
- **Codebuddy**：低频辅助。会话回顾 + 跟踪 `docs/R&D/PENDING.md` 待决结论。
- **VSCode**：编辑器配置（解释器指向 `D:\USERS\livez\Python\python.exe`、tasks），不承载规则。
- **运行时三角色（2026-10-27 立项，P-042 一期）**：本地 Agent 按职责分为编排（读契约、派 step、收 verdict）、执行（按执行包实施、产 PR）、验证（跑门禁、读数、唯一持有 verdict；观测与报告归此角色）。执行与验证独立——执行方自报数字无效。三角色为运行时分工非工具实体；实体映射已登记：ZCode=验证（2026-10-28 回归，见角色矩阵）；执行/编排映射待用户裁决。验证例程真源 = kernel `verification.md`。

## kernel 映射
| core 文件 | Cursor | Codebuddy | ZCode |
|-----------|--------|-----------|-------|
| `constraints.md` | `001-general.mdc` | `001-general.md` | `001-general.md` |
| `environment.md` | `004-project.mdc` | `004-project.md` | `004-project.md` |
| `testing.md` | `004-project.mdc` | `004-project.md` | `004-project.md` |
| `doc-sync.md` | `009-doc-sync.mdc` | `009-doc-sync.md` | `009-doc-sync.md` |
| `routing.md` | `010-routing.mdc` | `010-routing.md` | `010-routing.md` |
| `frontend.md` | `011-frontend.mdc` | `011-frontend.md` | `011-frontend.md` |
| `verification.md` | `012-verification.mdc` | `012-verification.md` | `012-verification.md` |

## 生成与审计
- 生成薄壳：`python scripts/sync_agent_rules.py`（写 kernel-ref 哈希，幂等）。
- 审计漂移：`python scripts/audit_agent_ops.py`（kernel-ref + doc drift + 墓碑门禁 + PENDING 滞留 **DOC-3** + module-map 对账 check 3 + 测试登记 check 4/5 + 单测 pin **E2**；`--selftest` 解析回归；挂 PR→main CI，**每个 PR 必跑**——`pull_request.paths` 已于 2026-09-20 移除）。

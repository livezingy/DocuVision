# AGENTS.md — 多 Agent 规则体系入口

> 本仓库由多个 AI 助手（Cursor / ZCode / Codebuddy / VSCode）协作开发。
> 共享约束的唯一真源在 `docs/agent-ops/core/`；各 Agent 目录为**生成式薄壳**，勿手改。

## 快速导航
| 目标 | 路径 |
|------|------|
| 唯一真源（kernel） | `docs/agent-ops/core/constraints.md` / `environment.md` / `testing.md` / `doc-sync.md` |
| Agent 花名册 | `docs/agent-ops/core/agents.md` |
| 生成各 Agent 薄壳 | `python scripts/sync_agent_rules.py` |
| 审计漂移（kernel-ref + doc） | `python scripts/audit_agent_ops.py` |
| 稳态运维（巡检 + KPI） | `docs/agent-ops/operations.md` |
| 代码审查规范 | `docs/agent-ops/review.md` |
| 待决决策清单 | `docs/R&D/PENDING.md` |

## 规则层次
1. **共享约束（唯一真源）** → `docs/agent-ops/core/`（4 文件，约 60 行/个软上限）。
2. **各 Agent 副本（生成）** → `.cursor/rules/`、`.codebuddy/rules/`，由 sync 脚本派生并写 `kernel-ref` 哈希。
3. **Agent 特有（本地，不参与 sync）** → 各目录的非生成文件（如 Cursor `002-python`/`003-git`）。
4. **ZCode** → 无副本目录，原生加载本文件并直读 kernel（历史 GLM 规则已退役；patch 协议存档见 `docs/agent-ops/glm-sandbox-patch.md`）。

## ZCode 会话规则

### 红线（逐字摘自 kernel `constraints.md` §自主边界，以 kernel 为准；命中先问）
- 删除文件、目录或 git 历史（本轮明确授权的除外）。
- 修改 `.env`、密钥、token、CI/CD 配置（含 `.github/workflows/**`）。
- 数据库 schema 变更或数据迁移。
- git push、git rebase、git reset --hard、强制推送。
- 安装新的全局依赖或修改系统配置。
- 公开发布（npm publish、部署生产、发文章等）。
- 本机无 GPU：不宣称 GPU / 云端功能"已验证"；GPU 依赖改动交付 mock 单测 + Cloud 验证步骤。

### 任务分流
| 任务 | 读 / 做 |
|------|---------|
| 纯逻辑/契约改动 | kernel `testing.md`（测试分层）+ 本地 pytest 全绿 + 小步 commit |
| GPU 依赖改动 | mock 单测 + 交付文档写 Cloud 验证步骤与验收标准 |
| 前端改动 | `node --check`；触及 UI 时列云手测清单 |
| 试用/演示 | `docs/demo/TRIAL_REMOTE_60MIN.md` + `scripts/trial/trial_preflight.py` |
| 审查任务 | `docs/agent-ops/review.md`（分级/证据/依据三要素） |

## 修改规则的正确姿势
- 改共享约束 → 改 `docs/agent-ops/core/` 对应文件 → 跑 `python scripts/sync_agent_rules.py` 派生副本 → 同时 commit kernel 与副本。
- **勿手改**各 Agent 的生成副本：会被 sync 覆盖，且 `audit_agent_ops.py` 会报 DRIFT。
- 新 Agent 加入 → 在 `agents.md` 登记角色，并在 `sync_agent_rules.py` 映射表补一条。

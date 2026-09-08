# Agent-ops 稳态运维（Operations）

> 稳态运维 = 周期巡检 + KPI。审计框架见 `scripts/audit_agent_ops.py`（统一 kernel-ref + doc drift）。

## 周期巡检
| 触发 | 频率 | 命令 |
|------|------|------|
| 本地手动 | 改 core 后 / 每周 | `python scripts/audit_agent_ops.py` |
| PR→main CI | 每次 PR | 挂 `agent-ops-audit` workflow（见下） |
| 定期 schedule | 每周 | CI cron（可选） |

## KPI
| 指标 | 定义 | 目标 |
|------|------|------|
| audit 通过率 | PR→main 中 audit 全绿占比 | 100% |
| 漂移检出率 | kernel-ref 漂移被 CI 检出的占比 | 100% |
| 待决决策滞留 | `docs/R&D/PENDING.md` 待确认结论数 | 趋向 0 |
| 记忆回流及时率 | 结论 N 天内固化到 `MEMORY.md` / `architecture/` | 100% |

## 巡检动作
1. 跑 `python scripts/audit_agent_ops.py`。
2. 有 ERROR（kernel-ref 漂移）→ 跑 `python scripts/sync_agent_rules.py` 重新派生，commit kernel + 副本。
3. 有 WARN（doc-drift）→ 修文档引用或登记 `docs/R&D/PENDING.md`。
4. 检查 `PENDING.md` 待决项，确认后晋升 / 移除。

## CI 挂载（需授权）
audit 挂 PR→main 的 CI，需新建 `.github/workflows/agent-ops-audit.yml`（属 CI 变更，需用户授权后创建）。

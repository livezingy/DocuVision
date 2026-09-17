# Agent-ops 稳态运维（Operations）

> 稳态运维 = 周期巡检 + KPI。审计框架见 `scripts/audit_agent_ops.py`（kernel-ref + doc drift + module-map 对账 check 3 + 测试登记对账 check 4；解析器回归 `--selftest`）。

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
1. 跑 `python scripts/audit_agent_ops.py --selftest`（解析器回归，15 例）+ `python scripts/audit_agent_ops.py`。
2. ERROR `agent-rules`（kernel-ref 漂移）→ 跑 `python scripts/sync_agent_rules.py` 重新派生，commit kernel + 副本。
3. ERROR `module-map`（check 3）→ 按 module-map §6 断言定位：路径缺失改文档 / 计数漂移同步 §2-§3 的端点数与文件数 / 门禁符号缺失修 §5 行 / 登记缺失补 `docs/README.md` 或 owning 附表 `docs/agent-ops/doc-sync-ownership.md`。
4. ERROR `test-registry`（check 4）→ 按输出补登记 `backend/tests/test_registry.json`（或删幽灵条目）；WARN 表示 Phase A CI 列表与登记不一致，需人工裁决（实现 `scripts/test_registry_audit.py`）。
5. WARN `doc-drift` → 修文档引用或登记 `docs/R&D/PENDING.md`；WARN `module-map`（A5 新鲜度）→ 发版后刷新 module-map 头部「最近对照」。
6. 检查 `PENDING.md` 待决项，确认后晋升 / 移除。

## CI 挂载（已落地）
`.github/workflows/agent-ops-audit.yml`（2026-09-16 起）：pull_request + push(main) 触发；
步骤 = `--selftest` → 全量 audit；paths 覆盖 `docs/agent-ops/**`、`.cursor/rules/**`、`.codebuddy/rules/**`、
`scripts/sync_agent_rules.py`、`scripts/audit_agent_ops.py`、`AGENTS.md`、`.gitignore`，以及 module-map 对账输入
`backend/app/routers/**`、`frontend/modules/**`、`scripts/frontend_domain_map.json`、`docs/architecture/**`、`docs/README.md`。

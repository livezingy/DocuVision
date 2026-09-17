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
步骤 = `--selftest` → 全量 audit；`pull_request.paths`（2026-09-17 按"改动能否翻转判决"补全）覆盖
`docs/agent-ops/**`、`.cursor/rules/**`、`.codebuddy/rules/**`、`AGENTS.md`、`.gitignore`、
`DEVELOPMENT.md`、`CHANGELOG.md`（A5 新鲜度输入）、**`scripts/**`**（粗粒度：audit 自身实现模块、
A0 查符号的全部门禁脚本、`frontend_domain_map.json`）、module-map 输入 `backend/app/routers/**`、
`frontend/modules/**`、`docs/architecture/**`、`docs/README.md`，以及 check 4 的两个输入
`backend/tests/**`、`.github/workflows/kie-phase-a.yml`。
注：`paths` 只作用于 `pull_request`——`push` 到 main 无过滤，audit 每次必跑。

## CI 成本与配额（2026-09-17 实测，含 ESLint 接入后的口径）

**现状：公开仓（`livezingy/DocuVision`，PUBLIC）→ 标准 runner 的 Actions 分钟数免费、不计费**，
所以"配额"**不是**本仓当下的约束。真正的约束是**并发槽位**（公开仓免费计划约 20 个并发 job，
本仓每次 PR push 占 3-4 个 → 需 ~5-7 个 PR 同时推才可能碰到，单人仓可忽略）与**信号质量**。

单次时长实测（`gh run list` 的 createdAt→updatedAt；每条 workflow = 1 个 job，
GitHub 按 job 计费且**向上取整到 1 分钟**）：

| workflow | 实测 | 备注 |
|---|---|---|
| Agent-ops Audit | 11-12s | 纯 stdlib，零安装 |
| Lint（Python 四门禁） | 12-16s | 2026-09-17 之前的口径 |
| Lint（**含 ESLint 块**） | **19s**（2026-09-17 首次实测：run 35195278470 / job 105116921946，job 16s。ESLint 块只 +6s = `setup-node` 1s + `npm ci` **4s**（**冷** npm 缓存，且无 Actions 缓存）+ `eslint .` 1s —— 远低于预估的 30-60s） | 本仓**唯一的 node 依赖面**，也是唯一新增的"与代码无关"失败源（npm registry 抖动 / 缓存键变化） |
| KIE Phase A | 21-27s | 已含 `cache: pip` 的依赖安装；push 事件默认 `skipped`（`[run ci]` 闸门生效） |

**触发即重算：仓库转为私有**（或迁到带配额的 CI）→ 一次 PR push 跑 3-4 个 job = **3-4 计费分钟**；
Free 计划 2,000 min/月 ≈ **500-650 次 PR push/月**。届时的取舍顺序：① 按"改动能否翻转判决"逐条收窄
`paths`；② 把 `scripts/**` 一类宽路径改回精确清单；③ **最后**才考虑砍 ESLint 步骤——它是唯一能看到
死代码/未用绑定的门禁（F1-F7、C1-C9 都是结构性的），砍它等于退回 P-010 之前。
另：若给 `main` 加 branch protection 并勾选 required checks，噪声成本立刻从"注意力"变成"合并延迟"
（每个 PR 至少等最慢的一条），那时更该精确化 `paths` 而不是全开。

**已处置（2026-09-17，用户授权）**：三个 workflow 的 7 处 action 已升级到声明 node24 的 major ——
`actions/checkout@v4 → v5`（3 处）、`actions/setup-python@v5 → v6`（3 处）、`actions/setup-node@v4 → v5`（1 处）。
依据：官方 changelog（「Deprecation of Node 20 on GitHub Actions runners」2025-09-19，编辑注记至 2026-08-25）
给出 **2026-06-16 runner 默认切 Node24、2026-09-23 移除 Node20**；移除后仍声明 `node20` 的 action **将无法工作**
（过渡期 `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION` 届时失效）。升级前已用 `gh api` 读各 tag 的 `action.yml`
逐个核实 `runs.using`（v4/v5 旧 major = `node20`，上述新 major = `node24`）。
变更面仅 3 个 workflow、均为裸调用或常规参数（无 `fetch-depth` / submodules / token 覆盖）。

**噪声控制（比配额更真实）**：三条 workflow 均已开 `concurrency.cancel-in-progress: true`；
`pull_request` 均按 `paths` 过滤；`kie-phase-a.yml` 另有 push 的 job 级 `[run ci]` 闸门；
**`main` 无 branch protection**（`gh api .../protection` → 404），即检查是**提示而非阻塞**——
所以噪声的主要形态是"红了没人被迫修 → 信号贬值"。唯一有效的原则是：
**让每条 workflow 只在"改动能翻转其判决"时触发**，而不是"全开 + 习惯性忽略"。

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
1. 跑 `python scripts/audit_agent_ops.py --selftest`（2026-09-20 实测输出 `all 16 checks passed`）+ `python scripts/audit_agent_ops.py`。
   （此前记的"15 例"与实际输出不一致——以命令输出为准；`--selftest` 含 check 4 的登记回归。）
2. ERROR `agent-rules`（kernel-ref 漂移）→ 跑 `python scripts/sync_agent_rules.py` 重新派生，commit kernel + 副本。
3. ERROR `module-map`（check 3）→ 按 module-map §6 断言定位：路径缺失改文档 / 计数漂移同步 §2-§3 的端点数与文件数 / 门禁符号缺失修 §5 行 / 登记缺失补 `docs/README.md` 或 owning 附表 `docs/agent-ops/doc-sync-ownership.md`。
4. ERROR `test-registry`（check 4）→ 按输出补登记 `backend/tests/test_registry.json`（或删幽灵条目）；WARN 表示 Phase A CI 列表与登记不一致，需人工裁决（实现 `scripts/test_registry_audit.py`）。
5. WARN `doc-drift` → 修文档引用或登记 `docs/R&D/PENDING.md`；WARN `module-map`（A5 新鲜度）→ 发版后刷新 module-map 头部「最近对照」。
6. 检查 `PENDING.md` 待决项，确认后晋升 / 移除。
7. e2e 门禁回归（改 e2e / 白名单 / 前端渲染时）：`python scripts/check_e2e_allowlist.py --selftest` +
   `python scripts/check_e2e_allowlist.py`（module-map §5 的 **E1**）；白名单条目超 90 天会 WARN，
   棘轮上限可用 `--update` 只降不升地收紧。

## CI 挂载（已落地）
`.github/workflows/agent-ops-audit.yml`（2026-09-16 起）：pull_request + push(main) 触发；
步骤 = `--selftest` → 全量 audit。
**2026-09-20（branch protection 引导）**：`pull_request.paths` **整体移除**（lint.yml 同日同款）——
`lint` / `e2e` / `agent-ops-audit` 已设为 main 的 **required status checks**（ruleset
`main-branch-protection`），而 path 过滤的 workflow 在不匹配的 PR 上**不会运行**，其必需检查会停在
"Expected"、PR 永远无法合并。2026-09-17 的"改动能否翻转判决"paths 清单保留在 P-011/本文历史里，
作为**将来 CI 转计费时重新收窄**的参照（届时需改用"必需检查上报"的替代机制，如汇总 job）。

`lint.yml`（2026-09-20 起为**两个 job**）：`lint` job = 4 个 stdlib 门禁 + **E1 e2e 白名单/钉死**
（`check_e2e_allowlist.py`，stdlib、零安装）+ ESLint；`e2e` job = Playwright 14 用例
（浏览器缓存 → `--with-deps chromium` → `test:e2e` → 工件上传）。E1 刻意留在 stdlib 段内：
即使将来某次 `paths`/job 条件跳过了 `e2e` job，白名单防腐化的规则仍会被评估。

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
| Lint（**含 ESLint 块**） | **19s**（2026-09-17 首次实测：run 35195278470 / job 105116921946，job 16s。ESLint 块只 +6s = `setup-node` 1s + `npm ci` **4s**（**冷** npm 缓存，且无 Actions 缓存）+ `eslint .` 1s —— 远低于预估的 30-60s）。**2026-09-20 复测 18s**（run 35485821396：新增 E1 步骤后仍为同量级） | 与 2026-09-20 新增的 `e2e` job 并列为本仓两个 node 依赖面，也是新增的"与代码无关"失败源（npm registry 抖动 / 缓存键变化） |
| KIE Phase A | 21-27s | 已含 `cache: pip` 的依赖安装；push 事件默认 `skipped`（`[run ci]` 闸门生效） |
| Lint（**`e2e` job**，2026-09-20 起） | **44s**（首次实测：run **35485821396** / job **106011880370**，2026-09-20T03:09:04→03:09:48。分步：`npm ci` ~2s（npm 缓存命中）+ 缓存查询 1s + **`install --with-deps chromium` 19s**（冷缓存，含下载 Chrome for Testing 145 / ffmpeg / headless shell）+ 套件 **7.6s（14 passed，2 workers）** + 工件上传 1s + post 步骤 ~7s。首次运行已写入浏览器缓存（键 = lockfile 哈希）→ **第二次实测 32s**（run 35486645577，2026-09-20T03:28:12→03:28:44，浏览器缓存命中） | 第二个 node 依赖面。浏览器缓存键跟 `frontend/package-lock.json`（`@playwright/test` 版本由 lock 钉死，故缓存不会跨版本复用）；实测冷缓存的代价只有 19s——**原先 1.5-3 min 的估算高了一个数量级**。**已知成本**：job 挂在 `lint.yml` 内、无 job 级 `paths`，所以 backend-only 的 PR 也会跑它（44s 冷 / 32s 热，均非分钟级）；替代方案是拆独立 workflow（`paths: ["frontend/**"]`），为保持 workflow 数量不增而未选 |

**触发即重算：仓库转为私有**（或迁到带配额的 CI）→ 一次 PR push 跑 **4-5 个 job = 4-5 计费分钟**
（2026-09-20 起 `lint.yml` 自带 `lint` + `e2e` 两个 job；同日实测：`lint` 18s / `e2e` 44s / `audit` 7s，
wall time 48s，故"计费分钟"完全由**向上取整到 1 分钟/job**决定，与真实耗时无关）；Free 计划 2,000 min/月 ≈
**400-500 次 PR push/月**。
届时的取舍顺序：① 按"改动能否翻转判决"逐条收窄 `paths`；② 把 `scripts/**` 一类宽路径改回精确清单，
并让 `e2e` job 只在 `frontend/**` 变化时触发（拆独立 workflow 或 paths-filter）；
③ **最后**才考虑砍 ESLint / e2e 步骤——ESLint 是唯一能看到死代码/未用绑定的门禁（F1-F7、C1-C9 都是
结构性的），e2e 是唯一能看到"DOM 断言全绿但页面抛错"的门禁（P-016 实测 8 条 pageerror 藏在 14/14 里）。
另：若给 `main` 加 branch protection 并勾选 required checks，噪声成本立刻从"注意力"变成"合并延迟"
（每个 PR 至少等最慢的一条），那时更该精确化 `paths` 而不是全开。

**已处置（2026-09-17，用户授权）**：三个 workflow 的 7 处 action 已升级到声明 node24 的 major ——
`actions/checkout@v4 → v5`（3 处）、`actions/setup-python@v5 → v6`（3 处）、`actions/setup-node@v4 → v5`（1 处）。
依据：官方 changelog（「Deprecation of Node 20 on GitHub Actions runners」2025-09-19，编辑注记至 2026-08-25）
给出 **2026-06-16 runner 默认切 Node24、2026-09-23 移除 Node20**；移除后仍声明 `node20` 的 action **将无法工作**
（过渡期 `ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION` 届时失效）。升级前已用 `gh api` 读各 tag 的 `action.yml`
逐个核实 `runs.using`（v4/v5 旧 major = `node20`，上述新 major = `node24`）。
变更面仅 3 个 workflow、均为裸调用或常规参数（无 `fetch-depth` / submodules / token 覆盖）。
**已处置（2026-09-20，用户授权）—— runner 镜像期限**：push `67d3083` 的三个 job 各带 1 条注解，内容
**不是** Node 弃用（node24 升级确认无告警），而是 runner 预告「The ubuntu-latest label will migrate to
Ubuntu 26 beginning **October 19, 2026**」（actions/runner-images#14748）。影响面是 `setup-python` 与
Playwright 的 `install --with-deps`（apt 依赖）都跑在 runner 镜像上，被动切换当天可能变成一次无关的红。
**处置**：三个 workflow 的 `runs-on` 由 `ubuntu-latest` **固定为 `ubuntu-24.04`**（lint.yml 两个 job、
agent-ops-audit.yml、kie-phase-a.yml），把"被动漂移"改成"显式升级"。
**剩余触发（常驻）**：升级到 Ubuntu 26 应当是主动动作 —— 先本地/分支验证 `--with-deps` 在该镜像可用
（或等 Playwright 声明支持），再改这个 pin；届时可与 P-010/P-011 的配额重算合并做一次 CI 巡检。
**已验证（2026-09-20，push `3eb8c2c` 的 run 35486645577）**：`ubuntu-24.04` 下两个 job 均绿
（`lint` **15s** / `e2e` **32s**，浏览器缓存命中），且**四个 check-run 的注解数全部为 0** ——
即那条 ubuntu-latest 迁移提醒确实因固定镜像而消失，Node 弃用告警也仍为 0。

**已验证（2026-09-17，push `ebbf825` 的 run）**：`Lint` run 35198052898 绿、job 14s、12 个步骤全 success，
**run 上不再出现 Node 20 弃用注解**；`Agent-ops Audit` 同一 push 绿（15s）；`KIE Phase A` 被触发但 job
按 `[run ci]` 闸门 **skipped**（符合设计）。三个 workflow 的 YAML 已用 `yaml.safe_load` 复核：步骤数与
`uses:` 版本均符合预期。

**噪声控制（比配额更真实）**：三条 workflow 均已开 `concurrency.cancel-in-progress: true`；
`kie-phase-a.yml` 另有 push 的 job 级 `[run ci]` 闸门。
**2026-09-20 起（用户裁决，选项 b"完整保护"）**：`main` 由 ruleset `main-branch-protection` 保护
（required PR + required checks `lint` / `e2e` / `agent-ops-audit`，禁删除 / 禁 force-push，无 bypass）——
检查从**提示**变成**阻塞**，直推 main 被 ruleset 拒绝，一切改动走 feature 分支 + PR。
因此"让每条 workflow 只在改动能翻转其判决时触发"的旧原则对 **PR** 不再适用（与 required checks 不兼容，
见上文），对 **push** 仍然成立；每个 PR 的等待成本 = 最慢一条检查（实测 `e2e` 45s 热）。

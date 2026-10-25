# Agent-ops 稳态运维（Operations）

> 稳态运维 = 周期巡检 + KPI。审计框架见 `scripts/audit_agent_ops.py`（kernel-ref + doc drift + 墓碑门禁 + **PENDING 滞留 DOC-3** + module-map 对账 check 3 + 测试登记对账 check 4/5（stub 作用域）；解析器回归 `--selftest`）。

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
| 待决决策滞留 | `docs/R&D/PENDING.md` 中 `status: open` / `status: decided` 的条目数（由 DOC-3 校验的元数据推导，**非手写统计**） | 趋向 0 |
| services 冻结边计数 | `scripts/service_dependency_allowlist.json` 在册条目数（由 `python scripts/lint_services.py` 输出与 JSON 推导，**本表不留数字副本**；只减不增，新增条目 = 红线先问） | 趋向 0 |
| 结论到晋升时长 | `status: landed` 的条目自 `since` 起 **90 天**内晋升 `docs/architecture/`，或改列 `retained` 并写明保留理由（阈值与 DOC-3 的 WARN 同源，超期即未达标） | 100% |

> 口径更正（2026-09-26，P-025）：原「记忆回流及时率」引用 `MEMORY.md`——**该文件全仓不存在**，指标无从测量；原「待决决策滞留」亦无测量方式。
> 两条现已改为上表口径，事实源 = PENDING 各条的 `> status:` 元数据（门禁 DOC-3），本表不再出现无法测量的指标。

## 巡检动作
1. 跑 `python scripts/audit_agent_ops.py --selftest` + `python scripts/audit_agent_ops.py`。
   （**本行刻意不记用例数**——历史上"15 例"/"16 例"两次都随用例增删变旧；以命令输出为准。`--selftest` 覆盖 check 4 登记回归、
   check 5 stub 作用域与 **DOC-3 元数据/滞留回归**。）
2. ERROR `agent-rules`（kernel-ref 漂移）→ 跑 `python scripts/sync_agent_rules.py` 重新派生，commit kernel + 副本。
3. ERROR `module-map`（check 3）→ 按 module-map §6 断言定位：路径缺失改文档 / 计数漂移同步 §2-§3 的端点数与文件数 / 门禁符号缺失修 §5 行 / 登记缺失补 `docs/README.md` 或 owning 附表 `docs/agent-ops/doc-sync-ownership.md`。
4. ERROR `test-registry`（check 4）→ 按输出补登记 `backend/tests/test_registry.json`（或删幽灵条目）；WARN 表示 Phase A CI 列表与登记不一致，需人工裁决（实现 `scripts/test_registry_audit.py`）。
5. WARN `doc-drift` → 修文档引用或登记 `docs/R&D/PENDING.md`；WARN `module-map`（A5 新鲜度）→ 发版后刷新 module-map 头部「最近对照」。
6. 检查 `PENDING.md` 待决项（状态见各条 `> status:` 元数据；`landed`/`decided` 超 90 天会以 **DOC-3 WARN** 列出）→
   `landed` 晋升 `architecture/` 或改列 `retained`（写明理由）；`decided` 收口（转 `landed`/`retained` 或拆出在途
   义务）；已结移除；并按规定在 commit / PR 留一行 `Promotion-check: …`（P-025）。
7. e2e 门禁回归（改 e2e / 白名单 / 前端渲染时）：`python scripts/check_e2e_allowlist.py --selftest` +
   `python scripts/check_e2e_allowlist.py`（module-map §5 的 **E1**）；白名单条目超 90 天会 WARN，
   棘轮上限可用 `--update` 只降不升地收紧。
8. 单测门禁回归（增删 `frontend/tests/unit/**` 时）：`python scripts/unit_suite_pin.py --selftest` +
   `python scripts/unit_suite_pin.py`（module-map §5 的 **E2**）；有意的用例增减须**同 commit** 更新
   `scripts/unit_suite_pin.json`，删除文件或用例跳过会被拦下（vitest 本身在 `lint` job 内跑，这两类都不会让它变红）。
9. services 结构门禁（增删/搬移 `backend/app/services/**` 或改 import 时）：`python scripts/lint_services.py --selftest` +
   `python scripts/lint_services.py`（module-map §5 的 **S1a/S1b/S1c/A2b**，经 audit 接线）。ERROR → 按输出定位：
   层/域误置改代码，真需跨域边走 Placement X 判据（登记 = **红线先问**）；WARN 冻结边逾期/已消解 →
   移除条目收棘轮。**P-037 已于 2026-10-25 收口**（冻结边 14→0、allowlist 空、>500 巨户清零且
   `file_size_allowlist` pins 同日清零——空表 = 全员受 500 全局预算约束，新增 pin 只应出现在
   拆分在途的临时豁免上）。

## 清账批次（正式动作，触发式而非周期式）

> 巡检动作第 6 步是「看告警处置单条」；**清账批次是批量的状态收口**，且是唯一允许编辑 `docs/R&D/PENDING.md`
> 的**写入通道**（**单写入通道纪律**，kernel `doc-sync.md`；任何 Agent 均可充当清账批次会话，但必须走本节程序）。
> 纪要类 local-only 文件的删除同样适用（见该文件 §R&D 索引同批）。

- **触发（两个条件同时满足，缺一跳过）**：
  ① **版本收口**（一次收口 PR / tag）；② **累计 ≥2 条 eligible**。
  eligible = 有结论可晋升 living doc ／ 已结可移除 ／ 正文埋有应迁出的触发式残留 ／ 正文该压缩（retained/decided
  流水账），命中任一即算。其中可机检自动计数的是 DOC-3 滞留 WARN（`landed`/`decided` 超 90 天，audit 输出
  `[INFO] eligible clearing candidates: N`）；其余三类属语义判断，由清账会话按本清单人工识别。刻意**不设周期**
  （"每 N 天"无据，且会产生无米之炊的空批次）。
- **清单（批次内逐项执行）**：
  1. **状态迁移**：`landed` → 晋升 `docs/architecture/` 或改列 `retained`（写明理由）；已结条目移除并在抬头历史行留去向。
  2. **保留理由核查**：`retained` 条目的理由是否仍成立；埋在正文里的触发式残留迁出为独立 `open` 条目（真实工作项
     不得藏在保留理由段——P-025 禁止的形态）。
  3. **压缩**：retained / decided 长流水账正文裁到「保留理由 + 判例 + 指针（git 历史 / CHANGELOG / living doc）」；
     decided 条目压缩前必须先迁出在途义务，不丢真实工作项。
  4. **同批更新 runs 索引**：删除了 `docs/R&D/runs/` 文件就同步删 `docs/R&D/README.md` 索引行，并本地跑
     `python scripts/docs_refs_audit.py --check-rnd-index` 复核（runs 被 gitignore，死链 CI 看不见）。
  5. **留痕**：commit / PR 正文写一行 `Promotion-check: <n> eligible (P-xxx…) -> promoted|deferred`（零条也写，P-025）。
  6. **历史段上限**：PENDING 抬头「历史」段只保留**最近 5 批**清账的结案记录（N 由当轮清账会话按需自定），
     更早的结案明细进 git 历史——历史行同为 append-only 膨胀面，不设上限会缓慢累积。
- **PR 纪律**：清账 PR 保持**单一目的**（只动 PENDING / README / runs 索引），先 rebase 再合。
- **会话判据（reviewer 驳回依据）**：一次对 PENDING 的编辑**算清账批次**，当且仅当 = 触发条件满足（版本收口 +
  ≥2 eligible）+ 走完本清单 + PR 单一目的。三者缺一的 PENDING 编辑（含顺手改条目正文、非收口窗口的 status
  迁移）都应被 review 驳回并改走正规批次——本纪律无机制前置拦截，全靠此处事后把关。

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

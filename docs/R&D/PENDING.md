# 待决决策清单（PENDING）

> 每次会话开始时检查本文件——可见"有 N 条结论待确认"。
> 结论确认后：晋升 `docs/architecture/`，然后从本清单移除。

## 待确认（本区共 **18** 条）

- **机检索引（勿手改）**：`P-008` `P-011` `P-015` `P-017` `P-018` `P-020` `P-023` `P-024` `P-025` `P-026` `P-027` `P-033` `P-034` `P-035` `P-036` `P-037` `P-038` `P-039`
- **状态是单一事实源**：每条标题下首行的 `> status: <open|decided|landed|retained> · since: YYYY-MM-DD`。
  状态计数与 90 天滞留 WARN 由 `scripts/audit_agent_ops.py`（门禁 **DOC-3**）输出——**本抬头不再手写统计副本**
  （P-019 单源化教训（该条已结并移除，见上行历史）：数字副本必漂，清账前此处曾把 5 条已结条目计在"待裁决"）。
- **状态语义**：`open` = 未裁决 ｜ `decided` = 已裁决、尚有未完成动作或待验证 ｜ `landed` = 已落地、结论待晋升审视
  （`since` 起超 90 天 = WARN，提示晋升 `docs/architecture/` 或改列 `retained`）｜ `retained` = 已结且**有意**保留在清单
  （保留理由必须写在条目内）。
- **晋升检查点**：写本文件或 CHANGELOG 时必须回答一轮「本轮有无条目达到可晋升/可移除标准」，并在 commit message /
  PR 正文留下 `Promotion-check: <n> eligible … -> promoted|deferred`（零条也写）——规则见 kernel `doc-sync.md`。
- 历史（**只保留最近 5 批**结案记录；更早批次 = 2026-09-25 及以前（含 P-001 已按用户裁决移除、P-012 已结并晋升 `docs/architecture/v1.7-roadmap.md`）——明细见 git 历史）：
**P-022 已结并晋升 `docs/architecture/doc-governance.md`**（2026-09-25，走本抬头「结论确认 → 晋升 → 移除」正规流程；门禁登记为 `module-map.md` §5 的 **DOC-1 / DOC-2**；此前索引漏登 P-022 亦随该次修正）；
**P-007 / P-010 / P-013 / P-016 已结并移除**（2026-09-25 清账批次，同走「结论确认 → 晋升 → 移除」流程；结论分别由 `docs/architecture/v1.9-roadmap.md` §Scope S1 ｜ `docs/agent-ops/operations.md` §CI 成本与配额 + CHANGELOG ｜ `docs/agent-ops/doc-sync-ownership.md` 主表+脚注 2 ｜ kernel `frontend.md` 已知 gap 条目承载，明细证据仍在 CHANGELOG 与 git 历史）；
**P-006 已按用户裁决移除**（2026-09-26，**非**晋升路径：其主体 `.zcode/` 目录连同 `.gitignore` 的 `.zcode/plans/` 规则一并删除，预计半年内不使用该工具，后续要用再立项；该目录从未入库，故无 git 历史可回溯）；
**P-032 已结并晋升 `docs/architecture/evidence-layer.md`**（2026-10-07，走「结论确认 → 晋升 → 移除」正规流程：该文即 `backend/app/services/evidence/**` 的 owning living doc，text-first 契约在其 §2 模块表（`grounding.py`/`text_first.py`/`pico.yaml` 三行）+ §4.1 text-first 分支（旗标语义 / 抽取输入 / 信任判据 / `evidence.stats` 键）；Cloud 复验读数（E1 3/3 逐字命中 / E5 10=10 / E7 620 passed）记入该文「最近对照」行，明细证据仍在 CHANGELOG `[Unreleased]` 与 git 历史；两项后续项经用户裁决删除，故无遗留动作）；
**P-002 / P-021 / P-028 / P-029 / P-030 / P-031 已结并移除**（2026-10-07 清账批次，同走「结论确认 → 晋升 → 移除」流程；结论现载体：P-002 → `docs/architecture/provenance-review.md` §4/§5 ｜ P-021 → `docuvision-system-design.md` §3.2–§3.4 + `ocr-quality-harness.md` §5 + `docs/demo/QUALITY_CASE_STUDY.md` + 契约单测 ｜ P-028 → `provenance-review.md` §4.4 ｜ P-029 → `evidence-layer.md` + `capability-card-v1.12` 行 13 ｜ P-030 → `kie.md` §4/§4.2 + `docuvision-system-design.md` §7.1/§7.8 ｜ P-031 → `kie.md` §4.2 + `KIE_ACCEPTANCE_CRITERIA.md` §Required key hints；明细证据仍在 CHANGELOG 与 git 历史）；另 **P-021 的 F1 判例**（allowlist 内文件按记录值钉死，改前先查 allowlist）已随本批次并入 `DEVELOPMENT.md` 第 1 条；
**P-015 / P-020 / P-023 由 `landed` 改列 `retained`**（2026-10-07，用户裁决；保留理由已写入各条首行——分别保留 LFS 否决理由与重议触发 / harness 证据附件与规模偏差 / stub 作用域判例）；
**P-014 / P-019 已结并移除**（2026-10-16 清账批次，走「结论确认 → 晋升 → 移除」正规流程；两条均**零 living doc 反引**——除 CHANGELOG 与 git 历史外，无任何追踪文档引用其编号。P-014 的退役等价性证据（`boot_sequence` 计数与事实源同 commit，否则 C3 红）现载体 = `scripts/check_frontend_baseline.py` 的数量一致性基线 + ESLint `no-undef`（已随必需检查 `lint` 运行）；P-019 的「描述性数字副本必漂 ⇒ 单源化」教训已由 **P-025** 明文继承并落门禁 **DOC-3**（`module-map.md` §5）；明细证据仍在 CHANGELOG 与 git 历史）；
**P-033 由 `landed` 改列 `retained`**（2026-10-16，用户裁决；保留理由已写入该条首行——E3 边界「只覆盖该生成器三个输出」是 `module-map.md` §5 E3 行的判据出处）；
**P-027 / P-018 由 `decided` 改列 `retained`；P-026 核定保留；迁出 2 条触发式残留为 P-035 / P-036；压缩 P-008 / P-017 / P-027 正文**（2026-10-16 **清账批次（第二批）**：① P-027 / P-018 的在途义务经处置/迁出后清空（P-027 另经用户裁决**移除**「BR 葡语解锁触发」与「R1 taxonomy 转用例」两项工作项）⇒ 收口为 `retained`，保留理由 + 判例 + 指针已写入各条首段；② P-026 保留理由核查通过（`doc-governance.md` 仍以其作正控先例），状态不变；③ 原埋藏在 P-027 / P-011 / P-008 正文的两条触发式残留迁出为独立 `open` 条目 **P-035**（分岔 C 优先级重排）与 **P-036**（CI 触发范围与 paths 重收窄，P-008 · P-011 合并项）；④ P-008 / P-017 / P-027 长流水账压至「保留理由 / 待决三要素 + 判例 + 指针」，正文裸 commit hash 一并消除；⑤ `runs/P027/` 保留依据由「在途义务未清」改为「被 tracked 文档反引」，P-034 落「实施读数走 `runs/` 不进正文」口径。明细证据仍在 CHANGELOG 与 git 历史）

### P-008 · v1.9 候选：孤儿模块与悬空测试的巡检门禁（2026-09-16，FRONT-C1 走查衍生）
> status: retained · since: 2026-09-26
- **保留理由（2026-10-16 清账批次压缩；原 ~120 行流水账 → 本节，明细进 git 历史）**：本组暴露并机检化了两个同型缺口——**「声明的东西是否真被接上」没有巡检**（孤儿模块 / 悬空测试）；其机检落点（**F7 / T1 / A6 / E1 / E2 / C9**）全部在册，且被 `docs/architecture/module-map.md` §5 与 kernel 反引 ⇒ 条目不可移除。保留本条目是为了存**两份判例**（下两条）。
- **判例 1 · 「声明但从未运行」**：① **孤儿模块可达性 = lint F7**（`modules/**` 必被 `app.js` / `index.html` / 其它脚本 import；例外登记 `frontend_domain_map.json` 的 `known_orphans`，每条附 `added` + evidence，**只登记不接线**）。首发抓到 `floating-progress.js`（D11），P-010 清账又暴露 `utils/geometry.js`（其唯一生产 importer 是 app.js 的**死 import**）；**2026-09-20（v1.9 S4）用户裁决两个孤儿全部退役**（各自单独 commit、事实源同 commit 同步；`known_orphans` 现为空，A6 告警未触发）。② **悬空测试 = audit check 4 / T1**（`backend/tests/test_registry.json` ↔ 递归磁盘 `test_*.py` ↔ `kie-phase-a.yml` Phase A 列表三向对账；未登记 / 幽灵条目 / CI 跑到未登记或 `kind≠phase-a-ci` = ERROR，CI 侧漂移 = WARN）。③ **collection 容错** = `backend/pytest.ini` 的 `--continue-on-collection-errors`（仍以非零码退出；现载体 = kernel `testing.md`）。
- **判例 2 · 「跳过即静默降覆盖」**：单测侧与 e2e 侧各一道防缩水门禁——**E2** = `scripts/unit_suite_pin.py` + `unit_suite_pin.json`（`frontend/tests/unit/**/*.test.js` 的文件数 / 用例声明数必须等于 pin；`it.skip` / `it.todo` / `test.skip` / `describe.skip` / `describe.todo` 出现即 ERROR，空套件 fail-closed；经 `audit_agent_ops.py` import 接线、复用必需 check ⇒ **零 CI 配置改动**；首版 pin = **7 files / 67 cases / 0 skips**）；**E1** = `scripts/check_e2e_allowlist.py`（白名单**下沉为数据** `frontend/tests/e2e/expected-errors.json`「字面量子串、**禁正则元字符**」+ 棘轮 `scripts/e2e_allowlist_ratchet.json` 只降不升 + 套件钉死 `scripts/e2e_suite_pin.json`；**E1 刻意留在 `lint` job 的 stdlib 段** ⇒ 即使将来 paths 跳过 `e2e` job，白名单规则仍被评估）。
- **已结的其余面（原为残留，均已处置；勿再引用旧表述）**：① `main` 由 ruleset `main-branch-protection` 保护——**必需 PR** + 必需检查 `lint` / `e2e` / `agent-ops-audit` + 禁删除 / 禁 force-push、**无 bypass**（对管理员同样生效）；前置引导（PR 触发去 paths 化）先于 ruleset 落 main，避免「必需检查停在 Expected」的自锁。② **口径 (a)「运行时错误门禁」已落地并成为阻塞检查**（`lint.yml` 新增 `e2e` job：`checkout → python 3.11 → node 22 + npm ci → actions/cache@v5 → install --with-deps chromium → npm run test:e2e`，CI 下 `workers: 2` / `retries: 0` 不变；`helpers/coverage.js` 断言本次运行 `pageerror` / `console.error` 为空、`EXPECTED_ERRORS` **刻意从空开始**、`PW_COVERAGE=0` 为完整逃生口）；口径 (b) 模块加载门禁**不单独设**（与 F7 高度重叠，C7 已查 MIME）、(c) 监听器覆盖门禁**否决**（覆盖率不是正确性属性，且改测试会改变红绿）。③ **A6 孤儿登记时效**（`known_orphans` 每条须带 ISO `added`，超 `ORPHAN_STALE_DAYS = 90` 仍在册 = WARN；`frontend_coupling.py::check_orphan_staleness`，`--selftest` case16 覆盖 stale / 无日期 / 新鲜三态）——**A6 即 DOC-3 的形态先例**。④ **C9 注入保真**（`app.js` 传给每个 `initXxx` 的 key 集合必须**恰好等于**模块体实际读取的 `deps.*` 集合：缺 = 留空桩 / 多 = 死注入 / 签名非空且非 `deps` = fail-closed；`frontend_coupling.py::check_injection_keys`，随 `check_frontend_baseline.py` 进 `lint.yml`）——**刻意不用 JSDoc/tsc、也不用快照数据**（快照形态在「模块新增依赖而数据未更新」时仍全绿，恰是要防的失效形态），**也不走 vitest**（vitest 当时不在 CI，只保护本机）。
- **保留的已知 gap（用户裁决 / 规则本意，不再列待决）**：**F6 保持名字级**弱断言（2026-09-26 用户裁决 accepted；JSDoc + `tsc --allowJs --checkJs --noEmit` 实测 272 错**无一是类型系统独有信号**，评估见 roadmap §S3）；**F7 只判可达性、不判接线**为规则本意，其运行时覆盖度报告（候选 B MVP = `frontend/tests/e2e/helpers/coverage.js` 打点 + `coverage-report.js` 汇总，**报告不是门禁**）已落地。
- **指针**：`docs/architecture/module-map.md` §5（F7 / T1 / E1 / E2 / C9 / A6 行）｜ kernel `docs/agent-ops/core/frontend.md`（F6/F7 已知 gap）与 `testing.md`（collection 容错）｜ `docs/architecture/v1.9-roadmap.md` §S1 / §S3 ｜ CHANGELOG `[Unreleased]` 与 git 历史。

### P-011 · CI 触发分支仍只覆盖 main（2026-09-17 登记；2026-09-25 清账批次改列已结保留记录）
> status: retained · since: 2026-09-20
- 现状：`lint.yml`、`agent-ops-audit.yml`、`kie-phase-a.yml` 的 `pull_request` 均为 `branches: [main]`
  （`agent-ops-audit.yml` 另有 push→main）→ **feature 分支阶段完全依赖 agent 自觉跑本机门禁**。
- 本次实证代价：P-004 的 stacked PR #22 因 base 非 main，`statusCheckRollup: []`——**一次 CI 都没跑**，
  只有 retarget 到 main 之后才被校验（`gh pr checks 22` → no checks reported）。
- 选项：① `pull_request` 放开为 `["**"]`（CI 配额与噪声上升，需先确认）；
  ② 维持 main-only，但把"本机四门禁 + `audit --selftest`"写进 feature 分支的 Definition of Done；
  ③ 折中：只对 `docs/**`、`scripts/**`、`*.md` 这类低风险路径放开。
- 触发：下一批 feature 分支开工前定；当前实际按 ② 运转（本机跑门禁 + 合 main 时 CI 复核）。
- 相关：`.cursor/rules/003-git.mdc`（`[run ci]` 手动触发约定）、P-008、`lint.yml` 的路径过滤（docs-only PR 不触发 lint）。
- **状态（2026-09-17，治理批次未改动 workflow——红线）**：该批次的触发分支与 paths 保持原样；
  **同日稍后由用户授权单独改了 `paths`**（见下）。
- **机制澄清（2026-09-17）**：`agent-ops-audit.yml` 的 `paths` 过滤**只作用于 `pull_request`**——`push` 到 main
  无 paths 过滤，audit 每次必跑 → 所有缺口都只发生在 **PR 阶段**（评审门），不是"永远不跑"。
- **已处置（2026-09-17，用户授权）**：`backend/tests/**` 已加入该 `pull_request.paths`。**同时修正本条的措辞
  错误**：`backend/pytest.ini` **不是** check 4 的真源——check 4 只读 `backend/tests/test_registry.json` +
  递归 `backend/tests/**/test_*.py` + `.github/workflows/kie-phase-a.yml`（`scripts/test_registry_audit.py:36/37/41`）。
  附带结论：pytest.ini 的 `--continue-on-collection-errors`（P-008 ③）**目前无任何机检覆盖**——要守它得加一条
  断言，而不是加 paths。
- **已处置（2026-09-17，用户裁决走"路线 B 粗粒度"）**：`pull_request.paths` 现覆盖 audit 的全部
  判决相关输入——新增/替换为 **`scripts/**`**（吸收原先逐条列举的实现模块、A0 查符号的门禁脚本、
  `frontend_domain_map.json`）、`CHANGELOG.md`（A5 输入）、`.github/workflows/kie-phase-a.yml`（check 4 输入）；
  `backend/tests/**` 同日已加。选 B 而非"逐条精确补"的理由：精确清单**已经漂过一次**（新增
  `scripts/frontend_coupling.py` 作为实现依赖时未同步），而漏一个输入的代价是**静默**；粗粒度的代价实测
  仅 ~12s/次且公开仓分钟数免费。
- **✅ 已结（2026-09-20 用户裁决；原「重估触发」已在此触发一次并处置）**：main 启用 ruleset `main-branch-protection`（required PR + 必需检查 ⇒ 直推 main 被**拒绝**，一切改动走 feature 分支 + PR）；同 commit 将 `lint.yml` 与 `agent-ops-audit.yml` 的 **`pull_request.paths` 移除**（必需检查必须在每个 PR 上报，否则停在 `Expected` 卡死 PR），`push.paths` 保留（仅供 bypass 场景）；新增 `e2e` job 时**维持 main-only**（与三个既有 workflow 一致，即继续按选项 ② 运转：本机门禁 + 合 main 时 CI 复核）。**判例 = 触发范围与 paths 的取舍必须服务「必需检查在每个 PR 上报」**：2026-09-17 选的「路线 B 粗粒度」清单（`scripts/**` / `CHANGELOG.md` / `kie-phase-a.yml` / `backend/tests/**`；理由是精确清单**已经漂过一次**、漏一个输入是**静默**失效）保留为**转计费后重新收窄**的参照；公开仓每 PR 成本 ~1 min（免费）。
- **触发式残留已迁出**：「仓库转私有（开始计费）/ audit 明显变慢 ⇒ 回到逐条精确 paths」**重估 / 重开条件**，以及可选治本项（让 audit 自检「我的输入 ⊆ workflow 的 paths」，把漂移变红灯）→ 已合并迁出为独立 open 条目 **P-036**（2026-10-16 清账批次；`v1.9-roadmap.md` 的「重估触发见该条」即此意）。

### P-015 · 大文件与 Git LFS 取舍（2026-09-17，治理批次评估）
> status: retained · since: 2026-09-17
- **保留理由（2026-10-07，landed → retained；用户裁决）**：结论①（维持现状）与「新增 >5MB 二进制须在 PR 声明」已由 kernel `docs/agent-ops/core/constraints.md` §通用工程纪律承载（该条款正文仍引用本条：「见 P-015 的取舍」）；本条目保留的是**否决 Git LFS 的理由**与**重议触发**（clone 体积或 CI 时长成为实际问题时重开②）——两者只在此处留档，落在 living doc 会无谓扩面。
- 背景：本批次按要求扫描 `test_data/testfiles/**` 与 `docs/architecture/media/**` 中 **>5MB** 的文件，
  产出 LFS 候选清单（**只评估报告，不执行迁移**）。
- 实测（2026-09-17；四个文件均经 `git ls-files` 确认**已被跟踪**，即已进 git 历史）：

  | 大小 | 文件 |
  |------|------|
  | 17.69 MB | `test_data/testfiles/receipts/multipage/receipt_multipage_2p.pdf` |
  | 9.33 MB | `docs/architecture/media/PDF Parsing Document AI.gif` |
  | 8.56 MB | `test_data/testfiles/invoices/multipage/invoice_multipage_3p_items.pdf` |
  | 5.30 MB | `test_data/testfiles/invoices/multipage/invoice_multipage_2p_header_detail.pdf` |

- 性质：均为**测试夹具与文档演示媒体**（非构建产物），且 `test_data/testfiles/**` 是 `.gitignore`
  负向规则**显式纳入**版本控制的（选择性跟踪二进制）→ 属"有意入库"，不是误提交。
- **结论（2026-09-17 用户裁决，本组可结）**：取 **① 维持现状**，并补一条**轻量约束**——新增 >5MB 的二进制
  （测试夹具 / 演示媒体）必须在 PR 描述写明「理由 + 是否测试夹具」。已写入 kernel
  `docs/agent-ops/core/constraints.md` §通用工程纪律，经 `scripts/sync_agent_rules.py` 派生到
  `.cursor/rules/001-general.mdc` + `.codebuddy/rules/001-general.md`（副本勿手改）。
- 否决 ② 的理由：Git LFS 的失败模式比"仓库变大"更危险——未装 `git-lfs` 时 clone 得到的是**指针文件**，
  e2e / C1-C8 会静默吃到坏夹具（很难归因）；且要求所有 clone/CI 前置安装，与本仓「无前置依赖」取向冲突。
  否决"连历史一起迁"：改写已推送历史，红线级，收益（省几十 MB）远小于代价。
- 触发（保留）：clone 体积或 CI 时长成为实际问题时重议 ②。
- 相关：`.gitignore` 的 `!test_data/testfiles/**` 负向块；kernel 的"大二进制入库须声明"条款。
- 更新（2026-10-03）：`test_data/testfiles/receipts/multipage/`（含 `receipt_multipage_2p.pdf`，17.69MB）已在
  testfiles 治理批次整体删除，上表该行仅作历史记录；`build_receipt_multipage_2p` 已从
  `test_data/scripts/build_multipage_kie_fixtures.py` 移除。

### P-017 · F1 500 行预算是否调整（按域差异化预算 vs 上调预算）（2026-09-20，v1.9 S2-5 暴露）
> status: open · since: 2026-09-20
- **待决问题**：单文件 **500 行**预算（kernel `frontend.md` + `DEVELOPMENT.md` 第 4 条 + `frontend_size_allowlist.json` 棘轮口径）在**复杂服务层反复失真**时，是否调整上限策略、怎么调——**裁决对象应是「backend 服务层是否需独立预算」，而非仅凭前端 `pipeline/run.js` 一次越线**。
- **500 失真的证据面（供裁决；2026-10-05 实测）**：① 巨函数切分会**增加**行数（新增函数边界 / 闭包参数 / docstring），与「切分让文件变小」的假设相反 ⇒ 2026-09-20 S2 批 6 次切分中 `pipeline/run.js` **474 → 524 越线**；② `backend/app` 侧已有 **9 个文件经 `file_size_allowlist.json` 棘轮固化**（`layout_service.py` 1804 · `table_service.py` 1613 · `document_pipeline_orchestrator.py` 1248 · `formula_service.py` 734 · `batch_service.py` 686 · `figure_service.py` 681 · `envelope_builder.py` 620 · `export_service.py` 544 · `ocr_service.py` 457；合计 ~8,300 行，3 个 >1200）⇒ 棘轮条目本身就是「撞线即固化」的产物记录；③ **门禁口径辨析**：`lint_file_size.py` 只扫 git-tracked 的 `backend/app` + `scripts/`（`SCAN_ROOTS`）⇒ `scripts/measure/*` 与 `test_data/scripts/*` 属 **local-only 无护栏区**（不进 F1 视野），`frontend/*.js` 归 `lint_frontend` F1–F7 另一套，`backend/tests/*` 豁免；④ **当前最贴线** = `scripts/lint_frontend.py` **497/500**。
- **候选路线（各自优缺点待裁决时展开）**：① **按域差异化预算**——在 `frontend_domain_map.json` 为每域登记预算（大域放宽、单文件工具域维持 500）。优点：切分线可按域缝走、预算仍是可评审的数据编辑；缺点：预算表成为**新的漂移面**（需门禁 + 棘轮 + staleness，参照 A6 做法），且「域内单文件 900 行」的退化仍需再细化。② **上调全局预算**（如 500 → 700）。优点：规则简单、无新增维护面；缺点：失去「接近上限」预警信号，与 app.js 172 行棘轮的参照关系需重算语义，且不区分「巨文件但内聚」与「巨文件且杂糅」。
- **已裁决、不属本条待决的部分**：本次越线按 S2 先例拆同域兄弟模块（`frontend/modules/pipeline/task-socket.js`；F3 允许同目录兄弟 import，C8 边表与 C9 注入均不变）；**不进 allowlist**（那是把臃肿固化成基线，与「棘轮只减不增」方向相反），抬上限属 kernel 红线、需单独授权。
- **共同前置**：任何路线都要先写明 kernel `frontend.md` / `DEVELOPMENT.md` 第 4 条 / `frontend_size_allowlist.json` 的同步义务与棘轮口径。
- **触发条件**：下一次 F1 越线（切分 / 功能增长 / 新模块任一原因），或用户主动要求评估上限策略。
- **指针**：`docs/architecture/v1.9-roadmap.md` §S2（F1 预算与本项的真实冲突、切分先例）/ §S3（tsc **不是**「比行数更好的质量代理」，故不能以引入类型检查替代本条讨论）｜ `scripts/file_size_allowlist.json`（棘轮）+ `scripts/lint_frontend.py`（F1–F7）｜ CHANGELOG 与 git 历史。

### P-018 · GT 工厂立项：评测 harness（P0）与 born-digital 弱 GT 合成（P1）（2026-09-21，投标竞争力分析产出）
> status: retained · since: 2026-09-25
- **保留理由（2026-10-16 清账批次：`decided` → `retained`；用户裁决）**：P0 / P1 / P2 已分别由 **P-020**、**P-027** 落地（见本节末状态段），P3 已封存为「VLM 符号读数」立项的首期工作包、P4 属无外部 GT 时的兜底 ⇒ **本条已无在途工作项**（原「分岔 C 优先级重排」已迁出为 **P-035**）。保留的是**立项口径本身**：总原则「先建秤再建货」、P0 指标定义（本条即其原始出处）、条件式排序（分岔 B）与「明确不做」的 80/20 红线。`since` 保留原裁决日。
- **来源**：Steelflo 类 retainer 单竞争力分析——公开世界稀缺带 GT 标注的工程图纸/复杂版面文档（FloorPlanCAD/CGHD
  只覆盖 CAD 平面图/电路图，钢结构加工图无公开 GT）。用户 2026-09-21 裁决投入排序后落字立项。
- **总原则：先建秤再建货**——GT 的第一产品是可复现分数（行业数字 = 投标护城河），不是标注数据。
  任何标注投入排在评测 harness 之后。
- **条件式排序**（若获得外部 GT）：
  - **分岔 B（工程图纸 / steel fabrication 类 GT）**：图纸评测直升第一优先——公开稀缺 + 直接命中 retainer
    类单 + 竞品空白。
  - 常规排序：**P0** 评测 harness 骨架（本条第一交付物，指标定义见下）→ **P1** born-digital 文本层 →
    弱 GT 合成管线（Proof Pack review_list 即雏形）→ **P2** 表格结构 GT 对账（P-002 验收基线；公开资源
    PubTabNet / FinTabNet / WTW，WTW 最接近真实客户文档）→ **P3** 符号 GT（✓⊗●○，标注最便宜，搭 P2
    顺带，**不单独立项**）→ **P4** 图纸裁剪自标 smoke（20-30 张，无外部 GT 时兜底）。
- **P0 指标定义**（harness 第一交付物的验收口径）：
  1. 表格：逐格准确率（cell-level accuracy，值归一化后匹配）+ TEDS（结构+内容树编辑距离）；
  2. 版面：区块 IoU（text / table / figure 三类，IoU≥0.5 计命中，报各类均值）；
  3. 符号：检测 F1（box IoU≥0.5 且类别正确）；
  4. 图纸/图表裁剪：召回 + IoU；
  5. KIE：字段级 F1（值归一化后匹配）。
  - **兑现注记（2026-10-03，P-027 R3）**：#5 已由 P-027 R3 验收三闸 harness 兑现为**闸 1 字段级核对**（GT 行频段对
    join + 脚注 token squash 域匹配，金样 6 行校准）；行结构化投影与列绑定缺口归 R4（见 P-027 R3 行）。
  - smoke 基线：5-10 个已有多态文件（含 mamba p12/p29）；输出 = per-file JSON + 单行汇总（可贴 gig /
    Proof Pack）。
  - **实现边界**：只评不修；读 API 输出（envelope / JSON），**不 import 被测管线内部模块**；harness 自身
    改动不触发管线门禁（解耦）。
- **P1 弱 GT 管线技术边界**：
  - 输入：born-digital PDF 文本层（PyMuPDF 词级 bbox）；输出：弱 GT JSON（词级 bbox + 文本；表格结构
    启发式可后置到 P2）。
  - **"弱"的定义**：born-digital 假设下文本层视为真值，不做人工校验；用途限于**回归比对**（同文件两次跑
    分数稳定）与 OCR/视觉输出对账，**不宣称绝对准确率**（对外话术只用于"我们 vs 通用工具"的相对比较）。
  - 与 Proof Pack 的关系：review_list（OCR vs 文本层对照）升级为分数输出，**不另起炉灶**。
  - 与 P-002 的关系：mamba p12/p29 红率 58%/97% 从人工看变分数，P-002 的立项触发条件获得量化入口。
  - C9 一致性：弱 GT 由文本层推导生成、不手工维护快照（"从源推导，不留手工快照"）。
- **明确不做**（80/20 红线）：端到端模型重训 · 大规模人工标注 · GT 标注平台化建设。
- **验收**：P0 完成 = smoke 基线同输入同分数可复现（本机可跑，不依赖 GPU）；P1 完成 = 任一 born-digital
  文件产出弱 GT + 三方对照分数（OCR vs 文本层 vs 视觉）。
  - **验收注记（2026-10-02，P-027 R2）**：P1 已在客户 RF 语料兑现——MY/BD/IE 三件 23 页 **1427 行**弱 GT + 行级
    对账读数（MY 0.9945 / BD 0.9885 / IE 0.2308，IE 为合并格结构错位，见 P-027 R2 行）；三方之「视觉」腿在 RF
    语料无直接视觉块来源（drawings 仅框架线），缺口如实登记随 P-027 归 R4。
- **触发条件**：立即可启动（P0 不依赖外部 GT）；P2-P4 按获得外部 GT 或 P-002 立项顺次激活。
- **相关**：P-002（P1 是其量化入口）· Proof Pack（雏形复用）· 护城河共识（fixture 库 + 行业数字 + JSS，
  不在管线代码）。
- **状态（2026-09-22 登记；2026-09-25 清账批次更新）**：立项登记已落地（PR #30，docs-only）；执行包
  `docs/R&D/P018-GT工厂-立项条目.md` 已在落地后删除（local-only，内容已由本条承载）。
  **P0 评测 harness 与 P1 弱 GT 合成已由 P-020 落地**（2026-09-24 M1+M2，local-only，指标族与边界按本条护栏执行，
  TEDS 随 P2）——**P2 表格结构 GT 对账已由 P-027 落地（2026-09-28，选型 = WTW，基线读数见下）**；
  P3-P4 仍按获得外部 GT 或 P-002 立项顺次激活。

**P2 激活与落地（2026-09-28，P-027 执行包）**：表格结构 GT 对账以 WTW（ICCV 2021，14,581 张，拍照/扫描/网页
三来源）为主选落地——数据验收（许可/抽检/sha256 清单）+ C-1/C1 锚点（单表图像 tables[] 行为与 view 层坐标帧）+
`scripts/measure/{wtw_loader,teds}.py`（local-only）+ `evaluate-table` 子命令（预测只读缓存 D10、配对写死 D11）。
口径 = 表检测召回/IoU（view 层）+ 行列/合并占用矩阵（grid_exact + grid_f1）+ S-TEDS（结构面；GT 无 cell 文本，
full TEDS 不可做，内容面归 P-027）；对外只报自建口径、不作官方 leaderboard。基线读数（test 分层子集 n=300，
seed=42）：grid_exact 145/300、grid_f1 均值 0.8989、mean_s_teds 0.8399、table_recall 0.8300。
该秤兼作 P-002 结构面验收基线与引擎升级的表格回归哨兵；本包不产生销售口径数字。
- 读数出处与证据链（**抄录自 `test_data/TestResult/harness/wtw/eval_c5/wtw_metrics.csv` 汇总行**，local-only）：
  预测一次落盘 300/300（云端 run = PR #35 的 P-021 unwarping 修复 merge，**在 main 历史上且
  `backend/**` 与该提交**逐字节零差异** ⇒ 读数可迁移到当前 main；paddle 3.3.0 / paddleocr 3.3.2，
  `language=ch` 单变量），
  `failed.txt` / `id_mismatch.txt` 双空、`pred_manifest.txt` 300 行且逐行 sha256 复算 **0 不符**；
  判分只读缓存（D10），**同一缓存两次判分 CSV 与 report 均逐字节相同**（GB2，`sha256 e44d5e6d…`）；
  `audit_agent_ops.py` 0/0、`--selftest` 59/59、`git diff --stat` = 本文件 + CHANGELOG 共 2 个 tracked 文件（GB3）。
  登记期由真实批数据打出的一个**秤侧真 bug 已修并留在断言覆盖内**：`grid_compare` 只补列不补行，行数不等即
  `IndexError` 中止全批判分（C4 等形试件掩盖了它，故 C4 读数不受影响——修后 C4 单图输出与钉死件逐字节一致）。
  另记一项**已被证伪的告警**：34 张的 `document_info.page_image_meta` 与 XML `<size>` 呈 w/h 互换（EXIF 方向），
  但预测框与 GT 框**越出 XML 帧者均为 0** ⇒ 属元数据上报口径，**坐标帧一致**，判分不受污染。

**P3 激活与暂停（2026-10-02，X1 裁决 = 选项 D）**：P3 符号 GT 按「P-002 已落地（2026-09-29，PR #46）」触发条件激活
（执行包 `P018-P3-符号GT-执行包（draft-v3）.md`，AgentE 执行；原文 :311-312「P3 不单独立项」被触发条件覆盖，
沿革保真不回改）。C0 静态自检 11/11 过（含字体钉死 sha `3fdf69ca…` / 五字形渲染验证 coverage≥0.70 / CONFUS 等价表
逐字核对）；C1 探针（五类各 3 + 2 文本控制格，云端，paddleocr 3.3.2 / A10，ch≡en 逐字节）实测：断言②
PASS（已检出符号 IoU≥0.5 = 4/4，GT 名义盒 + 6pt 基线补偿几何有效），**断言①③ FAIL——引擎对白底孤立符号漏检
（✓ 1/3、⊗/●/○ 0/3、✗ 3/3 读成 X；R2 命中）**。Ying 裁决暂停：R2 实证已登记于本条目（原执行记录
`docs/R&D/P018-P3-执行记录.md` 属 local-only，**已不在磁盘**（2026-10-16 复核）、无 git 历史可回溯；结论即下方 A1/X3 两段），
**试件规格 §2 / 五类判据 / 指标定义 #3 零变更**；仪器保留 local-only
（`scripts/measure/synth_symbols.py` 渲染核心 + 探针产物 + c0 自检仪 A6 钉子同步扩至 11 文件）。重启前置：Ying 对
A（符号嵌入文档语境，联动 D2/R9）/ B（类集缩减）/ C（det 调参解禁）再裁决；P-027 harness 文档债修复随下次
落地批次同带。**A1 修订（同日 Ying 选型 A1 = 行级语境）**：§2 符号格改「词(14pt)+空格+符号(28pt 原位)」行级
语境（词表 YES/NO/NA，词与类别独立，控制列钉最左，seed=42 不变）；D1 判定对象改最右符号字符；D2 行级为常态；
D3 增符号域/右端切分/观察近似集 {×,x,X}（ALIAS_TO_CLASS 仅用于切分宽与观察标注，不参与类别等价）；R9 升
主路径（切分判分，停手条件后移至切分后断言②）；合并行只认最右、其余记 FN；指标定义 #3 原文与五类等价
**零变更**。修订稿 = `P018-P3-符号GT-执行包-A1修订稿.md`（local-only；**该文件与旧探针目录均已不在磁盘**（2026-10-16 复核，
`docs/R&D/**` 不入 git 故不可回溯），规格要点即上文 A1 修订段）。**X3 = D'（同日 Ying 裁决）：P3 收尾，本包完结**。A1 重跑（probe_a1，
云端复跑）再次硬闸：词 15/15 满置信读出（行先验修复对文本完全生效），但符号 TP=0——**引擎符号可读边界
实测定格**：✓→√（墨迹紧盒，边缘）、✗→X（行内并入），**⊗/●/○ rec 层不可读**（孤立与行级双条件确认；决定性
证据 = row0 ○ 的 det 盒完整覆盖圆而 rec 只出尾随空格）；失败定位于 PP-OCR 文本管线的结构性边界（与官方
issue #9466 一致；Paddle 官方符号路线 = PaddleOCR-VL-1.5，明确特殊符号/复选框）。**判据/试件规格/指标定义
#3 零变更**（五类保留为愿景）。**C2~C4 不执行**，封存为「VLM 符号读数」立项的首期工作包（synth 渲染核心 /
A1 试件 / S-1·S-2 切分规则 / D8 engine 列原样复用；新 D 系列契约定义与产品侧路线 = 该立项前置裁决）。
**家族排序**：P-027 R1 随任意 docs PR 随手带 → P-027 R2 中英文件弱 GT 合成升主线（其登记条款「P-018 P3 在前」
随本裁决解除）→ VLM 符号读数立项其后（无在案需求信号，能力储备性质；可选 A1 探针 × Qwen smoke 半日内先证
「VLM 能否读圆族」）。登记清算：CHANGELOG / harness 架构文档无落地读数不登记；P-027 harness 文档债随其落地
批次。执行记录 `docs/R&D/P018-P3-执行记录.md`（local-only）**已不在磁盘**（2026-10-16 复核，`docs/R&D/**` 不入 git）；本段即其 §4.4–§4.7 的结论文本。

### P-020 · OCR 质量测量 harness M1+M2 落地（P-018 P0/P1 实施，2026-09-22 四轮讨论定稿）
> status: retained · since: 2026-09-24
- **保留理由（2026-10-07，landed → retained；用户裁决）**：规格与口径已于 2026-09-26 晋升 `docs/architecture/ocr-quality-harness.md`（该文 §7 明示本条目 = 「harness 落地证据与规模偏差的登记条目」）；本条目保留的是**唯一入库的证据附件**——云读数（锚点-1/2、base B 空间门禁 15/15 FAIL→PASS、G4 smoke 曲线）、实际 **1958 行 vs 预算 1205（+62.5%，用户 2026-09-22 裁决接受）** 的据实偏差、C1 静态核对结论（result JSON 无 cell 级 bbox ⇒ cell accuracy 口径）。
- 交付（**local-only，不入 git**）：`scripts/measure/{__init__,metrics,degrade,gt_factory,harness_cli,test_metrics}.py`
  ——机器本地测量仪器，源码与产物均留本机不入库。`.gitignore:273 scripts/*` 是用户既定策略（271-272 行注释原文
  「User-requested: never track these folders」），本次裁决**保持 local-only、未改 `.gitignore`**。
  `backend/app/**` 修改面 = 0；`backend/tests/test_registry.json` **未改**——工具与其测试同处 `scripts/measure/`，
  不属 `backend/tests/**` 对账范围，故无 T1 登记义务（原计划「登记 test_metrics.py」因 local-only 裁决而作废）。
  **本次入库的只有本 PENDING 条目与 CHANGELOG 一段。**
- 指标族：matched_rate → micro/corpus/macro CER → LCS → line_exact → table/non-table/digit 子分 + cell accuracy；
  DP 单位唯一=字符（D2），行=配对单位；归一化 L1/L2 分层（归一化为空的元素剔除出 CER 串、仅进 SKIPPED 列）；
  回溯平局写死 sub > del > ins（`12`→`21` 稳定记 2 sub，保 D9 归因可复现）。
- deviate-1：TEDS 随 P2（结构真值依赖）；deviate-2：被测执行收紧为「读 result JSON」（遵 P-018 契约，harness 与被测解耦）。
- **C1 静态核对关键发现（影响 P0 指标 1a）**：result JSON **不含 cell 级 bbox**——`cell_bbox` 仅是重建输入、
  不落盘（`backend/app/services/table_service.py:262-283`）；`proof_render.py:15-21` 亦明言 per-cell bboxes
  需由 `table["bbox"]` 均匀网格再推导。故 cell accuracy 收敛为「表级 IoU 配对 + 表内 cell 序列比对」，
  `cell_word_bbox`（backfill 落盘）为可选几何来源。已回写执行包 §C1 / §2.1。
- **规模偏差（据实登记，2026-09-24 复算）**：实际 **1958 行** vs 执行包 §3.1 预算 1205 = **+62.5%**，超出 §9
  护栏 #5 的 ±20% 上限；**用户 2026-09-22 裁决接受**（保留 docstring/类型/单测可读性）。分文件：`metrics.py`(569) /
  `harness_cli.py`(494) / `test_metrics.py`(380) / `gt_factory.py`(318) / `degrade.py`(183) / `__init__.py`(14)。
  **`metrics.py` 已越过 500 行**——该结论为**人工计数**：`lint_file_size.py` 以 `git ls-files` 枚举（git 模式），
  untracked 文件不在扫描集，故 F1 门禁对 local-only 源码**不生效**，入库无涉；若日后要入库，须先拆 `metrics.py`。
  增幅主要来自 D-A 顺序配对与保序 DP 对齐、C1 导入约定、DP 平局裁决、SKIPPED 语义、31 项断言与 15 列 CSV/HTML
  报告，**非功能扩张**。
- 验收：G1 恒等 hash / G2 已知答案 11 断言 / G3 复现逐位一致 / G4 smoke 5-10 文件（P-018 验收口径）。
- **状态（2026-09-22）**：**本机可判定项全绿**——G1（identity 与直接渲染逐位 hash 相等）、G2（11/11，
  `pytest scripts/measure/test_metrics.py` → 23 passed）、G3（同输入跑两次逐位一致，含 CSV 字节相等）、
  `audit_agent_ops.py` 0 error / 0 warning、`--selftest` 16/16。
  **云端未验证**：C1 动态锚点-1/2/3（逐层坐标系生死判 / result JSON 字段 / mamba born-digital）与 G4 smoke
  须在 Pro GPU 机器真跑管线产 result JSON，步骤与判据见执行包 §10；按 AGENTS.md「本机无 GPU」红线，
  **不宣称云端已验证**。执行包 `docs/R&D/runs/P020-ocr-harness-M1M2-执行包.md` **已于 2026-10-07 清理**（`docs/R&D/README.md:41` 留痕：实质结论已由 living doc `docs/architecture/ocr-quality-harness.md` + CHANGELOG 承载）——其 §10 runbook 与回填模板随之不可回溯（`docs/R&D/**` 不入 git）；如需复跑，按该文 base A/B 坐标系契约 + 本条目 2026-09-24 读数段重建步骤。
- **状态（2026-09-24，云端 15 份 result JSON + 15 份 OCR JSON 回传后判读）**：
  - **锚点-1 通过（实证）**：`view` 层（**含 table/figure**，`envelope_builder.py:273-331` 逆旋转对全部 kind 统一生效）
    15/15 落试件画布；唯一纠偏页 `…__rotate_15`（`angle=270`）实证 view = 该层 `polygon_preprocessed`
    逆旋转 270° 的精确像。执行包 §3.3 原「table 恒 preprocessed」推论**据此收紧**：`tables[].bbox` 属
    preprocessed 系、**禁入指标路径**，但 view 层的 table/figure 与 GT 同系，D7 照旧。
  - **锚点-2 通过（结论为「无」）**：11 份含表 result JSON 中 `cell_bbox`/`cell_word_bbox`/`cell_provenance`
    **零出现** → cell accuracy 确立走「表级 IoU 配对 + 表内 `data` 序列比对」。
  - **base B 空间门禁 15/15 FAIL（新发现，已落执行包 §10.11/§10.12）**：`POST /api/v1/ocr` 返回的
    `text_blocks` 坐标**不在试件像素系**，而是与之相差一个 similarity（实测 scale 1.00–1.14、残余旋转
    随 spec 从 −0.3° 单调走到 −19.7°，即近似「被去旋转后的页面」+ 另一次缩放）。根因在本仓可证：
    `_convert_predict_dict`/`_parse_result`/`_call_ocr` 全程逐点透传、引擎初始化未设检测侧尺寸参数、
    PDF 分支另在 2×（144 DPI）下渲染。
  - **D-A 裁决（用户）**：line 级文本**改按阅读顺序配对**（两侧各用尺度无关的 `metrics.reading_order` 排序，
    再用保序 DP `metrics.align_by_order` 对齐；AS 多出的行免费跳过、GT 漏配的行按删除计费），**几何只留给
    base A** 做 block/table/figure IoU。收益：坐标永不跨越 base-B 帧边界，**复用本批 base B 即可出数**，
    零产品改动、零污染（未用 GT 反解修正 AS 侧）。修 `/api/v1/ocr` 属产品改动，本包不做、另行立项。
  - **顺带修掉两个通用 bug**：① GT 记录保留**源 PDF 页号**（arxiv 试件切自 p12）而 base A/B 看到的是 `page=1`
    → 按页 join 会静默产出 0 对，改为按 JSONL 序号 join；② 空配对/空 GT 切片的指标曾读 `0.0`（会被读作
    「完美」），改为 `None`（未测量）或 `1.0`（GT 有行却全未配上 = 全删除，属已测量的失败）。
  - **G4 smoke（15 行 × 15 列齐）**：`cer_micro` 在 5 个 fixture 上单调不降（`identity ≤ rotate:3 ≤ rotate:15`）
    **5/5 ✓**；`cer_macro` 4/5、`cer_corpus` 2/5（后者把 AS 多出的表格体计为插入，对表格型文件 >1 且可能
    非单调——**口径性质，非脚本缺陷**，故 §10.9 已注明曲线 sanity 以 `cer_micro` 为准）。
    `cell_accuracy` 随旋转单调下滑、`cer_table` 单调抬升，符合预期；GT 无 cell 的页（arxiv）两列读 `-`。
  - 复验：G1/G2/G3 全绿（`pytest scripts/measure/test_metrics.py` → **31 passed**；G3 同输入两次
    `metrics.csv` **逐位相等**），`audit_agent_ops.py` **0 error / 0 warning**。
  - **仍未验证**：M3 共识分诊、TEDS 等本包不做项。base B 坐标问题的**根因与修法已由 P-021 定位并验证**
    （未落地）。
- **规格晋升（2026-09-26）**：本条的**规格与口径**已晋升 `docs/architecture/ocr-quality-harness.md`（living；登记于
  `docs/README.md` 索引第 15 条与归属表），两份 local-only 过渡稿（提案 `ocr-quality-measurement-harness.md` 与
  设计稿 `ocr-quality-measurement-design.md`）已随之删除；自此本条只承载**证据与规模偏差**（云读数、1958 行偏差、
  C1 静态核对），改规格去 living doc、勿改本条。

### P-023 · 测试 stub 作用域无规则：模块级 `sys.modules` 占位会**伪造「本机已装 Paddle」**（2026-09-25，P-021 首次 CI 运行产出；同日裁决并落地 R1–R3）
> status: retained · since: 2026-09-25
- **保留理由（2026-10-07，landed → retained；用户裁决）**：规则与门禁均已入库——kernel `docs/agent-ops/core/testing.md` §pytest 边界（清单内必须作用域化）+ §测试登记口径（加进 CI 清单须跑完整文件列表）+ `scripts/test_registry_audit.py::check_stub_scope`（audit check 5）+ `module-map.md` §5 **T2**；本条目保留的是**判例**：「模块级 stub 伪造“本机已装 Paddle”」与「单文件验证掩盖跨文件污染」两个失效形态——与 P-008 保留 T1/T2 判例同型，且是 check 5 规则的出处。

- **来源**：P-021 的契约单测首次进 Phase A CI（与 P-021 的修法同批）后 `kie-contract` **17s FAIL**，且失败在
  **本改动未触碰的文件**：`tests/test_table_template_analyze.py::test_analyze_form_accepts_table_template`
  → `ModuleNotFoundError: No module named 'fastapi'`（`1 failed, 45 passed`；**新单测自身全程绿**）。
  用户 2026-09-25 追问"是上下文过长还是规则不明确"，据此立项。
- **现象（机制）**：新单测在**模块级**写 `sys.modules["paddle"] = types.ModuleType("paddle")`（为让
  `ocr_service.py:9` 的顶层 `import paddle` 通过；占位模块不含任何 Paddle 代码）。pytest 在**收集阶段**就 import
  所有测试模块，故该占位在邻居运行时**仍然存在**；邻居用 `pytest.importorskip("paddle")` 作**环境闸门**
  （其注释原文："Phase A CI … intentionally runs without Paddle, so skip there"），读到"有 Paddle"→ 不再跳过
  → 撞上它*间接*保护的 `from fastapi.testclient import ...`（Phase A venv 故意不带 fastapi）。
- **根因定性：规则盲区（主因），非上下文长度**——即使上下文无限也会踩，因为无一处成文、只能靠推断：
  - `004-project.mdc:50-60`（kernel `core/testing.md`）的判据只问**"你的测试需不需要服务器/GPU"**，
    从不问第二问：**"你的测试会不会替*别人*假装 Paddle 已就位？"** `sys.modules`、stub 作用域、`monkeypatch`、
    "Phase A 是单进程共享会话" 全仓无一处成文。
  - **先例不完整（核心成因）**：`test_layout_types.py:20-23`、`test_layout_page_skip.py:20-22` 都用**模块级** stub
    且自述"本机无 paddle 所以 stub"，**无一行**提示"此模式只适用于不在 Phase A 清单的文件"。两者登记
    `kind: full`（不在 CI 清单）→ 该模式**只在 `kind: full` 内自洽**。对 Agent 而言先例权重常高于规则文本，
    故那个缺注的模板被直接照抄。
  - 仓库**知道**"是否进 CI 清单"有语义（`test_registry_audit.py` 三向对账 + `kind` 枚举），但从未写出其语义后果。
  - 另有一份独立责任（**验证设计**，与上下文无关）：把测试加进**共享会话**清单，却在**单文件**模式下验证——
    跨文件污染**结构上**不可能被单文件运行暴露；正确代理成本为零（见 R3）。
- **预存性（本坑先于 P-021 存在；已实测 2026-09-25）**：两个 `kind: full` 文件的模块级 stub 是**入库既有**的，
  按字母序**早于** `test_table_template_analyze.py` 被收集 → 任何收集整个目录的会话都会让该闸门失效。
  之所以长期未炸：既有全量实测在**云端**做（`CLOUD_VALIDATION.md:458`：`430 passed, 1 skipped, 0 failed`），
  而云端**装了 fastapi** → 闸门放行后邻居正常跑并**通过**；一旦环境是**无 fastapi + 无 paddle**
  （= Phase A CI / 本机）即硬失败。
  - ① 最小复现 `pytest tests/test_layout_page_skip.py tests/test_table_template_analyze.py -q`：
    修前 **1 failed**（失败＝邻居同一用例，`ModuleNotFoundError: No module named 'fastapi'`）⇒
    **不含 P-021 的任何文件也照样红**；修后 **8 passed, 1 skipped**。
  - ② 整目录断言 `pytest tests -q -k analyze_form_accepts_table_template`：修前 **1 failed**；修后
    **1 skipped, 5 errors**（5 errors 为本机缺 fastapi 的**既有**收集错误，与本文无关，由 `pytest.ini` 的
    `--continue-on-collection-errors` 容忍）⇒ "任何收集整个目录的会话都会中招"成立。
- **危险方向（写规则/门禁的核心理由）**：本次只是"误红"，属**幸运**——闸门保护的是 `fastapi` import，所以立刻炸。
  若邻居的闸门只决定**要不要跑**，同一泄漏会表现为**静默少跑**：无红灯、覆盖悄悄消失。**规则文本防意图，门禁防复发。**
- **落地（本 PR；用户 2026-09-25 裁决：R2 范围取 (ii) 全部 `backend/tests/**`）**：
  - **R1 规则**：kernel `docs/agent-ops/core/testing.md` §pytest 边界加判据——**清单内必须作用域化**
    （fixture 的 `monkeypatch.setitem`，或加载期的 `unittest.mock.patch.dict`），**禁止**模块级 `sys.modules[...]`；
    清单外（`kind: full`）可用模块级。生成副本由 `scripts/sync_agent_rules.py` 重生成（勿手改副本）。
  - **R2 门禁**：`scripts/test_registry_audit.py` 新增 `check_stub_scope()` + `_module_level_sys_modules_writes()`
    ——AST，只认**模块级**写入、**不下潜**函数/类/lambda，覆盖**全部** `backend/tests/**`；接线 `audit_agent_ops.py`
    （1 行调用 + docstring）；selftest **26 → 31**（+5 条纯谓词断言）；`module-map.md` §5 增 **T2** 行、§6 A6 行补 check 5。
  - **R3 验证义务**：kernel 同文 §测试登记口径 加一条——**把测试加进 CI 清单时，本机验证必须跑完整文件清单**，
    不许只跑单文件（补上「验证设计」那一份缺口）。
  - **R4（归属说明）**：另一项是给 **P-021 条目** 的 ② 行补注"该先例是模块级 stub、本次改为 `monkeypatch` 作用域、
    成因见 P-023"——**属 P-021 的记录，随 P-021 的分支落地，不并入本 PR**。
- **正向对照（跑在真实事实上）**：接线后首次 audit **精准命中**两处既有缺陷
  （`backend/tests/test_layout_page_skip.py:22`、`test_layout_types.py:23`）**加**两处 kernel 副本漂移；修完即
  **0 error / 0 warning**。本分支 Phase A 清单读数为 **42 passed, 1 skipped**（该清单不含 P-021 新增的契约单测）。
- **顺带修复既有缺陷**：那两个 `kind: full` 文件改为**加载期作用域**（`unittest.mock.patch.dict(sys.modules, …)`，
  载完自动回滚）⇒ **本机整目录跑不再红**（见上 ①② 的修前/修后对比）。
- **现行控制**：本 PR 之后，`backend/tests/**` 的任何模块级 stub 都会在本地与 CI 同时被 check 5 拦下。
- **触发条件**：任何新增/修改 `backend/tests/**` 且需要 stub 重依赖（`paddle`/`cv2`/`torch` 等）时；改
  `test_registry.json` 的 `kind` 或 Phase A 清单时应同查本条目。
- **状态（2026-09-25）**：**已落地**（登记与落地同日）；R4 见上（归 P-021 的记录）。

### P-024 · 长对话/压缩后的「开新对话」提议**无触发点**：判据存在却从不被调用（2026-09-25，用户追问产出；登记待裁决）
> status: retained · since: 2026-09-25
- **保留理由（2026-10-08，`decided` → `retained`；用户裁决）**：规则与两副本已落地（kernel `constraints.md` 两个强制检查点 + `sync_agent_rules.py` 派生）、CHANGELOG 已记；2026-10-07 撤销"实测回填"义务后**本条已无剩余动作**，`decided`（= 尚有未完成动作或待验证）语义不再成立。保留作判例：「判据存在但无调用点」与"代价不对称 ⇒ 默认失败"的登记形态（与 P-008 保留判例同型），并作为 §检查点范式（`Session-check`）的出处。

- **来源**：P-021 / P-023 收尾时，用户问"继续在本对话执行是否越来越混乱"，继而追问"**为什么四条全中，会漏提议**"。
  据此立项（属 **agent-ops 规则**，与 P-023 的 `testing.md` 不同域；**零产品代码改动**）。
  **口径修正（2026-09-25 裁决时补）**：用户可观察的硬事实只有「**未提议发生**」；「四条全中」系该会话**事后自报**，
  而本条目的论点恰是自报不可靠 ⇒ 自报计数只作佐证、不作证据。
- **现象（机制）**：kernel `docs/agent-ops/core/constraints.md:30` 已给出**可观测代理**四条（压缩事件 / 同一文件
  重复读 ≥2 次 / 连续工具调用因内容不符失败 ≥2 次 / 需推翻自身先前结论），但**本对话四条全部命中、我一次都没提议**；
  是用户问起、我去查才发现"全中"。
- **根因定性：判据存在、调用点缺失（主因）**——不是判据错，是**没有任何事件强制我评估这四条**：
  1. `:30` 是条件语句（"任一命中即主动提议"），执行依赖"我想起来检查"，而"想起来"正是长对话中最先失效的能力。
  2. **检测器与被检测对象同源**：`:30` 已承认"自省不可靠"，却仍把"数自己的重复次数"交给同一个自省；且四条**全部
     要求跨轮记忆**，而**压缩会删掉计数所需的账本**（本轮历史已被压缩）⇒ 不是判断失效，是**数据缺失**。
  3. **① 把平台可观测降级成自省**：压缩完成即触发，却写成"出现压缩事件 → 提议"，于是 Agent 把会话开头的压缩摘要
     读成"起始条件"而非"触发信号"（本轮即此实例）。
  4. **代价不对称**：提议在当下读起来像"抵抗任务"，不提议无审计/无产物/无红灯 ⇒ 默认失败。对照：CHANGELOG 义务、
     `audit_agent_ops` 0/0、`lint_file_size` 棘轮之所以生效，都因为**有产物或门禁兜底**。
  5. **载体只读一次**：判据仅存在于一份约 40 行的规则文件中，进上下文后不再被主动翻出（本轮规则检索全在"paddle
     边界"上，从未回到 `:29-30`）。
- **预存性**：与 P-021/P-023 无关，属长对话固有问题；**任何发生压缩或触及任一代理的会话都会踩**，与上下文上限高低无关。
- **危害方向：静默退化（比误红更隐蔽）**。本轮已出现实例：PENDING P-021 原写"改后 458 < 500 不触 F1 门禁"
  （实为 457 棘轮，落地必红）；CHANGELOG 的 "The line is kept" 在后续提交后已过期；我那版 stub 污染。
  三者都不是规则拦住的，而是**跑门禁偶然撞见**——若没撞见，就会被当成事实继续引用。
- **待裁决选项（互不排斥；a 最便宜、c 治本）**：
  - **(a) 把 ① 从自省摘出去**：改 kernel `:29` 为「**正在阅读压缩摘要 ⇒ 触发已发生**：回复开头先给一行判断 +
    可粘贴交接块（除非用户明确说继续）」。把"注意到事件"换成"认得正在读的输入"，可靠性差一个数量级。
  - **(b) 加检查点而非判据**：绑到已必然经过的结构点——①每个已提交/已合并的交付物；②每次写 CHANGELOG/PENDING 时。
    要求**写出一行四条计数与结论，全 0 也要写**（跳过会留空白，因而可见）。
  - **(c) 账本外置（治本）**：会话内维护落盘 ledger（候选     `docs/R&D/.session-ledger.md`），每次交付追加
    `ts, rereads, tool_failures, reversals, compaction_seen` ⇒ 压缩后读它即恢复计数，把"跨轮记忆"换成"落盘状态"。
    引入新文件 ⇒ 须另走治理。**（2026-09-25 裁决：挂起**——其唯一增益是"计数跨压缩持久"，但写仍靠 ② 的检查点、
    读仍靠 ① 的触发；先跑 (a)+(b) 取证，确认确需跨压缩恢复计数再议。）
  - **(d) 让自报可 diff**：commit / PR body 增机器可查字段
    `Session-check: rereads=… failures=… reversals=… compaction=… -> propose-new-chat=…`；`module-map.md` §5 增门禁行
    （仿 `T2` / `DOC-1` 的位置，`module-map.md:126-128`），由 `audit_agent_ops.py` 的 `check_agent_rules()`（`:422`）
    只查**存在性与格式**。**（2026-09-25 裁决：按原文不可实现，降级**——`check_agent_rules()` 只做 kernel→副本重渲染比对
    且 `audit_agent_ops.py` 跑在 checkout 上**读不到 PR body**；能读 commit message，但 CI 浅克隆（`fetch-depth: 1`）
    常读不到 PR 自身的 commit ⇒ 查最近 N 条会**假绿**。落地形态改为：字段落 **commit message / PR 正文**，reviewer 抽查、
    不进 audit；将来若要机器查须先改 fetch-depth 或只查 push→main，均属 CI 红线、另行走授权。）
- **能力边界（必须写明，否则方案变幻觉）**：②③④ 是**会话内事件**，CI 看不到对话记录，故**无法**自动判定；能自动的
  只有 ①（前提：平台把压缩事件写入状态）。**(d) 的价值是"跳过会留空白、reviewer 可抽查"，不是"数值一定准"。**
- **落点（若裁决采纳）**：kernel `docs/agent-ops/core/constraints.md` → `scripts/sync_agent_rules.py` 重生成副本
  （`:39` / `:102` → `.cursor/rules/001-general.mdc` / `.codebuddy/rules/001-general.md`）→ CHANGELOG →
  `audit_agent_ops.py` 0/0；(d) 另需在 `docs/architecture/module-map.md` §5 登记门禁行。
- **建议组合**：(a) + (b) 先做（各约 1 行，成本最低）——**该组合能抓住本轮这一例**：在"第二个提交之后"这个检查点上
  会被要求写出 `reversals=3`，那是命中而非空白。(c)/(d) 视裁决。
  **（2026-09-25 用户裁决：采纳 (a)+(b)，带三修正**——① (a) 的"可辨识"是平台前提、未验证，落地为**条件条款**并在下次
  压缩后实测回填，不可辨识即自动失效；② (b) 收窄到**两个**检查点（创建 commit/PR、写 CHANGELOG/PENDING）防仪式化蔓延；
  ③ (d) 降级为 commit message / PR 正文字段、**不进 audit**（见上）。**回溯验证**：本轮会话若按 ② 执行，在 PR 检查点
  会写出 `failures≥2`（多次 shell 引号失败）、`reversals≥2`（采集块 `$OUT` 缺陷与 `[6]` 假红判据，均推翻先前"可直接粘贴"
  的结论）⇒ 会触发提议，"能抓住"得到一次实证。**）
- **现行控制（2026-09-25 起生效）**：kernel `constraints.md` 沟通方式节新增两个强制检查点（可辨识压缩输入 ⇒ 触发已发生；
  交付检查点一行 `Session-check: …`，全 0 也写），两副本（`.cursor/rules/001-general.mdc` / `.codebuddy/rules/001-general.md`）
  已由 `scripts/sync_agent_rules.py` 再生成、未手改。
- **遗留义务已撤销（2026-10-07 用户裁决）**：原「(a) 的前置实测」——下次压缩后向 Agent 提问「你现在读的是压缩摘要吗」并回填可否辨识——**不可控且没有必要**，撤销该实测义务与登记要求。kernel `constraints.md` ① 条当日**文本保留不动**（只撤销登记义务）；**2026-10-08 该条已改写为「尽力而为」措辞**（#76 同批落地，两副本由 sync 再生成），故「不可辨识即自动失效」不再是承诺、也不再追踪，实际按「只靠 ② 检查点运转」执行（本条保留 (a)+(b) 的裁决与落地记录本身）。
- **触发条件**：任何长对话（≥1 次压缩、或触及四条代理任一）收尾 / 换阶段时；改 `constraints.md` 的会话管理条时同查本条目。
- **状态（2026-09-25）**：**已裁决并落地**——采纳 (a)+(b) 带三修正；kernel `constraints.md` 沟通方式节已增两个强制检查点，
  两副本已由 sync 再生成，CHANGELOG（Unreleased/Changed）已记一段；(c) 挂起、(d) 降级（理由见上）。
  本条目自身即第 ② 检查点的首个执行实例。

### P-025 · R&D 晋升与滞留**只靠人记**：义务存在、触发点与机检都不存在（2026-09-26，用户追问产出；同日裁决并落地 (a)+(b)）
> status: retained · since: 2026-09-26
- **来源**：用户问「R&D 晋升是否都要手动触发、规则里有无说明、任务完成后是否会自动检查可否晋升/删除」。逐项核对后确认三处缺口，
  据此立项（属 **agent-ops 治理**，与 P-024 同域；**零产品代码改动**）。
- **现象（机制）**：`doc-sync.md` §文档生命周期「R&D 结论稳定后晋升 `docs/architecture/`，不在 R&D 堆长期真源」是**纯义务文本**——
  无触发点、无机检、无超期告警。`audit_agent_ops.py` 的六个 check 无一读取 R&D 目录或 PENDING 条数；反向证据更明确：
  `docs_refs_audit.py` 的 `EXEMPT` 把 `docs/R&D/**` 显式豁免（理由合理——决策日志本就要引用已删事物），
  于是"该晋升/该删除"这件事在 CI 里**连输入都不存在**。
- **根因（三条，按可修性排序）**：
  1. **结构与 CI 错位（不可全部修）**：`.gitignore` 只放行 `docs/R&D/README.md` 与 `PENDING.md` ⇒ CI 的 checkout 里
     根本没有其余 R&D 文件。目录侧**结构性不可机检**，只能本机脚本 + 习惯兜底。
  2. **入库侧本可机检，却存了手写副本**：PENDING 抬头把状态统计写成自然语言（"已结保留记录 N 条 / 其余 N 条待裁决"），
     该副本**已漂过一次**——清账前它把 P-007/P-010/P-013/P-016/P-015 五条已结条目计在"待裁决"里（P-019 同类病灶）。
  3. **KPI 无测量、且引用幽灵文件**：`operations.md` 的"待决决策滞留"无任何测量方式；"记忆回流及时率"引用 `MEMORY.md`
     ——该文件**全仓不存在**，且 `N 天` 未定义 ⇒ 两条指标实质失效。
- **落地（本 PR，用户裁决 (a)+(b) 同款思路）**：
  - **(a) 机检**：`scripts/docs_refs_audit.py` 新增 `check_pending_staleness()`，`module-map.md` §5 登记 **DOC-3**，
    由 `audit_agent_ops.py` import 接线 ⇒ **复用既有 required check `agent-ops-audit`，零 CI 配置改动**。
    判据：条目缺 `> status:` 元数据 / 状态未知 / 日期非 ISO / 未来日期 = **ERROR**（fail-closed，同 A6 口径）；
    `landed` 超 `PENDING_STALE_DAYS = 90` 天 = **WARN**（提示晋升或改列 `retained` 并写明理由）；抬头 ID 索引与
    `### P-xxx` 标题集合不一致、或"共 N 条"不符 / 标题重复 = **ERROR**；`open`/`decided`/`retained` 不受时钟约束。
  - **数据面**：PENDING 每条标题下首行加 `> status: <open|decided|landed|retained> · since: YYYY-MM-DD`（状态单一事实源），
    抬头改为"机检索引 + 状态语义 + 晋升检查点"，**删除手写统计副本**（数字口径改由门禁输出，P-019 单源化教训）。
  - **(b) 检查点**：kernel `doc-sync.md` 加强制义务——每次写 PENDING / CHANGELOG 必须回答一轮「本轮有无条目达到
    可晋升/可移除标准」，并在 commit message / PR 正文留一行 `Promotion-check: <n> eligible … -> promoted|deferred`
    （零条也写；与 `Session-check` 同形，靠"跳过会留空白"约束，**不设 CI 机检**）。
  - **KPI 漂移**：`operations.md` 两条 KPI 改为可测量口径（`landed` 90 天晋升窗口 = DOC-3 的 WARN；删掉 `MEMORY.md` 幽灵引用），
    并如实登记"`local only` 不得提交由 `.gitignore` 兜底、结构性无机检"。
- **能力边界（必须写明，否则方案变幻觉）**：本条目只把「**入库侧 + 义务文本**」这一半机检化。`docs/R&D/*`（除 README/PENDING）
  **依然不可机检**——CI 看不到它们，local-only 面的省视只能靠本机脚本或人；`Promotion-check` 与 `Session-check` 一样
  **不进 audit**（读不到 PR 正文、浅克隆看不到 PR 自身提交）。另：DOC-3 只判"元数据是否合法 + 是否超期"，
  **不判**某条目"该不该晋升/删除"——那是人的裁决，门禁只负责把逾期项摆到台面上。
- **沉淀的取值口径（未来改状态时照此）**：`open` = 未裁决 ｜ `decided` = 已裁决、尚有未完成动作或待验证 ｜
  `landed` = 已落地、结论待晋升审视（`since` = 落地日）｜ `retained` = 已结且有意保留（保留理由写在条目内，无时钟）。
  状态分布**不在本条存快照**——以各条 `> status:` 元数据为唯一事实源（副本必漂，P-019 教训）。
- **相关**：P-019（数字副本单源化，本轮直接继承其教训）、P-008 A6（`check_orphan_staleness` 是 DOC-3 的形态先例）、
  P-024（检查点范式与 `Session-check`）、`docs/agent-ops/doc-sync-ownership.md`（R&D 不作 owning doc 的既有口径）。
- **晋升审视（2026-09-26，用户裁决）**：DOC-3 规则文本晋升 `docs/architecture/doc-governance.md` §3
  （与 DOC-1/DOC-2 同文；正控 = 同日 P-026 登记三处同步走通 + audit 0/0，selftest 59/59）。
  本条目改列 `retained`：保留作「义务文本 → 机检判据」的登记判例与 DOC-3 能力边界（结构性不可机检的那一半）
  的出处；取值口径的真源在抬头，不在此。

### P-026 · 质量叙事组装：P-021 闭环公开案例文档（2026-09-26）
> status: retained · since: 2026-09-26
- **来源**：09-25 审计报告建议 #1+#2（GT 工厂第一笔回报资产化），用户当日批准。原 P025 执行包的
  B 部分重编号落地；其 A 部分（G4 sanity 双指标）已被 round3 实证否决（`matched_rate 0/5` 非单调），
  整体废弃。
- **范围（git 5 文件）**：`docs/demo/QUALITY_CASE_STUDY.md` 公开案例文档（英文物料：测量→根因→修复→
  量化闭环，8 项锁定数字 + as-of 戳 + 诚实条款）；`docs/README.md` / `TRIAL_DEMO.md` 各加链接；
  本条目 + 抬头索引/计数同步 + CHANGELOG 段。
- **验收**：GB1（audit 0/0、selftest 59 不变）/ GB2（8 项数字逐项对账）/ GB3（diff 守恒 = 5 文件）。
- **状态**：已落地（PR #43 并入 main，三项必需检查全绿；明细见 CHANGELOG 与 git 历史）。
  **晋升审视（2026-09-26，用户裁决）**：无 architecture 内容可晋升——案例文档是对外 demo 资产，归宿即
  `docs/demo/`（已在）；结论已由 living 资产承载（`docs/demo/QUALITY_CASE_STUDY.md` + `docs/README.md`
  索引 + CHANGELOG + git 历史）。改列 `retained`：保留 as-of 2026-09-25 的 8 项数字对账基线、重编号缘由
  （P-025 已被 DOC-3 占用）与 A 部分废弃（round3 实证否决双指标口径）的记录。
- **保留核查（2026-10-16 清账批次）**：**保留理由仍成立**——`docs/architecture/doc-governance.md`（DOC-1/2/3 晋升流程）仍以本条为**正控先例**（「同日 P-026 登记实操」），条目不可移除；as-of 2026-09-25 的 8 项数字对账基线仍是对外案例文档与 CHANGELOG 的锚。**去留裁定 = 保留 `retained`，状态不变、正文不压缩**。

### P-027 · RF 频率分配表 fixture 簇：内容面表格 GT 触发（2026-09-30 Agent U 立项包；10-02 Ying 裁决立项）
> status: retained · since: 2026-10-02
- **保留理由（2026-10-16 清账批次：`decided` → `retained`；用户裁决）**：R1–R4 四轮与「产品侧立项 A / D8」已全部落地，**在途义务已清**（见下条）⇒ `decided`（= 尚有未完成动作）不再成立。保留的是**两样不可移除的东西**：① 下文「(0)–(3)」**口径冻结段**是入库文档的引用靶（`docs/architecture/ocr-quality-harness.md` 的 R2/R3/R4 行，含「三种分母并列见 PENDING P-027 (2)」）；② 下列两条**判例**。`since` 保留原裁决日；原 ~100 行流水账明细进 git 历史与 `docs/R&D/runs/P027/`。
- **在途义务处置（收口依据）**：① 「R3 缺口 1 · IE 语义层产品侧修复」= **A 项已落地**（2026-10-15，PR #85）；② 「D8 Confidence 产品源」= **已落地并经 Cloud 端到端验证**（2026-10-14/15）；③ 「分岔 C 优先级重排」已迁出为 **P-035**；④ 同域的 CI 触发范围残留已迁出为 **P-036**；⑤ 「BR 葡语解锁触发」与「R1 taxonomy 转用例」经用户 2026-10-16 裁决**移除**（不再作为工作项跟踪，明细进 git 历史）。
- **判例 1 · 「只评不修 + 粒度修正」的边界（R1–R4 结论骨架）**：R1 语言盘点（MY/BD/IE 主体英语，BR 葡语搁置）→ R2 弱 GT 合成与行级对账（23 页 / 1427 行；`line_match_rate` MY 0.9945 · BD 0.9885 · **IE 0.2308 = 已登记的已知局限口径，不回改**）→ R3 客户三金件机检化为**可复现行级秤**（闸 1 行级 join / 闸 2 频段在场 / 闸 3 `flag_rate`）→ R4 IE 语义层专项（**D4′ 跨块端点拼对**，配对单元 = 频段行，行重建 23 页 1.0000）。**X3 预研 NO-GO**（IE 文本层词级退化：词高中位 25pt 跨 ~2.5 视觉行 + 同内容双列重复 ⇒ 几何配对层救不了，真实修复在语义层）与 **X4 裁决**（R3 主体以「IE = line GT 已知局限口径」继续）是「**判据不因读数难看而回改、缺口如实登记**」的形态先例；**视觉第三腿（版面区块 IoU）判为结构性不可测，明确不发明 proxy**。R3 D4 边界（闸 1 = 字段级在场核对，`row_correct` 与 `presence_rate` 为两个独立强度判据、不互相折算）已于 2026-10-05 追认为正式口径。
- **判例 2 · 「先证接线、再验读数」**：D8 的 Cloud 端到端验证首轮八次全 `[FAIL]`，定案为**被测副本含模块、缺接线**（两侧静默返回 ⇒ 零告警的假阴性）⇒ 新增 `scripts/measure/check_d8_wiring.py`（5 锚点）并接进 E2E runbook 公共前置；次轮又暴露 `bool(np.ndarray)` 兜底雷（`_as_sequence()` 修法）。**流程教训：端到端报 "worker error" 时须先分清栈帧起点是产品代码还是引擎**，否则会把可静态定位的缺陷当成环境/版本不兼容。明细见 `runs/P027/R4-执行记录.md` 与 git 历史。
- **支撑事实（供上述两条判例的读者定位，不重复流水）**：资产与红线（客户四国 PDF / 三金件 / 28 列 schema；**客户 PDF·xlsx 永不进 git**、客户验收数字不作能力背书）｜ 隔离区与生命周期（`test_data/assets/upwork-…/` ↔ `test_data/derived/{gt,cache,eval,packs}/`，指纹口径为**内容指纹**非字节 sha）｜ 秤侧代码（`scripts/measure/{rf_rows,rf_gates,rf_eval,rf_sem_gt,rf_sem_eval,rf_*}*.py`，local-only 不入 git）。以上均在 git 历史与 `runs/P027/` 有完整记录。

- **产品侧立项 A · 合并格语义进 layout 行列结构（2026-10-09 Ying 裁决；✅ 已落地 2026-10-15）**：合并格语义解析落在 **layout 模型的行/列结构输出**（不在识别层、不做后处理糊层；**识别层**「只能旗标」立场不变，解锁的只是**语义结构层**）。**冻结口径**：`html_structure` 的 `rowspan`/`colspan`/`has_merged_cells`/`header_span_map` 为合并格语义**唯一真源**（无结构串时由 `data` 空串占位反推 covered 集）；**暴露面限管线内部**（`LayoutModel` merge band / `derive_cell_bbox` span bbox / backfill anchor-vs-covered），**不写进 result JSON / view 层**；cell 数据原值透传（禁修正小数点、禁猜值）。投影规则 = **方案 A（span 折叠对齐）**，含五条守卫（失败即两键都不挂 + 单表一条 warning ⇒ **降级而非发明**）与四类已知降级触发；三新键语义（`html_structure.span_map` / `cell_confidence_grid` / `cell_td_span`）与逐表读数面见 `docs/architecture/provenance-review.md` §4.4 与 `runs/P027/R4-执行记录.md`。**Cloud 复测（A3）读数未回升**（IE 列绑定 0.5278 / 合并格完整 0.7917）：根因经 A/B 实测判定为**判据自身的固有边界**（脚注 token 亦印在另一列 ⇒ D5「族→pred 列单射」判据边界，非合并格语义、非 matcher 缺陷）⇒ **「应回升」预期已撤回、判据前提不成立**；R2 的 IE 0.2308 旧读数**不回改**。

- **产品侧立项 D8 · Confidence 产品源 = OCR 块 `rec_score` 传导（2026-10-09 Ying 裁决；✅ 已落地并经 Cloud 端到端验证）**：产品侧 confidence 语义 = **PaddleOCR `rec_score` 传导**（`ocr_service` 的 `text_blocks[].confidence`），**非模型原生概率**；与既有 `kie_confidence_avg`（填充率启发值）**语义不同、不得混用或互相折算**。**来源裁决 = 方案 A**（同一次 PP-StructureV3 推理的 `table_res_list[].table_ocr_pred.rec_scores` ⇒ 零新增推理；**不得**为省事把 `text_blocks` 接上主管线而翻转表格数据来源）。**设计冻结三条**：①按格分组取 **min**（格内无条目 ⇒ `None`）；②逐表自动选帧（raw / flip 取命中多者，**平局取 raw**）；③**命中率哨兵**（`hits / n_rec < 0.8` ⇒ 整表 `measured = False` + `reason = frame_unresolved`，**绝不静默产出全 0 / 全 1**）。**契约**：`cell_confidence` 载荷 **7 键**（`cells`/`frame`/`measured`/`reason`/`hits`/`n_rec`/`n_cells`，**无 `unassigned`**）；**grid 在场 ≠ 已测量，消费方须先读 `measured`**；聚合 = cell 取 min、行级取 min；范围只做**表 cell + 行级**（KIE 字段级 confidence 不做，证据层无连接点）。**验收判例见上「判例 2」**；源选项取证（P1–P6 探针）、H1/H2 定案、接线四处落点、`layout_service.py` 1804→1614 前置重构、Cloud 端到端成败读数，均见 CHANGELOG 与 `runs/P027/`。
- **登记未解（不属本条裁决范围，勿在此取值）**：① harness **构建侧输出路径仍指向已退役的隔离区树**（`rf_gt.DERIVED` / `GT_DIR` / `PNG_DIR`、`rf_sem_gt.R4_DIR` 死常量）⇒ 跑 `build-rf-*` 会重建已退役目录树，**输出面重定位属另一决策**；② **A4 解锁触发未满足**（A 项已 ✅，但 RF 语料仍无 pipeline result JSON）⇒ 「定位 vs 识别」对照（口径 (0)）**锁定中**。
**待裁决与已裁决口径（2026-10-09 汇总；**唯一真源**）；（2026-10-13：(1) 已裁决；（2026-10-14：(0) 已裁决「不并列」· (2) 已裁决「绑定统一 D4′ + 非冻结读数」· (3) 批 1 / 批 2 均已落地（批 2 的契约面待在云验收））——**原「open · 3 项」已全部收口，无遗留 open 项**（(3) 云契约面复核 ✅ 2026-10-15 云实跑收口，见下方批 2「云端待办」收口记录；唯一遗留 = 重生成快照尚未入 PR #84）**
> 本节即**闸 3 与 D8 的口径唯一真源**（信号选择 / 绑定口径 / 聚合规则 / 非冻结读数 / 解锁触发），**勿回历史行取值**；裁决后同 commit 修订本节并落 `Session-check`。执行流水、取证读数、接线落点与 Cloud 验证环境真源见 CHANGELOG 与 `docs/R&D/runs/P027/`。
- **（0）闸 3 读数取哪个信号 —— ✅ 2026-10-14 裁决：取 pred 侧识别分（`rec_score` 传导），不并列版面检测分**：产品 Confidence 语义 = `rec_score` 传导 + 行级取 min（`table_cell_confidence.py`）；版面检测分（`layout_service.py:788` 的 `element['confidence']`，经 `envelope_builder.py:194/201` 透传、`:406/418` 聚合为 `quality.avg_layout_confidence`）是**检测框/分类质量**、产品不会写进 Confidence 列 ⇒ 拿它对标客户 ≤5% 是另一件事。**「定位 vs 识别」对照挪到表语料**（四件表：`layout.elements[].confidence` 与 `cell_confidence` 同在一份 result JSON，零新增推理）——**须如实说明粒度**：报告里的 cells 只留 `cells_sha256`（值在 R5/R6 探针里）⇒ **页级 `avg_layout_confidence` vs 格级分布，不是行级对行级**；要行级对照须先把 cells 落进报告。**RF 语料上 (a)/(c) 对照不可行**：RF 缓存来自 `/api/v1/ocr`、不含 layout 元素；且 `cell_confidence` 在 RF 语料部分页整页缺失（2/9 页 `tables=[]`），cell→频段行的投影依赖**未落地的 A 项**（合并格语义）⇒ 现在切对照会**静默缩小覆盖率**。**解锁触发**：**A 项落地 + RF 语料有 pipeline result JSON 时**，再补 (c) 与识别分的对照。**两信号语义不同，禁互相折算**（原纪律不变）。
- **（1）口径① 命中率阈值 —— ✅ 2026-10-13 裁决：维持 `0.8`（Ying）**：现值 **`0.8`**（`backend/app/services/table_cell_confidence.py:45` `DEFAULT_FRAME_OK_RATIO`，命名常量 + 注释记裁决）。**裁决依据（2026-10-13 扩充实测，八表）**：选定帧命中率 **19/19（bank）· 53/53（rep）· 124/124（p3）· 118/126 与 91/98（p2 两表）· 84/84（p1）· 45/45 与 51/51（bmcmed p6 两表）**、被拒帧 **0.00** ⇒ 空带比原三夹具更宽，任何 `0.0–0.84` 取值结果相同、余量充足。**维持理由**：**1.0 会误杀** `invoice_multipage_3p_items`（24/26 = 0.923 ⇒ 整表 `measured=False`）；**≤0.5 过松** ⇒ 错帧条目被归入错格，数字退化为"归格噪声"并**抬高** `flag_rate`。**复审条件**：仅当新夹具使选定帧命中率下探至 **<0.85** 时重审（现最低 0.923，余量 0.123）。**（已裁决，勿重开。）**
- **（2）口径② `high`/`medium`/`low` 切点（直接决定闸读数，属口径）**：秤侧公式 = `flag_rate = #{label ∈ (medium, low)} / #{有标签行}`（`scripts/measure/rf_gates.py:195-202`），硬线 `FLAG_RATE_GATE = 0.05`（`:39`，源自客户 Target 1）。实测分数**饱和且区间极窄**：bank 表条目 min **0.932009** / mean 0.991024、invoice 表条目 min **0.958547** / mean 0.990791、页面级 min 0.924591 ⇒ 观测下沿（0.93–0.96）与 5% 硬线**同量级**，故切点须钉在观测下沿附近才有判别力。**推荐：medium 起 0.95 / low 起 0.90**，并**同步声明该数值与客户 ≤5% 非同义**（`rec_score` 口径下的自定义阈值指标）。**连带必答两点**：①聚合规则已冻为 **cell 取 min、行取 min** ⇒ 行标签由**最差格**决定，行级 `flag_rate` **严格高于**格级，可比性说明须写明；②**分母缩小陷阱**——`rf_gates.py:196` 的 `confs = [c for c in confs if c]` 使**未测量行直接退出分母**，难表一旦 `measured=False` 会**美化**读数 ⇒ 须**并列输出"已测量行数 / 总行数"覆盖率**。**前置建议**：先跑一次 Cloud **直方图**探针再定档（现仅有 min/mean/max 三点，且 `pdf/sample_report` 的分数统计**未打印**），避免"猜档位"。**（2026-10-13 更新：前置已满足）** ①**探针侧直方图已有**——`probe_d8_table_ocr_scores.py` 落 `rec_scores_histogram` / `rec_scores_percentiles`（六夹具 + `overall_*`），`scripts/measure/R5|R6/**` 本地已存；②**闸 3 侧行级直方图与覆盖率已随 harness 落地**（见上「两侧缺一不可」条）⇒ 现在只差**一次云跑取行级读数**即可定档，且可用 summary 里的直方图**离线试算任意切点**而不必改代码。注：本地已有的六夹具表级 <0.95 占比为 **5.3%（bank）– 33%（bmcmed p6 表0）**，行级取 min 后只会更高 ⇒ 原推荐 `0.95/0.90` 的乐观性**须在定档时重估**。**（2026-10-14 更新：读数已落本机 + 用户裁决「本机已验证可跑的不上云」）** ①**可跑性**：`rf_gt.PDF_DIR` 迁移回退已加（`rf_gt.py:52-54`：取 `test_data/assets/*/raw` 中三件齐备者、`sorted` 保确定性）⇒ `python scripts/measure/rf_gates_cli.py evaluate-rf-gates --rows test_data/derived/gt/r3 --cache test_data/derived/cache --out <dir>` 本机即产权威三件；**必须显式传 `--out`**（CLI 默认 `rows.parent/eval_r3` 会写进 `gt/`，与既有产物目录不符）。②**本机实测（现行绑定口径 = T1 块内）**：`all` gt_rows 65 / joined 52 / row_correct **0.8000** / footnote_set 1.0000 / invented 3 / presence **0.8550**（112/131）/ **flag_rate 0.0577**（3/52，超 5% 硬线）/ coverage **0.8000**；分国 = MY 0.6000 / flag_rate 0.0000 / cov 0.6000、BD 1.0000 / 0.0741 / 1.0000、IE 0.8750 / 0.1429 / 0.8750；行级直方图（edges 0.80→1.00）counts `[0,0,0,0,2,1,0,2,9,10,28]`（**左尾 3 行落 [0.92,0.95)**，与 T1 口径下"仅 3 行可判"一致）。③**产物落点**：读入 `test_data/derived/eval/r3_v2`（**并列登记，不回改 `eval/r3` 的 R3 历史读数**——X4 口径）。④**遗留（已随本轮 D4′ 消解）**：`MY-p060` 的 `gate3_coverage` 渲染为 `-`（`n_joined=0` 时）——D4′ 后 `MY-p060` joined **6/6**、coverage **1.0000**，该形态在本语料不再出现；页级 `confidence_coverage` 在「有 GT 行但零测量」时仍记 `None`（渲染 `-`，语义 = N/A），保留原实现不改。⑤**相邻漂移 —— ✅ 已同批修**：`docs/architecture/ocr-quality-harness.md` 的 P-027 R3/R4 行已改述为 pred 侧 `rec_score` 读数（不再写「闸 3 flag_rate——Confidence 无产品源读 None」）。
  **（2026-10-14 裁决：绑定口径统一 + 非冻结读数）** ①**绑定口径统一**——闸 1/闸 2/闸 3 **一律用 D4′（T1 块内完整对 + T2 跨块端点拼对）**（`rf_gates.py` 新增 `_scan_endpoints` / `_page_binding` / `bind_pair`；闸 3 `row_confidence` 同步改 D4′），复用 R4 `rf_sem_eval` 已实证 1.0000 的行重建口径，**避免秤内两套绑定**。理由：旧「块内对扫描」把**整页级丢行**（频段被 OCR 读成两个块 ⇒ 落「未测量」并退出分母），**MY-p060 六行全因此形态**；统一后 65/65 回满。**脚注级风险**：T2 是**页级**端点存在性，端点重复时可能绑到邻行块——实测「严格邻接 T2」与「宽松 T2」结果**同形**（12 行邻接 + 1 行宽松）⇒ 脚注级、不单列。②**切点维持 0.95/0.90**——左尾最大间隙在 **0.947→0.9674**，0.95 正落其中（原预览值不必改）；**不为过线挪到 0.94**。③**读数并列登记、不回改历史**（同 X4 口径）——**D4′ v2**（`test_data/derived/eval/r3_v2`，GB2 同缓存双跑三产物**逐字节同**）本机实测：`all` gt_rows **65** / joined **65** / row_correct **1.0000**（R3 同面 0.8000）/ footnote_set 1.0000 / invented 3 / presence **0.9237**（121/131，R3 同面 0.8550）/ **flag_rate 0.0923**（6/65，**超 5% 硬线**）/ coverage **1.0000**；分国 = MY 0.0667 / BD 0.0741 / IE 0.2500（各 2 行 flag）。**三种分母并列（禁只报一个）**：现绑定 measured-only **3/52 = 5.77%** ｜ D4′ 后 measured（= 全 65 行）**6/65 = 9.23%** ｜ 「未测量按需复核计」（旧绑定）**16/65 = 24.6%**。**结论**：修好绑定后 RF 语料在 0.95 档下 **9.23% > 客户 5% 硬线**——登记为**内部回归基线**（**不是执行失败**）；被 flag 的 6 行含 R4 已定位的 **#7 失效行**（`IE-000040700000-000040980000` = p079 `40.7-40.98`）⇒ 该信号**有判别力**。④**非同义声明**：该数值与客户 ≤5% **非同义**（客户 Confidence 列语义**无原文定义**——`Output_format.pdf` 缺件，只能按样例推断；聚合规则格取 min、行取 min ⇒ **行级必然高于格级**；语料粒度 ≈ **1.5%/行**（65 行）⇒ **不宜做贴线结论**）；它是 `rec_score` 口径下的**自定义阈值指标**。⑤**新增 `gate3_flagged_rows`**（行 id 清单，页级 cap 8 / 汇总 cap 20，**确定性序 = 页序 + GT 行序**，`Row_ID` 缺则回落 `{page_id}#{行序}`）随 CSV/report/summary 落盘——此前只有计数与直方图、人工复核清单拿不到；**不破 GB2**。实测清单（`all`）：`BD-000018780000-000018900000` · `BD-001690000000-001700000000` · `IE-000040660000-000040700000` · `IE-000040700000-000040980000` · `MY-001700000000-001710000000` · `MY-001710000000-001930000000`。⑥**非冻结读数处理**：0.95 仅 `MEDIUM_CUT` **预览常量**（非口径），行级直方图 + coverage 随 summary 落盘 ⇒ 任意切点可**离线重算**、不必改码 ⇒ 读数以「**可复算基线**」登记而非冻结常量。**冻结的只有「口径选择与语义声明」**：信号选择（(0) 不并列）· 绑定统一（D4′）· 聚合规则（cell/row 取 min）· 非同义声明 · 解锁触发（A 项 + pipeline result JSON）。**验收**：`scripts/measure/test_rf_gates.py` **16 passed**（含 D4′ 跨块拼对 / 单端点不拼对 / `flagged_rows` 清单·回落·cap / CSV 列同步 + 双跑逐字节）。
- **（3）`0.0 → None` 语义修正（D8 姊妹项；2026-10-14 二次核查 = 可达性更正 + 修复面收窄 + 分两批落地，见下）**：把"未测量"塌成伪值的位置——①`layout_service.py:788`（近邻 3px 匹配失败 ⇒ `0.0`；**主路径可达**）；②`layout_service.py:854`（**`0.01` 魔法占位**，出现在 `inferred_bbox: True` 的推断兜底路径——该路径**根本不存在检测结果**，却给出一个"像分数"的常数；**2026-10-14 二次核查更正：不可达**——该分支在 `:670 if 'parsing_res_list' in item_keys:` 之后，而 `:826` 已 `return elements` ⇒ **与 ⑤ 同因**，**降为登记项、不列入修复**）；③`table_service.py:431`（`"confidence": 0.0,  # No confidence score available`，恒 `0.0`；**行号更正**：旧记 `593-594` 系 1804 行版本的行号）**＋姊妹点 `:260`**（`element.get('confidence', 0.0)`——把版面检测分当表置信度，同一塌陷形态，2026-10-14 新增）；④`envelope_builder.py:27-34`（`_as_confidence(value, default=0.0)`，`None`/非法 ⇒ `0.0`；调用点 `:194` / `:201`）。
  **2026-10-14 核查新增三处**：⑤`layout_service.py:953`（`float(score) if score else 0.0`）——入口 `:925` / `:931` 把缺字段默认成 `0`，且用**布尔真值** `if score` ⇒ 真实 `0.0` 与"字段缺失"不可区分、对 ndarray 会抛（与 D8 同型雷）；**但生产不可达**：`:670` 的 `if 'parsing_res_list' in item_keys:` 在 paddlex 3.3.12 恒真 ⇒ `:826 return elements` 提前返回，双保险 = R5 实测 `result_item_keys` 无 `preds`/`boxes`/`layout_dets` ⇒ `:901` 再次 return。**仅登记为死分支/潜在雷，不计入修复**）；⑥`envelope_builder.py:406`（`np.mean(confidences) if confidences else 0.0`）——**这正是产出 `quality.avg_layout_confidence` 的兜底本身**：空列表 ⇒ `0.0`，与"测得很低"不可区分，且 `np.mean` 会把上游**非零伪值**（如 ④ 的 `0.01`）一并平均进去（`0.0` 则在 `:390-391` 被 `> 0` 滤掉，不进分母 —— 见下更正）；⑦`routers/tasks_content.py:184-185` 与 `:230`（`float(confidence_raw or 0)`）——**对外 API 响应**面把 `None`/缺失 ⇒ `0.0`（落在 `routers/` 而非 `services/`，最易漏）。
  同型但不属 D8 面板（一并登记、不并入本项）：`figure_service.py:616`（`"confidence": 0.0`）、`seal_service.py:234`（`float(... or 0.0)`）；反例：`document_type_classifier.py:73/79` 的 `0.0` **语义正确**（"无提示"本就是 0），**不算塌陷**。
  按 D3/D7「未测量 ≠ 0」**均应 `None`**。**危害描述更正（2026-10-14 二次核查，读 `envelope_builder.py:390-391` 的 `conf = block.get("confidence", 0.0); if conf > 0`）**：`0.0` **不会拉低均值——它被剔出分母**，⑥ 的真实病是**分母静默缩小**（把"没测到"伪装成"没这块"）；真正入均值并拉低均值的只有 ④ 的 `0.01`（`>0` ⇒ 入均值）。影响面：**已对外暴露**的 `quality.avg_layout_confidence` 与**真实的低分检测**不可区分（把"没测到"伪装成"测到很低"），与（2）的覆盖率问题同源。**定量证据（2026-10-14，官方四件读数）**：`bank` 的 `avg_layout_confidence = 0.3540` 远低于其余三件（`rep 0.9033` / `inv 0.7797` / `pico 0.7508`），而 R5 探针显示该页 `layout_det_n_boxes = 2` ⇒ 多数元素在 `:788` 邻域匹配失败落 `0.0` 后**退出分母**，0.3540 只是少数命中块的平均（`conf==0.0` 的逐元素计数 **✅ 2026-10-15 官方云跑核实（HEAD = 批 2 代码提交）**：四件 `layout.elements` 逐元素 `conf==0.0` / `None` / 缺键 **三项全 0**（bank n=2 / inv n=29 / pico n=35 / rep n=14）——官方四件上伪 0.0 **未现形**，且 `bank` 该页**本就只检出 2 个版面元素**（与 R5 探针 `layout_det_n_boxes=2` 同值）⇒ `avg=0.3540` 即这 2 个真实元素的平均，本条旧假设「多数元素匹配失败落 0.0 退出分母」**不成立**（低均值 = 元素确实少，非分母被伪值缩小）；**反例参照**：IE 9 页 result JSON 实测逐元素 conf **全非零** = `zeros=0`）。
  **登记建议（用户 2026-10-14 裁决采纳）**：登记为 D8 姊妹条目。**修复面（按可达性收窄）** = ①③（含姊妹 `:260`）④⑥⑦；**②⑤ 仅登记**（同因不可达）。
  **契约影响（决定批次划分，2026-10-14 核查）**：
  - ③（含姊妹 `:260`）**纯内部**：`tables[]` 不在任何 pydantic 模型 / `response_model` 中（`routers/tasks_content.py:30-37` 直返裸 dict），且两侧消费点已写死"`None` → 回落 `score` → 0"（`services/export_service.py:22-26`、`frontend/modules/utils/csv.js:52-55`；`frontend/modules/result-panels/tables.js:284` 亦把非 number 归一为 `null`）⇒ **不动模型 / 快照 / 前端**。
  - ①④⑥ 与 ⑦ **属对外契约变更、共用一个契约面**：`FusedBlock.confidence: float = 0.0`（`models/api_models.py:40`）与 `QualityLayer.avg_layout_confidence: float = 0.0`（`:146`）经 `routers/jobs.py:41` 的 `response_model=JobEnvelope` 暴露；`tests/snapshots/openapi_baseline.json:599-603` / `:988-992` 声明 `"type": "number"`（另有默认对象 `:792-793`）⇒ 改 `Optional[float]` 必须重生成快照（cloud-only：`DOCUVISION_CLOUD_TESTS=1 DOCUVISION_OPENAPI_BASELINE=write`）。**三项连带（缺一即红）**：(i) `envelope_builder.py:391` 的 `conf > 0` 对 `None` **抛 `TypeError`**（质量层直接崩）⇒ 必须同批 None-safe；(ii) `tests/test_envelope_builder.py:89-96` 的 `TestNullConfidence` **现钉死** `block["confidence"] == 0.0` / `payload.confidence == 0.0`、`:233-234` 钉死 `isinstance(..., float)` ⇒ 本项是**意图变更**，不许可默默改测试；(iii) `jobs.py:41` 带 `response_model_exclude_none=True` ⇒ `None` 在响应里的语义是**键整个消失**（`payload` 内 `Dict` 值同样被剔除），不是输出 `null` —— 消费方须按"缺键"处理。
  **行数约束（棘轮只减不增）**：`layout_service.py` 1614 = 上限 · `table_service.py` **795 = 上限**（**更正**：旧记"1336 = 其棘轮上限"已随 F1 拆分过时）· `envelope_builder.py` **620 = 上限** · `routers/tasks_content.py` 425/500（余 75）。⇒ 批 2 若在 `envelope_builder.py` **新增**键（如 `blocks_without_confidence`）必然越线（红线禁抬高上限）⇒ 只能做"类型/默认值层面的等价改写"，或先在同文件内腾出等量行。
  **分两批落地（2026-10-14 用户裁决）**：
  - **批 1 · ✅ 已落地（纯内部）**：③ 两处——`:260` → `element.get('confidence')`（**今日为 no-op**：① 未改前 `element['confidence']` 恒为 float；其作用是让 ① 落地后表级如实为 `None`，避免批 2 漏改）、`:431` → `None`。行数不变（795 = 上限，未触棘轮）；验收 = 后端全量 pytest + `lint_file_size` + `audit_agent_ops` 全绿；**不涉模型 / 快照 / 前端**。
  - **批 2 · ✅ 已落地（2026-10-14，①④⑥⑦ 同批；本机可判定部分全绿，契约面待在云验收）**：**①块级** `layout_service.py:788` 近邻匹配失败 `0.0 → None`、`envelope_builder.py:27-28` `_as_confidence(default=None)` 保 None（调用点 `:194`/`:201` 不改）；**②页级** `:390-391` 入集判据 None-safe（`conf is not None and conf > 0`）、`:406` 空集 `0.0 → None`、`:418` `float()` 加 None 守卫；**契约** `api_models.py:40` `FusedBlock.confidence: Optional[float] = None`、`:146` `QualityLayer.avg_layout_confidence: Optional[float] = None`；**⑦** `tasks_content.py:184-185`（信封路径）与 `:230`（legacy 路径）不再 `or 0` 塌陷 ⇒ `None` 透传。**本机验收**：后端全量 `617 passed / 19 skipped / 5 采集错误`（与基线同形、**零新增失败**）；`lint_file_size OK`、`audit_agent_ops 0/0`、`lint_routes OK`、`lint_frontend OK`。**前端零改动**（既有"未测量表达"先例已覆盖：`csv.js:51-58` 的 `null → 回落 score → 0`、`tables.js:284` 归一非数值为 `null`、`text.js:185-190` guard `!= null`、`shell/ui.js:294` 与 `figures.js:65` 的 `|| 0`；`figures.js:49-51` 与 `text.js:215-217` 的旧渲染路径对 `null` 仍是 `0.0%`，与改前同形）。**行数中性核对**：`envelope_builder.py` 6 增 6 删 · `layout_service.py` 1/1 · `table_service.py` 2/2 · `api_models.py` 2/2 ⇒ 三个贴顶文件（620 / 1614 / 795）**一处未越线**；`tasks_content.py` 净 +1 行（425/500，非棘轮文件）。
    **「意图变更」声明（2026-10-14 用户裁决执行；本批不是缺陷修复而是语义切换）**：现行行为**三条全中被声明** ⇒ ①测试 `tests/test_envelope_builder.py:89-96` `TestNullConfidence`（注释即动机 "layout may emit confidence=None when det score unmatched"，断言 `== 0.0`）；②契约 `api_models.py:40/:146` + `tests/snapshots/openapi_baseline.json:599-603/:988-992`（`type: number` / `default: 0.0`）；③实现动机 `_as_confidence(value, default=0.0)` 本身就是该声明的落地。**旧公开语义** = 「confidence 是浮点数，缺分即 `0.0`」（= 未测量与测得 0 合并）；**新公开语义** = 「confidence 是 `Optional[float]`，缺分即 `None`，并经 `routers/jobs.py:41` 的 `response_model_exclude_none=True` 在响应里表现为**键消失**」。**三个抉择点（用户采纳推荐）**：①块级改 `Optional`；②页级空集 `None`（**不新增 `blocks_without_confidence` 键**——那正是上条行数约束里会撞 620 上限的备选路线）；③**接受"键消失"、不动 `exclude_none`**（该开关是**路由级**，为一个字段打开会波及整条响应里所有 None 字段）。**测试面成本 = 1 个用例、2 行断言**（`TestNullConfidence`：`== 0.0` → `is None` + 注释反映新意图）；**其余零改动**——`test_avg_layout_confidence_type`（`:233-234` 的 `isinstance(..., float)`）**存活**（其夹具全为 `_elem(..., conf=0.9)`，`_elem` 默认 `conf=0.9`）。**客户可见面零影响**：受影响字段只在内部 `JobEnvelope` / task result JSON；客户交付物是 28 列行 CSV/JSON，导出层已有 `None → score → 0` 回落（故对客户交付契约无改动）。**顺带扩散（如实登记，同向更诚实、无崩溃）**：`figures[]` 的 `confidence` 由 `figure_service.py:492` 的 `elem.get("confidence", 0.0)` 取值，元素未匹配时由 `0.0` 变 `null` ⇒ `pack_export_service.py:222` 该列由 `"0.0"` 变空串，前端渲染同形。
    **云端待办（本批唯一未完成项）→ ✅ 云验收完成（2026-10-15 云实跑回传，HEAD = 批 2 代码提交）**：①基线重生成 diff 实测**只含两字段**——`FusedBlock.confidence` `{default:0.0, type:number}` → `{anyOf:[number,null]}`（pydantic v2 对 `Optional[float]=None` 不写 `default: null`）+ `QualityLayer.avg_layout_confidence` 同型（该 hunk 在回传 diff 截断处之后，待入 PR 后本地对 origin 复核）+ `quality.default` 对象删去 `"avg_layout_confidence": 0.0` 一行 ⇒ 判据满足；②契约面 **13 passed**、全量 **649 passed / 1 skipped**（与上轮 659 的差 = `test_live_api.py` 10 例被 `--ignore`，本机 collect 已核实 = 10 tests，**无掉用例**）；write 跑 `1 passed, 1 skipped`（skipped = 写完基线即 `pytest.skip("baseline written")`，路由数 54 守卫 passed）；③批 2 轻量数据件（`bank` 的 result.json 逐元素计数）随 D8 E2E official 一并取回：四件 `conf==0.0`=0 / None=0 / 缺键=0（见上条 2026-10-15 核实）；`avg_layout_confidence` 四件与改前逐位一致（0.3540049 / 0.9032753 / 0.7796613 / 0.7507506）——均值不变为预测结果（伪 0.0 本就被 `conf>0` 剔出分母），且 bank 仅 2 元素全有实测分 ⇒「如实重算」成立。**~~遗留 1 项~~ ✅ 已闭合（2026-10-16 复核）**：重生成的 `backend/tests/snapshots/openapi_baseline.json` 已随 **PR #84 合入 main**（该快照已随 PR #84 并入 main），本地实测该快照 `avg_layout_confidence` 已为 `anyOf:[number, null]`（`backend/tests/snapshots/openapi_baseline.json:993-996`）；**A 项 PR #85 亦已合**（合入后即当前 main HEAD）⇒ 本批**无遗留**。**本机 `fastapi` 未装 ⇒ 本机绿不得当契约面证据**（本机基线那 5 个采集错误里就有 `test_blocks_reading_order.py`）。
  **登记（用户 2026-10-14 指出；本轮留档、未改代码）**：`backend/app/services/table_cell_confidence.py:260-265` 的 `attach_cell_confidence` docstring 写 "Tables without an element, or with an unmeasured payload, are left untouched"，**与实现不符**——`measured=False` 的载荷是非空 dict（truthy）⇒ **照挂**（本机以 `measured=False` + `cells=[None,None]` 试跑得 `attached=1`；E2E 记录亦印证 `pico measured=false` 被报出）。**两条后续**：①~~该 docstring 应改为"未测量载荷照挂、由消费方查 `measured`"（1 行、零风险，可并入批 2 或单独提交）~~ **✅ 已随 A 项修正（2026-10-15）**：`table_cell_confidence.py:394-395` 现为「An unmeasured payload (``measured=False``, ``cells`` all ``None``) is attached as-is — consumers must check ``measured`` before trusting ``cells``」，与实现相符（见 A 项审查结论 ⑧）；②**消费方纪律**：读 `cell_confidence` 前必须先查 `measured`，否则 `cells` 全 `None` 会被误当"已测量"——**该纪律现已同名外延到投影 grid**（`cell_confidence_grid` 在场亦**不等于**已测量，见 A 项审查结论 P2-1）。
- **A 项（合并格语义/投影规则）落地收口（2026-10-15；取代本节「仍未做」:630①，投影规则已定档并实现）**：**投影规则 = 方案 A（span 折叠对齐）**——①**锚位在解析处**：`table_html.py` 抽 module-level 共享占位走查 `_walk_occupancy`（`_html_to_data` 与 `_extract_html_structure` 同源，消除两处行过滤漂移；行一致性过滤分支经核实为**死代码**——每行恒 `[''] * max_cols` ⇒ ratio 恒 1.0——原样保留），`html_structure` 新增 **`span_map`**（`<td>` 文档序、每项 `{row,col,rowspan,colspan}`，**row/col = 输出行索引**：仅在该行被 `any(cell.strip())` 接纳后提交 ⇒ 丢空行不偏移；`>20` 列截断同步丢 `col>=20` 锚位；无 `<table>` 早退 `return {}` 不变，钉死 `test_table_header_structure.py` 既有精确断言）；②**续位 = `None`**（非 0、非复制值）：`table_cell_confidence._project_cell_confidence` 由 `attach_cell_confidence` 逐表调用（**签名不变、orchestrator `:287` 零改动**），产出 `cell_confidence_grid`（与 `data` 同形）+ `cell_td_span`（与 `cells` 同长、`<td>` 序，由 span_map 单一计算派生）；③**投影与 backfill 信任门控解耦**——不走 `backfill_table_cells`（其只在 trusted / rotation==0 / 非 deskew-unwarp 页运行，会把不可信页的已测量表静默判为无 grid），故 `table_backfill.py` **零改动**；④**五条守卫**（字段 list / `len(span_map)==len(cells)` / int 且 span≥1 / 锚位含 span 端点界内 / **语义位**＝覆盖矩形非锚位格须为 `''` 且锚位不重复）任一失败 ⇒ 两键都不挂 + 单表一次 warning（含 id+原因），**降级而非发明**；**已知降级触发四类**：`max_cols<2` 单列表、`>20` 列宽表、嵌套 `<table>` 致 `find_all` 递归多计、PaddleOCR 版本漂移致 `len(cell_box_list) != td` 数。**读数面**：`proof_report` 指标卡增「低置信/未测量格」格卡 + 逐表第 8 列（`low/unmeasured`），统计经 `summarize_cell_confidence` 读**扁平载荷**（`measured` 为第一判据）⇒ grid 降级或不可信页下读数仍成立；`LOW_CONFIDENCE_CUT = 0.90` 为**未裁预览常量**（同 (2) `MEDIUM_CUT` 处理，可离线按直方图重切）。**payload 体量增长（如实登记）**：每表 +`格数×float`（grid）+ `格数×小字典×2`（span_map + cell_td_span，后者与 span_map 同值——四项定档之"扁平侧可辨识合并格"义务所致，由 span_map 单一计算派生非独立重算）。**本机验证**：全量 **646 passed / 19 skipped / 5 collection errors**（开工基线 617 → **+29** 新用例 = 特征化 9 + span_map 6 + 投影/汇总 13 + proof pack 1，零回归；5 error 为既有无 fastapi/paddle）；`lint_file_size OK`（`table_html.py` 392→**444**、`table_cell_confidence.py` 279→**414**、`proof_report.py` 461→**482**，均 <500；`table_service.py`/orchestrator/`envelope_builder.py`/`layout_service.py` 四固化文件零改动）；`audit_agent_ops 0/0`、`docs_refs_audit 0/0`、`lint_frontend OK`。**A3 云采集已执行（2026-10-15；判据未达成，且经实测判定「判据前提不成立」）**：回传包 `test_data/derived/packs/r4_results.tar.gz` 解包至 `packs/r4_cloud_upload/r4_out/`，**sha256 9/9 复核 0 不符**；云侧 = **本分支 HEAD**（含 A 项）+ `dirty_files=0` + **`paddleocr 3.3.2 / paddlex 3.3.12`（锁定栈零漂移）** + NVIDIA A10。回传 envelope **确认含 A 项三新键**（`html_structure.span_map` / `cell_confidence_grid` / `cell_td_span`）⇒ **投影确已触发**；挂载 **5/7** 表（p079/p197/p318/p331/p363 挂 grid；**p007 `span_map` 48 vs `cells` 47、p158 29 vs 26 两表按守卫降级**——两键都不挂、诚实缺键，属已知的 td 计数漂移类）。**读数 = IE 列绑定 0.5278 / 合并格 0.7917，与 A 项前 `eval/r4` 基线 23 个逐页行逐字节相同**（新读数并列登记于 `eval/r4_a`，**不回改历史**）⇒ **判据「应回升」未达成**。**根因（两条秤侧路径均 A/B 实测零影响）**：①秤的 pred 侧**只读 `tables[].data`**（`scripts/measure/rf_sem_eval.py` 的 `load_envelope_cells`），A 项对 `data` 零改动（实测 9 页 `data` 与 `html_structure.rows` 新旧**逐字节相同**）；②本语料合并格**只有 rowspan、`colspan` 恒 1** ⇒ **span 锚列 ≡ 网格列（恒等）**，把 `load_envelope_cells` 改走 span_map 预期提升 **0**（A/B 逐页同）；③**词法边界匹配**（本轮已采纳，见下）在本语料 **A/B 逐实例命中集 0 差异**。**四个失分族同属一类**：脚注 token **亦印在另一列**——`IE-p197` 法规列**真印**交叉引用 `5.925`（**非**数字串片段；早先判读已更正）、`IE-p318`/`IE-p331` 脚注定义散文列、`IE-p007` `rowspan` 频段标签合并格吸收了下行标签 `5.317A` ⇒ 属 **D5「族→pred 列单射」判据的固有边界**，**非合并格语义、非 matcher 缺陷、非 A 项可触及**；**R2 IE 0.2308 未回改** ✓，`:663` 的「应回升」表述已同步更正。**本轮采纳的秤侧改动（local-only，不入 git）**：`bind_columns` 候选筛选改**词法边界命中**（`lexical_hit` + `unit_squash`：token 出现处前后不得紧邻数字，且判定域须**保留印刷 token 分隔**）——**硬化而非读数推动项**（本语料 0 差异）；回归 = `scripts/measure/test_metrics.py` 新增 `test_r4_eval_column_binding_lexical_boundary_known_answer`（含「整体 squash 域会误杀 `5.150 ECA36` 的 `ECA36`」钉死）；`pytest scripts/measure/test_metrics.py` = 改前 **71 passed / 1 failed / 1 skipped**（失败项 = `test_r4_eval_glue_probe_known_answer` 的 `test_data/rf-quarantine/itu/ITU_services.csv` stale 硬路径，自 2026-10-04 重组起红），**已修**（见下「附带修复」④）⇒ 改后 **77 passed / 0 skipped**。**与 GT 侧口径的故意差异**：`rf_sem_gt.service_tokens` 的服务**长词表**匹配用字母数字+连字符边界（`(?<![a-z0-9-])`），本轮 `lexical_hit` **收紧为仅数字边界**——脚注 token 常与词粘连（`RADIONAVIGATION5.76`，正是 #5 探针形态），字母边界会误杀这类**真出现**；数字边界只拦「更长数字串的片段」，即本指标要拦的形态。**A3 附带修复（2026-10-15；均 `scripts/measure/**` local-only、不入 git）**：①**默认路径回退**——`rf_gt` 新增 `ROWS_DIR` / `SERVICES_CSV`（沿 `PDF_DIR` 先例：**旧路径优先、缺失即按 2026-10-04 迁移后位置回退**，sorted 保确定性），`rf_sem_eval.evaluate_pages` 默认与 `rf_sem_cli` 的 `--rows` 改用它；②**不再静默**——`evaluate_pages` 在 `rows_dir` 缺 MY/BD 行时打 `[warn]`（此前零报错地把两国行级 GT 记空）；③**伪页面**——新增 `rf_gt.list_page_ids`（`PAGE_ID_RE`，宽松 2-4 位国别码 / 1-5 位页号），`evaluate_pages` 由**缓存目录派生页集**处改用它 ⇒ `cache/manifest.json` 不再成行；`rf_gates.evaluate_rows` / `rf_eval.evaluate_files` 先按 GT 派生页集、缓存仅作查表（多余 key 惰性）**未改动**（`list_page_ids` docstring 已注明）；④**同族 stale 硬路径清扫**（后三处为本次新发现）——`test_metrics._IE_PDF`（旧 `rf-quarantine/pdf` 硬路径使 **C2 金样闸自迁移起被静默 skip**）、`test_r4_eval_glue_probe_known_answer` 词表路径、`rf_sem_gt.verify_gold_sem` 与 `derive` 的两处词表路径、`derive` manifest 的 `services_csv.relative_to(QUARANTINE)`（迁移后必抛 `ValueError`）——一律改走 `rf_gt` 迁移感知常量 / 新 `_src_path`（相对仓根，失败退绝对值）。**验证**：`pytest scripts/measure`（三个测试文件）= 改前 3 failed / 1 skipped ⇒ 改后 **128 passed**（含本轮新增三口径回归 ⇒ 77）；**不传 `--rows`/`--services` 直跑** `evaluate-rf-sem` ⇒ `[all] pages` **24→23**、MY/BD GT **30/27** 行齐备、读数与传参跑**逐位一致**（IE 0.5278 / 0.7917）。**已裁决并落地（方案 A，2026-10-15）：聚合三口径并列**——原登记缺陷：①**聚合率列口径不自洽**——`rf_sem_eval._aggregate` 率列取「**有读数页的均值**（macro）」，而同行的计数列是**求和**（micro）⇒ IE 报 `col_binding_rate` **0.5278** 而 micro 是 `7/11 = 0.6364`、`merged_complete_rate` **0.7917** 而 micro 是 `5/7 = 0.7143`（`row_rebuild_rate` / `glue_rate` 在 IE 上两者恰好同值；`[all]` 的 glue macro **0.0049** vs micro `3/326 = 0.0092`）；**根因 = 与同家族 R3 三闸口径不一致**——`rf_gates.aggregate` 的率列**全部按计数重算（micro）**且带 `gate3_coverage`（防「分母缩小陷阱」），`rf_sem_eval` 侧既无 micro 亦无 coverage；**落地（纯加法、未覆写历史产物）**：(a) 并列 **`*_micro`**——分子/分母 = 同行**已有**计数列（`MICRO_SPEC`）⇒ 不可能与计数漂移；(b) 并列 **`*_coverage`**——有读数页 / 本 scope 页数；(c) 四个 `*_rate` 列名**不改**（语义仍是 macro），**引用口径钉死 = micro**（与 R3 对齐），口径声明落在 report 的 `<h2>Rate aggregation</h2>` 段与 `summary.json` 的 `notes`；`*_micro`/`*_coverage` 是**聚合层**量 ⇒ 页级行显式 `None`（渲染 `-`）。**实测新读数（本次重跑）**：IE `col_binding` macro **0.5278** / micro **0.6364** / coverage **0.6667**、`merged_complete` macro **0.7917** / micro **0.7143** / coverage **0.4444**；`[all]` macro **0.5278** / micro **0.6364** / **coverage 0.2609**（**仅 6/23 页有列绑定读数**——此前不可见的分母真相）、`glue` macro **0.0049** / micro **0.0092** / coverage **0.7391**。已按 (c) 在 `CHANGELOG.md` 与 `docs/architecture/ocr-quality-harness.md` 的 R4 行标注 macro 并同时给出 micro。回归 = `scripts/measure/test_metrics.py::test_r4_eval_aggregate_macro_micro_coverage_known_answer`（构造 macro ≠ micro 的已知答案：0.75 / `2/3` / coverage 0.5）。**仍登记（未修、待裁决）**：①**构建侧输出路径仍指向已退役的隔离区树**——`rf_gt.DERIVED` / `GT_DIR` / `PNG_DIR`（`build-rf-gt` 会 `mkdir(parents=True)`）与 `rf_sem_gt.R4_DIR`（现为**死常量**）仍解析到 `test_data/rf-quarantine/derived/**` ⇒ **照跑会重建已退役目录树**；输出面重定位（落 `test_data/derived/gt/r2` 或别的）属另一决策，本轮未动。**A4 触发条件**：A 项 ✅ 已落地 + RF 语料有 pipeline result JSON（未满足）⇒ (c) 对照仍未解锁（见 (0)）。

- **A 项 PR #85 审查结论（2026-10-15；自审 ⇒ 独立性弱于他人审查，规范 = `docs/agent-ops/review.md`）**：结论 = **有条件通过（无 P0）**。**P1-1**（载荷双份序列化且当前无生产消费方：`cell_td_span` 与 `html_structure.span_map` 同值、全仓引用只有测试 ⇒ 建议删一或按 `has_merged_cells == False` 省略投影）**明示接受、择一延后**；**P1-2 已于本 PR 内处置**（五类守卫分支补齐 5 条单测 + 夹具钉死「失败时两键都不挂 + 每表恰一条 warning」+ 具体 reason 入断言，该文件 32 → 37 passed）；**P2 可延后五项**：grid 的 `None` 二义与 docstring 反读风险（契约措辞「grid 在场 ≠ 已测量，须读 `measured`」已补）· `header_span_map` ↔ `span_map` 命名近义 · 逐表列不可区分「表未测量」与「已测量但零条目」 · `LOW_CONFIDENCE_CUT` 暂无判别力（输出面自带 preview 标注、不误导）· 投影成败不可观测（返回值被丢弃、无计数）。**核验通过项**：投影逐表无条件执行且不经 backfill 门控 · orchestrator 零改动 · `tables[].data` 语义逐字节未变 · 无 `<table>` 早退 `{}` · 四固化文件零改动 · 降级不发明值 · 前端不读新键。测试范围 = 本机纯逻辑三文件 + `pytest scripts/measure`（128 passed）；需 Cloud/GPU 的项**无新增**。明细见 `runs/P027/` 与 git 历史。

**D8 端到端验证的环境真源（2026-10-13 / 10-14 两轮 Cloud 事故与收敛）**

- **首轮八次全 `[FAIL]`（2026-10-13）**：四件 × 两版（patch / official）**零告警同形失败** ⇒ 定案（H5）= **被测副本含 D8 模块、缺 D8 接线**（模块与接线是两个提交；`table_cell_confidence.py` 的 `if ocr_pred is None: return None` 与 `layout_service` 的 `if cell_confidence:` 都在**静默**返回 ⇒ 探针只查"模块能否 import"、**不查接线** = 假阳性）。**流程教训（已一般化，即「判例 2」）**：端到端验证前必须先核验「被测副本是否含目标接线」⇒ 新增 `scripts/measure/check_d8_wiring.py`（5 锚点）并接进 `d8_e2e_run.sh` 的**公共前置**。
- **第二轮 official 四件整页崩（2026-10-14，接线补齐后）**：`[NO_TABLES]` + `layout_elements_n=0` + `worker error: The truth value of an array with more than one element is ambiguous`。**根因定死在本机代码**：`cell_confidence_from_table_item` 三处兜底写成 `… or []` 而 PP-StructureV3 给的是 `np.ndarray` ⇒ `bool(ndarray)` 抛 `ValueError` ⇒ 整页 `_parse_result` 失败（聚合体本身 array-safe，**只有兜底是雷**）。**同时推翻上一轮判据**：「`_parse_result` 属主进程 ⇒ worker 报错与接线无关」是错的——`_parse_result` 就在 worker 里跑。**修法** = 新增 `_as_sequence()`（ndarray→list，永不对原始字段取真值）。
- **收敛读数**：**四件 × 两版全 `[ALL PASS]`**，`cell_confidence` 7 键齐、无 `unassigned`；`bank` `flip → raw`、`pico#p3_e2` `measured false → true` 且 `hits 1/124 → 118/124`，`rep` / `inv` 两版 `cells_sha256` **逐字节相同**（patch 零扰动）；`d8_e2e_report.py --compare` 三项 verdict 全 true；cloud-only 全量 **659 passed / 1 skipped** ⇒ **加键未破路由契约、`openapi_baseline.json` 无需重生成**。运行手册与读数工具（`D8_E2E_RUNBOOK.md` / `d8_e2e_run.sh` / `d8_e2e_report.py`）均 local-only。
- **遗留（登记）**：`layout_service.py` 1614 行 = `scripts/file_size_allowlist.json` 既有上限 ⇒ 「把 worker 送回的子栈帧落日志」这一**可诊断性缺陷**改动**未落地**（**抬棘轮属红线**，须先在别处腾出余量）。

- **相关**：P-027 R3/R4（秤侧出处）· `docs/architecture/ocr-quality-harness.md` §4 钉死设计点 D8 · P-028（sanity 旗标可作辅助信号，本批不并入）
- **`docs/R&D/runs/P027/` 保留理由（2026-10-07 登记；2026-10-16 更新——本条已转 `retained`，保留依据由「在途义务未清」改为「被 tracked 文档反引」）**：该目录 5 件（`R2-执行记录` · `R3-执行包` · `R3-执行记录` · `R4-执行包` · `R4-执行记录`）**尚不可删**——`docs/R&D/README.md` 的 runs 政策以「无 tracked 文档仍引用它」为删除前提，现存三条反引：① 本仓 P-002 条目（follow-up 触发证据段）把 IE-p079 判据指向「P-027 R4 执行记录 §4.1」；② CHANGELOG `[1.11.0]` P-027 R2/R3/R4 三段以 `runs/P027/R3-执行记录.md` / `R4-执行记录.md` 为 execution record；③ R4 记录 §6「保留判据与明细」是隔离区 `test_data/derived/**` 证据链的唯一盘存表。**触发**：待上述引用全部转指其它载体时，同批删除本目录并同步 `docs/R&D/README.md` 的 runs 索引（对照：P-030/P-031/P-032 的 local-only 执行包已按「提炼后删除」清理）。

### P-033 · 测试夹具可复现哨兵：生成器 `--check` 进 CI（2026-10-08）
> status: retained · since: 2026-10-08
- **保留理由（2026-10-16，`landed` → `retained`；用户裁决）**：门禁与边界均已入库——CI 步骤 `.github/workflows/lint.yml:91-92`（`lint` job 内 `node test_data/scripts/generate_general_testfiles_pure.mjs --check`）、`module-map.md` §5 行 **E3**、`test_data/testfiles/README.md` R3、CHANGELOG `[Unreleased]`；本条目保留的是 **E3 边界**（只覆盖该生成器的三个输出目录；图片类夹具与其它生成器须先证「内容指纹可复现」才纳入）——`module-map.md` E3 行的「图片类/其他生成器见 P-033 边界」即指向本条，故不能随晋升一并删除。`since` 仍记原始落地日。
- **来源**：2026-10-08 夹具收敛批次（PR #74）实测——`generate_general_testfiles_pure.mjs` 与已提交样例**不幂等**：4 件因早于 ASCII-safe 修复而文本层带 U+2014 三字节乱码（pdfplumber 读作 `(cid:226)(cid:128)(cid:148)`），1 件因列宽默认值变化重生成即并字（`Professional services4 0- Phase 1`），1 个 README 漂移。**漂移此前完全无机检**：只有人重跑才看得见——与 P-008「声明的东西是否真被接上」同类缺口。
- **机制**：生成器已具备 `--check`（不写、列出漂移件、有漂移 exit 1）与 `--only <文件名>`；本条目把它**接进 CI**——在既有的必需检查 `lint` job 内、Node 就绪后执行 `node test_data/scripts/generate_general_testfiles_pure.mjs --check`，非零退出即红（沿用 P-008/P-025 的"复用既有 required check"取向）。
- **落点**：`.github/workflows/lint.yml`（lint job 新步，置于 Node setup 之后、`npm ci` 之前 = 失败快、且该脚本零 npm 依赖；**红线文件，用户 2026-10-08 显式授权**）· `module-map.md` §5 登记 **E3** · `test_data/testfiles/README.md` R3 写明"CI 强制" · CHANGELOG。
- **判据**：`--check` 输出 `OK - no drift` 且 exit 0（收敛前实测 `6 drifted output(s)` 且 exit 1）。
- **能力边界（必须写明，否则方案变幻觉）**：本门禁只覆盖**该生成器**的三个输出（`GeneralFiles/`、`invoices/`、`images/kie/` 的新样例）；**不纳入**其他夹具生成器（如 `test_data/scripts/generate_kie_id_card_samples.py` 的 PIL 渲染件）与**图片类夹具**（JPEG/PNG 编码与元数据不可字节复现）——纳入前须先证明"内容指纹可复现"（口径参照 `test_data/scripts/verify_assets.py`）。local-only 面（`docs/R&D/**`、`scripts/measure/**`）不在视野。
- **触发条件**：改 `generate_general_testfiles_pure.mjs` 或 `test_data/testfiles/**` 样例时（本地先跑 `--check`，CI 兜底）；新增夹具生成器时按上条评估是否纳入。
- **相关**：PR #74（`--check`/`--only` 与收敛批次）· `test_data/testfiles/README.md` R1/R3 · P-008（"声明但未接线"形态）· P-025（门禁 + 检查点范式）。

### P-034 · KIE text-first 通道泛化到 coi（2026-10-09 立项；兑现原 P-030 `carrier` park 的真修）
> status: decided · since: 2026-10-09
- **来源**：原 P-030 的 parked follow-up（已随 P-030 升删，原文见 CHANGELOG 与 git 历史）——`carrier` 在承保人名（INSURER A–F）为空的样本上回落到评级样板句（tampa 实测 `A.M. Best B+ VII or Better Insurance Carrier`）；两版 prompt 调优（v1 负向词表 / v2 只取 INSURER A–F + 去重 + 全空）经 Cloud 双向复验**均未达标（tampa 均 ×5，已排除缓存）**，结论 =「纯 prompt 无法在**扁平化 ACORD 文本**上分离评级行/空标签 ⇒ 真修须在**输入层给 KIE 结构化区块文本**（另立项）」。**2026-10-09 Ying 裁决：泛化到 `coi`**。
- **技术底座（已存在，无需新造）**：P-032 M1/M2 的 text-first 通道（`backend/app/services/kie/text_first.py`，221 行）已把 PDF 原生文本层切块并加全局唯一标记 `[p{page}_b{block}]` 作为 KIE 输入；当前**仅 `pico` + PDF**。
- **唯一开关**：`text_first.py:44` 的 doc-type 判定 `!= "pico"` → 白名单 `{"pico", "coi"}`。KIE 侧（`backend/app/orchestration/document_pipeline_orchestrator.py:645`）与证据门侧（`backend/app/services/evidence/gate.py:397-411`）**都经同一个判定**，故**不得**在 orchestrator 另起分支；两侧漂移由 `backend/tests/evidence/test_evidence_text_first.py::test_d2_gate_text_first_scope_mirrors_m1` 守护（泛化须同步该文件的新增 coi 正向用例）。
- **无需新增 doc-type 登记**：coi 已在 `kie.md` §4.2 的**七处触面**全部在册（`KIE_SUPPORTED_DOC_TYPES` / `_registry.yaml` / `coi.yaml` / 前端 `KIE_DOC_TYPES` / index.html radio / `_KEYWORDS` / `_PRODUCTION_KEY_HINTS`），三向哨兵 `backend/tests/test_kie_domain_consistency.py` 为 7==7==7；本次只改**通道判定**，不动 doc-type 集合。
- **前置（不可跳过）**：①**阈值重校准**——`BODY_PAGE_MIN_TEXT_ELEMENTS = 8` / `BODY_PAGE_MIN_TEXT_CHARS = 500` 的模块 docstring 明写「calibrated on the 5 pico corpora」⇒ 必须在 ACORD/coi 语料上重校准，否则单页表单可能被 `select_body_pages` 判为非正文页而退回 legacy 图像通道；②**语料文本层盘点**——只有 `trusted_grounding_page_set` 放行的页才走 `text_layer`（`text_first.py:201-208`），须先确认 coi 夹具哪些为 born-digital（`coi_acord25_synth_green.pdf` 文本层含 EIN，可用；其余待查）。
- **prompt 重做（carrier 的真修所在）**：park 时两版 prompt 失败的前提是**扁平化文本**；text-first 换成**带块标记的分块文本**（不同基底），故 prompt 须在新基底上重新设计（让模型引用 `[pN_bM]` 标记而非裸值），**不得**沿用或微调 park 掉的旧改动（两版均未入库）。
- **same-source 契约（不得破坏）**：`build_text_first_payloads` 直接 import `evidence.grounding` 的 `grounding_source` / `trusted_grounding_page_set`（`text_first.py:196-202`），与证据门接地文本同源；泛化只改 doc-type 白名单，**该共享行不动**。
- **验收**：同一样本 `EVIDENCE_TEXT_FIRST` **on/off 双跑**，五字段逐一比对——`carrier` 不再回落样板句，且 `policy_type` / `eff_date` / `exp_date` / `limits` **不退化**。**必须实测的风险点**：text-first 分支**只发文本、不发图像**（`backend/app/services/kie/KieManager.py:158-178`），ACORD 的勾选框/评级行/limits 表是否依赖视觉信号须在该对照中证实或证伪。KIE 属 GPU 依赖 ⇒ 本机 mock 单测 + 交付文档写 Cloud 验证步骤与验收标准（**不宣称云端已验证**）。
  **Cloud 验证交付文档（B 项验收；2026-10-15 预登记 = 清「交付文档未写」欠债；**未实跑，不宣称云端已验证**）**：⓪**前置（两项未完成，①-④ 不得开跑）**——(a) **阈值重校准**：`text_first.py:27-28` 的 `BODY_PAGE_MIN_TEXT_ELEMENTS=8` / `BODY_PAGE_MIN_TEXT_CHARS=500`（docstring 自述 "calibrated on the 5 pico corpora"，`:12`）须在 ACORD/coi 语料重校准，判据 = 夹具逐页 `select_body_pages` 判定与文本层盘点一致（**无正文页被误判非正文而退回 legacy 图像通道**——单页表单是最可能踩中的形态）；(b) **coi born-digital 盘点**：逐夹具核 PDF 原生文本层与 `trusted_grounding_page_set` 放行集合（放行页为空 ⇒ 该夹具只能走 legacy，须如实登记、不得混入对照）；已知 `coi_acord25_synth_green.pdf` 文本层含 EIN 可用，其余待查。①**副本核验**：被测分支含白名单泛化（`text_first.py:44` `!= "pico"` → 白名单 `{"pico","coi"}`；KIE 侧与证据门侧同一判定，不得另起分支）+ 新基底 prompt；云端全量须含 `tests/evidence/test_evidence_text_first.py`（同步新增的 coi 正向用例）与 `tests/test_kie_domain_consistency.py`（7==7==7）通过。②**on/off 双跑**：同一样本（**必测 tampa** —— INSURER A–F 空样本）`DOCUVISION_EVIDENCE_TEXT_FIRST=on` 与 off 各跑一次 KIE（同输入文件、同版本、排除缓存）。③**判据（五字段逐一比对）**：`carrier` 不回落评级样板句（`A.M. Best …` 形态零出现）；`policy_type` / `eff_date` / `exp_date` / `limits` 不退化（on 相对 off 无字段丢失或降精度）。**风险实测义务**：text-first 只发文本不发图像——若 on 侧在勾选框/评级行/limits 表上退化，**如实登记"该字段依赖视觉信号"并回到设计复核，不硬凑通过**。④**回传（实施读数去向 · 本批口径）**：两次任务的五字段 on/off 对照表（含 `carrier` 值是否引用 `[pN_bM]` 标记）+ 任务 result JSON 与关键服务日志 **落 `docs/R&D/runs/P034/`（local-only）**，**本条目正文只登记结论与指针、不写读数**；新增/删除该目录文件须**同批**更新 `docs/R&D/README.md` 的 runs 索引（`python scripts/docs_refs_audit.py --check-rnd-index`）。⑤**通过后动作**：读数与日期登记回本条、本条方可转 `landed`；不通过则在带块标记的新基底上迭代 prompt（**禁**沿用 park 掉的 v1/v2 旧改动——前提基底已不同）。
- **与 P-027 解耦**：本条属 **kie / evidence 域**（owning doc = `docs/architecture/kie.md` + `evidence-layer.md`），**不**计入 P-027 的在途义务，其落地不解锁 `docs/R&D/runs/P027/` 的删除条件。
- **相关**：P-032（text-first 通道出处）· `docs/architecture/kie.md`（§3 输入通道 / §4.2 七处触面 / §6 已知局限）· `docs/architecture/evidence-layer.md` · P-030（已删，载体结论在 `kie.md` §4/§4.2）
- **触发条件**：coi 域任何 carrier / 字段精度批次；改 `text_first.py` 的 doc-type 白名单或 `EVIDENCE_TEXT_FIRST` 语义时同查本条目。

### P-035 · 分岔 C：RF / 监管真实需求信号出现时的 P-027 优先级重排（2026-10-16，自 P-027 迁出）
> status: open · since: 2026-10-16
- **登记门槛（两问）**：①**不归入已有条目**——P-018 的分岔 B 只覆盖「获得外部 GT」，P-027 只记家族排序，均不含本条的触发与重排口径；②**无可晋升载体**（未来触发式工作项，无 living doc 可承载）。
- **来源（迁出）**：原埋在 P-027 正文「排序」段的触发式残留；P-027 于 2026-10-16 清账批次压缩时迁出为本条（真实工作项不得留在保留理由段）。
- **待决问题**：RF / 监管类文档再现**真实需求信号**（客户询单 / RFP / retainer 类单）时，P-027（RF 频率表 fixture 簇）是否**直升第一优先**——含它与 P-018 P3/P4 家族排序的重排口径。
- **候选路线**：① **直升第一优先**（信号强、直接命中竞品空白，与 P-018 分岔 B 对工程图纸 GT 的处理同型）；② **维持现排序**（「P-018 P3 在前」），仅作并行推进。
- **触发条件**：RF / 监管类真实需求信号出现（与 P-018 分岔 B 的「获得外部 GT」并列观察）。
- **指针**：P-018（GT 工厂立项：分岔 B / 家族排序）｜ P-027（RF fixture 簇 · R1–R4 执行记录）｜ `docs/architecture/ocr-quality-harness.md`（RF 秤的 living 载体）。

### P-036 · CI 触发范围与 paths 的重收窄（仓库转私有计费 / audit 变慢时）（2026-10-16，自 P-008 · P-011 合并迁出）
> status: open · since: 2026-10-16
- **登记门槛（两问）**：①**不归入已有条目**——P-008 / P-011 均为 `retained` 结案记录（只留判例与指针，不再承载在途工作项），本条是两者 CI 侧残留的合并承载体；②**无可晋升载体**（触发式工作项，无 living doc 可承载）。
- **来源（迁出）**：P-011 正文的「重估触发」/「重开条件」+ P-008 正文「残留②（触发范围仍 main-only）」，两条目于 2026-10-16 清账批次合并迁出为本条。
- **待决问题**：现行 CI 触发为 **`pull_request` 全放开、`push` 仅 main**（2026-09-20 用户裁决：必需检查必须在每个 PR 上报，故移除 `lint.yml` / `agent-ops-audit.yml` 的 `pull_request.paths`；feature 分支阶段仍只靠本机门禁）。**仓库转私有（开始计费）或 audit 明显变慢时**，是否/如何回到「逐条精确 paths」清单？
- **候选路线**：① **维持现状**（现状实测公开仓 ~1 min/PR 且分钟数免费）；② **回到 2026-09-17 的「路线 B 粗粒度」清单并按输入逐条精确化**（清单原文在 CHANGELOG `[Unreleased]` 与 git 历史；须覆盖 audit 的全部判决相关输入——漏一个输入是**静默失效**）；③ **让 audit 自检「我的输入 ⊆ workflow 的 paths」**，把这类漂移变成红灯（代价 = 改 audit 实现必须同 commit 改 workflow 红线文件，需豁免机制，**须单独授权**）。
- **触发条件**：仓库转私有（计费）或 audit 明显变慢（两者之一出现即重开）。
- **指针**：`docs/architecture/v1.9-roadmap.md`（branch protection / required checks 决策行）｜ CHANGELOG `[Unreleased]`（paths 翻转判决与清单原文）｜ `.github/workflows/{lint,agent-ops-audit,kie-phase-a}.yml`。

### P-037 · services 结构门禁 S1 落地与冻结边还债（2026-10-24，runs/split 批 0 启动时登记）
> status: decided · since: 2026-10-24
- **登记门槛（两问）**：①**不归入已有条目**——P-017 只管行数预算、P-019 已结（单源化教训），本条是**结构落点**维度，无在册承载体；②**不可直接晋升**——S1 机制本身已晋升（kernel `routing.md`/`testing.md` + `module-map.md` §2b/§5），但**14 条冻结边的还债批次是在途义务**，需跟踪轨迹至棘轮收口。
- **已落地（批 0，2026-10-24，本 PR）**：`lint_services.py`（S1a/S1b/S1c，499 行，经 audit 接线零 CI 改动）+ `service_domain_map.json`（15 域 63 文件 fail-closed）+ `service_dependency_allowlist.json`（冻结棘轮）+ module-map §2b/A2b + kernel 三文件 + Placement footer 第 6 项 + DEVELOPMENT 第 7 条 + operations KPI。落地复算逐行核对了 2026-10-16 快照的 13 边（全命中）。
- **基线勘误（重要）**：lint 首跑发现第 14 条**预存在**跨域边 `proof_report.py:22 → table_cell_confidence`（report→table，2026-10-15 随 P-027 A 合入）——runs/split 01 审核「零漏边」结论**不成立**，已按冻结语义登记（added 2026-10-24 + erratum note）。初始基线 = **14 边 / 15 条目**，非 13。
- **在途义务（还债批次，序列与操作规范见 `docs/R&D/runs/split/` 批次执行计划）**：批 1 机制消解（I-1 首登 `pdf_raster` 共享叶 → `kie->infra`/`document->infra` 消解；`pipeline->L2` 倒置）→ 批 2 两组环整改（evidence⇄kie、hitl⇄kie，上提公共谓词；**碰 GPU 路径须 mock+云测**）→ 批 3+ 巨型文件拆分（table_service → layout_service → 单域文件 → orchestrator/envelope_builder 殿后，L2 动管线入口需端到端）。每批：改码前基线四样快照 + 等价性证据档 A/B/C + `file_size_allowlist` 棘轮同步收紧 + Placement 判据。
- **进展（2026-10-25，批 10 时点）**：批 1-9 已收口——批 7 formula（钉死 6→5）、批 8 batch 拆三 + `batch->infra` 消解（边 2→1）、批 9 figure 拆二（钉死 4→3）；**批 10 export 544 → 四件家族**（门面 233 + Markdown/DOCX 渲染 Mixin 146/154 + 纯格式 helper 叶 76；钉死 3→2，仅剩看管线 ocr 457/main 257——**>500 巨户清零**）。批 6.5-9（PR #99-102）CI 绿待授权合并。**批 11（evidence->hitl 倒置，边 1→0）+ 云测集中一轮见 runs/split 14 号计划**。
- **触发条件**：本 PR 合入后按批次序列推进；冻结边 90 天时钟（最早 2027-01-14 起）到期未动 = lint WARN，巡检可见。
- **指针**：`docs/architecture/module-map.md` §2b/§5/§6（A2b）｜ kernel `routing.md`（S1 三规则 + services 黄金样例）与 `testing.md`（Placement）｜ CHANGELOG `[Unreleased]`（S1 条目含勘误）｜ `docs/R&D/runs/split/`（目录级：批次执行计划与后续执行记录）。

### P-038 · I-1 共享叶登记制 `shared_leaf_modules`（S1+1 增量；L1 强度已裁决 A）（2026-10-24，自 runs/split 03 §4 立项登记）
> status: open · since: 2026-10-24
- **登记门槛（两问）**：①**不归入 P-037**——那是还债轨迹，本条是**新增登记机制**的待决范围（机制面独立：判据 + 登记表 + 对账，runs/split 01 Adversarial check 已警告其成本）；②**不可直接晋升**——L2/L3 人审未做，无定稿可载。
- **待决问题**：34 个零出向候选逐个过 **L2（无域语义）/ L3（无域状态）人审**后范围定稿。首登 `pdf_raster`（纯光栅化工具，判据清晰）即消解 P-037 批 1 的两条 `->infra` 边；`page_text_trust` 是「事实共享叶」（被 table/evidence/document 三域跨域消费）但 L2 存疑（「页面文本信任」可能带域语义），待人审——通过可再消解 `table->document` 与 `evidence->document` 两条。
- **已裁决（2026-10-19，runs/split 03 §4.3）**：L1 判据强度 **A（零出向谓词）**——一条谓词、零白名单、零漂移面；强度 B（允许基础层出向的白名单）保留为升级路径，非废弃。
- **进展（批 6，2026-10-25）**：已登记 6 叶——`pdf_raster`（批 1）/ `text_first_contract` + `kie_default_rules`（批 2）/ `page_text_trust`（P-038 D）/ `bbox_geometry`（P-038 A+）/ `table_cell_confidence`（批 6：纯逐格置信度量，layout 解析路径 / report 指标卡 / orchestration L2 三方消费、table 域零消费；allowlist target 的「移模块或倒置」判档**移模块**——倒置结构不可能，raw `table_res_list` payload 仅存在于 layout `_parse_result` 调用点——同批消解 `layout->table` 与 `report->table`，棘轮 4→2）。候选范围定稿仍在途。
- **候选路线**：S1+1 批次两步走（34 候选逐个 L2/L3 → 范围定稿后在 `service_domain_map.json` 增 `shared_leaf_modules` 登记面 + S1b 识别为合法通道 + §2b 基建行）。
- **触发条件**：P-037 批 1 启动时（首登 `pdf_raster` 是批 1 第一项的前置）。
- **指针**：`docs/R&D/runs/split/`（03 §4 候选池实证与 L1 强度裁决表，目录级）｜ P-037（还债批次序列与消解目标）。

### P-039 · main/runtime 顶层 paddle import 惰性化（解锁本机 TestClient 测试面）（2026-10-25，批 3 云测判红教训产出）
> status: landed · since: 2026-10-25
- **登记门槛（两问）**：①**不归入已有条目**——P-036 管 CI 触发范围、P-037 管 services 还债，本条是**本机开发面**的依赖装配问题；②**无可晋升载体**（工程改动项，无 living doc 可承载）。
- **事实（2026-10-25 实测；同日三次归因修正，最终以逐文件错误文本为准）**：本机 5 个测试收集错误实测为 **4 个 fastapi 缺失 + 1 个 paddle 缺失**（勘误链：误记"纯 paddle"→ 勘为"3 fastapi + 2 paddle"→ 终测 4+1：analyze_kie_options / blocks_reading_order / phase1_analyze_form 为 fastapi 缺失且装完会继续撞 paddle 墙，trial_auth 纯 fastapi，layout_page_id 纯 paddle——连续误差印证 09 教训：归因必须精确到逐文件错误文本）。装 paddlepaddle CPU（1.5-2.5GB）被否决（巨型依赖 + 本机无 GPU 红线仍约束结论表述）。
- **已落地（2026-10-25，分支 feat/p039-lazy-paddle-imports，候选①+②合并）**：runtime 的服务闭包决定只做 main/runtime 不够——layout_service/ocr_service 的顶层 `import paddle`（两处均为**零使用的死 import**）会把墙原样砌回。四处全部惰性化：main.py 横幅块（paddle 版本 print + paddlex home 验证）迁入 runtime 的 `_log_paddle_stack_banner()`；runtime GPU 探测包进 `_detect_use_gpu()`（无 paddle 时 use_gpu=False 降级）；**初始化顺序语义逐字保持**（横幅 → GPU 自检 → 单例构造）。本机验收：`import app.main` 可行且 paddle 不入 sys.modules；全量 681 passed / 0 收集错误（批 3 基线 657 + 5 错）；门禁五件套全绿，棘轮 main.py 268→257。**云测一轮全过（档 B 证据闭合，同日）**：/health healthy + engines 非空、全量 689 passed 1 skipped（与 09 批 3 复跑读数同数）、live 10 passed（GPU 管线真跑）。环境侧：fastapi==0.109.0 + python-multipart + matplotlib 3.11.2（py3.11 适配）经用户确认安装；httpx 需 <0.28（requirements 既有钉版，starlette 0.35 TestClient 与 httpx 0.28 不兼容）。
- **遗留（已裁决并落地，批 6.5，2026-10-25）**：用户裁决 openapi 快照 ×2 **转本机面**（`DOCUVISION_CLOUD_TESTS` skipif 移除；`app.main` 自 P-039 本机可 import 且路由装配为静态清单，本机 schema 与云端一致——5 测试本机全过、与 GPU 盒生成的 baseline 逐字节一致）；`test_table_template_analyze` 保留 `importorskip("paddle")` full-env 标记（真需要 paddle）。本机全量 681/19 → **686 passed / 14 skipped**。
- **指针**：`docs/R&D/runs/split/12-P039-lazy-paddle-imports.md`（执行记录：逐点使用形态评估表、档 B 逐 hunk 分类、读数对账；local-only）｜ `docs/R&D/runs/split/09-批3-执行记录.md` §七（盲区归因教训）｜ kernel `testing.md`（本机/Cloud 判据，经本轮实证仍自洽）｜ CHANGELOG `[Unreleased]`。



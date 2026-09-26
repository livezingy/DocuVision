# 待决决策清单（PENDING）

> 每次会话开始时检查本文件——可见"有 N 条结论待确认"。
> 结论确认后：晋升 `docs/architecture/`，然后从本清单移除。

## 待确认（本区共 **14** 条）

- **机检索引（勿手改）**：`P-002` `P-008` `P-011` `P-014` `P-015` `P-017` `P-018` `P-019` `P-020` `P-021` `P-023` `P-024` `P-025` `P-026`
- **状态是单一事实源**：每条标题下首行的 `> status: <open|decided|landed|retained> · since: YYYY-MM-DD`。
  状态计数与 90 天滞留 WARN 由 `scripts/audit_agent_ops.py`（门禁 **DOC-3**）输出——**本抬头不再手写统计副本**
  （P-019 单源化教训：数字副本必漂，清账前此处曾把 5 条已结条目计在"待裁决"）。
- **状态语义**：`open` = 未裁决 ｜ `decided` = 已裁决、尚有未完成动作或待验证 ｜ `landed` = 已落地、结论待晋升审视
  （`since` 起超 90 天 = WARN，提示晋升 `docs/architecture/` 或改列 `retained`）｜ `retained` = 已结且**有意**保留在清单
  （保留理由必须写在条目内）。
- **晋升检查点**：写本文件或 CHANGELOG 时必须回答一轮「本轮有无条目达到可晋升/可移除标准」，并在 commit message /
  PR 正文留下 `Promotion-check: <n> eligible … -> promoted|deferred`（零条也写）——规则见 kernel `doc-sync.md`。
- 历史：P-001 已按用户裁决移除 2026-09-20，后续有需要再立项；P-012 已结并晋升 `docs/architecture/v1.7-roadmap.md`；
**P-022 已结并晋升 `docs/architecture/doc-governance.md`**（2026-09-25，走本抬头「结论确认 → 晋升 → 移除」正规流程；门禁登记为 `module-map.md` §5 的 **DOC-1 / DOC-2**；此前索引漏登 P-022 亦随该次修正）；
**P-007 / P-010 / P-013 / P-016 已结并移除**（2026-09-25 清账批次，同走「结论确认 → 晋升 → 移除」流程；结论分别由 `docs/architecture/v1.9-roadmap.md` §Scope S1 ｜ `docs/agent-ops/operations.md` §CI 成本与配额 + CHANGELOG ｜ `docs/agent-ops/doc-sync-ownership.md` 主表+脚注 2 ｜ kernel `frontend.md` 已知 gap 条目承载，明细证据仍在 CHANGELOG 与 git 历史）；
**P-006 已按用户裁决移除**（2026-09-26，**非**晋升路径：其主体 `.zcode/` 目录连同 `.gitignore` 的 `.zcode/plans/` 规则一并删除，预计半年内不使用该工具，后续要用再立项；该目录从未入库，故无 git 历史可回溯）

### P-002 · 表格逐格对齐的文本优先重构（v1.9 候选，2026-09-13）
> status: open · since: 2026-09-13
- 来源：v1.8.1 PROOF-001 云端实测（mamba p12/p29 红率 58%/97%，均匀网格对应在非等宽表上大面积失准）
  + 用户裁决（红框停画、绿/琥珀锚定印刷字符已落地 c37e35c）；用户提出"比对应直接基于文本坐标"。
- 现状边界：born-digital 表格的逐格红/绿标注精度受均匀网格限制；琥珀（真实修正）已由
  `cell_word_bbox` 锚定精确；红（对齐失败）不画、仅入清单。
- 待决项（三层对应 + 两条配套）：
  1. **值匹配优先**：表 bbox 邻域文本层词中找与 OCR 值归一化相等的词（治"准确数字被标红"）；
  2. **几何包含**（现状三关）作降级；
  3. **文本聚类映射**：y 聚行 / x 分列，映射 vision 网格索引（处理非等宽与同值碰撞）；
  4. `mismatch_details`/对齐记录加 `reason` 字段（value_match/geometric/no_aligned_line/crossing/multi_line）；
  5. **回填 sanity 规则**：仅当 OCR 值与文本层值呈 OCR 混淆形态（同长度/同字符集小扰动）才改值，
     否则标红——封死非等宽表上"推导框完整装下邻居值 → 回填错值"的注入路径。
- 触发条件：真实客户文档（trial 3-5 单）证明需要逐格红/绿标注或出现误报投诉时立项；
  立项即需 BACKFILL-001 云端重验。责任仓：`table_backfill.py` 对应层 + 契约 `reason` 字段。
- 技术规格存档：`docs/architecture/provenance-review.md`（§4 sanity 规则规格 / §5 三层对应）。

### P-008 · v1.9 候选：孤儿模块与悬空测试的巡检门禁（2026-09-16，FRONT-C1 走查衍生）
> status: retained · since: 2026-09-26
- 背景：v1.8.3 FRONT-C1 走查 + SPLIT-U4 期间，同一类缺口**两次暴露**——**"声明的东西是否真的被接上"没有巡检**。
  1. **孤儿模块**：`frontend/modules/floating-progress.js`（D11，92 行）**不被任何文件 import**（v1.8.2 起其三个
     函数就无外部调用者，`index.html` 有 DOM 无 JS 驱动）→ 浏览器从不加载。接线属行为变更，需单独决策。
  2. **悬空测试**：4 个测试文件在 v1.8.2 拆分后与实现漂移（`tasks` / `process_document` 迁至 `app.core.runtime`），
     且**不在 `kie-phase-a.yml` 列表、不在任何验收文档、本地跑不了（需 paddle）** → 靠云端全量偶然撞出
     （`test_analyze_kie_options.py` 甚至中断了整个 collection）。2026-09-16 已修复（commit `579a454` / `8cf4dd7` / `ebf859d`）。
- 共同缺口：模块要"被 import"、测试要"被某处登记并真的运行"——两者都缺机检。
- 建议（不属 v1.8.3 范围）：
  ① 前端**孤儿模块可达性审计**（本次为一次性人工核查，脚本未落地）；
  ② `backend/tests/*.py` 必须出现在 `kie-phase-a.yml` 的 Phase A 列表**或**某个登记表里（悬空测试巡检）；
  ③ 全量 pytest 口径加 `--continue-on-collection-errors`——本次一个 collection error 让 430 个用例一个都没跑。
- 相关已知 gap：`lint_frontend.py` F6 是**名字级弱断言**，抓不到"在 deps 里被引用但漏 import"（v1.8.3 B5a 实际踩中一次，
  靠 e2e + pageerror 探针定位）。彻底解法需作用域分析。
- **状态（2026-09-17，治理批次已落地，①②③ 全部机检化——本组可结）**：
  ① **孤儿模块** = lint **F7**（`modules/**` 必被 `app.js` / `index.html` / 其它脚本 import；例外登记
  `frontend_domain_map.json` 的 `known_orphans`，每条附 `added` + evidence；**只登记不接线**）。
  ② **悬空测试** = audit **check 4**（`scripts/test_registry_audit.py`：`backend/tests/test_registry.json`
  ↔ 递归磁盘 `test_*.py` ↔ `kie-phase-a.yml` Phase A 列表三向对账；未登记 / 幽灵条目 / CI 跑到未登记或
  kind≠`phase-a-ci` = ERROR，CI 侧漂移 = WARN）。
  ③ **collection 容错** = `backend/pytest.ini` 的 `--continue-on-collection-errors`（仍以非零码退出）。
  首次全量 F7 扫描（多行 import 感知）结果：**只有 `floating-progress.js`（D11）一个孤儿**，与 P-008 记载一致；
  P-010 清账时又暴露第二个 —— `modules/utils/geometry.js`（其唯一生产 importer 是 app.js 的**死 import**，
  删掉后成为孤儿；5 个函数现仅被 `tests/unit/geometry.test.js` 覆盖）。
  **孤儿裁决（2026-09-20，v1.9 S4，用户确认）：两个孤儿均退役**（D11 连同 DOM/CSS；geometry 连同其单测），
  各自单独 commit、事实源同 commit 同步；`known_orphans` 清空（A6 告警在此之前完成裁决，未触发）。
  **遗留 gap**：F6 仍是名字级弱断言（中间态评估见下）；F7 只判可达性、不判接线（规则本身保留）。
  **状态更新（2026-09-20，v1.9 收口）**：两个在册孤儿已按裁决**全部退役**（`known_orphans` 清空，见 S4-A/B）。
  **gap 2 残留（2026-09-20 用户裁决"选项 b 完整保护"）→ ✅ 已结**：main 由 ruleset
  `main-branch-protection`（id 23724962）保护——**必需 PR** + 必需检查 `lint` / `e2e` / `agent-ops-audit`
  （三者已在每次 PR 必跑，见 P-011）+ 禁删除 / 禁 force-push，**无 bypass**（对管理员同样生效）；
  e2e 从"提示"变为**阻塞检查**。前置引导（PR 触发去 paths 化）先于 ruleset 落 main，避免"必需检查停在
  Expected"的自锁；并用 P-010 第二批的 PR 端到端验证了整套流程。**本组关闭。**
  **F6 中间态结论（2026-09-20，v1.9 S3）**：JSDoc + `tsc --allowJs --checkJs --noEmit` **不引入**——
  实测 272 错中无一是类型系统独有信号，且对"deps 引用但未注入"只有手工维护键表才覆盖（= 快照形态）；
  详见 roadmap §S3。
- **遗留 gap 1 已定并落地（2026-09-17，选项 B）**：新增 **C9 注入保真** —— `app.js` 传给每个 `initXxx` 的 key
  集合必须**恰好等于**该模块体实际读取的 `deps.*` 集合（缺 key = 留空桩；多 key = 死注入；签名非空且非 `deps`
  = fail-closed）。机检 `scripts/frontend_coupling.py::check_injection_keys`，由 `check_frontend_baseline.py`
  默认运行 → **随 `lint.yml` 进 CI**。
  落地取舍两条（与建议稿的差异，均取"能 CI 强制"的一侧）：**① 没做成 vitest 测试**——vitest / e2e 当前**不在 CI**，
  只保护本机，不足关闭 gap；改落在 C 系列（`check_frontend_baseline.py` 已在 lint.yml 内）。
  **② 没用"`frontend_domain_map.json` 填 `init_deps` 数据"的形态**——那是快照：模块新增依赖而数据未更新时仍然全绿，
  恰是要防的失效形态；改为**从模块源码直接推导**（`deps.*` 读取集合），零维护。
  证据：25 个 init 导出 / 24 个参与比对（`initAnnotationInteractions` 经注入而非调用，由 F6 管辖；`initializeAPIConnection`
  名称前缀命中，无参故无副作用）+ 5 组负向测试（缺 key / 冗余 key / 给无参 init 注入 / 非 `deps` 参数 fail-closed /
  真源码基线零误报）全通过。
  **A 的中间态（JSDoc + `tsc --allowJs --checkJs --noEmit`）记为 v1.9 前端批次评估**（已定路线，非待决）。
- **遗留 gap 2 仍待确认**：F7 只判可达性、不判接线。候选 B = e2e 运行时覆盖度报告 + pageerror/console 监听
  （非阻塞，产出"死代码候选"清单一并喂 P-010 下一轮）；**待定**：报告类型 / 存放位置 / 查看频率。
  A（DOM 桩 ↔ 脚本引用的静态对应）已评估为**否决**（启发式误报会让人开始忽略 F7）。
- **gap 2 中"可机检的那一半"已落地（2026-09-17，用户裁决）**：audit check 3 新增 **A6 孤儿登记时效**——
  `known_orphans` 每条必须带 ISO `added`（缺失 / 格式错 = ERROR，fail-closed），超过 `ORPHAN_STALE_DAYS = 90`
  仍在册 = **WARN**（文案即"re-decide wire-or-retire and record the decision in PENDING"）→ 把"定期巡表"
  降为"看告警"。实现在 `frontend_coupling.py::check_orphan_staleness`（纯函数；`--selftest` case16 覆盖
  stale / 无日期 / 新鲜三态），由 `audit_agent_ops.py` 调用；N=90 的理由：超过一个季度就不再算"下一批再说"。
  **候选 B 已落地为 MVP（2026-09-17，用户裁决）**：`frontend/tests/e2e/helpers/coverage.js`
  （包装 `page` fixture 注入记录器：patch `EventTarget.prototype.addEventListener` /
  `removeEventListener` 打点，按**注册点堆栈**归属到模块）+ `coverage-report.js`（Playwright
  `globalTeardown`：合并 `test_data/TestResult/PhaseUI/coverage-fragments/` 的碎片 →
  `coverage-<date>.md`）+ `coverage-setup.js`（`globalSetup`：每次跑前清空碎片）+ `playwright.config.js`
  接线；4 套 Pro spec 各只改一行 import。**报告不是门禁**（永不红），`PW_COVERAGE=0` 关闭打点。
  **首次运行结果（14/14 通过，12.2s）**：33 模块加载 31 —— 未加载的正是两个已知孤儿（与 F7 结论互证）；
  14 模块注册了监听器，**5 个"注册了但从未触发"**（`batch.js` / `hitl-review.js` /
  `preview-paging/core.js` / `pipeline/result.js` / `shared/export-ui.js`），22 个零监听器（多为纯函数/配置叶）；
  **并抓到 8 条真实 pageerror** → 已另立 **P-016**。开发期两个缺陷全靠"跑真套件"暴露并修掉：
  ① wrapper 调 `addEventListener` 时**漏传 `type`**（监听器被注册到垃圾类型上 → 一次都不触发 → 14/14 全红）；
  ② 未清碎片 → 把上一次的结果当成本次（补 `globalSetup` 解决）。
  **第 1 步已落地（2026-09-17，用户裁决）**：报告之外，`helpers/coverage.js` 现在**断言本次运行
  `pageerror` / `console.error` 为空**——测试体全绿但页面报错 = 该用例判红（fixture teardown 抛错），
  失败信息同时给出错误内容与两条出路（修因 / 带理由加进 `EXPECTED_ERRORS`）。`EXPECTED_ERRORS`
  **刻意从空开始**（首跑实测 0 条），规则与 ESLint 接 CI 时"先清零再接"一致；`PW_COVERAGE=0` 同时关闭
  记录与断言（逃生口必须是完整的）。**它不需要 CI 改动、也不需要 branch protection 就有用**——这正是
  它与"接 CI"的分界。
  验证（双向）：探针① 测试体通过但页面打 `console.error` → **1 failed**（断言按设计生效）；
  探针② 给该错误加 allowlist 条目后同一探针 **1 passed**，且报告仍如实记录那 1 条 error；随后全套
  **14/14**、`0 runtime error(s)`。
  **第 2 步（仍未决，前置 = e2e 进 CI + 建议先开 branch protection）**：三种候选口径的取舍——
  (a) **运行时错误门禁 = 推荐**（唯一能自动抓 P-016 那一类的口径；现为 0 条、可零白名单起步；
  代价 = 白名单腐化风险 + CI 侧 chromium 安装与缓存，本机缓存实测 ~706MB）；
  (b) **模块加载门禁 = 不单独设**（与 F7 静态可达性高度重叠，增量仅剩"服务端未提供/MIME"这类，而 C7 已查 MIME）；
  (c) **监听器覆盖门禁 = 否决**（覆盖率指标不是正确性属性；设成门禁只会逼着补 e2e 场景或加白名单，
  且**改测试会改变红绿**，信号性质很差）。
  **第 2 步已落地（2026-09-20，用户裁决）——口径 (a) 运行时错误门禁，附完整的防腐化措施**：
  `lint.yml` 新增 `e2e` job（`checkout → setup-python 3.11 → setup-node 22 + npm ci →
  actions/cache@v5（`~/.cache/ms-playwright`，键跟 lockfile）→ `install --with-deps chromium` →
  `npm run test:e2e` → 工件 `always()` 上传）；`playwright.config.js` 在 CI 下 `workers: 2`、
  `retries: 0` 不变（retry 会掩盖恰要暴露的 flake）。白名单同步**下沉为数据**：
  `frontend/tests/e2e/expected-errors.json`（条目须带 `reason` + `added`；`match` 是**字面量子串**，
  禁正则元字符 —— 一个 `.*` 会整类放行而看起来只是一行配置）+ `scripts/e2e_allowlist_ratchet.json`
  （上限 5 = headroom，`--update` 只降不升）+ 套件钉死 `scripts/e2e_suite_pin.json`（4 spec / 14 用例，
  `test.skip|fixme` 任一出现即 ERROR，防门禁靠"缩水"失效）；机检 **E1** =
  `scripts/check_e2e_allowlist.py`（33 例 `--selftest`；格式/未来日期/元字符/boilerplate/未知键/超限
  = ERROR，>90 天 = WARN）。**E1 刻意放在 `lint` job 的 stdlib 段**：即使将来 paths 或 job 条件跳过
  `e2e` job，白名单规则仍被评估。证据：e2e **14/14**（本地 11.7s / `CI=true` 19.3s），**0 runtime error**；
  探针（白名单损坏）→ 加载期显式抛错而非静默放行。
  **残留（本组不因此关闭）**：① **仍非阻塞** —— `main` 无 branch protection，CI 红只是提示；
  ② **触发范围仍 main-only**（P-011 现状），feature 分支要本机跑；③ ~~CI 侧实测时长待首次上云回填~~
  **已回填**：push `67d3083` 的 Lint run **35485821396** —— `lint` **18s** / `e2e` **44s**
  （冷缓存下 `install --with-deps chromium` 仅 19s、套件 7.6s/14 passed、2 workers、0 runtime error，
  浏览器缓存已写入）；④ ~~e2e / vitest 仍未进 required checks~~ **已处置（2026-09-26 复核，见下）**。
- **状态更新（2026-09-26：用户裁决 F6 + 复核全部残留）**：
  - **F6 弱断言：accepted**（用户 2026-09-26 裁决）——不引入 JSDoc/tsc，F6 保持**名字级**；fails-closed 的部分由 C9 承接
    （deps 键集合已经机检）。该缺口转为"已知 gap"形态保留，不再是本条的待决项。
  - **残留 ①②④ 复核 = 均已处置（原文过时，勿再引用旧表述）**：① `main` 已有 ruleset `main-branch-protection`
    （必需 PR + 必需检查且无 bypass，见 P-011）；② `lint.yml` / `agent-ops-audit.yml` 的 `pull_request.paths` 已移除
    （P-011，2026-09-20）⇒ **每个 PR 都跑**，feature 分支不再只靠本机；④ **vitest 早已在 CI**——
    `.github/workflows/lint.yml:86` 的 `npm run test:unit` 位于 `lint` job 内（提交 `3b5cc46`，2026-09-20「v1.9 S0」），
    因 `lint` 是必需检查 ⇒ **红灯阻塞合并**；e2e 则是独立必需 job（`2f15b2f`）。
  - **唯一新残留（待裁决，非阻塞）**：vitest **没有防缩水门禁**——`scripts/**` 零处引用 `test:unit` / `vitest`，
    删掉一个单测文件或加 `.skip` 只会让 CI 报告更少的用例数、**不会红**（`vitest run` 仅在"一个测试文件都没有"时失败）；
    e2e 侧有 `scripts/e2e_suite_pin.json`（spec 5 / tests 15）+ **E1** 兜底，单测侧无对应物。**本机实测现为 7 files / 67 tests**
    （历史记的"80 例"已因 v1.9 S4 退役 `geometry` 单测而过时；`lint.yml` 注释里的"80 unit tests"同源过时——**CI 配置属红线，未改**）。
- **✅ 已结（2026-09-26，唯一残留当日补齐）**：上条列的"单测防缩水"落地为门禁 **E2**——
  `scripts/unit_suite_pin.py` + `scripts/unit_suite_pin.json`（`frontend/tests/unit/**/*.test.js` 的文件数/用例声明数
  必须等于 pin；`it.skip`/`it.todo`/`test.skip`/`describe.skip`/`describe.todo` 出现即 ERROR，空套件 fail-closed），
  经 `audit_agent_ops.py` import 接线（复用必需 check，**零 CI 配置改动**）；module-map §5 登记 E2、归属表补行。
  首版 pin = **7 files / 67 cases / 0 skips**（与 `npm run test:unit` 的 7 passed files / 67 passed tests 一致）。
  正向对照：真实源码上删一个用例 / 插一个 `it.skip` / 空套件 → 三种形态均 ERROR；`unit_suite_pin.py --selftest` 15/15。
  **本组自此关闭**（①②④ 已由 ruleset/paths 移除/vitest 在必需 job 内处置；F6 弱断言由用户裁决接受为已知 gap；
  F7 只判可达性不判接线为规则本意，其运行时覆盖度报告（候选 B MVP）已落地）。保留本条目是为了存两份判例：
  "声明但从未运行"与"跳过即静默降覆盖"——两者的机检分别是 T1/T2 与 E2。

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
- **重估触发**：仓库转私有（开始计费）、audit 变慢、或 `main` 开 branch protection 时，回到"逐条精确"。
- **未做（可选治本）**：让 audit 自检"我的输入 ⊆ workflow 的 paths"（只读解析 workflow，不写）——把这类漂移
  变成红灯；代价是"改 audit 实现必须同 commit 改红线文件"，需豁免机制，故本轮不做。
- **已裁决（2026-09-20，用户裁决）**：新增 `e2e` job 时**维持 main-only**，与三个既有 workflow 一致
  （即继续按选项 ② 运转：本机门禁 + 合 main 时 CI 复核）。同一裁决也覆盖了新 job 的触发范围，
  故"feature 分支不跑 CI"的现状不变；重估触发如上。
- **✅ 已结（2026-09-20，重估触发"main 开 branch protection"已触发并处置）**：main 启用 ruleset
  `main-branch-protection`（required PR + 必需检查，见 P-008）→ 直推 main 被**拒绝**，一切改动走
  feature 分支 + PR；同 commit 将 `lint.yml` 与 `agent-ops-audit.yml` 的 **`pull_request.paths` 移除**
  （必需检查必须在每个 PR 上报，否则停在 "Expected" 卡死 PR），`push.paths` 保留（仅供 bypass 场景）。
  2026-09-17 的"翻转判决"paths 清单保留为**转计费后重新收窄**的参照；公开仓每 PR 成本 ~1 min（免费）。
  **本组关闭**；重开条件：仓库转私有（计费）或 audit 明显变慢。

### P-014 · `shell/tools.js` 的 `startProcessing` 未绑定 + P-010 清账未清零（2026-09-17）✅ 已结（按 ②′ 整体退役）
> status: retained · since: 2026-09-17
- 现象（ESLint 首次全量扫描发现，也是唯一剩余报错）：`frontend/modules/shell/tools.js` 的
  `initAnalysisView()` 内调用 `startProcessing()`，但该模块**没有**这个标识符的绑定——D4 的姊妹文件
  `shell/ui.js` 通过 `initShellUi({ startProcessing })` 拿到了注入绑定，tools.js 漏了 → **L3 违规 +
  潜在 ReferenceError**（v1.8.3 拆分的遗留）。
- 影响面（**实测，非推测**）：该回调绑的 DOM id 是 `#startProcessBtn`，而 `index.html` 里**不存在**该 id
  （真正的按钮是 `#runAnalysisBtn`，绑在 `shell/ui.js`）→ 监听器从未挂上，**当前无用户可见故障**；
  本次 e2e **14/14** 全绿（含 UI-Q-01「Run Analysis 取选中项」）亦印证。
- 未在本次治理批次修复的理由：kernel `constraints.md` §通用工程纪律「**禁止顺手修无关缺陷——要修就单独
  commit/PR**」；而把不存在的全局"声明"进 ESLint `globals` 会**掩盖真实缺陷**，更不可取。因此 ESLint 当前
  报 **1 error**、`npm run lint` 退出码 1，**P-010 阶段 3（接 CI）被此项阻塞**。
- 待决（二选一，均属行为/契约变更，需单独 commit）：
  ① **注入修复**：`initShellTools({ startProcessing, ... })` + 模块内绑定（与 `shell/ui.js` 同构），
     并同步 `module-map.md` §3 D4 行的对接说明；运行期行为不变（元素不存在）。
  ② **删除死回调**：删掉 `initAnalysisView` 内的 `#startProcessBtn` 监听块（保留函数本体以不动
     `boot_sequence`），属死代码清理。
- 触发：v1.9 前端批次；或任何一次要动 `shell/tools.js` / D4 装配的改动（届时一并处理）。
- 相关：P-010（阶段 3 阻塞项）、P-008（同类拆分遗留）。
- **状态（2026-09-17，已按选项 ②′ 执行完毕，本组可结）**：用户裁决「整体退役」→ 删除
  `initAnalysisView` 函数本体，并移除 `app.js` 的 import 与引导调用；`boot_sequence` 与
  `domains["D4 shell-init"]` **同 commit** 由 17 → 16（代码与数据必须同改，否则 C3 立即红）；
  `module-map.md` §3「16 项」与 `frontend/README_FRONTEND.md` 引导片段同步；顺手修掉
  `options-dialog.js` 第 9/24 行把 D6 钩子归属写成 `initAnalysisView` 的陈旧注释
  （真实赋值点是 `shell/ui.js::initResultTabs` 调 `setSyncProcessingModeUI`）。
  **等价性证据（机器可判）**：F6 由 26 → **25** 个 init 导出且全部被装配；C3「16 steps, all defined」、
  C1-C8 全绿、`frontend/app.js` 173 → **172** 行（棘轮下调）；`bootstrap.test.js` 的引导顺序断言（数据驱动）绿；
  vitest **80/80**、e2e **14/14**；**`npm run lint` 首次清零（0 error）** → P-010 阶段 3 的前置已解除
  （接 CI 仍需授权）。历史保留在本条与 CHANGELOG + git，不再计入待确认。

### P-015 · 大文件与 Git LFS 取舍（2026-09-17，治理批次评估）
> status: landed · since: 2026-09-17
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

### P-017 · F1 500 行预算是否调整（按域差异化预算 vs 上调预算）（2026-09-20，v1.9 S2-5 暴露）
> status: open · since: 2026-09-20
- **触发事实（实测，S2 全批 6 次切分）**：巨函数切分会**增加**文件行数（新增函数边界、闭包参数与 docstring），
  与"切分让文件变小"的假设相反。四个模块切后 274 / 357 / 418 / 365 行仍在预算内；**`pipeline/run.js`
  474 → 524 行越线**——即 500 在"376+ 行且需同文件切分"的文件上开始失真。
- **本次处置（已裁决，不属本条待决部分）**：2026-09-20 用户确认把 WS / 回退轮询实现（约 240 行）拆到同域兄弟
  `frontend/modules/pipeline/task-socket.js`——F3 允许同目录兄弟 import，C8 边表与 C9 注入均不变，事实源同
  commit 同步 module-map §3 的 D8 行（3 文件）。**未**加 `frontend_size_allowlist.json` 条目：那是把臃肿
  固化成基线（与"棘轮只减不增"方向相反），且抬上限属 kernel 红线，需单独授权。
- **本条待决：下次再撞线时才展开**（不要提前改政策）。届时应给出这两条路线的**详细取舍（各自优缺点）**交用户裁决：
  ① **按域差异化预算**：在 `frontend_domain_map.json` 为每域登记预算（如目录域 D4/D5/D8/D9 放宽，单文件工具域维持 500）。
     优点：大域不再为"数字"找缝，切分线可按域缝走；预算仍是数据编辑（可评审、可审计）。
     缺点：预算表成为**新的漂移面**（需门禁 + 棘轮 + staleness 机制，参照 `known_orphans` 的 A6 做法）；
     "域"的稳定性依赖后续拆分，仍可能出现"域内单文件 900 行"的退化，届时预算能否按域内文件再细化需一并说明。
  ② **上调全局预算**（如 500 → 700）：优点：规则简单、一次性、无新增维护面与漂移面。
     缺点：失去"接近上限"这一预警信号（文件在更高水位腐化）；`frontend_size_allowlist.json` 的 `budget`
     与 app.js 172 行棘轮构成参照系，上调后需重算该参照关系的语义；且与 S2 刚建立的"切分先例"相比，
     它不区分"巨文件但内聚"与"巨文件且杂糅"。
- **共同前置**：任何路线都要先给出**500 在何处失真的证据**（当前仅 1 次越线，尚不足以支撑改政策），
  并写明 kernel `frontend.md` + `DEVELOPMENT.md` 第 4 条 + `frontend_size_allowlist.json` 的同步义务与棘轮口径。
- **相关**：roadmap §S2「F1 预算与本项的真实冲突」（含切分先例）；S3 结论（tsc **不是**"比行数更好的质量代理"，
  故不能以"引入类型检查"替代本条讨论）；P-010（前端风格 linter 缺位，同属"质量代理"话题）。
- **触发条件**：下一次 F1 越线（切分 / 功能增长 / 新模块任一原因），或用户主动要求评估上限策略。

### P-018 · GT 工厂立项：评测 harness（P0）与 born-digital 弱 GT 合成（P1）（2026-09-21，投标竞争力分析产出）
> status: decided · since: 2026-09-25
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
- **触发条件**：立即可启动（P0 不依赖外部 GT）；P2-P4 按获得外部 GT 或 P-002 立项顺次激活。
- **相关**：P-002（P1 是其量化入口）· Proof Pack（雏形复用）· 护城河共识（fixture 库 + 行业数字 + JSS，
  不在管线代码）。
- **状态（2026-09-22 登记；2026-09-25 清账批次更新）**：立项登记已落地（PR #30 → main `337f4e0`，docs-only）；执行包
  `docs/R&D/P018-GT工厂-立项条目.md` 已在落地后删除（local-only，内容已由本条承载）。
  **P0 评测 harness 与 P1 弱 GT 合成已由 P-020 落地**（2026-09-24 M1+M2，local-only，指标族与边界按本条护栏执行，
  TEDS 随 P2）——**下一阶段 P2 表格结构 GT 对账（公开资源 PubTabNet / FinTabNet / WTW 选型）待用户裁决**；
  P3-P4 仍按获得外部 GT 或 P-002 立项顺次激活。

### P-019 · module-map §6 A3 行数字副本漂移 → 单源化（2026-09-18 登记，同日裁决，09-21 重编号落地，已结保留记录）
> status: retained · since: 2026-09-22
- 现象：`module-map.md` §6 断言表 A3 行（143 行）的 `boot_sequence` 副本写 **17**，事实源
  `frontend_domain_map.json` 实测 **16**，同文件 §3 登记行（85 行）为「16 项」——同一数字一份文件两处、一对一错。
  全景速览文档构建时实测发现（`len(json['boot_sequence'])`）。
- 根因：P-014 当天改 §3 数字时，其同步清单不含 §6 副本行——描述性数字副本在一切对账范围之外（audit 的
  数量正则要求「N 项」后缀，§6 的「（17）」形态天然漏网）。其余四个副本数字当时恰好没变，属侥幸不是正确。
- 编号说明：本条最初拟以 P-017 登记（09-18），未及落地即被 v1.9 列车的 F1 预算议题占用该号
  （`9f3e546`，09-20），故改 P-019。
- 裁决：用户 2026-09-18 拍板 **② 单源化**（vs ① 最小修 17→16）：改动同为一行，① 保留复发面（P-014 当天即
  实证），② 整类清零。与 C9「从源推导、不留手工快照」及 A0 语法冻结方向一致；**明确不做**：给 §6 副本数字
  加对账（扩 A0 解析 = 用新复杂度还旧债）。
- 执行：A3 行五个数字副本下架，单元格指向 §3 单一源；语义判据（名单与 json 键 basename 一致）保留。
- 证据：audit 本机复跑 `0 error / 0 warning` + `--selftest` 16/16——**2026-09-22 执行后实测回填**：
  `[AUDIT] 2026-09-22 10:31 0 error(s), 0 warning(s)`；`[SELFTEST] all 16 checks passed`（与判据相符，
  停止条件未触发）。CI 侧 `agent-ops-audit` 会因 `docs/architecture/**` 路径自动复跑。
- 相关：P-014（漂移源头，其同步清单即"漏了什么"的对照）、P-008 gap 2（同类盲区）、kernel `doc-sync.md` 机制 4。
- **状态（2026-09-22）**：已落地（PR #30 → main `06b77d1`）；执行包
  `docs/R&D/P019-modulemap-A3漂移-执行包.md` 已在落地后删除（local-only，内容已由本条承载）。
  **据实记录两处与原执行包的偏差**：
  ① **提交形态**：原护栏要求「修复本体 / 登记记录」两个 commit 分离；本轮用户裁决改为压平——本议题
  **1 个 commit**，连同 P-018 登记共 **2 个 commit** 推送（压平后 SHA：`337f4e0` + `06b77d1`；
  PR 内开发期 SHA `cd86632` + `74270f0` 因 rebase 合并已不在 main 历史）。
  ② **CI 机制描述已过时**：本条证据行的「`agent-ops-audit` 会因 `docs/architecture/**` 路径自动复跑」
  已不再准确——`agent-ops-audit.yml` 的 `pull_request.paths` 已于 2026-09-20（P-011 / branch protection）
  **移除**，audit 现对**每个 PR 必跑**、与是否触及 `docs/architecture/**` 无关（见该 workflow 头部注释）；
  结论（CI 会复跑）不变，机制口径以 workflow 为准。

### P-020 · OCR 质量测量 harness M1+M2 落地（P-018 P0/P1 实施，2026-09-22 四轮讨论定稿）
> status: landed · since: 2026-09-24
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
  **不宣称云端已验证**。执行包 `docs/R&D/P020-ocr-harness-M1M2-执行包.md` 保留（含 §10 runbook 与回填模板）。
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

### P-021 · `POST /api/v1/ocr` 返回坐标不在上传图像像素系（unwarping 未关闭）（2026-09-24，P-020 云端坐标核验产出；同日裁决并落地入库，待 round3 云端复测回填）
> status: landed · since: 2026-09-25
- **现象**：该端点是**已冻结的公开契约**（`backend/tests/snapshots/openapi_baseline.json`、
  `route_contract_freeze.json`、`test_route_inventory.py` 三处登记），但契约**未声明**
  `text_blocks[].bbox/polygon` 的坐标空间；实测其**不等于**上传图像像素系，而是相差一个**非刚性**形变
  （8 张合成探针实测 scale 1.1084–1.2257 且随探针变、拟合残差 9.9–51.6px、`frame_w` 2227–4067 无规律），
  旋转亦被**抹平**（探针 3° → 残留 −0.82°、15° → 残留 −2.80°）。凡消费该端点的场景（前端叠加框、
  裁剪、导出标注、与其它坐标源对齐）都会错位。
- **根因**：`backend/app/services/ocr_service.py:64-70` 的 `init_params` 只设了
  `use_doc_orientation_classify=False`，**未设 `use_doc_unwarping`**；PaddleOCR 3.3.2 中
  `use_doc_preprocessor` 默认为 **true**，其中 unwarping（UVDoc）**实际取值为 true**，det 因而跑在
  **形变后的画布**上，返回的 `dt_polys` 即该画布坐标。同仓 `layout_service.py:113-120` 早已显式设
  `use_doc_unwarping=False`（注释原文：Unwarping applies non-linear image deformation … the probe confirms
  correct spacing），`formula_service.py:188-189` 亦在另一路显式置 False——**只有 OCR 这一路漏了**。
  链路其余部分已排除：`_convert_predict_dict`(L130-191) / `_parse_result`(L326-368) / `_call_ocr`(L227-262)
  **全程逐点透传、零坐标归一化**；`text_det_params` = `limit_side_len=64 / limit_type=min /
  max_side_limit=4000`，对 2550×3300 不触发 resize。
- **一行修法**：`ocr_service.py:64-70` 的 `init_params` 增加 `"use_doc_unwarping": False,`。
  （该文件**受 git 跟踪**，修改需走 CHANGELOG / `audit_agent_ops.py` 义务。）
- **⚠️ 行数判断更正（2026-09-24 落地时实测）**：原文曾写"改后 458 < 500，不触 F1 文件规模门禁"——**错**。
  `ocr_service.py` 在 `scripts/file_size_allowlist.json` 中被**棘轮钉在 457 行**，规则 **R-b** 的硬上限
  **就是记录值本身**（不是 500；`--update` 只能下调、CI 从不传它）。故 `+1` 行即 FAIL（实测 `+9` 行时
  `[FAIL] 466 > allowlist 457`）。落地做法：把该处 4 行注释压成 3 行，与新增的 1 行 dict 项**净零**，
  实测 457 行、`lint_file_size.py OK`。**教训**：F1 的"500"是自由文件预算，allowlist 内的文件另有更紧的棘轮，
  改这些文件前必须先查 allowlist。
- **验证证据（2026-09-24，云端 Pro GPU，commit `a73468b`）**：8 张合成标定探针（`cal/`，含 `cal_truth.json`
  的精确 ink 真值）经 `POST /api/v1/ocr` 走**改前/改后**对照：
  - `scale` 1.1084–1.2257 → **0.9992–1.0001**；拟合残差 9.9–51.6px → **0.6–1.1px**；
  - `frame_w` 2227–4067（无规律）→ **等于各探针自身宽度**（2000 / 2549 / 2718 / 3316 / 3598，
    含横向 3600×2400 ⇒ 也不按短边归一化）；
  - 旋转 3° → **−2.99°**、15° → **−14.99°**（幅值等于探针角 ⇒ 未 deskew，语义正确；负号为
    图像 y 轴向下的坐标约定）；
  - `cal_shift300`（内容整体 +300px、画布不变）的 `extent_x0` 由 250（内容被重取景）→ **443**
    （base 为 145，差 +298 对应内容 +300 ⇒ 不再重取景）；
  - **8/8 原始响应逐字节改变** ⇒ 配置确已生效（首轮 after 曾与 before 完全一致，因未重启进程）；
    脚本输出判据 `VERDICT: endpoint == INPUT PIXEL FRAME`。
  - 证据落点（均 local-only、不入 git）：`test_data/TestResult/harness/cloud_run/cal/cal_out/` 下
    `layer0_engine_params.txt`（直读 `doc_preprocessor_res.model_settings.use_doc_unwarping: true`）、
    `layer1_result_structure.txt`、`layer2_calibration_{before,after}.txt`、
    `cal_ocr_{before,after}/`；完整说明与判据见 `_cloud_coord_check.md`（§0 结论 / §0.1 修复验证）。
- **补录收口（2026-09-25：原缺的 `commit` / GPU / 版本已补齐）**：
  - `commit` = **`a73468b`**（`a73468ba504645353561c3fd54fb0da1f9cff11a`，2026-09-17）——`commit_before.txt` /
    `commit_after.txt` **两侧 head 相同** ✓（2026-09-25 事后采集）。**before 侧树是干净的**：`commit_before.diff`
    = **0 字节**、porcelain 仅两条 `??` ⇒ "临时改动已回滚"由独立证据确认。同批入库：`gpu.txt`、`versions.txt`、
    `pip_freeze.txt`、`judge_report.txt`。
  - **环境**：GPU **NVIDIA A10 / driver 580.65.06 / 23028 MiB**｜Python 3.11.1｜paddleocr **3.3.2**｜
    paddlex **3.3.12**｜PyMuPDF **1.25.5**（在 pin `>=1.24,<1.26` 内）｜paddle 3.3.0 / torch 2.6.0+cu124（取自 `/health`）。
  - **读数可迁移性的关键旁证**：云端树比本地 main 旧 7 天（`a73468b` 09-17 vs `2c2589f` 09-24），但**被测文件同一 blob**——
    云端 `commit_after.diff` 的前像为 **`80c1fc5`**，入库提交前像**同为 `80c1fc5`** ⇒ `ocr_service.py` **逐字节相同**
    （09-17→09-24 之间的改动不涉及本议题），故 round2 读数可迁移到入库提交。
  - ⚠️ **云端补丁形态**：**仅加一行**（树 458 行，结果 blob `9cefadb`）；入库版为注释压缩后的**净零**（457 行，
    blob `5ef2596`）⇒ **行为等价、文本不同**，**复现时勿按字节比对**云端 diff 与入库提交。
  - ⚠️ **两条证据瑕疵（均不影响结论）**：① `after_restart.txt` 的 PID **94** 启动 **06:08:36**（UTC）早于
    `before_health` 的 06:21:26 ⇒ 该快照记的是 **before 阶段那个进程**，**不能证明"重启过"**（间接证据＝引擎
    惰性初始化 + 首轮"未重启 → after 与 before **逐字节相同**"的实测）；② `commit_before.txt` 采集时刻
    （`09-25T00:38:11Z`）**晚于** `commit_after.txt`（`00:37:17Z`）⇒ 这对快照是**事后重建**、只锚定两侧**代码状态**
    （拍 before 快照时把 `ocr_service.py` 还原过），**非"测量当时的进程状态"**。详见执行清单 §6.1。
- **副作用未知项**（**落地前必须补**）：unwarping 本为拍照/弯曲页准备，关闭可能降低那类文档的识别质量。
  现有读数只覆盖 8 张**合成**探针（检出 12/12 不变、池化置信度 0.9921 → 0.9921、非旋转探针最低置信度
  0.912 → 0.999 反而上升 ⇒ 平坦页上 unwarping 是在帮倒忙），**不能替代真实文档评估**：需用
  `test_data/testfiles` 的 15 份试件 PNG 在改前/改后各跑一次 `/api/v1/ocr`，比对 `text` 字段与置信度，
  重点覆盖表格、密集文本、以及存在真实弯曲/透视的样本。
- **连带重测义务**：① 该修复会**改变 OCR 文本**（8/8 响应不同），故 P-020 现有 15 份
  `OCR/*.ocr.json` 相对修复后服务**已过期**，`cer_*` 须在落地后重测并记录新 SHA；
  ② 落地后执行包 §10.11 的 base-B 空间门禁将转为 **PASS**（base B 几何可用），但 **D-A 顺序配对仍是正解**
  （它把帧依赖解耦，是更稳的结构）；③ 若启用 base B 几何，需重跑 G3 复现 + G4 并回填 §8 状态行。
  → 落地后这三条已落成**可执行清单**：`./P021-云端对照-执行清单与记录模板.md` §7（`commit.txt`/GPU 采集、
  OCR JSON 的 SHA 清单、`cer_*` 与 G3 复现、§10.11 门禁 FAIL→PASS 回填，以及"精简动作排在门禁 PASS 之后"的顺序红线）。
- **落地内容（2026-09-24，本 PR）**：
  ① 修法入 `backend/app/services/ocr_service.py`（`init_params` 增 `"use_doc_unwarping": False`；
  注释压至 3 行以守 457 行棘轮，见上「行数判断更正」）；
  ② 新增契约单测 `backend/tests/test_ocr_service_engine_params.py`：stub `paddle` + 按文件路径加载，
  **无需 Paddle/GPU**；断言 `use_doc_unwarping is False`（`is` 严格判据）、
  GPU 分支同样为 False、`device ∈ {cpu, gpu}`（非 `gpu:0`）、`use_doc_orientation_classify is False`，
  并断言 `is_ready()` 为真以排除"失败路径上记 kwargs"的假绿。
  **⚠️ 作用域更正（2026-09-25）**：首版照抄 `test_layout_page_skip.py` 的**模块级** stub，在 CI 首跑就把邻居
  `test_table_template_analyze.py` 的环境闸门（`pytest.importorskip("paddle")`）伪造放行而误红——已改为
  `monkeypatch` + fixture 作用域并加哨兵断言（`186047e`）。**那个先例本身不完整**；成因、规则与门禁见
  **P-023**（随独立分支 `chore/agent-ops-stub-scope` 落地）；
  ③ 该测试已登记 `backend/tests/test_registry.json`（`kind: phase-a-ci`）**并**加入 `kie-phase-a.yml`
  Phase A 清单（登记而不接线会触发 audit check 4 的 WARN，破坏 0/0）；`.cursor/rules/006-cloud-testing.mdc`
  的 Phase A 最小集同步；
  ④ **反向对照（防恒过）**：把该 flag 改为 `True`／整行删除 → 单测均 FAIL；原样 → PASS；
  ⑤ 归属表新增 `backend/app/services/ocr_service.py` 行（owning doc = `docuvision-system-design.md`
  §3.2–§3.4）。**该设计文档早已声明 `use_doc_unwarping=False` 为"当前固定为 False，引擎 init 硬编码"
  （§3.4）/ "永久禁用"（§3.3）** ⇒ 本 PR 是**代码追齐文档**，不是引入新语义。
- **round2 读数与单调性归因（2026-09-24，云端 Pro GPU，commit `a73468b`）**：G-B 15 组合
  **12 改善 / 0 回退 / 3 持平**；文本量大幅恢复（cosent r3 2712→4963、mamba r15 1361→2849 字符等），
  置信度多数持平或上升。**单调性 sanity：before 5/5 → after 3/5**。两处破口、坐标与归因
  （**用户 2026-09-24 裁决：按"口径性质偏离、不影响结论"接受**）：
  - **① `cosent-form-test-document` identity → rotate_3**：`cer_micro` 0.6509 → **0.5646**（降 0.086）。
    **归因 = 微观加权/分母效应**：同样两组上 `cer_macro` 方向**相反**（0.2758 vs 0.3022，即 identity 更好）、
    `line_exact_rate` 几乎相同（0.714 vs 0.700）、`matched_rate` 0.75 vs 0.714 ⇒ **只有 `cer_micro` 说 identity 更差**。
  - **② `financial_report_01` rotate_3 → rotate_15**：`cer_micro` 0.9581 → **0.9443**（Δ0.014）。
    **铁证**：`matched_rate` 1.0 → 0.5、`cer_macro` 0.3616 → **0.7857**（r15 差 0.42）、
    `cer_nontable` 0.3663 → 0.5714 ⇒ **三项都判 r15 更差**，唯 `cer_micro` 反向——该 fixture 仅 2 条文本 GT 行，
    分母极小，micro 口径抖动即可翻转顺序。
  - **旁证**：`cer_corpus` 在 **before/after 两侧都 4/5 破**（如 bank `2.2727>2.2500>0.8864`）⇒
    该指标族本就不单调；round-1 恰好 5/5 单调是偶然，故"以 `cer_micro` 为准"作为**单项** sanity 判据不稳。
  - **口径含义（不在本 PR 内）**：若要把曲线 sanity 改硬，应改为**多指标判据**（例如 `cer_macro` 与
    `matched_rate` 同时单调），属口径变更、须登记（对照执行包 §10.9）。
  - **块级/表级不参与**：`cer_table` 与 `blocks.csv`（text/table/figure 的 gt_n/ocr_n/matched/mean_iou）
    在 before/after **逐字节相同**（表/块取自 base A，本轮未重跑 analyze），故两处破口只能来自 base B 文本侧。
- **状态（2026-09-25）**：**已落地（代码 + 契约单测 + CI 接线入库）** + **round3 云端复测已验证**。
  round2 证据链已收口（commit / GPU / 版本补录见上，两处残留瑕疵已登记）；云端 round2 对该文件的临时改动
  **已回滚**——`commit_before.diff`（**0 字节**）+ `commit_before.porcelain.txt`（仅两条 `??`）**独立证实**，
  不再只是自述。`P-020 修改面 = 0` 仍保持（harness 侧未改）。
- **round3 读数（2026-09-25，云端 `f3517c7` Merge PR #35 + **重启后的进程**；本机判读）**：
  - **§10.11 base-B 空间门禁 FAIL→PASS，8/8**：`scale 0.9992–1.0001`、`mean_res 0.64–1.13px`、
    `rot −2.99°/−14.99°`（= 探针角）、`in_frame 8/8`。**未沿用 round2 的 G-A 读数**（本轮在含修法的构建上
    重新调用 `/api/v1/ocr` 采集）。严判（自设 `mean_res ≤ 1px`）6/8，两例 `1.13/1.03px`，与 round2 §6.2 同例同值。
  - **15 组合 `cer_*` / G-C 关键串与 round2 after 侧完全一致**（`cosent identity 0.6509`、`financial r15 0.9443`、
    `mamba r15 0.0670`；照片 `8/8 · 6/6 · 5/5`）；**G3 两次 `metrics.csv` 逐位相等**（sha256 `c41b7502…d6ef2e`）。
  - **单调性复检（多指标）**：`cer_micro` 3/5、`cer_macro` 4/5、`matched_rate` 0/5 ⇒ round2 §6.5-2 遗留项提出的
    "改看 `cer_macro` + `matched_rate` 同时单调"**作为硬判据不成立**（`matched_rate` 是配对覆盖、非质量单调量）
    ⇒ 曲线 sanity 维持**提示性**口径，不升级为门禁（属口径变更，另行登记）。
  - **环境**：GPU `NVIDIA A10 / driver 580.65.06 / 23028 MiB`、Python 3.11.1、paddleocr 3.3.2、paddlex 3.3.12、
    PyMuPDF 1.25.5（与 round2 同批一致）；**产物** `test_data/TestResult/harness/round3_20260925/`
    （`commit.txt` head=`f3517c7` 且 `commit.diff` **0 字节**、`gpu.txt`、`versions.txt`、`ocr_sha256.txt`
    26/26 与产物对账一致）、判读脚本 `judge_round3.py`（复用 round2 门禁代码，仅改 `HERE`）。
  - **26 份响应与 round2 `after/` 侧逐字节相同**（同引擎同配置的确定性复现）⇒ **无实质差异，故不追加 CHANGELOG**；
    round3 记录见 `./P021-云端对照-执行清单与记录模板.md` §6.6 与执行包 §10.12。
  - 收尾顺带更正采集块 `[6]` 自检的一处**假红**（原判据拿探针 `max_x` 与画布宽度比，marker ink 只占约 85% 画布宽
    ⇒ 正确树上也 8/8 假红），改用 marker 相似变换拟合，实测 8/8 PASS（详见执行包 §10.12）。
- **现行控制**：**§10.11 已 PASS**，该判据自 2026-09-25 起降级为**回归哨兵**（再 `FAIL` ⇒ 引擎配置漂移，
  如 `use_doc_unwarping` 被重新打开、或换/升级 OCR 引擎改了坐标帧）；**D-A 顺序配对仍是正解**——
  base B 只用于文本、几何取自 view 层（base A），理由是它把帧依赖解耦（与坐标当前是否可用无关）。

### P-023 · 测试 stub 作用域无规则：模块级 `sys.modules` 占位会**伪造「本机已装 Paddle」**（2026-09-25，P-021 首次 CI 运行产出；同日裁决并落地 R1–R3）
> status: landed · since: 2026-09-25

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
> status: decided · since: 2026-09-25

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
  （实为 457 棘轮，落地必红）；CHANGELOG 的 "The line is kept" 在 `33f5df5` 后已过期；我那版 stub 污染。
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
- **遗留义务（(a) 的前置实测）**：下次发生压缩后，向会话中的 Agent 提问「你现在读的是压缩摘要吗」，把可否辨识回填本条目；
  不可辨识则 kernel ① 条按其自述失效（只靠 ②），并在本行登记实测结果与日期。
- **触发条件**：任何长对话（≥1 次压缩、或触及四条代理任一）收尾 / 换阶段时；改 `constraints.md` 的会话管理条时同查本条目。
- **状态（2026-09-25）**：**已裁决并落地**——采纳 (a)+(b) 带三修正；kernel `constraints.md` 沟通方式节已增两个强制检查点，
  两副本已由 sync 再生成，CHANGELOG（Unreleased/Changed）已记一段；(c) 挂起、(d) 降级（理由见上）。
  本条目自身即第 ② 检查点的首个执行实例。

### P-025 · R&D 晋升与滞留**只靠人记**：义务存在、触发点与机检都不存在（2026-09-26，用户追问产出；同日裁决并落地 (a)+(b)）
> status: landed · since: 2026-09-26
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
  retained = P-011 / P-014 / P-019。
- **相关**：P-019（数字副本单源化，本轮直接继承其教训）、P-008 A6（`check_orphan_staleness` 是 DOC-3 的形态先例）、
  P-024（检查点范式与 `Session-check`）、`docs/agent-ops/doc-sync-ownership.md`（R&D 不作 owning doc 的既有口径）。

### P-026 · 质量叙事组装：P-021 闭环公开案例文档（2026-09-26）
> status: landed · since: 2026-09-26
- **来源**：09-25 审计报告建议 #1+#2（GT 工厂第一笔回报资产化），用户当日批准。原 P025 执行包的
  B 部分重编号落地；其 A 部分（G4 sanity 双指标）已被 round3 实证否决（`matched_rate 0/5` 非单调），
  整体废弃。
- **范围（git 5 文件）**：`docs/demo/QUALITY_CASE_STUDY.md` 公开案例文档（英文物料：测量→根因→修复→
  量化闭环，8 项锁定数字 + as-of 戳 + 诚实条款）；`docs/README.md` / `TRIAL_DEMO.md` 各加链接；
  本条目 + 抬头索引/计数同步 + CHANGELOG 段。
- **验收**：GB1（audit 0/0、selftest 59 不变）/ GB2（8 项数字逐项对账）/ GB3（diff 守恒 = 5 文件）。
- **状态**：已落地（案例文档随本 PR 落地；无后续动作，走晋升审视）。

# 待决决策清单（PENDING）

> 每次会话开始时检查本文件——可见"有 N 条结论待确认"。
> 结论确认后：晋升 `docs/architecture/`，然后从本清单移除。

## 待确认（本区共 **15** 条）

- **机检索引（勿手改）**：`P-008` `P-011` `P-014` `P-015` `P-017` `P-018` `P-019` `P-020` `P-023` `P-024` `P-025` `P-026` `P-027` `P-033` `P-034`
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
**P-006 已按用户裁决移除**（2026-09-26，**非**晋升路径：其主体 `.zcode/` 目录连同 `.gitignore` 的 `.zcode/plans/` 规则一并删除，预计半年内不使用该工具，后续要用再立项；该目录从未入库，故无 git 历史可回溯）；
**P-032 已结并晋升 `docs/architecture/evidence-layer.md`**（2026-10-07，走「结论确认 → 晋升 → 移除」正规流程：该文即 `backend/app/services/evidence/**` 的 owning living doc，text-first 契约在其 §2 模块表（`grounding.py`/`text_first.py`/`pico.yaml` 三行）+ §4.1 text-first 分支（旗标语义 / 抽取输入 / 信任判据 / `evidence.stats` 键）；Cloud 复验读数（`baffc46`：E1 3/3 逐字命中 / E5 10=10 / E7 620 passed）记入该文「最近对照」行，明细证据仍在 CHANGELOG `[Unreleased]` 与 git 历史；两项后续项经用户裁决删除，故无遗留动作）；
**P-002 / P-021 / P-028 / P-029 / P-030 / P-031 已结并移除**（2026-10-07 清账批次，同走「结论确认 → 晋升 → 移除」流程；结论现载体：P-002 → `docs/architecture/provenance-review.md` §4/§5 ｜ P-021 → `docuvision-system-design.md` §3.2–§3.4 + `ocr-quality-harness.md` §5 + `docs/demo/QUALITY_CASE_STUDY.md` + 契约单测 ｜ P-028 → `provenance-review.md` §4.4 ｜ P-029 → `evidence-layer.md` + `capability-card-v1.12` 行 13 ｜ P-030 → `kie.md` §4/§4.2 + `docuvision-system-design.md` §7.1/§7.8 ｜ P-031 → `kie.md` §4.2 + `KIE_ACCEPTANCE_CRITERIA.md` §Required key hints；明细证据仍在 CHANGELOG 与 git 历史）；另 **P-021 的 F1 判例**（allowlist 内文件按记录值钉死，改前先查 allowlist）已随本批次并入 `DEVELOPMENT.md` 第 1 条；
**P-015 / P-020 / P-023 由 `landed` 改列 `retained`**（2026-10-07，用户裁决；保留理由已写入各条首行——分别保留 LFS 否决理由与重议触发 / harness 证据附件与规模偏差 / stub 作用域判例）

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
- **500 失真的证据面更新（2026-10-05 实测，供本条裁决）**：`backend/app` 侧已有 **9 个文件通过 `file_size_allowlist.json` 棘轮固化**——`layout_service.py` 1804 · `table_service.py` 1613 · `document_pipeline_orchestrator.py` 1248 · `formula_service.py` 734 · `batch_service.py` 686 · `figure_service.py` 681 · `envelope_builder.py` 620 · `export_service.py` 544 · `ocr_service.py` 457（合计 ~8,300 行，其中 3 个 >1200）。即"500 在复杂服务层失真"已**不止上文 1 次前端越线**，而是被 allowlist **反复固化**（棘轮条目本身就是"撞线即固化"的产物记录）。**门禁口径辨析**：`lint_file_size.py` 只扫 git-tracked 的 `backend/app` + `scripts/`（`SCAN_ROOTS`），故 `scripts/measure/*`（`test_metrics.py` **1111** · `metrics.py` 569 · `harness_cli.py` 554 · `rf_rows.py` 464 · `test_wtw.py` 451 · `rf_sem_eval.py` 422 · `wtw_loader.py` 404）与 `test_data/scripts/*`（`gt_build_arxiv.py` 888 · `gt_diff_report.py` 550）属 **local-only 无护栏区**（不进 F1 视野）；`frontend/*.js` 三件（`upload-queue.js` 423 · `overlay-render.js` 418 · `shell/ui.js` 406）归 `lint_frontend` F1-F7 另一套；`backend/tests/*` 豁免。**当前最贴线** = `scripts/lint_frontend.py` **497/500（差 3 行）**，撞线时按 S2 先例拆同域兄弟模块、**不提前进 allowlist**（违反棘轮只减不增）。**裁决输入**：本行数据即"路线① 按域差异化预算 vs 路线② 上调全局预算"的量化证据面——届时讨论对象应是"backend 服务层是否需独立预算"，而非仅凭前端 run.js 一次越线。
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
- **状态（2026-09-22 登记；2026-09-25 清账批次更新）**：立项登记已落地（PR #30 → main `337f4e0`，docs-only）；执行包
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
  预测一次落盘 300/300（云端 `f3517c74` = PR #35 的 P-021 unwarping 修复 merge，**在 main 历史上且
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
逐字核对）；C1 探针（五类各 3 + 2 文本控制格，云端 `ed38bd0`，paddleocr 3.3.2 / A10，ch≡en 逐字节）实测：断言②
PASS（已检出符号 IoU≥0.5 = 4/4，GT 名义盒 + 6pt 基线补偿几何有效），**断言①③ FAIL——引擎对白底孤立符号漏检
（✓ 1/3、⊗/●/○ 0/3、✗ 3/3 读成 X；R2 命中）**。Ying 裁决暂停：R2 实证记录在案（`docs/R&D/P018-P3-执行记录.md`
local-only，§2.6 留选项空间），**试件规格 §2 / 五类判据 / 指标定义 #3 零变更**；仪器保留 local-only
（`scripts/measure/synth_symbols.py` 渲染核心 + 探针产物 + c0 自检仪 A6 钉子同步扩至 11 文件）。重启前置：Ying 对
A（符号嵌入文档语境，联动 D2/R9）/ B（类集缩减）/ C（det 调参解禁）再裁决；P-027 harness 文档债修复随下次
落地批次同带。**A1 修订（同日 Ying 选型 A1 = 行级语境）**：§2 符号格改「词(14pt)+空格+符号(28pt 原位)」行级
语境（词表 YES/NO/NA，词与类别独立，控制列钉最左，seed=42 不变）；D1 判定对象改最右符号字符；D2 行级为常态；
D3 增符号域/右端切分/观察近似集 {×,x,X}（ALIAS_TO_CLASS 仅用于切分宽与观察标注，不参与类别等价）；R9 升
主路径（切分判分，停手条件后移至切分后断言②）；合并行只认最右、其余记 FN；指标定义 #3 原文与五类等价
**零变更**。修订稿 = `P018-P3-符号GT-执行包-A1修订稿.md`（local-only，含钉死字形宽表与 C1 重跑规格；旧探针
目录保留为 X1 证据，A1 探针写 probe_a1/）。**X3 = D'（同日 Ying 裁决）：P3 收尾，本包完结**。A1 重跑（probe_a1，
云端 `ed38bd0`）再次硬闸：词 15/15 满置信读出（行先验修复对文本完全生效），但符号 TP=0——**引擎符号可读边界
实测定格**：✓→√（墨迹紧盒，边缘）、✗→X（行内并入），**⊗/●/○ rec 层不可读**（孤立与行级双条件确认；决定性
证据 = row0 ○ 的 det 盒完整覆盖圆而 rec 只出尾随空格）；失败定位于 PP-OCR 文本管线的结构性边界（与官方
issue #9466 一致；Paddle 官方符号路线 = PaddleOCR-VL-1.5，明确特殊符号/复选框）。**判据/试件规格/指标定义
#3 零变更**（五类保留为愿景）。**C2~C4 不执行**，封存为「VLM 符号读数」立项的首期工作包（synth 渲染核心 /
A1 试件 / S-1·S-2 切分规则 / D8 engine 列原样复用；新 D 系列契约定义与产品侧路线 = 该立项前置裁决）。
**家族排序**：P-027 R1 随任意 docs PR 随手带 → P-027 R2 中英文件弱 GT 合成升主线（其登记条款「P-018 P3 在前」
随本裁决解除）→ VLM 符号读数立项其后（无在案需求信号，能力储备性质；可选 A1 探针 × Qwen smoke 半日内先证
「VLM 能否读圆族」）。登记清算：CHANGELOG / harness 架构文档无落地读数不登记；P-027 harness 文档债随其落地
批次。证据 = `docs/R&D/P018-P3-执行记录.md`（local-only，§4.4-§4.7）。

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
  **不宣称云端已验证**。执行包 `docs/R&D/runs/P020-ocr-harness-M1M2-执行包.md` 保留（含 §10 runbook 与回填模板）。
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
- **状态**：已落地（PR #43 → main `35239fc`，三项必需检查全绿）。
  **晋升审视（2026-09-26，用户裁决）**：无 architecture 内容可晋升——案例文档是对外 demo 资产，归宿即
  `docs/demo/`（已在）；结论已由 living 资产承载（`docs/demo/QUALITY_CASE_STUDY.md` + `docs/README.md`
  索引 + CHANGELOG + git 历史）。改列 `retained`：保留 as-of 2026-09-25 的 8 项数字对账基线、重编号缘由
  （P-025 已被 DOC-3 占用）与 A 部分废弃（round3 实证否决双指标口径）的记录。

### P-027 · RF 频率分配表 fixture 簇：内容面表格 GT 触发（2026-09-30 Agent U 立项包；10-02 Ying 裁决立项）
> status: decided · since: 2026-10-02
- **来源**：Upwork ~022102306242203617428（四国频率表提取）——09-30 裁决不投（四信号硬闸），整包转信息沉淀
- **资产**：四国 PDF（MY 197p 12 列贴 ITU / BR 201p 葡语国别码 / BD 218p / IE 414p 无框线+格内子区间=旗舰）· 客户三金件（内试 90% 行级基线 + 9 条失败 taxonomy / 三闸验收规范 / 28 列 10 样例行）· itu_services.csv（公开可用）
- **价值**：9 条 taxonomy 逐条对口 P-002/HITL/block_order，2 条盲区候选（无空格 token、截断无谱隙可检）；28 列 provenance schema 与本仓 confidence/sanity 设计同构；兑现 P-027 预留位（内容面表格 GT）
- **红线**：客户 PDF/xlsx 永不进 git（隔离区，test_data 纪律）；客户验收数字不作能力背书；Output_format.pdf 缺件不阻塞（28 列语义按样例推断，range-split 仅一例不结论）
- **执行拆分（未排队；R1 可随任意 docs PR 随手带）**：R1 资产归位+语言盘点+taxonomy 转用例（小）→ R2 弱 GT 合成主线 = **中英文件**（MY/BD/IE 按推定英语主体、以 R1 盘点确认为准；P-018 P1 文本层路线迁移）→ R3 验收三闸 harness 化（P-020/P-027 家族）→ R4 爱尔兰 borderless 专项（T3 极限测试场）
- **语言策略（10-02 Ying 裁决：主攻中英文）**：**BR（葡语）整体搁置**——结构表征价值由 R1 承接，不进 R2 主线、不写葡语专用归一化（diacritics/NBSP/soft-hyphen）；**解锁触发**：账本再捕 ≥1 条非中英文真实需求（第二语种 RFP/询单）→ 战略层重排裁决解锁 BR + 多语归一化专项
- **R1 语言盘点落地（2026-10-02，R2 判定同步）**：MY/BD/IE 主体均确认为**英语**（判定规则 3 未触发，R2 中英主线成立；MY/BD 无国别码系列、IE = ITU 5.xxx + ECA + IRL1 三族并存），BR 葡语确认（**搁置维持**）；四件文本层均**可用**（仅个别公式页 θ/≤ 为源文件字体映射符号，表体零污染）。明细 = `test_data/rf-quarantine/rf-inventory.md`（隔离区 local-only）
- **R2 弱 GT 合成与对账落地（2026-10-02，执行包 draft-v1，AgentE 执行）**：P-018 P1 文本层路线迁移至 RF 语料——行级位置配对对账（D11 抄录适配：greedy IoU≥0.5 一对一，配对帧 = 图像 px）。子集规则 v1 出 **23 页**（MY 7 + BD 7 + IE 9 含 borderless 探针页；MY/BD 全文无 `(Continued)` 标签页，2 槽如实记 None，名义 25 页）· **1427 行弱 GT**（C9：现场派生不留快照，pymupdf/源 sha256/命令随 derivation.json 落盘）· 质量闸 **0 页 excluded**（复现 R1 表体零污染）。对账读数（`line_match_rate` / `cer_micro` / `verbatim_pass_rate`）：**MY 0.9945 / 0.0128 / 8/8** · **BD 0.9885 / 0.0039 / 5/6**（唯一失配针 = 尾标点逗号→句点，逐字闸如实判失，taxonomy #2 机理）· **IE 0.2308 / 0.0073 / 1/2**——IE 6 个表页 GT 行盒中位高 132-138px（文本层把合并格单元读作跨多行 line 对象），OCR 块数与 GT 行数几乎一一对应且配对行内 cer 仅 0.0073 ⇒ **文本读出、几何结构性错位 = taxonomy #7 主战场实证**；IE borderless 探针页 p005 配对正常（17/20）⇒ 失败主因是合并格而非无框线。**X1 裁决 = (a)** C1 生死锚点按字面 MY-p007 目录页跑（PASS 0.9508/0.1346）；**X2 留痕** = 判分器首版误用 bbox_pt 帧致 paired=0，修正为 §3 契约 bbox_px 帧 + 回归测试钉死；**X3 已裁决（2026-10-03）** = IE 合并格页词盒分裂配对预研**排进 R3 前置**（见下条）。三方第三腿（版面区块 IoU）**缺口如实登记**：RF 页 drawings 仅框架线（IE 无框线页 = 0），视觉块不可直接产出，时间盒一次已花，归 R4。**R4 判读（2026-10-03）= 结构性不可测**：R3 §2.4 词级退化传导——词元几何与唯一性不可靠 ⇒ 词簇区块 proxy 亦不可靠；不发明 proxy，如需视觉腿另行立项。`(Continued)` 观测：IE-p158 OCR 读出（yes/yes，taxonomy #6 观测兑现）。证据链：pred_manifest 25 行 sha256 复算 **0 不符**（含 2 个误 POST 的叠渲染件，已隔离 `cache_nonpage/`）；GB2 同缓存双跑 CSV/report **逐字节相同**（CSV `71e2d32e…`）；tracked 恰 3 文件（本条 + CHANGELOG + harness 架构文档）。产物 = 隔离区 `derived/{gt,png,cache,eval}/` + 判分器四件（local-only，不入 git）；执行记录 = `docs/R&D/runs/P027/R2-执行记录.md`（local-only）
- **X3 裁决（2026-10-03，Ying）**：IE 合并格页词盒分裂配对预研**排进 R3 前置**——R3（验收三闸 harness 化）启动前先处理：GT 行盒跨多视觉行（IE 六表页中位高 132-138px）时，以词级盒（`get_text("words")`，A2 锚点先例）行聚类重建配对单元后再对 OCR 块配对。预研判据与执行规格 = R3 执行包的前置裁决段；**R2 读数维持原样不回改**（IE 0.2308 即现行口径下的如实读数，预研成果仅用于其后的复测/升级）。
- **X3 预研结论（2026-10-03，执行包前置段 A，判据 1-4 全不过 = NO-GO）**：`rf_words.py`（231 行，y 中心聚类阈值=词高中位×0.5 写死）按 A.2.1 规格落地——**X3-1** 重建行中位高 97.0px（窗 18-30px）· **X3-2** IE 六页 paired=0、match_rate 0.0000（阈 ≥0.60）· **X3-3** 零配对行 · **X3-4** 恒等闸原文口径结构性不可满足（MY-p007 dict line 是**单元格粒度**：61 条 = 25 视觉行带；修正口径 25=25 全配对但 min IoU 0.7428 < 0.95）。**根因比 A.0 假设深一层**：IE 六页文本层**词级**退化（词高中位 25pt ≈ 2.5 视觉行、p99 70pt，且同内容双列重复 x≈138/x≈275 成对）——词元几何与唯一性本身不可靠，几何配对层救不了，真实修复在语义层（归 R4）。R2 的 0.2308 维持原样不回改；未降阈值/未换页/未改判据（修正口径仅作诊断留痕）。证据 = `derived/{gt_words,eval_x3,overlay_x3}/`；执行记录 §2。
- **X4 裁决（2026-10-03，用户确认）**：X3 NO-GO 确认；**R3 主体（三闸 harness 化）以「IE = line GT 已知局限口径」继续**——IE 六页用 R2 line GT（0.2308 口径）如实低读数 + 缺口登记 R4；X3-4 原文口径的粒度缺陷（cell vs visual row）随 R4 一并修正。**（已落地 2026-10-03 R4 D4**：配对单元 = 频段行 + D4′ 跨块端点拼对，行重建 23 页 1.0000，见 R4 落地段**）**
- **R3 验收三闸 harness 化落地（2026-10-03，执行包 draft-v1，本会话执行）**：客户三金件机检化为**可复现行级秤**（只评不修，P-020 边界）——`rf_rows.py`（464 行：28 列 schema 冻结 + 频段锚行派生 + x0 列窗几何归意的脚注字段；**金样闸 4/6 全对**（MY×2/BD×2 Row_ID+ITU+National 全对）+ 2/6 Row_ID 级（IE 脚注列按 X4 局限记 None））· `rf_gates.py`（343 行：闸 1 行 join + 脚注 token 在场 + row_correct；闸 2 文本层频段全集在场率 + 缺口清单双向；闸 3 flag_rate（Confidence 无产品源 → **None 未测量 ≠ 0**，R4 缺口）；无发明值 = OCR 频段对 ∖ 文本层频段对）· `rf_gates_cli.py`（87 行，`build-rf-rows`/`evaluate-rf-gates` 外置壳）· `harness_cli.py` 挂接 +3 行（7 子命令）。D4 边界：pred 行结构化投影不做（IE 几何损坏 + 列绑定缺口），闸 1 = 字段级在场核对（解释性裁定，Ying 可另裁）。判分读数（23 页 65 行，读 R2 缓存**零新增推理**；内部回归不外引）：闸 1 row_correct **MY 0.6000 / BD 1.0000 / IE 0.8750 / all 0.8000**（footnote_set 全 1.0000，join 52/65）· 闸 2 presence **MY 1.0000 / BD 0.8065 / IE 0.8205 / all 0.8550**（112/131，缺口清单双向落 CSV）· 闸 3 flag_rate **None**（Confidence 无产品源，R4 缺口）· 发明值 3。守恒断言 rows==anchors 全页过；GB2 同缓存双跑三产物**逐字节相同**（CSV `51c89fe6…`）；`test_metrics.py` 43→**58 passed**（+15 R3 断言）；`lint_file_size.py` OK。tracked 恰 3 文件（本条 + CHANGELOG + harness 架构文档）；产物 = 隔离区 `derived/{r3,eval_r3,eval_r3_b}/` + `plan_r3.json`（subset 三件合并，执行计划澄清 #1）；执行记录 = `docs/R&D/runs/P027/R3-执行记录.md`（local-only）
- **R3 设计时裁决已定（盲区 #1/#5 候选方案，2026-10-03 Ying 采纳）**：**#1 脚注子区间作用域** = 「行带包络 + 区间包含」双约束绑定（脚注 token 归属其 y 带所在频段行；印刷子区间的脚注以区间包含校验），harness 侧只做作用域越界计数观测，修复归产品侧；**#5 无空格 token（RADIONAVIGATION5.76）** = 「词法边界探针」计量（token 同时命中服务词表前缀与 `5.\d+` 脚注词法后缀即计一次粘连），harness 只输出粘连率观测，切分修复归产品/R4。#9 已由 R3 闸 2 兑现其机器化形态（在场核对）。
- **R4 IE 语义层专项落地（2026-10-03，执行包 draft-v2，本会话执行）**：R3 §6.3 缺口的**语义层秤**（只评不修，P-020 边界；技术路线 = 语义信号而非词盒几何）——`rf_sem_gt.py`（337 行：IE 语义 GT = **锚形全匹配**频段行（书脊列排除，正文伪锚拒收、p158 真锚找回）+ 三族脚注码语义列（5.xxx→ITU / ECA→Regional / IRL→National）+ 服务词表（ITU_services.csv canonical 印刷域边界匹配）+ 合并格 = 频段列窗内容行覆盖；金样 9/9；守恒 rows==anchors + 未归类 0）· `rf_sem_eval.py`（416 行：行重建 **D4′ 跨块端点拼对**（X3-4 粒度修正落地：配对单元 = 频段行）/ 列绑定族→pred 列单射 / 合并格区间完整（起止印出 + 子区间不缺失，不判几何 IoU）/ #1 双约束冲突与 #5 词法边界探针观测；envelope 缺失读 **None（未测量 ≠ 0）**）· `rf_sem_cli.py`（101 行，`build-rf-sem-gt` / `evaluate-rf-sem` 外置壳）· `harness_cli.py` 挂接 +5 行。判分读数（文本侧 23 页 55 行，R2 缓存复用**零新增推理**；内部回归不外引）：行重建 **MY/BD/IE/all 全 1.0000**（R3 闸 1 同数据面 0.8000；MY 跨块子区间案例 149.9-150.05 命中）；#5 粘连 **BD 3/114 = 0.0167**（`RADIONAVIGATION5.470`/`5.337` 实样本 @ BD-p134）、IE 0/46、all 0.0049；#1 观测面 0（9 页子集无嵌套子区间行，金样页 p55/p244 不子集如实登记）；列绑定/合并格读数 **None**（IE 9 页 envelope 云端采集包备妥待执行，`derived/r4/cloud_pack/`）；Confidence 产品源维持未测量（D8，产品侧另立项）。§6.3 六条缺口承接：1/2/5 本包主体落地、3 维持未测量（产品源另立项）、4 已由本清单 §801 采纳兑现为观测口径、6 已由 §802 落地。GB2 双跑逐字节（CSV `12476506…`）；`test_metrics.py` 58→**71 passed**（+13 R4 断言，X3 旧断言零改动）；`lint_file_size.py` OK。tracked 恰 3 文件（本条 + CHANGELOG + harness 架构文档）；产物 = 隔离区 `derived/{plan_r4_ie.json, r4/, eval_r4/, eval_r4_b/}`；执行记录 = `docs/R&D/runs/P027/R4-执行记录.md`（local-only）。**envelope 回传补判（同日）**：云端采集 9/9 sha256 复核 0 不符（commit `ed38bd0c` + paddle 三件套 = kernel 锁定版本，零漂移）——列绑定 **IE 0.5278** / 合并格完整 **IE 0.7917**（GT 尾逗号假错位修正后，回归测试 72 passed，GB2 CSV `ca0a4fe9…`）；**p079 `40.7-4098MHz`（40.98 小数点丢失）= #7 家族产品侧失效实证，已登记 P-002 follow-up 触发证据**（同页列绑定全对 = 结构失效与绑定保持独立可测）；脚注定义页（p318/p331）被管线读成 2 列表、语义列结构不存在，0 读数为口径内如实读数。
- **已裁决并落地（2026-10-03 Ying 授权）：隔离区 git 防护（R3 执行计划澄清 #6）**：隔离区非二进制产物（md/csv/html/jsonl/txt/sha256/tar.gz，含客户文本的 gt jsonl 与判分 CSV）未被 gitignore 覆盖（R3 登记 22、R3 执行后实测 32），已增补 `.gitignore` 的 `test_data/rf-quarantine/` + `test_data/fonts/`（独立加固 commit，不入 GB3 计数）；「commit 只 add 指定文件 + porcelain 核对、严禁 `git add test_data/`」纪律保留为兜底（R2 起有效）。
- **排序**：P-018 P3 在前；分岔 C——RF/监管再现真实需求信号则 P-027 直升第一优先（类比 P-018 分岔 B）
- **derived/ 目录归类（2026-10-04，Ying 授权；不移动客户资产）**：隔离区派生产物 `derived/` 按四类重组 —— `gt/`（`r2`/`x3`/`r3`/`r4`/`plans`）· `cache/` · `eval/`（`r2`/`x3`/`r3`/`r4`/`r4_results`）· `packs/`（`cloud_pack`/`r4_cloud_upload`/`r4_out.zip`），各配 `manifest.json` 记录可复现三元组（源资产 sha256 + 脚本 + commit）。上列各轮「产物 = 隔离区 `derived/<旧名>/`」为**历史快照正文，保留不改**；新旧对应：`gt`→`gt/r2` · `gt_words`→`gt/x3` · `r3`→`gt/r3` · `r4/ie_sem_*`→`gt/r4` · `plan_*.json`/`subset_manifest.*`/`pred_manifest.*`→`gt/plans` · `eval`→`eval/r2` · `eval_x3`→`eval/x3` · `eval_r3`→`eval/r3` · `eval_r4`→`eval/r4` · `r4/results`→`eval/r4_results` · `r4/cloud_pack`→`packs/cloud_pack` · `r4/r4_cloud_upload`→`packs/r4_cloud_upload` · `r4_out.zip`→`packs/r4_out.zip`（`eval_r3_b`/`eval_r4_b`/`png`/`overlay_x3` 等旧轮次目录已不在，无对应）。客户源资产（`client/`·`pdf/`·`itu/`）原位未动；`rf-quarantine/manifest.json`↔`MANIFEST.md` 双源一致性由 `scripts/quarantine_manifest_audit.py` 机检（挂 `audit_agent_ops.py`）。
- **test_data 生命周期分层迁移（2026-10-04，Ying 授权）**：按「不可再生 / 可再生」物理隔离重构 —— `rf-quarantine/` 拆分为 `test_data/assets/upwork-022102306242203617428/`（`raw/` = 原 `client/*` + `pdf/*` 平铺；`public/` = 原 `itu/ITU_services.csv`；`manifest.json`；`notes/` = 原 `rf-inventory.md` / `rf-taxonomy-cases.md`）与 `test_data/derived/`（原 `rf-quarantine/derived/`，四类 `gt`/`cache`/`eval`/`packs` 不变）；`TestResult/` → `test_data/local/`（仅重命名，内容不变）。**手写 `MANIFEST.md` 退役**，`manifest.json` 为唯一指纹真源；审计由双源一致性改为**单源**（`scripts/quarantine_manifest_audit.py` → `scripts/assets_manifest_audit.py`，校验 schema / path 唯一与在场 / classification 枚举；逐文件 SHA256 仍由 `test_data/scripts/verify_assets.py` 承担）。根 `.gitignore` 新增 `test_data/assets/`、`test_data/derived/` 忽略并移除 `test_data/rf-quarantine/`，`TestResult/` → `local/`（含 `test_data/.gitignore`）。引用同步：frontend e2e（`playwright.config.js` + `coverage*.js`）、backend 工具（`summarize_kie_results.py`）、`test_data/scripts/*`（5 脚本）、kernel `environment.md` / `doc-sync.md`（已 `sync_agent_rules.py` 派生副本）及活文档（README / docs/architecture / docs/agent-ops / acceptance）。**客户资产仅 `test_data/` 内重组，未出仓库**。
- **资产指纹校验口径修正（2026-10-05）**：`test_data/scripts/verify_assets.py` 扩到双 schema（`assets[].path` 源资产 + `artifacts[].file` 产出件）+ **空清单防呆**（此前 `derived/*` 的 pack 清单因 schema 不识别被静默判「0 行 OK」= 假通过）。**口径修正（重要，勿再退回字节 sha）**：PyMuPDF `save()` 每次写入随机 `/ID[1]`，**派生产物字节不可复现**（同命令两次运行 sha256 不同，实测 `4d5aa2e0…` vs `62801eb3…`），故字节 sha256 不能作 `derived/packs/*` 的基准；改用**内容指纹**（`text_sha256` + `pages` + `words` + `rotation`），跨 run 稳定且仍能以 `rotation` 区分 IE-p079 两个产物（90 原始 / 0 证据包，text_sha 相同因 `set_rotation(0)` 只改元数据）。内容级校验走 PyMuPDF，不可用时记 `UNVERIFIED` 且非零退出，绝不静默通过；源资产字节路径零改动。实证：pack `c4_ie_p079` 2/2 OK、assets 12/12 OK（2 命名空间）、空清单 exit 1。P-028 rot0 证据包已按 generator 本地重生成（源件 sha `ae4ae7d8…` 校验通过），与云端实例**内容等价**（82 词 / rotation 0 / band 词 40.7+40.98 / judge_page_trust=text_layer 全部一致），字节 sha 不可比。
- **testfiles/others 迁入 assets（2026-10-04，Ying 授权）**：`test_data/testfiles/others/`（此前多个 **无单号** Upwork 需求单附件，4 件：`911_History_Report [1-10].pdf` / `ejemplo1_resultado.jpeg` / `ejemplo2_resultado.jpeg` / `P903454_1.jpg`）迁入新客户命名空间 `test_data/assets/upwork-legacy-202610/`（`raw/` 4 件原样保留 + `manifest.json` 4 件 SHA256 + `README.md`），与 `upwork-022102306242203617428/` 同构。命名 `legacy` 表「历史/无单号」、`202610` 界定「2026-10 前」。**校验/审计泛化**：`test_data/scripts/verify_assets.py` 与 `scripts/assets_manifest_audit.py` 由硬编码单 client 改为**遍历 `assets/*/` 全部命名空间**（新命名空间零改码接入；每个命名空间目录须含 `manifest.json`）。根 `.gitignore` 移除失效的 `test_data/testfiles/others/` 规则；`testfiles/README.md` / `acceptance/README.md` 同步。客户附件仅 `test_data/` 内重组，未出仓库。
- **R3 D4 边界解释性裁定追认（2026-10-05，Ying）**：R3 §5.2 的实现形态——闸 1 退化为「字段级在场核对」（pred 行结构化投影不做）、「无发明值」取 OCR 输出侧形态（幻影频段计数）——**追认为正式口径（保守形态即为口径），该裁定「Ying 可另裁」口关闭**。语义钉死：`row_correct`（行级 join）与 `presence_rate`（字段在场）为两个**独立强度**判据，各自如实登记、不互相折算；R4 D4′ 的行重建（配对单元 = 频段行 + 跨块端点拼对）属**判分器粒度修正**（X3-4 兑现），不改变本裁定「pred 侧行结构化投影不做」的边界；若未来产品侧 IE 语义层修复（R3 缺口 1）落地后需要行级投影核对，属新立项范围、不回改本口径。

**产品侧立项 A · 合并格语义进 layout 行列结构（2026-10-09，Ying 裁决；本轮允许真修）**
- **裁决**：①合并格语义解析**落在 layout 模型的行/列结构输出**（`backend/app/services/table_layout.py` 的 `LayoutModel` / `build_layout_model`），不在识别层、也不做后处理糊层；②**本轮允许真修**——P-028 X1=B 的「产品侧只能旗标」立场在**识别层**维持不变（`provenance-review.md` §4.4），本次解锁的只是**语义结构层**。
- **缺口原文**：R3 执行记录 §6.3 缺口 1（本地 `docs/R&D/runs/P027/R3-执行记录.md`）；R4 承接注记判「1/2/5 = 本包主体」仅限**秤侧**，产品侧修复此前未做。
- **冻结口径**：①合并格语义**唯一真源** = `html_structure` 的 `rowspan`/`colspan`/`has_merged_cells`/`header_span_map`（`backend/app/services/table_service.py:1207-1224`，已随 table dict 落盘 `:910`）；②**无结构串时 fallback** = 由 `data` 层空串占位反推 covered 集（`table_service.py:1046/1053` 已把合并格填空串；SLANeXt HTML 无 per-cell bbox 系已知情形，`table_cell_geo.py:53`）；③落点三文件 `table_layout.py`(202) / `table_cell_geo.py`(121) / `table_backfill.py`(417) 均为 P-028 拆分后**未固化**文件（`scripts/file_size_allowlist.json` 只固化 10 个文件，三者不在内），**不得改 `table_service.py`（已固化 1613）**。
- **暴露面（暂定，登记时采用推荐值）**：**只做管线内部**（`LayoutModel` 的 merge band / `derive_cell_bbox` 的 span bbox / backfill 候选格的 anchor-vs-covered 区分），**不写进 result JSON / view 层**——后者须改 `envelope_builder.py`（已固化 620），另行立项。
- **不改的**：cell 数据原值透传（禁修正小数点、禁猜值）；`row_correct` 与 `presence_rate` 两个判据的独立强度、以及 `:655` 的 D4 边界裁定均不回改。
- **验收**：①单测 = 合并格金样（`backend/tests/test_golden_backfill.py` G2c + `scripts/trial/generate_trial_samples.py::build_merged_band_table`、`test_table_header_structure.py` 多级表头/rowspan）；②Cloud 复测 = P-027 R4 语义秤的**列绑定 IE 0.5278 / 合并格完整 IE 0.7917** ~~应回升~~ —— **2026-10-15 实测未回升，判据前提不成立（更正见本节「A 项落地收口」末段）**，且 **R2 的 IE 0.2308 旧读数不回改**；③本机无 GPU ⇒ mock 单测 + 交付文档写 Cloud 验证步骤与验收标准。

**产品侧立项 D8 · Confidence 产品源 = OCR block confidence 传导（2026-10-09，Ying 裁决）**
- **裁决**：产品侧 confidence **取 OCR block 级 confidence 经行/字段聚合传导**——由此兑现 R4 D8 原文「已裁决 = (b) 归产品侧另立项」（`docs/R&D/runs/P027/R4-执行包.md:53`）。
- **缺口原文**：R3 执行记录 §6.3 缺口 3 =「管线未产 `Confidence`/`Flag_Reason` 列，闸 3 硬线（≤5%）未测量」；harness 读 `None`（未测量 ≠ 0）。
- **冻结口径**：confidence 语义 = **PaddleOCR `rec_score` 传导**（`backend/app/services/ocr_service.py:171-189` 的 `text_blocks[].confidence`），**非模型原生概率**——Qwen2.5-VL 路径无 logits/概率输出（`backend/app/services/kie_qwen_service.py:459-472`）；既有 `kie_confidence_avg` 仍是**填充率启发值**（`kie/kie_field_metrics.py:64-70`），两者语义不同、**不得混用或互相折算**。
- **落点**：①cell 级锚点 = `_reconstruct_table_with_ocr` 内的聚词段——**2026-10-09 已随 F1 搬移落至 `backend/app/services/table_ocr_blocks.py:82-97`**（搬移前为 `table_service.py:512-530`；该处**已持有带 confidence 的 OCR 块却只取 text**）；②confidence 网格随 `table_backfill.py:274-277` 现有四张 grid（`cell_provenance`/`cell_ocr_text`/`cell_word_bbox`/`cell_align_reason`）追加第 5 张 `cell_confidence`，行级值由 cell 值聚合。
- **前置已落地（2026-10-09，纯搬移、零行为变化）**：OCR 块簇（`_reconstruct_table_with_ocr` 33-152 + `_parse_cell_bbox` 154-195 + `_filter_text_blocks_in_bbox` 197-244 + `_find_text_blocks_in_cell` 246-288 + `_find_row_for_y` 290-310，共 278 行）**逐字节搬移**至新兄弟模块 `backend/app/services/table_ocr_blocks.py`（310 行，`TableOcrBlocksMixin`，经 MRO 挂在 `PPStructureTableEngine` 上 ⇒ 调用点与两个「按文件路径 importlib 加载」的测试零改动）；搬移块经 `git show HEAD` 逐行比对**完全等同**，全量回归 598 passed / 19 skipped / 5 errors 不变。棘轮随之下调 `table_service.py` 1613 → **1336**（`scripts/file_size_allowlist.json`，只减不增方向；`--update` 顺带收紧的 orchestrator 5 行无关余量已刻意还原以保持改动聚焦）。**故本条落点 = `table_ocr_blocks.py`（310/500，余量 190）+ `table_backfill.py`（417/500，余量 83）**，`table_service.py` 预期**零改动**；`cell_confidence` 仍未产出。
- **落点可达性更正（2026-10-09，代码实证；来源待裁决）**：**上述落点在生产不可达**——`backend/app/orchestration/document_pipeline_orchestrator.py:251` 取 `ctx["result"].get("text_blocks")` 后传给表格步骤（`:258`），但**全仓无任何代码写 `result["text_blocks"]`**（`text_blocks` 的唯一写入者是 `ocr_service.recognize` 的返回值 `ocr_service.py:311/322`，即 `/api/v1/ocr` 端点，`routers/analyzer.py:66`），故 `ocr_text_blocks` **恒 `None`** ⇒ `table_service._extract_from_layout_elements` 的 `if ocr_text_blocks and cell_bboxes…`（`table_service.py:274`）**永不成立** ⇒ OCR 重建路径（现 `table_ocr_blocks.py`）**在生产不被调用**。同时 `layout_service.py:737-740` 注释明写「parsing_res_list items do not carry a score field themselves; the score is only available in the upstream layout detection output」，故统一元素的 `confidence`（`layout_service.py:823`）是**版面检测分**而非 `rec_score`；`rec_scores` 全仓只被 `ocr_service._convert_predict_dict`（`:141/171-176`）读取，服务的是**独立 OCR 引擎**（`self._ocr.predict`），与 PP-StructureV3 管线**不同源**。**⇒「OCR block confidence」在主管线里目前没有来源**，须先裁决来源（三选项见下）再实现；**不得**为图省事把 `text_blocks` 接上主管线——那会让 `table_service.py:274` 成立并**翻转表格数据来源到 OCR 重建路径**，属行为大变。
- **来源三选项（待 Ying 裁决）**：**A** 从**同一次** PP-StructureV3 推理里取 OCR 层分数（若 `LayoutParsingResultV2` 暴露 `overall_ocr_res` 的 `rec_scores`/`rec_polys`）⇒ 零新增推理、语义与裁决一致，但**须先做 Cloud C1 探针**（打印结果对象的键/属性集合，纯观测、零产品改动）——**本机无 Paddle/GPU，该字段是否存在无法本地证实，仓库内亦无任何记录**；**B** 用独立 OCR 引擎逐页补跑（`ocr_service.recognize`，来源已确定）⇒ 代价 = **每页新增一次检测+识别推理**，且与 PP-StructureV3 **不同源**（两条 OCR 结论可能不一致）；**C** 改用已存在的版面检测分（`element['confidence']`）⇒ 零新增推理、今天可落，但**语义不同**（检测框置信度 ≠ 文字识别置信度），须另立口径且**不得**用于回答「中低识别置信行占比」。**推荐序：A（先探针）> C（若只需"有信号"）> B（成本与不一致风险最高）。**
- **来源方案 A 取证结论（2026-10-09，Ying 指定"先求证再写探针"）**：**有**。PaddleX 3.3 官方文档的 PP-StructureV3 输出字段表（3.3 线与锁定栈 paddlex 3.3.12 同线）逐字给出：①`overall_ocr_res` = `Dict[str, Union[List[str], List[float], numpy.ndarray]]`，含 **`rec_scores`** / `rec_texts` / `rec_polys` / `rec_boxes` / `dt_polys` / `dt_scores` / `textline_orientation_angles` / `text_rec_score_thresh` / `text_det_params`；②**`table_res_list[]` = `{cell_box_list, pred_html, table_ocr_pred{rec_polys, rec_texts, `rec_scores`, rec_boxes}}`** ⇒ **每个表格的单元格识别分数已按表分组**（比页面级 `overall_ocr_res` 更直接，无需几何配对）；③`parsing_res_list[]` 仅 `block_bbox/block_label/block_content/block_id/block_order`、**无 `score`**（与 `layout_service.py:737-740` 注释互证）。PaddleOCR 侧 `paddleocr/_pipelines/pp_structurev3.py`（v3.3.2）只是**薄封装**——`predict` 原样转发 PaddleX 结果、本文件不含任何字段定义，故字段权威出处是 PaddleX 文档/源码（PaddleX 仓库 raw 路径两次 404，未取到源文件；**关键结论以官方字段表为准，最终以探针在锁定栈上的实测回填**）。
- **接线含义（落点更新）**：源取 **`table_res_list[].table_ocr_pred`（首选）** / `overall_ocr_res`（回退）；而 `layout_service.py:711-724` **已经在遍历 `table_res_list`**（现只取 `pred_html`）⇒ 接线点即该处，属**同一份结果的字段透传，零新增推理**。
- **不可达性再加一条独立证据（同日）**：`table_service.py:268-269` 读的 `element['content']['cell_bbox']` **在 `backend/app` 内只有读取、没有写入**（`layout_service` 构造表格元素时只写 `element['html']`，见 `layout_service.py:832-837`）⇒ OCR 重建路径的两条前置条件（`ocr_text_blocks` / `cell_bboxes`）**在生产同时不可达**。
- **探针（已写就，待 Cloud 执行）**：`scripts/measure/probe_d8_table_ocr_scores.py`（local-only，`.gitignore:269 scripts/*` 已覆盖；命名沿 `probe_c1_r3.py` / `probe_c1_r4.py` 先例）。判据 **P1-P6**：P1 表存在且各表 `pred_html` 在场 / **P2 `table_ocr_pred.rec_scores` 在场** / **P3 `len(cell_box_list) == len(rec_texts) == len(rec_scores)`**（cell↔score 对齐）/ P4 `overall_ocr_res.rec_scores` 在场 / P5 `parsing_res_list` 无 `score` / P6 `_parse_result` 产出的元素无 `content.cell_bbox`；产物 `probe_d8.json`。**本机无 PaddleOCR（实测 `find_spec('paddleocr') = False`，探测路径已实测优雅退出码 2、临时文件零残留）⇒ 必须云端执行**：`cd backend && python ../scripts/measure/probe_d8_table_ocr_scores.py --pdf ../test_data/testfiles/GeneralFiles/bank_statement_sample.pdf --page 1`。**回填要求**：P1-P6 逐项结论 + 每表 `rec_scores` 的长度与 min/mean/max 记入本条目；**P2 与 P3 同时 PASS 才确认方案 A 成立**并据此实现 `cell_confidence`（P3 若 FAIL，则单元格级聚合不可用，须退回 `overall_ocr_res` + 几何配对，届时重新裁决）。
- **Cloud 探针读数（2026-10-09，Cloud GPU 机，分支 `probe-d8` @ `63ea47e`，paddleocr 3.3.2 / paddlex 3.3.12）**：两夹具各 1 张表，**判定两夹具一致 = P1 PASS / P2 PASS / P3 FAIL / P4 PASS / P5 PASS / P6 PASS**。读数：①`bank_statement_sample.pdf` p1 —— `cell_box_list=20` · `rec_texts=19` · `rec_scores=19`，`rec_scores` min 0.932009 / mean 0.991024 / max 0.999812；`overall_ocr_res.rec_scores` n=21 / min 0.943274 / mean 0.988158 / max 0.999901；②`invoice_multipage_3p_items.pdf` p1 —— `cell_box_list=32` · `rec_texts=26` · `rec_scores=26`，min 0.958547 / mean 0.990791 / max 0.999223；`overall` n=42 / min 0.924591 / mean 0.982971 / max 0.999424。**判读**：(i) **方案 A 的核心前提成立**——`table_ocr_pred.rec_scores` 在**同一次推理**内确实存在且为**表级、按识别条目分组**（P2 PASS）；`parsing_res_list` 无 `score`、`_parse_result` 元素无 `content.cell_bbox` 亦由实测坐实（P5/P6 PASS，此前只是文档/代码推断）。(ii) **P3 FAIL 系本条目预设判据过严**：预注册判据写成 `len(cell_box_list)==len(rec_texts)==len(rec_scores)`（隐含 1:1），而实测 `rec_texts == rec_scores` **恒等**、`cell_box_list > rec_texts`（20>19、32>26），差值形态与「空单元格不产生识别条目」吻合 ⇒ 格与条目**非一一对应**，但**未必不可用**；须区分 **H1**（空格无条目 ⇒ 几何归格即可用，未命中记 `None`）与 **H2**（识别条目为**行级**粒度 ⇒ 一格可含多条，须按格分组取 min）。
- **本轮不实现，先做第二探针定 H1/H2（2026-10-09）**：按预注册规则「P3 FAIL ⇒ 退回 `overall_ocr_res` + 几何配对并重新裁决」，**不直接改实现**。第二探针须回答三问：①识别框（`rec_boxes`/`rec_polys`）面积 vs 其所落单元格面积之比（≈1 ⇒ 格级 / ≪1 ⇒ 行级）；②每格命中条目数分布（max 是否 >1）；③未被任何条目命中的格是否为空格（对照 `pred_html` 经 `_html_to_data` 的 grid）。**H1 成立 ⇒ 首选源仍为 `table_ocr_pred`**（按格归格、未命中 = `None`，沿用"未测量 ≠ 0"）；**H2 成立 ⇒ `table_ocr_pred` 仍可用但须按格分组取 min**，或退回 `overall_ocr_res` 行级 + 几何配对——**两条路的聚合规则与 `high/medium/low` 阈值须一并裁决**（阈值直接决定闸读数，属口径而非实现）。
- **键集实测（2026-10-09，探针 JSON 回传；两夹具一致）**：`table_res_list[]` = `['cell_box_list','neighbor_texts','pred_html','table_ocr_pred','table_region_id']`；**`table_ocr_pred` = `['rec_boxes','rec_polys','rec_scores','rec_texts']`（与官方字段表逐字一致）**；`overall_ocr_res` = `['doc_preprocessor_res','dt_polys','input_path','model_settings','page_index','rec_boxes','rec_labels','rec_polys','rec_scores','rec_texts','return_word_box','text_det_params','text_rec_score_thresh','text_type','textline_orientation_angles','vis_fonts']`——**比文档少 `dt_scores`、多 `rec_labels`/`return_word_box`/`vis_fonts`**（官方字段表与实际输出的差异，以**实测**为准）；顶层 `result_item_keys` 16 键（含 `overall_ocr_res`/`table_res_list`/`layout_det_res`/`region_det_res`/`parsing_res_list`/`imgs_in_doc`/`width`/`height`/`page_count` 等）。**`cell_box_list[0]` 是 `[x0,y0,x1,y1]` 四数（非 8 数 polygon）**，例：bank 表 `[958.57, 426.21, 1175.53, 463.57]`。`_parse_result` 产出的元素键 = `['bbox','confidence','id','page','polygon_preprocessed','reading_order','text','type','type_name']`——**无 `content`**，表 HTML 挂在 `element['html']`（P6 实测成立，非推断）；`parsing_res_list` 条目是**对象**（`dir()` 中无 `score`，P5 实测成立）。**旁证（未定论）**：`rec_texts` 样本呈**单元格内容**形态（invoice 表首 5 条 = 表头 `Product Area` / `Product Description` / `Price` / `Quantity` / `Subtotal`），与 H1（格级、按格序）方向一致。
- **第四探针（帧判别）读数（2026-10-09，Cloud，同一 sha）**：**`rec_boxes` 与 `rec_polys` 逐字节相同**（三夹具一致 ⇒「换用 `rec_polys`」不是出路）。几何命中：`bank_statement` **raw 0 / flip 19**；`invoice_multipage_3p` **raw 24 / flip 0**；`pdf/sample_report` **raw 53 / flip 0**。三条推论：①**y 轴翻转（`y' = H − y`）只对 `bank_statement` 成立**，一刀切翻转会**破坏**另两个；②三夹具页面属性均正常——本地 PyMuPDF 实测 `rotation = 0`、标准 MediaBox/CropBox，且引擎自报 `doc_preprocessor_res.angle = 0` ⇒ **翻转非页面属性所致，根因未定位（位于 PaddleX 内部）**；③`crop_local_shift`（加表区域 bbox 偏移）后仍 `outside = 19` ⇒ **已排除「表内局部坐标」**这一假设。
- **H1/H2 定案与设计冻结（2026-10-09）**：**H2 成立**（`pdf/sample_report` 出现**一格 3 条**，且条目框面积中位仅为所在格的 **0.24**（min 0.03、max 1.00）⇒ 条目为**文本行级**，非 1:1）。设计冻结为三条：①**按格分组取 min**（格内无条目 ⇒ `None`）；②**逐表自动选帧**（raw 与 flip 取命中多者，**平局取 raw**）；③**命中率哨兵**（`hits / n_rec < 0.8` ⇒ **整表 `measured = False`**、每格 `None` 且 `reason = frame_unresolved`，**绝不静默产出全 0 / 全 1**）。三夹具在选定帧下命中率 **1.00 / 0.92 / 1.00**、被拒帧 **0.00**，判据余量充足。
- **核心模块已落地（2026-10-09，分支 `feat/p027-d8-cell-confidence`）**：`backend/app/services/table_cell_confidence.py`（**纯函数**：`as_box` / `_assign` / `aggregate_cell_confidence`；无 Paddle、无 IO、无 `self` 状态）+ `backend/tests/test_table_cell_confidence.py`（**11 例**，含三夹具几何的复现、`0.8` 哨兵边界、字符串/退化输入防递归与防抛）；`backend/tests/test_registry.json` 登记为 **`kind: full`**——**不登记 `phase-a-ci`** 是因为那只会产生 WARN，除非改 `.github/workflows/kie-phase-a.yml`（**CI 配置属红线**）。全量回归 598 → **609 passed** / 19 skipped / 5 errors；`audit 0/0`、`selftest 63/63`、`lint_file_size` OK。
- **接线已落地（2026-10-09，同一分支）**：`cell_confidence` **已进入管线**，四处落点——①`layout_service.py:659` 取**引擎帧页高**（`page_height_of`；**刻意不用 `_infer_page_bbox`**，因其兜底是硬编码 1000×1400，会把翻转帧算错）；②`layout_service.py:683-698` 表格遍历改为 `table_payload_map`（`html` 与**整条 `table_res_list` 项**一起保序，两列不再可能漂移）；③`layout_service.py:804-806` 逐表调 `cell_confidence_from_table_item` 挂到**表元素**的 `cell_confidence`（紧凑：每格一个 float + 6 个标量，**不入 view 契约**）；④`document_pipeline_orchestrator.py:285-287` 用 `attach_cell_confidence` **按 id** 落到 `result["tables"][i]["cell_confidence"]`（`table_service` 的表 id 即 element id，无需 bbox 启发式；`layout_elements` 为 `None` 时安全空转）。
- **接线前置重构（同日，另一 commit）**：`layout_service.py` **1804 → 1614**——删两处死代码（`_reinit_engine` 16 行、`_extract_text_from_parent` 17 行，后者函数体就是 `return parent_text`）+ 抽 6 个几何/文本纯工具（27 + 142 行）入 `_layout_geometry.py`（`_LayoutGeometryMixin`，经 MRO 挂载；**刻意不移** `_parse_result`/`_call_engine`/`_deduplicate_elements`，理由见该模块 docstring）。**刻意不删 `PPStructureEngine.analyze`**：它生产不可达（worker 在 `layout_service.py:1377-1387` 直调 `_analyze_pdf`/`_analyze_image`），但它是 `BaseLayoutEngine.analyze` 这个 `@abstractmethod` 的实现——删掉会使类变抽象、worker 构造即 `TypeError`。**注意**：`document_pipeline_orchestrator.py` 现为 **1297 = 其棘轮上限**（本次用掉了它此前 5 行余量）。
- **仍未做（下一步）**：①**未在 `table_backfill.py` 落第 5 张 grid**——现挂在表 dict 上的 `cell_confidence` 是**与 `cell_box_list`／`<td>` 文档序对齐的扁平列表**，而 `data` 的二维 grid 在**合并格**情形下位置数多于 td 数（A 项未落地、投影规则未定）⇒ 网格投影随 A 或单独小项裁定，**不在此硬凑**；②**开放口径**已汇总为下节「待裁决」块（信号选择 / 命中率阈值 / 切点 / `0.0→None`，共 **4 项**），**勿在本行取值**。
- **验证（同日）**：全量 **614 passed** / 19 skipped / 5 errors（开工基线 598 → **+16** 新用例）；`audit 0/0`、`selftest 63/63`、`lint_file_size OK`；两处搬移块经 `git show HEAD` 逐字节比对一致。**本机无 Paddle ⇒ 接线本身未经端到端验证**（`test_layout_page_id.py` 本地仍是既有的 `No module named 'paddle'` collection error，非本次引入）——端到端读数须待下次 Cloud 跑。
- **Cloud 端到端验证步骤与验收标准（GPU 依赖面，按 AGENTS.md 红线须交付；2026-10-13 修订）**：⓪**先核验被测副本含目标接线** —— `python scripts/measure/check_d8_wiring.py --repo <repo>` 须 `exit 0`（**模块与接线是两个提交**，缺接线时产物必然没有该字段且零告警；见下节「环境前置与首轮事故」）；①**装 paddle 的环境先跑** `cd backend && pytest tests/test_layout_page_id.py -q`（接线路径的唯一直接覆盖；本地因无 paddle 而 collection error）—— **2026-10-13 云端实测 3 passed ✓**；②**真跑含表文档**（`scripts/measure/D8_E2E_RUNBOOK.md` 的一键脚本；四件 = `GeneralFiles/bank_statement_sample.pdf` · `pdf/sample_report.pdf` · `invoices/multipage/invoice_multipage_3p_items.pdf` · `pdf/pub_bmcpubh_PMC13595506_p8-10.pdf`），在 `result["tables"][i]["cell_confidence"]` 上验收：**结构固定为 7 键**（`cells` / `frame` / `measured` / `reason` / `hits` / `n_rec` / `n_cells`；**没有 `unassigned`**，勿按它断言）、`len(cells) == n_cells`、`measured=True` 时 `hits / n_rec ≥ 0.8`；**`frame` 预期按版本分叉** —— **官方版 `bank = flip`、patch 版 `bank = raw`**（T2 的预期行为修正；旧文"`bank` 预期 `flip`"**作废**）；③**反向验收（哨兵）**：`pub_bmcpubh_PMC13595506_p8-10.pdf` **第 3 页是天然反向真件**（官方版 `measured=False` + `reason="frame_unresolved"` + `cells` 全 `None`；patch 版翻为 `raw`/`True`）—— **无需另造合成件**；**不得出现全 0 / 全 1**。读数经 `scripts/measure/d8_e2e_report.py` 汇总为**每版一个 JSON**，回填本条目。
- **聚合规则（已冻结，非开放项）**：cell 级取块间 **min**（安全侧：任一低置信块即低置信）；行级取 min。**信号选择与阈值不在此行**——见下节「待裁决」块（属**口径**，直接决定闸读数）。
- **两侧缺一不可 —— ✅ 已落地（2026-10-13，local-only）**：闸 3 已由「读 **GT 行**的 `Confidence` 列」（该列在 `scripts/measure/rf_rows.py:18-22` 已标「不可推导」⇒ 恒空、必记 `no_confidence_source`）改为**从 pred 侧读**——分值 = OCR 块的 `rec_score`（`rf_eval.pred_blocks` 新增 `confidence` 通路；`None` = 未测量 ≠ 0，`bool`/非数值不猜值）。绑定口径**松绑定**且与闸 1 join 同源（同一 `_freq_key`/`_scan_pairs`）：行频段对命中哪个块即取该块分，**多命中取 min**（同本条「聚合规则」的「行级取 min」）。**（2026-10-14 起改 D4′：T1 块内 + T2 跨块端点，三闸统一——见本节「(2)」的 2026-10-14 段；上句「同一 `_scan_pairs`」即 T1 面。）**落点：`scripts/measure/rf_gates.py`（新增 `row_confidence` / `score_histogram` / `_merge_histograms` + 闸 3 主体 + `aggregate` + 两处渲染）与 `scripts/measure/rf_eval.py`（`_score_of` + `pred_blocks`）；`rf_gates_cli.py` 回报行加 `coverage`。产物新增 `gate3_rows_measured` / `gate3_coverage`（= 已测量行 / GT 行，**防「分母缩小陷阱」**）两列，summary 增 `gate3_score_histogram`（与探针同款 edges ⇒ **可离线按任意切点重算**）；切点常量 `MEDIUM_CUT = 0.95` 标注为**未裁预览值**、渲染声明同步改写。自测 `scripts/measure/test_rf_gates.py`（**11 例**：适配器 rec_score 通路 / 行级取 min / 分母与覆盖率 / 切点排他性 / **GT 的 `Confidence` 列不再被读** / 未测量语义 / 汇总与直方图 / 渲染列同步与双跑逐字节同）。harness 属 local-only（`scripts/measure/**`），**不入门禁**；**实数据行级读数本机即可产出**——2026-10-14 实测：旧常量 `rf_gt.PDF_DIR = test_data/rf-quarantine/pdf` `exists=False`（2026-10-04 生命周期迁移后，三份客户 PDF 实测在 `test_data/assets/upwork-022102306242203617428/raw/`），给 `rf_gt.py` 加迁移回退后**全三闸本机跑通并逐项复现 R3 记录读数**（`all` = row_correct 0.8000 / presence 0.8550 / **flag_rate 0.0577** / coverage 0.8000）⇒ 原句「须待一次云跑」**作废**，该秤**不上云**（见下「待裁决」(2)）。
- **范围（暂定）**：本批只做**表 cell + 行级**；**KIE 字段级 confidence 不做**——证据层现无连接点（`kie/text_first.py:182-221` 的 payload 只到页级，`evidence/grounding.py` 的 `GroundingSource.blocks` 只有文本、无分数）。
- **契约影响**：若给 result JSON 加键 ⇒ `backend/tests/snapshots/openapi_baseline.json` 须重生成（cloud-only：`DOCUVISION_CLOUD_TESTS=1 DOCUVISION_OPENAPI_BASELINE=write`）并同步前端质量面板（`frontend/tests/unit/quality-panel.test.js`、`e2e/helpers/mock-pro-api.js`）；无路由签名变化，故 `test_route_contract_freeze.py` / `test_route_inventory.py`（55 路由）不受影响。
- **验收**：mock 单测（确定性，覆盖聚合规则与「缺块 = None」语义）+ Cloud 验证步骤；终局判据 = P-027 闸 3 `flag_rate` 由 `None` 变为**已测量数值**，并说明其与客户硬线 ≤5% 的可比性。
**待裁决与已裁决口径（2026-10-09 汇总；**唯一真源**）；（2026-10-13：(1) 已裁决；（2026-10-14：(0) 已裁决「不并列」· (2) 已裁决「绑定统一 D4′ + 非冻结读数」· (3) 批 1 / 批 2 均已落地（批 2 的契约面待在云验收））——**原「open · 3 项」已全部收口，无遗留 open 项**（(3) 云契约面复核 ✅ 2026-10-15 云实跑收口，见下方批 2「云端待办」收口记录；唯一遗留 = 重生成快照尚未入 PR #84）**
> 上文「仍未做」条的 ② 与「暂定口径」条里的"暂定/待定"表述**已由本节收口**，勿回旧行取值；裁决后同 commit 修订本节并落 `Session-check`；本条其余小节（缺口原文、取证读数、接线落点、Cloud 步骤）不受影响。
- **（0）闸 3 读数取哪个信号 —— ✅ 2026-10-14 裁决：取 pred 侧识别分（`rec_score` 传导），不并列版面检测分**：产品 Confidence 语义 = `rec_score` 传导 + 行级取 min（`table_cell_confidence.py`）；版面检测分（`layout_service.py:788` 的 `element['confidence']`，经 `envelope_builder.py:194/201` 透传、`:406/418` 聚合为 `quality.avg_layout_confidence`）是**检测框/分类质量**、产品不会写进 Confidence 列 ⇒ 拿它对标客户 ≤5% 是另一件事。**「定位 vs 识别」对照挪到表语料**（四件表：`layout.elements[].confidence` 与 `cell_confidence` 同在一份 result JSON，零新增推理）——**须如实说明粒度**：报告里的 cells 只留 `cells_sha256`（值在 R5/R6 探针里）⇒ **页级 `avg_layout_confidence` vs 格级分布，不是行级对行级**；要行级对照须先把 cells 落进报告。**RF 语料上 (a)/(c) 对照不可行**：RF 缓存来自 `/api/v1/ocr`、不含 layout 元素；且 `cell_confidence` 在 RF 语料部分页整页缺失（2/9 页 `tables=[]`），cell→频段行的投影依赖**未落地的 A 项**（合并格语义）⇒ 现在切对照会**静默缩小覆盖率**。**解锁触发**：**A 项落地 + RF 语料有 pipeline result JSON 时**，再补 (c) 与识别分的对照。**两信号语义不同，禁互相折算**（原纪律不变）。
- **（1）口径① 命中率阈值 —— ✅ 2026-10-13 裁决：维持 `0.8`（Ying）**：现值 **`0.8`**（`backend/app/services/table_cell_confidence.py:45` `DEFAULT_FRAME_OK_RATIO`，命名常量 + 注释记裁决）。**裁决依据（2026-10-13 扩充实测，八表）**：选定帧命中率 **19/19（bank）· 53/53（rep）· 124/124（p3）· 118/126 与 91/98（p2 两表）· 84/84（p1）· 45/45 与 51/51（bmcmed p6 两表）**、被拒帧 **0.00** ⇒ 空带比原三夹具更宽，任何 `0.0–0.84` 取值结果相同、余量充足。**维持理由**：**1.0 会误杀** `invoice_multipage_3p_items`（24/26 = 0.923 ⇒ 整表 `measured=False`）；**≤0.5 过松** ⇒ 错帧条目被归入错格，数字退化为"归格噪声"并**抬高** `flag_rate`。**复审条件**：仅当新夹具使选定帧命中率下探至 **<0.85** 时重审（现最低 0.923，余量 0.123）。**（已裁决，勿重开。）**
- **（2）口径② `high`/`medium`/`low` 切点（直接决定闸读数，属口径）**：秤侧公式 = `flag_rate = #{label ∈ (medium, low)} / #{有标签行}`（`scripts/measure/rf_gates.py:195-202`），硬线 `FLAG_RATE_GATE = 0.05`（`:39`，源自客户 Target 1）。实测分数**饱和且区间极窄**：bank 表条目 min **0.932009** / mean 0.991024、invoice 表条目 min **0.958547** / mean 0.990791、页面级 min 0.924591 ⇒ 观测下沿（0.93–0.96）与 5% 硬线**同量级**，故切点须钉在观测下沿附近才有判别力。**推荐：medium 起 0.95 / low 起 0.90**，并**同步声明该数值与客户 ≤5% 非同义**（`rec_score` 口径下的自定义阈值指标）。**连带必答两点**：①聚合规则已冻为 **cell 取 min、行取 min** ⇒ 行标签由**最差格**决定，行级 `flag_rate` **严格高于**格级，可比性说明须写明；②**分母缩小陷阱**——`rf_gates.py:196` 的 `confs = [c for c in confs if c]` 使**未测量行直接退出分母**，难表一旦 `measured=False` 会**美化**读数 ⇒ 须**并列输出"已测量行数 / 总行数"覆盖率**。**前置建议**：先跑一次 Cloud **直方图**探针再定档（现仅有 min/mean/max 三点，且 `pdf/sample_report` 的分数统计**未打印**），避免"猜档位"。**（2026-10-13 更新：前置已满足）** ①**探针侧直方图已有**——`probe_d8_table_ocr_scores.py` 落 `rec_scores_histogram` / `rec_scores_percentiles`（六夹具 + `overall_*`），`scripts/measure/R5|R6/**` 本地已存；②**闸 3 侧行级直方图与覆盖率已随 harness 落地**（见上「两侧缺一不可」条）⇒ 现在只差**一次云跑取行级读数**即可定档，且可用 summary 里的直方图**离线试算任意切点**而不必改代码。注：本地已有的六夹具表级 <0.95 占比为 **5.3%（bank）– 33%（bmcmed p6 表0）**，行级取 min 后只会更高 ⇒ 原推荐 `0.95/0.90` 的乐观性**须在定档时重估**。**（2026-10-14 更新：读数已落本机 + 用户裁决「本机已验证可跑的不上云」）** ①**可跑性**：`rf_gt.PDF_DIR` 迁移回退已加（`rf_gt.py:52-54`：取 `test_data/assets/*/raw` 中三件齐备者、`sorted` 保确定性）⇒ `python scripts/measure/rf_gates_cli.py evaluate-rf-gates --rows test_data/derived/gt/r3 --cache test_data/derived/cache --out <dir>` 本机即产权威三件；**必须显式传 `--out`**（CLI 默认 `rows.parent/eval_r3` 会写进 `gt/`，与既有产物目录不符）。②**本机实测（现行绑定口径 = T1 块内）**：`all` gt_rows 65 / joined 52 / row_correct **0.8000** / footnote_set 1.0000 / invented 3 / presence **0.8550**（112/131）/ **flag_rate 0.0577**（3/52，超 5% 硬线）/ coverage **0.8000**；分国 = MY 0.6000 / flag_rate 0.0000 / cov 0.6000、BD 1.0000 / 0.0741 / 1.0000、IE 0.8750 / 0.1429 / 0.8750；行级直方图（edges 0.80→1.00）counts `[0,0,0,0,2,1,0,2,9,10,28]`（**左尾 3 行落 [0.92,0.95)**，与 T1 口径下"仅 3 行可判"一致）。③**产物落点**：读入 `test_data/derived/eval/r3_v2`（**并列登记，不回改 `eval/r3` 的 R3 历史读数**——X4 口径）。④**遗留（已随本轮 D4′ 消解）**：`MY-p060` 的 `gate3_coverage` 渲染为 `-`（`n_joined=0` 时）——D4′ 后 `MY-p060` joined **6/6**、coverage **1.0000**，该形态在本语料不再出现；页级 `confidence_coverage` 在「有 GT 行但零测量」时仍记 `None`（渲染 `-`，语义 = N/A），保留原实现不改。⑤**相邻漂移 —— ✅ 已同批修**：`docs/architecture/ocr-quality-harness.md` 的 P-027 R3/R4 行已改述为 pred 侧 `rec_score` 读数（不再写「闸 3 flag_rate——Confidence 无产品源读 None」）。
  **（2026-10-14 裁决：绑定口径统一 + 非冻结读数）** ①**绑定口径统一**——闸 1/闸 2/闸 3 **一律用 D4′（T1 块内完整对 + T2 跨块端点拼对）**（`rf_gates.py` 新增 `_scan_endpoints` / `_page_binding` / `bind_pair`；闸 3 `row_confidence` 同步改 D4′），复用 R4 `rf_sem_eval` 已实证 1.0000 的行重建口径，**避免秤内两套绑定**。理由：旧「块内对扫描」把**整页级丢行**（频段被 OCR 读成两个块 ⇒ 落「未测量」并退出分母），**MY-p060 六行全因此形态**；统一后 65/65 回满。**脚注级风险**：T2 是**页级**端点存在性，端点重复时可能绑到邻行块——实测「严格邻接 T2」与「宽松 T2」结果**同形**（12 行邻接 + 1 行宽松）⇒ 脚注级、不单列。②**切点维持 0.95/0.90**——左尾最大间隙在 **0.947→0.9674**，0.95 正落其中（原预览值不必改）；**不为过线挪到 0.94**。③**读数并列登记、不回改历史**（同 X4 口径）——**D4′ v2**（`test_data/derived/eval/r3_v2`，GB2 同缓存双跑三产物**逐字节同**）本机实测：`all` gt_rows **65** / joined **65** / row_correct **1.0000**（R3 同面 0.8000）/ footnote_set 1.0000 / invented 3 / presence **0.9237**（121/131，R3 同面 0.8550）/ **flag_rate 0.0923**（6/65，**超 5% 硬线**）/ coverage **1.0000**；分国 = MY 0.0667 / BD 0.0741 / IE 0.2500（各 2 行 flag）。**三种分母并列（禁只报一个）**：现绑定 measured-only **3/52 = 5.77%** ｜ D4′ 后 measured（= 全 65 行）**6/65 = 9.23%** ｜ 「未测量按需复核计」（旧绑定）**16/65 = 24.6%**。**结论**：修好绑定后 RF 语料在 0.95 档下 **9.23% > 客户 5% 硬线**——登记为**内部回归基线**（**不是执行失败**）；被 flag 的 6 行含 R4 已定位的 **#7 失效行**（`IE-000040700000-000040980000` = p079 `40.7-40.98`）⇒ 该信号**有判别力**。④**非同义声明**：该数值与客户 ≤5% **非同义**（客户 Confidence 列语义**无原文定义**——`Output_format.pdf` 缺件，只能按样例推断；聚合规则格取 min、行取 min ⇒ **行级必然高于格级**；语料粒度 ≈ **1.5%/行**（65 行）⇒ **不宜做贴线结论**）；它是 `rec_score` 口径下的**自定义阈值指标**。⑤**新增 `gate3_flagged_rows`**（行 id 清单，页级 cap 8 / 汇总 cap 20，**确定性序 = 页序 + GT 行序**，`Row_ID` 缺则回落 `{page_id}#{行序}`）随 CSV/report/summary 落盘——此前只有计数与直方图、人工复核清单拿不到；**不破 GB2**。实测清单（`all`）：`BD-000018780000-000018900000` · `BD-001690000000-001700000000` · `IE-000040660000-000040700000` · `IE-000040700000-000040980000` · `MY-001700000000-001710000000` · `MY-001710000000-001930000000`。⑥**非冻结读数处理**：0.95 仅 `MEDIUM_CUT` **预览常量**（非口径），行级直方图 + coverage 随 summary 落盘 ⇒ 任意切点可**离线重算**、不必改码 ⇒ 读数以「**可复算基线**」登记而非冻结常量。**冻结的只有「口径选择与语义声明」**：信号选择（(0) 不并列）· 绑定统一（D4′）· 聚合规则（cell/row 取 min）· 非同义声明 · 解锁触发（A 项 + pipeline result JSON）。**验收**：`scripts/measure/test_rf_gates.py` **16 passed**（含 D4′ 跨块拼对 / 单端点不拼对 / `flagged_rows` 清单·回落·cap / CSV 列同步 + 双跑逐字节）。
- **（3）`0.0 → None` 语义修正（D8 姊妹项；2026-10-14 二次核查 = 可达性更正 + 修复面收窄 + 分两批落地，见下）**：把"未测量"塌成伪值的位置——①`layout_service.py:788`（近邻 3px 匹配失败 ⇒ `0.0`；**主路径可达**）；②`layout_service.py:854`（**`0.01` 魔法占位**，出现在 `inferred_bbox: True` 的推断兜底路径——该路径**根本不存在检测结果**，却给出一个"像分数"的常数；**2026-10-14 二次核查更正：不可达**——该分支在 `:670 if 'parsing_res_list' in item_keys:` 之后，而 `:826` 已 `return elements` ⇒ **与 ⑤ 同因**，**降为登记项、不列入修复**）；③`table_service.py:431`（`"confidence": 0.0,  # No confidence score available`，恒 `0.0`；**行号更正**：旧记 `593-594` 系 1804 行版本的行号）**＋姊妹点 `:260`**（`element.get('confidence', 0.0)`——把版面检测分当表置信度，同一塌陷形态，2026-10-14 新增）；④`envelope_builder.py:27-34`（`_as_confidence(value, default=0.0)`，`None`/非法 ⇒ `0.0`；调用点 `:194` / `:201`）。
  **2026-10-14 核查新增三处**：⑤`layout_service.py:953`（`float(score) if score else 0.0`）——入口 `:925` / `:931` 把缺字段默认成 `0`，且用**布尔真值** `if score` ⇒ 真实 `0.0` 与"字段缺失"不可区分、对 ndarray 会抛（与 D8 同型雷）；**但生产不可达**：`:670` 的 `if 'parsing_res_list' in item_keys:` 在 paddlex 3.3.12 恒真 ⇒ `:826 return elements` 提前返回，双保险 = R5 实测 `result_item_keys` 无 `preds`/`boxes`/`layout_dets` ⇒ `:901` 再次 return。**仅登记为死分支/潜在雷，不计入修复**）；⑥`envelope_builder.py:406`（`np.mean(confidences) if confidences else 0.0`）——**这正是产出 `quality.avg_layout_confidence` 的兜底本身**：空列表 ⇒ `0.0`，与"测得很低"不可区分，且 `np.mean` 会把上游**非零伪值**（如 ④ 的 `0.01`）一并平均进去（`0.0` 则在 `:390-391` 被 `> 0` 滤掉，不进分母 —— 见下更正）；⑦`routers/tasks_content.py:184-185` 与 `:230`（`float(confidence_raw or 0)`）——**对外 API 响应**面把 `None`/缺失 ⇒ `0.0`（落在 `routers/` 而非 `services/`，最易漏）。
  同型但不属 D8 面板（一并登记、不并入本项）：`figure_service.py:616`（`"confidence": 0.0`）、`seal_service.py:234`（`float(... or 0.0)`）；反例：`document_type_classifier.py:73/79` 的 `0.0` **语义正确**（"无提示"本就是 0），**不算塌陷**。
  按 D3/D7「未测量 ≠ 0」**均应 `None`**。**危害描述更正（2026-10-14 二次核查，读 `envelope_builder.py:390-391` 的 `conf = block.get("confidence", 0.0); if conf > 0`）**：`0.0` **不会拉低均值——它被剔出分母**，⑥ 的真实病是**分母静默缩小**（把"没测到"伪装成"没这块"）；真正入均值并拉低均值的只有 ④ 的 `0.01`（`>0` ⇒ 入均值）。影响面：**已对外暴露**的 `quality.avg_layout_confidence` 与**真实的低分检测**不可区分（把"没测到"伪装成"测到很低"），与（2）的覆盖率问题同源。**定量证据（2026-10-14，官方四件读数）**：`bank` 的 `avg_layout_confidence = 0.3540` 远低于其余三件（`rep 0.9033` / `inv 0.7797` / `pico 0.7508`），而 R5 探针显示该页 `layout_det_n_boxes = 2` ⇒ 多数元素在 `:788` 邻域匹配失败落 `0.0` 后**退出分母**，0.3540 只是少数命中块的平均（`conf==0.0` 的逐元素计数 **✅ 2026-10-15 官方云跑核实（HEAD=95413a6 = 批 2 代码）**：四件 `layout.elements` 逐元素 `conf==0.0` / `None` / 缺键 **三项全 0**（bank n=2 / inv n=29 / pico n=35 / rep n=14）——官方四件上伪 0.0 **未现形**，且 `bank` 该页**本就只检出 2 个版面元素**（与 R5 探针 `layout_det_n_boxes=2` 同值）⇒ `avg=0.3540` 即这 2 个真实元素的平均，本条旧假设「多数元素匹配失败落 0.0 退出分母」**不成立**（低均值 = 元素确实少，非分母被伪值缩小）；**反例参照**：IE 9 页 result JSON 实测逐元素 conf **全非零** = `zeros=0`）。
  **登记建议（用户 2026-10-14 裁决采纳）**：登记为 D8 姊妹条目。**修复面（按可达性收窄）** = ①③（含姊妹 `:260`）④⑥⑦；**②⑤ 仅登记**（同因不可达）。
  **契约影响（决定批次划分，2026-10-14 核查）**：
  - ③（含姊妹 `:260`）**纯内部**：`tables[]` 不在任何 pydantic 模型 / `response_model` 中（`routers/tasks_content.py:30-37` 直返裸 dict），且两侧消费点已写死"`None` → 回落 `score` → 0"（`services/export_service.py:22-26`、`frontend/modules/utils/csv.js:52-55`；`frontend/modules/result-panels/tables.js:284` 亦把非 number 归一为 `null`）⇒ **不动模型 / 快照 / 前端**。
  - ①④⑥ 与 ⑦ **属对外契约变更、共用一个契约面**：`FusedBlock.confidence: float = 0.0`（`models/api_models.py:40`）与 `QualityLayer.avg_layout_confidence: float = 0.0`（`:146`）经 `routers/jobs.py:41` 的 `response_model=JobEnvelope` 暴露；`tests/snapshots/openapi_baseline.json:599-603` / `:988-992` 声明 `"type": "number"`（另有默认对象 `:792-793`）⇒ 改 `Optional[float]` 必须重生成快照（cloud-only：`DOCUVISION_CLOUD_TESTS=1 DOCUVISION_OPENAPI_BASELINE=write`）。**三项连带（缺一即红）**：(i) `envelope_builder.py:391` 的 `conf > 0` 对 `None` **抛 `TypeError`**（质量层直接崩）⇒ 必须同批 None-safe；(ii) `tests/test_envelope_builder.py:89-96` 的 `TestNullConfidence` **现钉死** `block["confidence"] == 0.0` / `payload.confidence == 0.0`、`:233-234` 钉死 `isinstance(..., float)` ⇒ 本项是**意图变更**，不许可默默改测试；(iii) `jobs.py:41` 带 `response_model_exclude_none=True` ⇒ `None` 在响应里的语义是**键整个消失**（`payload` 内 `Dict` 值同样被剔除），不是输出 `null` —— 消费方须按"缺键"处理。
  **行数约束（棘轮只减不增）**：`layout_service.py` 1614 = 上限 · `table_service.py` **795 = 上限**（**更正**：旧记"1336 = 其棘轮上限"已随 F1 拆分过时）· `envelope_builder.py` **620 = 上限** · `routers/tasks_content.py` 425/500（余 75）。⇒ 批 2 若在 `envelope_builder.py` **新增**键（如 `blocks_without_confidence`）必然越线（红线禁抬高上限）⇒ 只能做"类型/默认值层面的等价改写"，或先在同文件内腾出等量行。
  **分两批落地（2026-10-14 用户裁决）**：
  - **批 1 · ✅ 已落地（纯内部）**：③ 两处——`:260` → `element.get('confidence')`（**今日为 no-op**：① 未改前 `element['confidence']` 恒为 float；其作用是让 ① 落地后表级如实为 `None`，避免批 2 漏改）、`:431` → `None`。行数不变（795 = 上限，未触棘轮）；验收 = 后端全量 pytest + `lint_file_size` + `audit_agent_ops` 全绿；**不涉模型 / 快照 / 前端**。
  - **批 2 · ✅ 已落地（2026-10-14，①④⑥⑦ 同批；本机可判定部分全绿，契约面待在云验收）**：**①块级** `layout_service.py:788` 近邻匹配失败 `0.0 → None`、`envelope_builder.py:27-28` `_as_confidence(default=None)` 保 None（调用点 `:194`/`:201` 不改）；**②页级** `:390-391` 入集判据 None-safe（`conf is not None and conf > 0`）、`:406` 空集 `0.0 → None`、`:418` `float()` 加 None 守卫；**契约** `api_models.py:40` `FusedBlock.confidence: Optional[float] = None`、`:146` `QualityLayer.avg_layout_confidence: Optional[float] = None`；**⑦** `tasks_content.py:184-185`（信封路径）与 `:230`（legacy 路径）不再 `or 0` 塌陷 ⇒ `None` 透传。**本机验收**：后端全量 `617 passed / 19 skipped / 5 采集错误`（与基线同形、**零新增失败**）；`lint_file_size OK`、`audit_agent_ops 0/0`、`lint_routes OK`、`lint_frontend OK`。**前端零改动**（既有"未测量表达"先例已覆盖：`csv.js:51-58` 的 `null → 回落 score → 0`、`tables.js:284` 归一非数值为 `null`、`text.js:185-190` guard `!= null`、`shell/ui.js:294` 与 `figures.js:65` 的 `|| 0`；`figures.js:49-51` 与 `text.js:215-217` 的旧渲染路径对 `null` 仍是 `0.0%`，与改前同形）。**行数中性核对**：`envelope_builder.py` 6 增 6 删 · `layout_service.py` 1/1 · `table_service.py` 2/2 · `api_models.py` 2/2 ⇒ 三个贴顶文件（620 / 1614 / 795）**一处未越线**；`tasks_content.py` 净 +1 行（425/500，非棘轮文件）。
    **「意图变更」声明（2026-10-14 用户裁决执行；本批不是缺陷修复而是语义切换）**：现行行为**三条全中被声明** ⇒ ①测试 `tests/test_envelope_builder.py:89-96` `TestNullConfidence`（注释即动机 "layout may emit confidence=None when det score unmatched"，断言 `== 0.0`）；②契约 `api_models.py:40/:146` + `tests/snapshots/openapi_baseline.json:599-603/:988-992`（`type: number` / `default: 0.0`）；③实现动机 `_as_confidence(value, default=0.0)` 本身就是该声明的落地。**旧公开语义** = 「confidence 是浮点数，缺分即 `0.0`」（= 未测量与测得 0 合并）；**新公开语义** = 「confidence 是 `Optional[float]`，缺分即 `None`，并经 `routers/jobs.py:41` 的 `response_model_exclude_none=True` 在响应里表现为**键消失**」。**三个抉择点（用户采纳推荐）**：①块级改 `Optional`；②页级空集 `None`（**不新增 `blocks_without_confidence` 键**——那正是上条行数约束里会撞 620 上限的备选路线）；③**接受"键消失"、不动 `exclude_none`**（该开关是**路由级**，为一个字段打开会波及整条响应里所有 None 字段）。**测试面成本 = 1 个用例、2 行断言**（`TestNullConfidence`：`== 0.0` → `is None` + 注释反映新意图）；**其余零改动**——`test_avg_layout_confidence_type`（`:233-234` 的 `isinstance(..., float)`）**存活**（其夹具全为 `_elem(..., conf=0.9)`，`_elem` 默认 `conf=0.9`）。**客户可见面零影响**：受影响字段只在内部 `JobEnvelope` / task result JSON；客户交付物是 28 列行 CSV/JSON，导出层已有 `None → score → 0` 回落（故对客户交付契约无改动）。**顺带扩散（如实登记，同向更诚实、无崩溃）**：`figures[]` 的 `confidence` 由 `figure_service.py:492` 的 `elem.get("confidence", 0.0)` 取值，元素未匹配时由 `0.0` 变 `null` ⇒ `pack_export_service.py:222` 该列由 `"0.0"` 变空串，前端渲染同形。
    **云端待办（本批唯一未完成项）→ ✅ 云验收完成（2026-10-15 云实跑回传，HEAD=95413a6 = 批 2 代码）**：①基线重生成 diff 实测**只含两字段**——`FusedBlock.confidence` `{default:0.0, type:number}` → `{anyOf:[number,null]}`（pydantic v2 对 `Optional[float]=None` 不写 `default: null`）+ `QualityLayer.avg_layout_confidence` 同型（该 hunk 在回传 diff 截断处之后，待入 PR 后本地对 origin 复核）+ `quality.default` 对象删去 `"avg_layout_confidence": 0.0` 一行 ⇒ 判据满足；②契约面 **13 passed**、全量 **649 passed / 1 skipped**（与上轮 659 的差 = `test_live_api.py` 10 例被 `--ignore`，本机 collect 已核实 = 10 tests，**无掉用例**）；write 跑 `1 passed, 1 skipped`（skipped = 写完基线即 `pytest.skip("baseline written")`，路由数 54 守卫 passed）；③批 2 轻量数据件（`bank` 的 result.json 逐元素计数）随 D8 E2E official 一并取回：四件 `conf==0.0`=0 / None=0 / 缺键=0（见上条 2026-10-15 核实）；`avg_layout_confidence` 四件与改前逐位一致（0.3540049 / 0.9032753 / 0.7796613 / 0.7507506）——均值不变为预测结果（伪 0.0 本就被 `conf>0` 剔出分母），且 bank 仅 2 元素全有实测分 ⇒「如实重算」成立。**遗留 1 项**：重生成的 `backend/tests/snapshots/openapi_baseline.json` 在云端工作区**尚未 commit/push 进 PR #84**（origin 头仍 95413a6）——须作第 4 个 commit 入分支，否则合并后 main 基线过期（下次云验证必红；CI 不受影响，云测在 CI 默认 skip）。**本机 `fastapi` 未装 ⇒ 本机绿不得当契约面证据**（本机基线那 5 个采集错误里就有 `test_blocks_reading_order.py`）。
  **登记（用户 2026-10-14 指出；本轮留档、未改代码）**：`backend/app/services/table_cell_confidence.py:260-265` 的 `attach_cell_confidence` docstring 写 "Tables without an element, or with an unmeasured payload, are left untouched"，**与实现不符**——`measured=False` 的载荷是非空 dict（truthy）⇒ **照挂**（本机以 `measured=False` + `cells=[None,None]` 试跑得 `attached=1`；E2E 记录亦印证 `pico measured=false` 被报出）。**两条后续**：①该 docstring 应改为"未测量载荷照挂、由消费方查 `measured`"（1 行、零风险，可并入批 2 或单独提交）；②**消费方纪律**：读 `cell_confidence` 前必须先查 `measured`，否则 `cells` 全 `None` 会被误当"已测量"。
- **A 项（合并格语义/投影规则）落地收口（2026-10-15；取代本节「仍未做」:685①，投影规则已定档并实现）**：**投影规则 = 方案 A（span 折叠对齐）**——①**锚位在解析处**：`table_html.py` 抽 module-level 共享占位走查 `_walk_occupancy`（`_html_to_data` 与 `_extract_html_structure` 同源，消除两处行过滤漂移；行一致性过滤分支经核实为**死代码**——每行恒 `[''] * max_cols` ⇒ ratio 恒 1.0——原样保留），`html_structure` 新增 **`span_map`**（`<td>` 文档序、每项 `{row,col,rowspan,colspan}`，**row/col = 输出行索引**：仅在该行被 `any(cell.strip())` 接纳后提交 ⇒ 丢空行不偏移；`>20` 列截断同步丢 `col>=20` 锚位；无 `<table>` 早退 `return {}` 不变，钉死 `test_table_header_structure.py` 既有精确断言）；②**续位 = `None`**（非 0、非复制值）：`table_cell_confidence._project_cell_confidence` 由 `attach_cell_confidence` 逐表调用（**签名不变、orchestrator `:287` 零改动**），产出 `cell_confidence_grid`（与 `data` 同形）+ `cell_td_span`（与 `cells` 同长、`<td>` 序，由 span_map 单一计算派生）；③**投影与 backfill 信任门控解耦**——不走 `backfill_table_cells`（其只在 trusted / rotation==0 / 非 deskew-unwarp 页运行，会把不可信页的已测量表静默判为无 grid），故 `table_backfill.py` **零改动**；④**五条守卫**（字段 list / `len(span_map)==len(cells)` / int 且 span≥1 / 锚位含 span 端点界内 / **语义位**＝覆盖矩形非锚位格须为 `''` 且锚位不重复）任一失败 ⇒ 两键都不挂 + 单表一次 warning（含 id+原因），**降级而非发明**；**已知降级触发四类**：`max_cols<2` 单列表、`>20` 列宽表、嵌套 `<table>` 致 `find_all` 递归多计、PaddleOCR 版本漂移致 `len(cell_box_list) != td` 数。**读数面**：`proof_report` 指标卡增「低置信/未测量格」格卡 + 逐表第 8 列（`low/unmeasured`），统计经 `summarize_cell_confidence` 读**扁平载荷**（`measured` 为第一判据）⇒ grid 降级或不可信页下读数仍成立；`LOW_CONFIDENCE_CUT = 0.90` 为**未裁预览常量**（同 (2) `MEDIUM_CUT` 处理，可离线按直方图重切）。**payload 体量增长（如实登记）**：每表 +`格数×float`（grid）+ `格数×小字典×2`（span_map + cell_td_span，后者与 span_map 同值——四项定档之"扁平侧可辨识合并格"义务所致，由 span_map 单一计算派生非独立重算）。**本机验证**：全量 **646 passed / 19 skipped / 5 collection errors**（开工基线 617 → **+29** 新用例 = 特征化 9 + span_map 6 + 投影/汇总 13 + proof pack 1，零回归；5 error 为既有无 fastapi/paddle）；`lint_file_size OK`（`table_html.py` 392→**444**、`table_cell_confidence.py` 279→**414**、`proof_report.py` 461→**482**，均 <500；`table_service.py`/orchestrator/`envelope_builder.py`/`layout_service.py` 四固化文件零改动）；`audit_agent_ops 0/0`、`docs_refs_audit 0/0`、`lint_frontend OK`。**A3 云采集已执行（2026-10-15；判据未达成，且经实测判定「判据前提不成立」）**：回传包 `test_data/derived/packs/r4_results.tar.gz` 解包至 `packs/r4_cloud_upload/r4_out/`，**sha256 9/9 复核 0 不符**；云侧 = **`commit b59008b`**（= 本分支 HEAD，含 A 项）+ `dirty_files=0` + **`paddleocr 3.3.2 / paddlex 3.3.12`（锁定栈零漂移）** + NVIDIA A10。回传 envelope **确认含 A 项三新键**（`html_structure.span_map` / `cell_confidence_grid` / `cell_td_span`）⇒ **投影确已触发**；挂载 **5/7** 表（p079/p197/p318/p331/p363 挂 grid；**p007 `span_map` 48 vs `cells` 47、p158 29 vs 26 两表按守卫降级**——两键都不挂、诚实缺键，属已知的 td 计数漂移类）。**读数 = IE 列绑定 0.5278 / 合并格 0.7917，与 A 项前 `eval/r4` 基线 23 个逐页行逐字节相同**（新读数并列登记于 `eval/r4_a`，**不回改历史**）⇒ **判据「应回升」未达成**。**根因（两条秤侧路径均 A/B 实测零影响）**：①秤的 pred 侧**只读 `tables[].data`**（`scripts/measure/rf_sem_eval.py` 的 `load_envelope_cells`），A 项对 `data` 零改动（实测 9 页 `data` 与 `html_structure.rows` 新旧**逐字节相同**）；②本语料合并格**只有 rowspan、`colspan` 恒 1** ⇒ **span 锚列 ≡ 网格列（恒等）**，把 `load_envelope_cells` 改走 span_map 预期提升 **0**（A/B 逐页同）；③**词法边界匹配**（本轮已采纳，见下）在本语料 **A/B 逐实例命中集 0 差异**。**四个失分族同属一类**：脚注 token **亦印在另一列**——`IE-p197` 法规列**真印**交叉引用 `5.925`（**非**数字串片段；早先判读已更正）、`IE-p318`/`IE-p331` 脚注定义散文列、`IE-p007` `rowspan` 频段标签合并格吸收了下行标签 `5.317A` ⇒ 属 **D5「族→pred 列单射」判据的固有边界**，**非合并格语义、非 matcher 缺陷、非 A 项可触及**；**R2 IE 0.2308 未回改** ✓，`:663` 的「应回升」表述已同步更正。**本轮采纳的秤侧改动（local-only，不入 git）**：`bind_columns` 候选筛选改**词法边界命中**（`lexical_hit` + `unit_squash`：token 出现处前后不得紧邻数字，且判定域须**保留印刷 token 分隔**）——**硬化而非读数推动项**（本语料 0 差异）；回归 = `scripts/measure/test_metrics.py` 新增 `test_r4_eval_column_binding_lexical_boundary_known_answer`（含「整体 squash 域会误杀 `5.150 ECA36` 的 `ECA36`」钉死）；`pytest scripts/measure/test_metrics.py` = 改前 **71 passed / 1 failed / 1 skipped**（失败项 = `test_r4_eval_glue_probe_known_answer` 的 `test_data/rf-quarantine/itu/ITU_services.csv` stale 硬路径，自 2026-10-04 重组起红），**已修**（见下「附带修复」④）⇒ 改后 **77 passed / 0 skipped**。**与 GT 侧口径的故意差异**：`rf_sem_gt.service_tokens` 的服务**长词表**匹配用字母数字+连字符边界（`(?<![a-z0-9-])`），本轮 `lexical_hit` **收紧为仅数字边界**——脚注 token 常与词粘连（`RADIONAVIGATION5.76`，正是 #5 探针形态），字母边界会误杀这类**真出现**；数字边界只拦「更长数字串的片段」，即本指标要拦的形态。**A3 附带修复（2026-10-15；均 `scripts/measure/**` local-only、不入 git）**：①**默认路径回退**——`rf_gt` 新增 `ROWS_DIR` / `SERVICES_CSV`（沿 `PDF_DIR` 先例：**旧路径优先、缺失即按 2026-10-04 迁移后位置回退**，sorted 保确定性），`rf_sem_eval.evaluate_pages` 默认与 `rf_sem_cli` 的 `--rows` 改用它；②**不再静默**——`evaluate_pages` 在 `rows_dir` 缺 MY/BD 行时打 `[warn]`（此前零报错地把两国行级 GT 记空）；③**伪页面**——新增 `rf_gt.list_page_ids`（`PAGE_ID_RE`，宽松 2-4 位国别码 / 1-5 位页号），`evaluate_pages` 由**缓存目录派生页集**处改用它 ⇒ `cache/manifest.json` 不再成行；`rf_gates.evaluate_rows` / `rf_eval.evaluate_files` 先按 GT 派生页集、缓存仅作查表（多余 key 惰性）**未改动**（`list_page_ids` docstring 已注明）；④**同族 stale 硬路径清扫**（后三处为本次新发现）——`test_metrics._IE_PDF`（旧 `rf-quarantine/pdf` 硬路径使 **C2 金样闸自迁移起被静默 skip**）、`test_r4_eval_glue_probe_known_answer` 词表路径、`rf_sem_gt.verify_gold_sem` 与 `derive` 的两处词表路径、`derive` manifest 的 `services_csv.relative_to(QUARANTINE)`（迁移后必抛 `ValueError`）——一律改走 `rf_gt` 迁移感知常量 / 新 `_src_path`（相对仓根，失败退绝对值）。**验证**：`pytest scripts/measure`（三个测试文件）= 改前 3 failed / 1 skipped ⇒ 改后 **128 passed**（含本轮新增三口径回归 ⇒ 77）；**不传 `--rows`/`--services` 直跑** `evaluate-rf-sem` ⇒ `[all] pages` **24→23**、MY/BD GT **30/27** 行齐备、读数与传参跑**逐位一致**（IE 0.5278 / 0.7917）。**已裁决并落地（方案 A，2026-10-15）：聚合三口径并列**——原登记缺陷：①**聚合率列口径不自洽**——`rf_sem_eval._aggregate` 率列取「**有读数页的均值**（macro）」，而同行的计数列是**求和**（micro）⇒ IE 报 `col_binding_rate` **0.5278** 而 micro 是 `7/11 = 0.6364`、`merged_complete_rate` **0.7917** 而 micro 是 `5/7 = 0.7143`（`row_rebuild_rate` / `glue_rate` 在 IE 上两者恰好同值；`[all]` 的 glue macro **0.0049** vs micro `3/326 = 0.0092`）；**根因 = 与同家族 R3 三闸口径不一致**——`rf_gates.aggregate` 的率列**全部按计数重算（micro）**且带 `gate3_coverage`（防「分母缩小陷阱」），`rf_sem_eval` 侧既无 micro 亦无 coverage；**落地（纯加法、未覆写历史产物）**：(a) 并列 **`*_micro`**——分子/分母 = 同行**已有**计数列（`MICRO_SPEC`）⇒ 不可能与计数漂移；(b) 并列 **`*_coverage`**——有读数页 / 本 scope 页数；(c) 四个 `*_rate` 列名**不改**（语义仍是 macro），**引用口径钉死 = micro**（与 R3 对齐），口径声明落在 report 的 `<h2>Rate aggregation</h2>` 段与 `summary.json` 的 `notes`；`*_micro`/`*_coverage` 是**聚合层**量 ⇒ 页级行显式 `None`（渲染 `-`）。**实测新读数（本次重跑）**：IE `col_binding` macro **0.5278** / micro **0.6364** / coverage **0.6667**、`merged_complete` macro **0.7917** / micro **0.7143** / coverage **0.4444**；`[all]` macro **0.5278** / micro **0.6364** / **coverage 0.2609**（**仅 6/23 页有列绑定读数**——此前不可见的分母真相）、`glue` macro **0.0049** / micro **0.0092** / coverage **0.7391**。已按 (c) 在 `CHANGELOG.md` 与 `docs/architecture/ocr-quality-harness.md` 的 R4 行标注 macro 并同时给出 micro。回归 = `scripts/measure/test_metrics.py::test_r4_eval_aggregate_macro_micro_coverage_known_answer`（构造 macro ≠ micro 的已知答案：0.75 / `2/3` / coverage 0.5）。**仍登记（未修、待裁决）**：①**构建侧输出路径仍指向已退役的隔离区树**——`rf_gt.DERIVED` / `GT_DIR` / `PNG_DIR`（`build-rf-gt` 会 `mkdir(parents=True)`）与 `rf_sem_gt.R4_DIR`（现为**死常量**）仍解析到 `test_data/rf-quarantine/derived/**` ⇒ **照跑会重建已退役目录树**；输出面重定位（落 `test_data/derived/gt/r2` 或别的）属另一决策，本轮未动。**A4 触发条件**：A 项 ✅ 已落地 + RF 语料有 pipeline result JSON（未满足）⇒ (c) 对照仍未解锁（见 (0)）。

**D8 端到端验证的「环境前置」与首轮事故（2026-10-13，Cloud 实跑）—— 本节为 D8 验证的环境真源**

- **现象**：在云端 `probe-d8` 工作副本上跑**四件 × 两版**（patch / 官方 baseline），**八次全部 `[FAIL] … no cell_confidence on table`**；两版**完全同形**、日志**零告警**。
- **定案（H5）**：**非产品缺陷、非 patch 问题** —— 被测副本**含 D8 模块、缺 D8 接线**，所以"产不出该字段"是必然结果。
- **三方证据**：①**云端 grep** —— `backend/app/services/layout_service.py` 与 `backend/app/orchestration/document_pipeline_orchestrator.py` 里 `cell_confidence` **均为空**（连 import 都没有），而 `backend/app/services/table_cell_confidence.py` **完整**（`:45` `DEFAULT_FRAME_OK_RATIO` / `:205` `cell_confidence_from_table_item` / `:235` `attach_cell_confidence`）；②**提交链** —— **模块 = `6047d5b`**（提交标题原文即 "…module (**pure logic, not wired yet**)"），**接线 = `c634272`**（`ed92bb2` 仅为腾出插入点）⇒ 副本可以停在"只有模块"的状态；③**`--inspect` 全树搜索** —— `field_paths.cell_confidence: []`（连 `layout/elements[*]` 也没有），而 `table0_keys` **含 `html`/`data`/`html_structure`** ⇒ 元素分支进得去、值却算不出 ⇒ 与"挂载代码不存在"一致。据此排除：**H2** 键名不符（`layout_table_blocks` ≥ 1 且表 id 为 `p1_e1` 形态）、**H3** 配对越界（`html` 与 `cell_confidence` 由同一条 `if` 管）、**H4** 搬运失败（`layout` 侧也没有）。
- **机制（为何零告警）**：`table_cell_confidence.py:213-215`（`if ocr_pred is None: return None`）与 `layout_service.py` 的 `if cell_confidence:` 都是**静默**返回/跳过；探针的 `engine_module.available` 只查**模块能否 import**、**不查接线** ⇒ 假阳性。
- **修法（不必重装 paddlex）**：`git cherry-pick c634272`，或按最小 patch 应用该提交对两文件的改动 —— `layout_service.py` **4 处**（模块导入 / `layout_page_height = page_height_of(first_item)` / `table_html_map` → `table_payload_map`（html 与 OCR 分数两列不再漂移）/ 表元素分支取 item 并挂 `element['cell_confidence']`），`document_pipeline_orchestrator.py` **1 处**（`attach_cell_confidence(ctx["result"]["tables"], layout_elements)`）；**改完重启服务**。⚠️ 该提交用掉了 orchestrator 的**最后 5 行棘轮余量**（`scripts/file_size_allowlist.json` 需同步）。
- **流程教训（新增义务，已一般化）**：**端到端验证前必须先核验「被测副本是否含目标接线」** —— 补丁侧早有锚点守卫（`paddlex/tests/check_patch_anchors.py`），而**产品侧代码此前无同类守卫** ⇒ 本次新增 `scripts/measure/check_d8_wiring.py`（**5 个锚点**：`layout_service.py` 4 + orchestrator 1；缺失即 `exit 1` 并打印修复指引），并接进 `scripts/measure/d8_e2e_run.sh` 的**公共前置**（版本守卫之后、patch / official 两版都查）。
- **配套（均 local-only、不入库）**：`scripts/measure/D8_E2E_RUNBOOK.md`（§0 准备 / §1 patch / §2 official / §3 对比；**不含安装与切换版本命令**）、`d8_e2e_run.sh`（一键跑一版，含版本守卫 + 接线守卫）、`d8_e2e_report.py`（每版一个 JSON；`--inspect` / `--list-outputs` / `--compare`）、`check_d8_wiring.py`。
- **影响面**：T1–T4 的 R6/R8/R9 读数（引擎侧 / 几何侧）**不受影响**；上文「验证（同日）」条的「**接线本身未经端到端验证**」**仍然成立**（本轮并未真正验证到接线）；`cell_confidence` 的 Cloud 验收（见上「Cloud 端到端验证步骤」条）**仍待重跑**。

- **第二轮事故并已定位（2026-10-14，接线补齐后 official 四件整页崩）**：补接线（`check_d8_wiring.py` exit 0、`pytest tests/test_layout_page_id.py` 3 passed）后，官方版跑四件仍 `[NO_TABLES]`，`--inspect` 报 `layout_elements_n=0`，`server.log` 报 `PPStructureV3 worker error: The truth value of an array with more than one element is ambiguous`。**根因已定死在本机代码，非 paddlex 不兼容**：`table_cell_confidence.py::cell_confidence_from_table_item` 的三处兜底写成 `_pick(ocr_pred, "rec_boxes") or _pick(ocr_pred, "rec_polys") or []`（`cell_box_list` / `rec_scores` 同款），而 PP-StructureV3 给的是 **`np.ndarray`**（`rec_boxes` 为 `(N,4)`）⇒ `bool(ndarray)` 抛 `ValueError` ⇒ 整页 `_parse_result` 失败 ⇒ worker 回 `('error', …)` ⇒ 四件全空（本机 numpy 1.26.4 已逐字复现；聚合体本身 array-safe，**只有兜底是雷**）。**推翻上一轮判据**："`_parse_result` 属主进程 ⇒ worker 报错与接线无关"是错的——`_call_worker_pdf_page_by_page` → 子进程内 `_analyze_image_layout_only` → `_call_engine` → **`_parse_result` 就在 worker 里跑**，故 worker 报错**不能**洗脱接线代码。**修法（本机已完成）**：新增 `_as_sequence()`（ndarray→list，永不对原始字段取真值），三处兜底改用它（`rec_boxes` 优先、`rec_polys` 兜底的取值顺序不变）；另：**曾一并给 `layout_service._call_worker` 的 error/retry 两分支加了「把 worker 送回的 traceback `msg[2]` 落日志」，但已回退**——`layout_service.py` 现为 **1614 行 = `scripts/file_size_allowlist.json` 的既有上限**，`lint_file_size` 直接 FAIL，而**抬高棘轮是红线**（丢弃子栈帧属可诊断性缺陷，改在别处腾出余量后再议，登记于此）。**验证**：本机 `pytest tests/test_table_cell_confidence.py` **19 passed**（新增 3 例：数组正常聚合 / `rec_polys` 兜底与标量容忍 / `page_height_of` 数组输入退化为 `0.0`）；`test_layout_page_id.py` 本机因无 `paddle` 仍为 collection error（既有，非本次引入）。**✅ 已验证通过（2026-10-14，Cloud 实跑；修复在分支 `fix/d8-numpy-truth-value` @ `0f321fc`，云端 checkout 该分支后重启服务重跑）**：**四件 × 两版全 `[ALL PASS]`**，`cell_confidence` 7 键齐、无 `unassigned`；`pytest tests/test_layout_page_id.py` **3 passed**（两版各一跑）；cloud-only `DOCUVISION_CLOUD_TESTS=1 pytest tests -q` **659 passed / 1 skipped** ⇒ **`cell_confidence` 加键未破路由契约，`openapi_baseline.json` 无需重生成**（PENDING:691 的契约担忧就此排除）。**四件读数（official → patch）**：`bank` `frame=flip → raw`、`hits 19/19`、`n_cells=20`（`cells_sha256` `E5A4… → 9668…`，**cells 随帧变**）；`pico#p3_e2` `frame=null → raw`、`measured=false → true`、`hits 1/124 → 118/124`、`n_cells=125`；`rep` `raw→raw` `53/53` `n_cells=45` 与 `inv` `raw→raw` `24/26` `n_cells=32`（这两件两版 `cells_sha256` **逐字节相同** ⇒ patch 零扰动）。**verdict（`d8_e2e_report.py --compare`，三项全 true）**：`section6_html_content_unchanged` / `section6_td_texts_unchanged` / `c8_cells_moved`；逐表 `cells_moved` = `bank` **True** · `pico` **True** · `rep`/`inv` **False**。**探针×产品交叉验证 4/4**（补跑的 `inv` 探针 `raw/24/26/32` 与产品同值；`pico` patch 侧 `118/124/125` 与 R6 探针同值；`R5` 官方侧 `bank`/`rep`/`pico p3` 亦逐项一致）。⇒ 上文「接线本身未经端到端验证」**就此关闭**，`cell_confidence` 的 Cloud 验收（本节 ⓪–③）**全部达成**。**遗留**：①原始 patch 文件 `scripts/measure/D8/d8_numpy_root_cause.patch` 已被「分支对齐」方案取代（云端旧 base 上叠加 patch 会错位，故改为 `git checkout origin/fix/d8-numpy-truth-value` 整体对齐）；②`_call_worker` 丢弃 worker 栈帧的日志改动**未落地**（`layout_service.py` 1614 行 = 棘轮上限，红线禁抬高），见上「修法」段。
- **教训登记**：端到端报 "worker error" 时须先分清栈帧起点是产品代码还是引擎——本轮因"`_parse_result` 在主进程"这一误判，把一次可静态定位的缺陷当成环境/版本不兼容（候选 a vs b 的消歧因此多花一整轮云跑）。

- **相关**：P-027 R3/R4（秤侧出处）· `docs/architecture/ocr-quality-harness.md` §4 钉死设计点 D8 · P-028（sanity 旗标可作辅助信号，本批不并入）

### P-033 · 测试夹具可复现哨兵：生成器 `--check` 进 CI（2026-10-08）
> status: landed · since: 2026-10-08
- **来源**：2026-10-08 夹具收敛批次（PR #74）实测——`generate_general_testfiles_pure.mjs` 与已提交样例**不幂等**：4 件因早于 ASCII-safe 修复（`b16c83a`）而文本层带 U+2014 三字节乱码（pdfplumber 读作 `(cid:226)(cid:128)(cid:148)`），1 件因列宽默认值变化重生成即并字（`Professional services4 0- Phase 1`），1 个 README 漂移。**漂移此前完全无机检**：只有人重跑才看得见——与 P-008「声明的东西是否真被接上」同类缺口。
- **机制**：生成器已具备 `--check`（不写、列出漂移件、有漂移 exit 1）与 `--only <文件名>`；本条目把它**接进 CI**——在既有的必需检查 `lint` job 内、Node 就绪后执行 `node test_data/scripts/generate_general_testfiles_pure.mjs --check`，非零退出即红（沿用 P-008/P-025 的"复用既有 required check"取向）。
- **落点**：`.github/workflows/lint.yml`（lint job 新步，置于 Node setup 之后、`npm ci` 之前 = 失败快、且该脚本零 npm 依赖；**红线文件，用户 2026-10-08 显式授权**）· `module-map.md` §5 登记 **E3** · `test_data/testfiles/README.md` R3 写明"CI 强制" · CHANGELOG。
- **判据**：`--check` 输出 `OK - no drift` 且 exit 0（收敛前实测 `6 drifted output(s)` 且 exit 1）。
- **能力边界（必须写明，否则方案变幻觉）**：本门禁只覆盖**该生成器**的三个输出（`GeneralFiles/`、`invoices/`、`images/kie/` 的新样例）；**不纳入**其他夹具生成器（如 `test_data/scripts/generate_kie_id_card_samples.py` 的 PIL 渲染件）与**图片类夹具**（JPEG/PNG 编码与元数据不可字节复现）——纳入前须先证明"内容指纹可复现"（口径参照 `test_data/scripts/verify_assets.py`）。local-only 面（`docs/R&D/**`、`scripts/measure/**`）不在视野。
- **触发条件**：改 `generate_general_testfiles_pure.mjs` 或 `test_data/testfiles/**` 样例时（本地先跑 `--check`，CI 兜底）；新增夹具生成器时按上条评估是否纳入。
- **相关**：PR #74（`--check`/`--only` 与收敛批次）· `test_data/testfiles/README.md` R1/R3 · P-008（"声明但未接线"形态）· P-025（门禁 + 检查点范式）。

### P-034 · KIE text-first 通道泛化到 coi（2026-10-09 立项；兑现原 P-030 `carrier` park 的真修）
> status: decided · since: 2026-10-09
- **来源**：原 P-030 的 parked follow-up（已随 P-030 升删，原文见 git `bdbe1ee`）——`carrier` 在承保人名（INSURER A–F）为空的样本上回落到评级样板句（tampa 实测 `A.M. Best B+ VII or Better Insurance Carrier`）；两版 prompt 调优（v1 负向词表 / v2 只取 INSURER A–F + 去重 + 全空）经 Cloud 双向复验**均未达标（tampa 均 ×5，已排除缓存）**，结论 =「纯 prompt 无法在**扁平化 ACORD 文本**上分离评级行/空标签 ⇒ 真修须在**输入层给 KIE 结构化区块文本**（另立项）」。**2026-10-09 Ying 裁决：泛化到 `coi`**。
- **技术底座（已存在，无需新造）**：P-032 M1/M2 的 text-first 通道（`backend/app/services/kie/text_first.py`，221 行）已把 PDF 原生文本层切块并加全局唯一标记 `[p{page}_b{block}]` 作为 KIE 输入；当前**仅 `pico` + PDF**。
- **唯一开关**：`text_first.py:44` 的 doc-type 判定 `!= "pico"` → 白名单 `{"pico", "coi"}`。KIE 侧（`backend/app/orchestration/document_pipeline_orchestrator.py:645`）与证据门侧（`backend/app/services/evidence/gate.py:397-411`）**都经同一个判定**，故**不得**在 orchestrator 另起分支；两侧漂移由 `backend/tests/evidence/test_evidence_text_first.py::test_d2_gate_text_first_scope_mirrors_m1` 守护（泛化须同步该文件的新增 coi 正向用例）。
- **无需新增 doc-type 登记**：coi 已在 `kie.md` §4.2 的**七处触面**全部在册（`KIE_SUPPORTED_DOC_TYPES` / `_registry.yaml` / `coi.yaml` / 前端 `KIE_DOC_TYPES` / index.html radio / `_KEYWORDS` / `_PRODUCTION_KEY_HINTS`），三向哨兵 `backend/tests/test_kie_domain_consistency.py` 为 7==7==7；本次只改**通道判定**，不动 doc-type 集合。
- **前置（不可跳过）**：①**阈值重校准**——`BODY_PAGE_MIN_TEXT_ELEMENTS = 8` / `BODY_PAGE_MIN_TEXT_CHARS = 500` 的模块 docstring 明写「calibrated on the 5 pico corpora」⇒ 必须在 ACORD/coi 语料上重校准，否则单页表单可能被 `select_body_pages` 判为非正文页而退回 legacy 图像通道；②**语料文本层盘点**——只有 `trusted_grounding_page_set` 放行的页才走 `text_layer`（`text_first.py:201-208`），须先确认 coi 夹具哪些为 born-digital（`coi_acord25_synth_green.pdf` 文本层含 EIN，可用；其余待查）。
- **prompt 重做（carrier 的真修所在）**：park 时两版 prompt 失败的前提是**扁平化文本**；text-first 换成**带块标记的分块文本**（不同基底），故 prompt 须在新基底上重新设计（让模型引用 `[pN_bM]` 标记而非裸值），**不得**沿用或微调 park 掉的旧改动（两版均未入库）。
- **same-source 契约（不得破坏）**：`build_text_first_payloads` 直接 import `evidence.grounding` 的 `grounding_source` / `trusted_grounding_page_set`（`text_first.py:196-202`），与证据门接地文本同源；泛化只改 doc-type 白名单，**该共享行不动**。
- **验收**：同一样本 `EVIDENCE_TEXT_FIRST` **on/off 双跑**，五字段逐一比对——`carrier` 不再回落样板句，且 `policy_type` / `eff_date` / `exp_date` / `limits` **不退化**。**必须实测的风险点**：text-first 分支**只发文本、不发图像**（`backend/app/services/kie/KieManager.py:158-178`），ACORD 的勾选框/评级行/limits 表是否依赖视觉信号须在该对照中证实或证伪。KIE 属 GPU 依赖 ⇒ 本机 mock 单测 + 交付文档写 Cloud 验证步骤与验收标准（**不宣称云端已验证**）。
  **Cloud 验证交付文档（B 项验收；2026-10-15 预登记 = 清「交付文档未写」欠债；**未实跑，不宣称云端已验证**）**：⓪**前置（两项未完成，①-④ 不得开跑）**——(a) **阈值重校准**：`text_first.py:27-28` 的 `BODY_PAGE_MIN_TEXT_ELEMENTS=8` / `BODY_PAGE_MIN_TEXT_CHARS=500`（docstring 自述 "calibrated on the 5 pico corpora"，`:12`）须在 ACORD/coi 语料重校准，判据 = 夹具逐页 `select_body_pages` 判定与文本层盘点一致（**无正文页被误判非正文而退回 legacy 图像通道**——单页表单是最可能踩中的形态）；(b) **coi born-digital 盘点**：逐夹具核 PDF 原生文本层与 `trusted_grounding_page_set` 放行集合（放行页为空 ⇒ 该夹具只能走 legacy，须如实登记、不得混入对照）；已知 `coi_acord25_synth_green.pdf` 文本层含 EIN 可用，其余待查。①**副本核验**：被测分支含白名单泛化（`text_first.py:44` `!= "pico"` → 白名单 `{"pico","coi"}`；KIE 侧与证据门侧同一判定，不得另起分支）+ 新基底 prompt；云端全量须含 `tests/evidence/test_evidence_text_first.py`（同步新增的 coi 正向用例）与 `tests/test_kie_domain_consistency.py`（7==7==7）通过。②**on/off 双跑**：同一样本（**必测 tampa** —— INSURER A–F 空样本）`DOCUVISION_EVIDENCE_TEXT_FIRST=on` 与 off 各跑一次 KIE（同输入文件、同版本、排除缓存）。③**判据（五字段逐一比对）**：`carrier` 不回落评级样板句（`A.M. Best …` 形态零出现）；`policy_type` / `eff_date` / `exp_date` / `limits` 不退化（on 相对 off 无字段丢失或降精度）。**风险实测义务**：text-first 只发文本不发图像——若 on 侧在勾选框/评级行/limits 表上退化，**如实登记"该字段依赖视觉信号"并回到设计复核，不硬凑通过**。④**回传**：两次任务的五字段 on/off 对照表（含 carrier 值是否引用 `[pN_bM]` 标记）+ 任务 result JSON 路径与关键服务日志。⑤**通过后动作**：读数与日期登记回本条、本条方可转 `landed`；不通过则在带块标记的新基底上迭代 prompt（**禁**沿用 park 掉的 v1/v2 旧改动——前提基底已不同）。
- **与 P-027 解耦**：本条属 **kie / evidence 域**（owning doc = `docs/architecture/kie.md` + `evidence-layer.md`），**不**计入 P-027 的在途义务，其落地不解锁 `docs/R&D/runs/P027/` 的删除条件。
- **相关**：P-032（text-first 通道出处）· `docs/architecture/kie.md`（§3 输入通道 / §4.2 七处触面 / §6 已知局限）· `docs/architecture/evidence-layer.md` · P-030（已删，载体结论在 `kie.md` §4/§4.2）
- **触发条件**：coi 域任何 carrier / 字段精度批次；改 `text_first.py` 的 doc-type 白名单或 `EVIDENCE_TEXT_FIRST` 语义时同查本条目。

- **`docs/R&D/runs/P027/` 保留理由（2026-10-07 登记）**：该目录 5 件（`R2-执行记录` · `R3-执行包` · `R3-执行记录` · `R4-执行包` · `R4-执行记录`）**尚不可删**——按 `docs/R&D/README.md` 的 runs 政策（"temporary, deletable once the project lands"，来源 commit `b3dcfa2`），删除前提是**本条 land**；现 status = `decided`，在途义务未清（R3 缺口 1 IE 语义层产品侧修复 / D8 Confidence 产品源 ——**两项已于 2026-10-09 立项，见本条「产品侧立项 A / D8」小节** / BR 葡语解锁触发 / 分岔 C 优先级重排 / R1 taxonomy 转用例）。三条引用使其成为不可断的判据出处：①CHANGELOG `[1.11.0]` P-027 R2/R3/R4 三段以 `runs/P027/R3-执行记录.md`、`R4-执行记录.md` 为 execution record；②本仓 P-002 条目（follow-up 触发证据段）把 IE-p079 判据指向「P-027 R4 执行记录 §4.1」；③R4 记录 §6「保留判据与明细」是隔离区 `test_data/derived/**` 证据链的唯一盘存表。**触发**：本条转 `landed`/`retained` 时，同批删除本目录并同步 `docs/R&D/README.md` 的 runs 索引（对照：P-030/P-031/P-032 的 local-only 执行包已按「提炼后删除」清理）。


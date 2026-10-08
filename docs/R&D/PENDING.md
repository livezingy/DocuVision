# 待决决策清单（PENDING）

> 每次会话开始时检查本文件——可见"有 N 条结论待确认"。
> 结论确认后：晋升 `docs/architecture/`，然后从本清单移除。

## 待确认（本区共 **14** 条）

- **机检索引（勿手改）**：`P-008` `P-011` `P-014` `P-015` `P-017` `P-018` `P-019` `P-020` `P-023` `P-024` `P-025` `P-026` `P-027` `P-033`
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

### P-033 · 测试夹具可复现哨兵：生成器 `--check` 进 CI（2026-10-08）
> status: landed · since: 2026-10-08
- **来源**：2026-10-08 夹具收敛批次（PR #74）实测——`generate_general_testfiles_pure.mjs` 与已提交样例**不幂等**：4 件因早于 ASCII-safe 修复（`b16c83a`）而文本层带 U+2014 三字节乱码（pdfplumber 读作 `(cid:226)(cid:128)(cid:148)`），1 件因列宽默认值变化重生成即并字（`Professional services4 0- Phase 1`），1 个 README 漂移。**漂移此前完全无机检**：只有人重跑才看得见——与 P-008「声明的东西是否真被接上」同类缺口。
- **机制**：生成器已具备 `--check`（不写、列出漂移件、有漂移 exit 1）与 `--only <文件名>`；本条目把它**接进 CI**——在既有的必需检查 `lint` job 内、Node 就绪后执行 `node test_data/scripts/generate_general_testfiles_pure.mjs --check`，非零退出即红（沿用 P-008/P-025 的"复用既有 required check"取向）。
- **落点**：`.github/workflows/lint.yml`（lint job 新步，置于 Node setup 之后、`npm ci` 之前 = 失败快、且该脚本零 npm 依赖；**红线文件，用户 2026-10-08 显式授权**）· `module-map.md` §5 登记 **E3** · `test_data/testfiles/README.md` R3 写明"CI 强制" · CHANGELOG。
- **判据**：`--check` 输出 `OK - no drift` 且 exit 0（收敛前实测 `6 drifted output(s)` 且 exit 1）。
- **能力边界（必须写明，否则方案变幻觉）**：本门禁只覆盖**该生成器**的三个输出（`GeneralFiles/`、`invoices/`、`images/kie/` 的新样例）；**不纳入**其他夹具生成器（如 `test_data/scripts/generate_kie_id_card_samples.py` 的 PIL 渲染件）与**图片类夹具**（JPEG/PNG 编码与元数据不可字节复现）——纳入前须先证明"内容指纹可复现"（口径参照 `test_data/scripts/verify_assets.py`）。local-only 面（`docs/R&D/**`、`scripts/measure/**`）不在视野。
- **触发条件**：改 `generate_general_testfiles_pure.mjs` 或 `test_data/testfiles/**` 样例时（本地先跑 `--check`，CI 兜底）；新增夹具生成器时按上条评估是否纳入。
- **相关**：PR #74（`--check`/`--only` 与收敛批次）· `test_data/testfiles/README.md` R1/R3 · P-008（"声明但未接线"形态）· P-025（门禁 + 检查点范式）。

- **`docs/R&D/runs/P027/` 保留理由（2026-10-07 登记）**：该目录 5 件（`R2-执行记录` · `R3-执行包` · `R3-执行记录` · `R4-执行包` · `R4-执行记录`）**尚不可删**——按 `docs/R&D/README.md` 的 runs 政策（"temporary, deletable once the project lands"，来源 commit `b3dcfa2`），删除前提是**本条 land**；现 status = `decided`，在途义务未清（R3 缺口 1 IE 语义层产品侧修复 / D8 Confidence 产品源 / BR 葡语解锁触发 / 分岔 C 优先级重排 / R1 taxonomy 转用例）。三条引用使其成为不可断的判据出处：①CHANGELOG `[1.11.0]` P-027 R2/R3/R4 三段以 `runs/P027/R3-执行记录.md`、`R4-执行记录.md` 为 execution record；②本仓 P-002 条目（follow-up 触发证据段）把 IE-p079 判据指向「P-027 R4 执行记录 §4.1」；③R4 记录 §6「保留判据与明细」是隔离区 `test_data/derived/**` 证据链的唯一盘存表。**触发**：本条转 `landed`/`retained` 时，同批删除本目录并同步 `docs/R&D/README.md` 的 runs 索引（对照：P-030/P-031/P-032 的 local-only 执行包已按「提炼后删除」清理）。


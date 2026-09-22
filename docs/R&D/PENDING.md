# 待决决策清单（PENDING）

> 每次会话开始时检查本文件——可见"有 N 条结论待确认"。
> 结论确认后：晋升 `docs/architecture/`，然后从本清单移除。

## 待确认（4 组；P-007 / P-008 / P-010 / P-011 / P-013 / P-014 / P-015 / P-016 / P-019 已结保留记录，P-012 已结并晋升 `docs/architecture/v1.7-roadmap.md`；
P-001 已按用户裁决移除 2026-09-20，后续有需要再立项）

### P-002 · 表格逐格对齐的文本优先重构（v1.9 候选，2026-09-13）
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

### P-006 · `.zcode` 目录跟踪策略（2026-09-15）
- 结论（已定）：`.zcode/` **纳入版本控制**（后续会有内容、可能值得提交），但 `.zcode/plans/` **不推远端**。
- 已落地：`.gitignore` 新增 `.zcode/plans/`（与 `.codebuddy/plans/` 同款规则形制）。
  实测验证：`.zcode/plans/` 下的 plan 文件命中忽略（`.gitignore:168`）；`.zcode/` 下新建普通文件显示为未跟踪且
  `git add --dry-run` 成功 → **`.zcode` 其余内容将来可直接提交**。
- 本次未提交 `.zcode` 本身（故留 PENDING）：忽略 `plans/` 后**目录为空**，git 不跟踪空目录
  （当前 `plans/` 是其唯一内容）。
- 待办（无需额外动作）：`.zcode` 出现首个非 plans 内容时，随该次改动一并 `git add .zcode/`。
- 先例：`.codebuddy/` 同款——`rules/` 5 个文件已跟踪、`plans/` 被忽略（`.gitignore:165`）。

### P-007 · 非 KIE 任务的 Processing Results 仍显示 KIE 元信息（2026-09-16，FRONT-C1 走查发现）
- 现象：跑完一次 invoice（KIE）任务后，Processing Results 出现 KIE 行；之后跑 **layout 任务**（无 KIE）
  该行**仍在**，值为 `KIE confidence: 0% · KIE fields: 0`，同面板还有 `Tables: 16 · Backfill: 89/588 (15%)`
  与 `⚠ kie_production: empty_fields`。
- **判定：既有行为，非 v1.8.3 回归**——前端 `renderQualityPanelPro` 与 v1.8.2 的 `app.js` **逐行等价**
  （59 行，唯一差异是 `export` 前缀；2026-09-16 脚本比对确认）。
- 根因（两层）：
  1. 后端 `app/models/api_models.py:136-144` 把 `kie_fields_count` / `kie_confidence_avg` /
     `kie_production_hit` / `kie_production_reason` 的默认值定义为 `0` / `0.0` / `False` / `""` ——
     **未跑 KIE 的任务照样带这些零值**（不是 `null`/缺省）；`kie_production_reason` 由
     `document_pipeline_orchestrator.py:1052/1062` 的 `evaluate_kie_production_hit` 写入。
  2. 前端 `modules/result-panels/quality.js` 的显示条件是「面板显示 = `kieAttempted || hasBackfill`，
     KIE 行显示 = `kie_confidence_avg != null`」——layout 任务有 backfill（Tables 16）→ 面板正常显示
     → KIE 行因默认值 `0.0` 而非 null 被一并显示。
- 修复方向（二选一，未做）：
  - **A 后端**：这些字段改 `Optional[...] = None`，前端 `!= null` 判断天然生效（零前端改动）；
    代价 = 动契约（OpenAPI 快照 / `batch_export_service` CSV 列 / KIE 契约测试需同步）。
  - **B 前端**：KIE 行显示条件从 `!= null` 收紧为 `kieAttempted`（或 `kie_stage` 非空）；
    纯前端、风险小，但属行为变更，需补 vitest/e2e 覆盖。
- 触发：并入 v1.9；若客户对结果面板"零值误导"有感知则提前。
- **状态（2026-09-20，用户裁决：方案 B，已立项 v1.9）**：判据**分两段**（2026-09-20 读码审核修正）——
  summary 行（`KIE confidence` / `KIE fields`）用 `quality.kie_confidence_source != ""` gate
  （`document_pipeline_orchestrator.py:1077-1080` 保证只在 `attempted && succeeded` 时非空；
  **不能只按 `kieAttempted`**：`skipped_doc_type` / `service_unavailable` / `runtime_error` 等失败路径
  同为 `attempted=True`（`:537/571/597/724`），只按它 gate 会留下失败态 "0%" 误显，P-007 修一半）；
  KIE 警告块按 `kieAttempted` gate。纯前端、不动 OpenAPI 契约；vitest **4 态** + e2e 1 例
  （需先扩 `mock-pro-api.js` 的 quality preset——现有 mock 使 quality 面板永远走隐藏路径）。
  范围与验收口径见 `docs/architecture/v1.9-roadmap.md` §Scope S1。
  **✅ 已结（2026-09-20）**：v1.9 S1 落地（commit `b571d21`）——`renderQualityPanelPro` 的 summary 行改按
  `kie_confidence_source` gate、警告块按 `kieAttempted` gate；覆盖同批补齐（vitest 4 态、e2e 1 例，
  并把 e2e mock 的 quality 换成真实后端形态 + `qualityPreset`）。证据：vitest 67/67、e2e 15/15 且
  `0 runtime error`、F1-F7 / C1-C9 / E1 / audit 全绿；scope 与验收口径保留在 roadmap §S1（本组按规则移除）。

### P-008 · v1.9 候选：孤儿模块与悬空测试的巡检门禁（2026-09-16，FRONT-C1 走查衍生）
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
  浏览器缓存已写入）；④ e2e / vitest **仍未进 required checks**，protected 分支策略是独立决策。

### P-010 · 前端风格 linter 缺位（2026-09-17，P-004 收尾时登记）
- 现状：`DEVELOPMENT.md` 第 4-6 条与 kernel `frontend.md` 只覆盖**结构与边界**（F1-F6 / C1-C8），
  无代码风格检查；后端至少有 `ruff check backend/ packages/docuvision-core/ --select F401,F841`（kernel `testing.md` §死代码检查）。
- 缺口：`frontend/modules/**` + `shared/**` 的**死代码 / 未用变量 / 未用导出**无任何机检，只能靠人读——
  P-008 的孤儿模块 `floating-progress.js`（D11）正是这类缺口的表现。
- 不做的理由（决定维持）：引入 ESLint/Prettier 会一次性报出大量既有问题（33 个模块 + shared + tests），
  必须单独立项：① 只开 high-value 规则（`no-unused-vars` / `no-undef` / import 相关），
  ② 分批清账到零，③ 最后才进 CI。
- 触发：v1.9；或前端出现一次"死代码 / 未用导出"类事故时提前。
- 相关：P-008（孤儿模块与悬空测试的巡检门禁）。
- **状态（2026-09-17，阶段 1 已落地）**：`frontend/eslint.config.mjs`（flat config；只开
  `no-unused-vars`（`args:"none"`）+ `no-undef`；browser globals + 4 个**真实**跨脚本全局
  `DocuVisionExport` / `DocuVisionDemo` / `DocuVisionUiFeatures` / `katex`；作用域 = `app.js` +
  `modules/**` + `shared/**`，`frontend/tests/**` 留第二批）+ `package.json` 的 `"lint": "eslint ."`。
  首轮 **76 项**（其中 49 项在 app.js：v1.8.3 拆分后遗留的**死 import**）已清账到 **1 项**；
  唯一剩余项是 P-014 的**真实缺陷**，已于同日 follow-up 按选项 ②′ 解决 →
  **`npm run lint` 现为 0 error（首次清零）**。
  **阶段 3（接 CI）已落地（2026-09-17，用户授权）**：`.github/workflows/lint.yml` 追加 `actions/setup-node@v4`
  （node `"22"`；eslint 10.10.0 的 `engines.node` = `^20.19.0 || ^22.13.0 || >=24`）+ `npm ci`（`working-directory: frontend`，
  lockfile 已跟踪）+ `npm run lint`，且置于四个 stdlib 门禁**之后**（stdlib 先失败就不必装 node）。
  `frontend/**` 本就在 lint.yml 的 paths 内 → **未改触发路径**。作用域仍为第一批：`frontend/tests/**` 未纳入（第二批）。
  **成本口径已落档**（2026-09-17）：ESLint 块是本仓唯一的 node 依赖面，其"配额"效应只在**仓库转私有**
  （或迁到带配额 CI）时才成立——公开仓分钟数免费。触发即重算的口径、各 workflow 实测时长（Audit 11-12s /
  Lint **19s**，其中 ESLint 块 +6s：`setup-node` 1s + `npm ci` 4s【冷缓存】+ `eslint .` 1s / Phase A 21-27s）
  与"转私有后的取舍顺序"写在
  `docs/agent-ops/operations.md` §CI 成本与配额；`lint.yml` 头部注释指向该节。
  **✅ 已结（2026-09-20，第二批落地）**：`frontend/tests/**` 纳入 ESLint（flat config 两个 scoped override：
  `tests/unit/**` = ESM + browser globals（jsdom）；`tests/e2e/**` = CommonJS + node globals（Playwright）；
  规则同第一批）。首扫仅 **5 项**：1 项真死绑定（`coverage-report.js` 解构 `loaded` 未用）+ 4 项
  `coverage.js` 混合环境（Node 文件内含 `page.addInitScript` 注入的浏览器代码）→ 以文件级
  `/* global window, document */` 精确声明而非全局放宽。`npm run lint` 0 error，vitest 67/67、
  e2e 15/15 回归绿。第一批 + 第二批全部落地，**本组关闭**；"格式化器（Prettier 类）"不在本组范围，
  若有诉求属新立项（全量重排与 F1/C1 行数棘轮冲突，需先裁决）。
  **触发**：仓库转私有、或 `main` 开 branch protection 时，按该节的 ①→③ 顺序重算并收窄 `paths`。
  回归证据：vitest **80/80**、e2e **14/14** 全绿；`frontend/app.js` 211 → **172** 行（棘轮已两次下调）。
  3 个结构性测试的断言从"app.js import X"改为"X 被某消费者 import"——旧断言钉的正是这批**死 import**，
  详见 `frontend/tests/unit/_sources.js` 头注。

### P-011 · CI 触发分支仍只覆盖 main（2026-09-17，P-004 收尾时登记）
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

### P-013 · 服务层模块的 owning doc 未核实（2026-09-17，doc-sync 归属表补全时登记）
- 背景：补全 kernel `doc-sync.md` 机制 2 归属表时逐模块核实 owning doc。有把握的行已写入
  `docs/agent-ops/doc-sync-ownership.md`；以下模块**只出现在 frozen release 文档或测试清单里**，
  没有稳定的 living owning doc，故**只留 TODO、不猜**（P-012 教训）：
  `backend/app/services/` 的 `batch_service`、`batch_export_service`、`hitl_policy`、`hitl_queue`、
  `webhook_service`、`document_info_utils`、`document_profile`、`document_type_classifier`、
  `file_type_detector`、`kie_fields_update`、`formula_service`、`seal_service`、`page_type_probe`、
  `pdf_raster`、`pdf_tools_service`、`pymupdf_table_engine`、`single_file_pipeline`、
  `unified_layout_service`、`_layout_order`；`backend/app/core/` 的 `aistudio_compat`、`debug_utils`、
  `gpu_lib_path`、`trial_auth`；`backend/app/models/` 的 `analyze_options`、`layout_result`。
- **状态（2026-09-17 用户裁决选项 C 并执行完毕，本组可结）**：对上述 25 个模块做**双重**扫描（模块/文件名 +
  派生类名）比对 living 文档集 → **2 个有载体**（`batch_service.py` / `hitl_queue.py` → `v1.5-roadmap.md`，
  已补入主表）、**23 个无常驻 living 契约**（在附表脚注 2 **显式列出**，不再"留空让人猜"）。
  判定规则与 5 条"仅被提及不计载体"的线索一并写入脚注；触发条件改为常驻条款：
  **任一模块发生契约变更时先定归属再改**。
- 结论固化位置：`docs/agent-ops/doc-sync-ownership.md`（主表 + 脚注 2）——该表本身即机制 2 的结论载体，
  故不另晋升 `docs/architecture/`。
- 相关：`docs/agent-ops/doc-sync-ownership.md` 脚注 2；kernel `core/doc-sync.md` 机制 2。

### P-014 · `shell/tools.js` 的 `startProcessing` 未绑定 + P-010 清账未清零（2026-09-17）✅ 已结（按 ②′ 整体退役）
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

### P-016 · `onload="adjustDocumentSize()"` 内联处理器 ReferenceError（2026-09-17，覆盖度报告首跑发现）
- 现象：每次预览图加载都抛 `ReferenceError: adjustDocumentSize is not defined`——8 个 e2e 用例各命中一次。
  证据：`test_data/TestResult/PhaseUI/coverage-2026-09-17.md` §4（由 P-008 gap 2 的运行时覆盖度报告产出，
  非人工观察）。
- 根因：`frontend/modules/preview-paging/nav.js:108`、`render.js:87` 与 `render.js:103` 在**模板字符串**里拼出
  `<img id="documentImage" ... onload="adjustDocumentSize()">`。**内联事件处理器在全局作用域求值**，而
  `adjustDocumentSize` 是模块内绑定（`preview-paging/core.js` 导出；`overlay-render.js` 经 `deps` 注入）→
  全局查不到 → 必抛。全仓该模式共 **3 处**，均在 D5 预览域。
- 为什么此前所有门禁都看不见（这条比缺陷本身更值钱）：ESLint `no-undef` **只分析代码、不分析字符串**
  （引用在模板字面量里）；C9 只比对 `deps.*` 键集合；F6/F7/C1-C9 全是结构性；e2e 只断言 UI 行为、
  **不断言"无 pageerror"** → 于是 14/14 全绿同时带着这个错误。
- 影响面（需实测确认，不过度断言）：同一路径另有模块作用域的 `setTimeout(() => adjustDocumentSize(), 100)`
  兜底（`nav.js:112` / `render.js:93,109`），故**当前未观察到用户可见故障**；但每次预览都污染控制台/错误上报，
  且"依赖兜底恰好存在"很脆。与 P-014 同类：错误真实，影响面由实测决定。
- 候选修法（三选一，均属前端行为/结构变更，**需单独 commit**）：
  ① 模板改为 `data-*` + `addEventListener('load', …)`（根治，顺带清掉内联 handler）；
  ② 在模块内 `el.onload = adjustDocumentSize`（需先拿到元素，改动最小）；
  ③ 保留内联写法但显式 `window.adjustDocumentSize = …`——**不推荐**，新增全局桥，违反 L3 / DEVELOPMENT.md 第 6 条。
- 可复用结论：**内联事件处理器是 `no-undef` 的结构性盲区**。修 ① 时可考虑同时补一条 lint
  （模板里出现 `on\w+="` 即报）或写进 kernel `frontend.md` 的已知 gap。
- 触发：v1.9 前端批次；或任何一次要动 D5 预览渲染的改动（届时一并处理）。
- 相关：P-008 gap 2（发现它的报告）、P-014（同类"错误真实但影响面待实测"）、P-010。
- **状态（2026-09-17 用户裁决"根治方案"= 选项 ①，已修完，本组可结）**：三处模板的内联 handler 全部换成
  模块内的真实监听器——新增 `core.js::bindDocumentImageLoad(onError?)`（`addEventListener('load', …)`；
  `onerror` 仅在 render.js 传回调；`image.complete` 时立即补一次调用以覆盖**缓存命中不触发 load** 的情形），
  `nav.js:108` / `render.js:87,103` 的 `onload=` `onerror=` 属性删除，改为插入 HTML 后调用；
  render.js 的失败 UI 提为模块内函数 `showPreviewImageFailed()`（不再依赖 `this.parentElement` 字符串转义）。
  `frontend_domain_map.json` 的 D5 函数清单同 commit 登记新函数。
  **证据**：① 全仓 `on(load|error|click|…)=` 内联 handler 计数 **3 → 0**（唯一残留是 core.js 里说明本修复的注释）；
  ② 覆盖度报告 `0 runtime error(s)`（修复前 8 条），"注册了但从未触发"由 5 → 4（`preview-paging/core.js` 的
  load 监听器现在真的触发了 —— 修复顺带改善了覆盖信号）；③ e2e **14/14**（11.4s）、vitest **80/80**、
  `npm run lint` 0、F1-F7 / C1-C9 / audit 全绿。
  **未做（可选）**：给"模板里出现内联 handler"加一条机检（本轮是 3 处、已清零，属预防性）；
  可复用结论"内联 handler 在全局作用域求值、是 `no-undef` 的结构性盲区"已写进 kernel `frontend.md` 的已知 gap。

### P-017 · F1 500 行预算是否调整（按域差异化预算 vs 上调预算）（2026-09-20，v1.9 S2-5 暴露）
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
- **状态（2026-09-22）**：立项登记已落地并推送（commit `cd86632`，docs-only）；执行包
  `docs/R&D/P018-GT工厂-立项条目.md` 已在落地后删除（local-only，内容已由本条承载）。
  **P0 评测 harness 与 P1 弱 GT 合成尚未开工**——按本条护栏，实现属独立后续批次（各自立项、各自验收），
  本条目只登记决策与边界，不含任何 `scripts/` / `backend/` 代码。

### P-019 · module-map §6 A3 行数字副本漂移 → 单源化（2026-09-18 登记，同日裁决，09-21 重编号落地，已结保留记录）
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
- **状态（2026-09-22）**：已落地并推送（commit `74270f0`）；执行包
  `docs/R&D/P019-modulemap-A3漂移-执行包.md` 已在落地后删除（local-only，内容已由本条承载）。
  **据实记录两处与原执行包的偏差**：
  ① **提交形态**：原护栏要求「修复本体 / 登记记录」两个 commit 分离；本轮用户裁决改为压平——本议题
  **1 个 commit**，连同 P-018 登记共 **2 个 commit**（`cd86632` + `74270f0`）推送。
  ② **CI 机制描述已过时**：本条证据行的「`agent-ops-audit` 会因 `docs/architecture/**` 路径自动复跑」
  已不再准确——`agent-ops-audit.yml` 的 `pull_request.paths` 已于 2026-09-20（P-011 / branch protection）
  **移除**，audit 现对**每个 PR 必跑**、与是否触及 `docs/architecture/**` 无关（见该 workflow 头部注释）；
  结论（CI 会复跑）不变，机制口径以 workflow 为准。

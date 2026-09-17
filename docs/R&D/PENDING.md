# 待决决策清单（PENDING）

> 每次会话开始时检查本文件——可见"有 N 条结论待确认"。
> 结论确认后：晋升 `docs/architecture/`，然后从本清单移除。

## 待确认（7 组；P-013 / P-014 / P-015 已结保留记录，P-012 已结并晋升 `docs/architecture/v1.7-roadmap.md`）

### P-001 · Upwork 切片与改造建议（2026-08-31）
- 来源：2026-08-31 会话（Upwork 切片与改造建议，口头交付）
- 状态：已口头交付，未落文档 / 未改代码，等用户确认方向
- 待决项：
  1. **SDK 门面按交付物切**：`extract_tables()` / `extract_fields()` / `to_excel()` / `review_report()`，推翻 8/23 引擎式 4 函数（`ocr()`/`extract_layout()` 降为内部能力）。
  2. **存疑标记落到交付文件**（Excel `⚠` 列 / review.csv），非 Web UI 的 HITL 队列。
  3. **反对 P0-1 可搜索 PDF 最高优先级**；真正 P0 = alias JSON 化 + 存疑标记 + 合并 sheet。
  4. **P2-1 Mail bridge 不建**（n8n / Power Automate 足够）。
  5. **前端 SPA 冻结不删除**；formula_service / seal_service 冻结。
- 确认动作：确认后写 `docs/architecture/` 或更新 `MEMORY.md`，并从此清单移除。
- **进展（2026-09-12，v1.8.1 C6 登记；决策项仍待确认，不移除本组）**：第 2 条「存疑标记落到交付文件」
  已由 v1.8.1 Proof Pack 实质兑现——HTML 报告 review_list（≤50 条 OCR vs 文本层对照）+
  annotated.pdf 红虚线格 + report.json 机读版，即「Excel `⚠` 列 / review.csv」思路在 PDF/HTML
  交付形态上的落地；第 3 条「真正 P0」相应部分兑现。第 1（SDK 门面）/4（Mail bridge）/5（SPA 冻结）
  仍待决。证据：分支 `feature/v1.8.1`（420a142..df21015）；gig 话术映射
  `docs/R&D/upwork/Proof-Pack-gig话术模板-v1.8.1-2026-09.md`。

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
  **遗留 gap（保留在本组）**：F6 仍是名字级弱断言；F7 只判可达性、不判接线——两个已登记孤儿尚未接线/退役。
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
  **仍未决**：候选 B 的运行时覆盖度报告形态（报告类型 / 存放位置 / 查看频率）——已给出形态示例，待确认后再实施。

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
- **仍未覆盖（判定规则：改动这里能否翻转 audit 的判决？逐项过）**，待下一轮裁决：
  `.github/workflows/kie-phase-a.yml`（check 4 解析它）、`scripts/test_registry_audit.py`（check 4 的实现体）、
  `scripts/frontend_coupling.py`（2026-09-17 起 audit check 3 经它读 A6 事实）、§5 门禁表引用的
  `scripts/lint_file_size.py` / `lint_routes.py` / `lint_frontend.py` / `check_frontend_baseline.py`（A0 查其符号
  是否存在）、`CHANGELOG.md`（A5 新鲜度输入）。
  两条路线：**逐条精确补**（清单会长、且会漂——本轮就漂了一次）vs **粗粒度** `scripts/**` + `CHANGELOG.md`
  + `kie-phase-a.yml`（代价≈每次脚本改动多跑一次 11s 的 audit）。
  可选治本：让 audit 自检"我的输入 ⊆ workflow 的 paths"（只读解析 workflow，不写），把漂移变红灯——需单独授权。

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

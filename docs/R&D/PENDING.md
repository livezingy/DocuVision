# 待决决策清单（PENDING）

> 每次会话开始时检查本文件——可见"有 N 条结论待确认"。
> 结论确认后：晋升 `docs/architecture/`，然后从本清单移除。

## 待确认（6 组）

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

### P-009 · `docs/release/README.md` 版本索引落后 4 版（2026-09-16，v1.8.3 发版时发现）
- 现状：索引表最新一行是 **v1.6.0**；`v1.7.0` / `v1.8.0` / `v1.8.1.0` / `v1.8.2.0` 四个 tag 均未登记，
  且 `RELEASE_1.7_NOTES.md` 及之后**都不存在**——v1.7 起实际简化了 NOTES/CHECKLIST 流程。
- 影响：低。发版信息由 `CHANGELOG.md` 承载（每版都有段），索引表只是导航层；但从 `docs/release/README.md`
  进入的读者会以为项目停在 v1.6.0。
- 待决（二选一）：
  ① 补齐 v1.7 → v1.8.3 五行（并决定是否恢复 NOTES 文件）；
  ② **承认流程已简化**：把索引表的 Notes/Checklist 列改为"见 CHANGELOG 对应段"，删除失效引用。
  ② 更符合近四版的实际做法（都没写 NOTES）。
- 触发：下一次发版前，或并入 v1.9 的文档整理。

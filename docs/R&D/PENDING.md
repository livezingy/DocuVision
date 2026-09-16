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

### P-004 · 新建 `docs/architecture/module-map.md`（当前态模块地图）（2026-09-15）
- 目的：补齐「架构与运作模式」层——单一权威入口，回答 main 上的**模块边界 / 依赖方向 / 不变量门禁**。
- 现状缺口：`docuvision-system-design.md` 是"语义/契约"向（引擎选型/坐标/三层数据结构/API 语义），`最近对照` 已落后 2 版；
  `docs/architecture/` 无任何文档回答"模块怎么摆、依赖往哪走"。
- 时机：**v1.8.3 之后**——前端段会被 v1.8.3 整体改写（`app.js` → `modules/` 15 域），先写即作废；
  届时前端证据**直接取自 v1.8.3 自己的 `domain-map.md`**（145 函数 × 15 域已扫完），无需重扫。
- 触发条件（提前）：若 v1.8.3 延期 >1 个月，则先落地后端段填补空缺。
- 交付物：`docs/architecture/module-map.md`（后端段 + 前端段 + 不变量门禁表，头部带"最近对照"）
  + 对账体检（并入 `scripts/audit_agent_ops.py`：校验 map 内路径/脚本真实存在）+ `docs/README.md` 索引一行。
- 前置已就绪：v1.8.2 后端段证据（`routers/` 13 域 / `core/runtime.py` / `models/api_models.py` / 双 lint 脚本 / 三条静态测试）。

### P-005 · v1.8.3 FRONT-C1 云端走查待执行（2026-09-15）
- 状态：**B0-B5b 全部落地并提交**（B5a `f024183` / B5b `71f228e`）；**FRONT-C1 是 v1.8.3 唯一未执行项**（设计稿 §7-FRONT-C1，属 U4 验收）。
- 待执行（一次云会话办三件事）：
  1. **FRONT-C1 走查**——Cloud Studio StaticFiles 下 ≥10 分钟人工交互（上传→分析→预览翻页→叠加层→导出 CSV/MD→批量→HITL resolve→trial key 拒绝→公式渲染），
     DevTools Network 确认模块文件全 200 + JS MIME、无 404；
  2. **缓存重验证实测**（D9 落地判据，**唯一部署层硬依赖**）——对 `frontend/**` 下发 `Cache-Control: no-cache` 或强 ETag，
     然后「改模块 → 重新部署 → 普通刷新仍拿到新文件」三测；
  3. **并入 v1.8.2 SPLIT-C1 复核**（快照零 diff + 路由冻结 + lint 双绿）**+ P-003① SPLIT-U4**（`DOCUVISION_CLOUD_TESTS=1`）。
- 执行清单（local-only，含 PowerShell/curl 命令、判定表、排查点）：`docs/R&D/PLAN/v1.8.3-frontend-split/FRONT-C1-checklist.md`。
- 本地已完成的等价部分：38/38 资产 200 + JS MIME、e2e 14/14、lint F1-F6 / C1-C8、`--syntax` 34/34（含 app.js）。
- 冻结触发：若第 2 项「缓存重验证」失败（普通刷新拿到旧模块），**v1.8.3 不可发布**——需先在部署层修缓存策略。
- 收口审计发现（既有状态，非本版回归；已写入清单附录 A）：`modules/floating-progress.js`（D11）是**唯一孤儿模块**——
  v1.8.2 起 `showFloatingProgressCard` / `updateFloatingProgress` 就无外部调用者（`index.html` 有其 DOM 无 JS 驱动），
  走查时「浮卡不出现」不算缺陷；接线属行为变更（v1.9 候选）。

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

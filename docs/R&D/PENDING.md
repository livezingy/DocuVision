# 待决决策清单（PENDING）

> 每次会话开始时检查本文件——可见"有 N 条结论待确认"。
> 结论确认后：晋升 `docs/architecture/`，然后从本清单移除。

## 待确认（2 组）

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

# 表格回填与 Provenance Review 机制（技术参考）

> 状态：§1-§3 为 v1.8/v1.8.1 **已实现行为**（分支 `feature/v1.8.1`，c37e35c）；§4-§5 为 **v1.9 提案**（PENDING P-002，未实现）。
> 代码归属：`backend/app/services/table_backfill.py`（漏斗）、`page_text_trust.py`（页信任）、
> `proof_render.py` / `proof_report.py` / `proof_pack.py`（证明包）。
> 设计稿：`docs/R&D/PLAN/v1.8.1-proof-pack-design.md`（本地规划区）。

## 1. Review 覆盖范围（现有行为）

Review（即报告的 review list 与逐格 provenance 标注）是三重窄域的交集：

| 维度 | 范围 | 裁决位置 |
|---|---|---|
| 内容域 | 仅 `result["tables"]` 中的**表格** | orchestrator `table_step` |
| 格子域 | 仅**候选格**：数字/金额（含千分位、货币符）、日期、含数字编码、固定符号集（✓⊗●○）；≤40 字符 | `table_backfill.is_candidate_cell` |
| 页面域 | 仅**文本层可信页**：`invisible_ratio < 0.2` 且 `image_coverage < 0.5`；`overlay`（扫描件 OCR 叠加层）/ `no_text` / `mixed` 一律拒收 | `page_text_trust.judge_page_trust` |
| 坐标域 | 仅**原始坐标空间**：`angle_deg == 0` 且非 doc-unwarping（deskew/unwarp 页的表 bbox 与 PDF 文本层不可靠对齐） | v1.8.1 门禁（D10） |

**明确不覆盖**：表格外内容（段落/标题/公式/印章）、表格内散文格（非候选）、KIE 结构化字段、
扫描件（无原生文本层，"overlay 文本层"是 OCR 产物，采信即循环验证）、多行单元格（几何包含的
单行要求，v1.9 处理）。

**页面级 vs 内容级**：`quality.table_backfill.page_verdicts`（text_layer/overlay/mixed/no_text）
是页面级判定分布；review list 是格级条目。两者不互相替代。

## 2. 判定流水线（现有规则）

```
table_step（orchestrator）
  ├─ enabled 门禁：table_text_backfill == "auto"（API 仅收 off|auto）
  │   × settings.TABLE_TEXT_BACKFILL kill switch
  ├─ 表提取：SLANeXt 结构 + PaddleOCR 文字 → tables[]（data/bbox/html）
  └─ backfill_tables() 漏斗（CPU-only，失败不致命）：
       1. 页信任 gatekeeper（per 表所在页）
       2. 候选筛选 is_candidate_cell
       3. 几何包含三关（derive_cell_bbox 均匀网格推导格子框）：
            a. 框内有词（词中心落框）
            b. 词完整含于框（任一词跨界 → 失败）
            c. 框内词恰好一行（多行/零行 → 失败）
       4. 内容比对 normalize_for_compare（NFKC + 空白 + 标点折叠）：
            一致 → text_confirmed（绿）
            不一致 → text_backfilled（琥珀，data 改为文本层值）
            三关任败 → text_mismatch（红，text_layer_text=""）
       5. 匹配词并集 bbox 持久化（cell_word_bbox，pt 空间）——仅绿/琥珀格
```

**契约产物**：
- 表级：`cell_provenance`（标签矩阵）、`cell_ocr_text`（回填格 OCR 原文）、
  `cell_word_bbox`（绿/琥珀格的印刷字符外接框，v1.8.1）
- 质量级：`quality.table_backfill`：`enabled` / `pages_judged` / `pages_text_layer_trusted` /
  `pages_skipped_preprocessed` / `cells_candidates|confirmed|backfilled|mismatch` /
  `backfill_rate` / `mismatch_rate` / `mismatch_details[]`（封顶 50）/
  `mismatch_details_truncated` / `page_verdicts[]`

## 3. 标注绘制规则（v1.8.1，proof_render）

- **绿框 / 琥珀框**：锚定 `cell_word_bbox`（匹配词并集外接框 = 印刷字符的精确范围，pt 空间
  直接绘制，无 px/pt 转换）——由构造保证精确；旧结果文件无该键时回退均匀网格框。
- **红格：不画**。红 = 对齐失败 = 无匹配几何，任何框都是均匀网格近似而非证据；红明细保留在
  报告 review list（≤50 条）与 report.json。
- **蓝框（表）/灰框（图）**：边界指示，无 provenance 语义；蓝框来自视觉表 bbox÷2，属近似，
  报告已披露。
- **跳过**：文档级 `preprocessed`/`deskewed`（整文档不画）、页级 `rotation`/`geometry`
  （view 尺寸可校验且偏差 >2% 时）。
- 页脚图例：`Proof: green=verified, amber=corrected; review items in report.html`。

## 4. Sanity 规则（v1.9 提案——防错值注入）

### 4.1 动机：几何包含存在一条错值注入路径

几何包含决定"哪些文本层词被绑定到这个格子"，但它无法区分**本格真值**与**邻居值**：
非等宽表上，某格的推导框可能**完整装下隔壁列的一个短值**（单词、单行、不跨界——三关全过），
内容比对发现 OCR 值 ≠ 框内值 → 回填成邻居的值 = **静默数据损坏**。
现有防护（候选正则、单行、全含）是一阶必要条件，不充分。

### 4.2 规则规格

回填（值替换）执行前，要求 OCR 值 `a` 与文本层值 `b`（均先经 `normalize_for_compare`）
满足 **OCR 混淆形态** `is_ocr_confusion(a, b)`：

1. **长度约束**：归一化后长度相等，或差 1（允许 OCR 字符粘连/断裂，如 `l1` ↔ `11`）；
2. **逐位混淆集**：位置对齐后，相同字符通过；不同字符必须命中双向混淆集——
   `0↔O/o`、`1↔l/I/i`、`5↔S/s`、`8↔B`、`6↔b/G`、`9↔g/q`、`2↔Z/z`、`✓↔√`、`●↔•`、`×↔x`；
3. **替换位数上限**：`len ≤ 6` 允许 1 位；`len > 6` 允许 2 位。

**裁决**：满足 → 正常回填（琥珀）；不满足 → `text_mismatch`（红，入 review list，data 不动）。

### 4.3 效果与诚实边界

- **拦截的**：典型邻居值抽取——如 OCR `12,900.00` vs 邻居 `-250.00`（归一化 `1290000` vs
  `25000`，长度差 2 → 拒绝）、`3480.25` vs `12500`（长度差 + 非混淆位 → 拒绝）。
  失败模式从"静默错值"降级为"可复核红旗"。
- **拦不住的**：邻居值与 OCR 值恰好呈单字符混淆（如 `1284` vs `1281`）的极小概率情形——
  sanity 是强过滤器，不是等值证明；残余风险由 review list 兜底（该格出现在报告里可复核）。
- **绿格的对称限制**：错误对应若恰好内容一致（邻居值 == OCR 值），会标绿但标注位置错——
  数据无损、证据有偏；该情形只能靠 v1.9 tier-3 的位置语义消除，sanity 管不了。
- **实现位置**：`backfill_table_cells` 的 backfilled 分支前置判断；~20 行 + 单测；
  属漏斗行为变更 → BACKFILL-001 云端重验。

## 5. v1.9 三层对应机制（提案，PENDING P-002）

对应机制决定"哪个文本层词属于哪个格子"，当前仅有 tier-2。提案按精度降级：

1. **值匹配**：表 bbox 邻域的文本层词中找与 OCR 值归一化相等的词（治"准确的数字被标红"；
   天然过 sanity）；
2. **几何包含**：现状三关，值匹配不唯一（同值碰撞）时降级使用；
3. **文本聚类映射**：表 bbox 内按基线 y 聚行、x 投影分列，把 vision 网格索引映射到真实
   印刷行列（处理非等宽列、多行单元格、同值碰撞的位置消歧）。

配套：对齐记录与 `mismatch_details` 增加 `reason` 字段
（`value_match` / `geometric` / `no_aligned_line` / `crossing` / `multi_line` / `shape_mismatch`）。
**边界原则**：文本层管真值与对应，vision 结构管语义（行列含义、合并格）；扫描件无文本层，
本机制整体不适用，其信任叙事走引擎级指标（symbol_benchmark 等），两条叙事不混。

**触发与验收**：真实客户文档（trial 3-5 单）证明需要逐格标注或出现误报时立项（P-002）；
立项即需 BACKFILL-001 云端重验（行为变更）。

## 6. 证据产物速查

| 层 | 产物 | 消费方 |
|---|---|---|
| 表格 | `cell_provenance` / `cell_ocr_text` / `cell_word_bbox` | 证明包渲染、机读客户 |
| 质量 | `quality.table_backfill.*`（含 `mismatch_details[]`、`page_verdicts[]`） | 报告指标卡、review list |
| 报告 | `report.json`（review_list 全量、backfill_demo、annotation_summary）+ `annotated.pdf`（绿/琥珀锚定框 + 蓝表框） | 客户 / 程序核验 |
| 调试 | `debug/backfill_alignment.json`（DEBUG_MODE 时逐候选对齐证据） | 排障 |

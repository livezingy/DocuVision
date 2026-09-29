# 表格回填与 Provenance Review 机制（技术参考）

> 状态：§1-§3 为 v1.8/v1.8.1 **已实现行为**（分支 `feature/v1.8.1`，c37e35c）；§4-§5 为 **v1.9 已实现**（P-002 三层对应 + sanity 闸，`feat/p002-table-alignment`）。
> 代码归属：`backend/app/services/table_backfill.py`（漏斗）、`table_alignment.py`（对齐层新代码宿主：布局模型 / T1 / T3 / sanity，P-002 D1）、`page_text_trust.py`（页信任）、
> `proof_render.py` / `proof_report.py` / `proof_pack.py`（证明包）。

## 1. Review 覆盖范围（现有行为）

Review（即报告的 review list 与逐格 provenance 标注）是三重窄域的交集：

| 维度 | 范围 | 裁决位置 |
|---|---|---|
| 内容域 | 仅 `result["tables"]` 中的**表格** | orchestrator `table_step` |
| 格子域 | 仅**候选格**：数字/金额（含千分位、货币符）、日期、含数字编码、固定符号集（✓⊗●○）；≤40 字符 | `table_backfill.is_candidate_cell` |
| 页面域 | 仅**文本层可信页**：`invisible_ratio < 0.2` 且 `image_coverage < 0.5`；`overlay`（扫描件 OCR 叠加层）/ `no_text` / `mixed` 一律拒收 | `page_text_trust.judge_page_trust` |
| 坐标域 | 仅**原始坐标空间**：`angle_deg == 0` 且非 doc-unwarping（deskew/unwarp 页的表 bbox 与 PDF 文本层不可靠对齐） | v1.8.1 门禁（D10） |

**明确不覆盖**：表格外内容（段落/标题/公式/印章）、表格内散文格（非候选）、KIE 结构化字段、
扫描件（无原生文本层，"overlay 文本层"是 OCR 产物，采信即循环验证）、多行单元格
（v1.9 起由文本聚类层 T3 处理，见 §5）。

**页面级 vs 内容级**：`quality.table_backfill.page_verdicts`（text_layer/overlay/mixed/no_text）
是页面级判定分布；review list 是格级条目。两者不互相替代。

## 2. 判定流水线（现有规则）

> v1.9（P-002）：在第 2 步候选筛选之后插入三层对应（T1 值匹配 → T2 几何包含 → T3 文本聚类，
> 见 §5）；本节保留 v1.8 基线行为描述。

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

## 4. Sanity 规则（v1.9 已实现——防错值注入）

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
   `0↔O/o`、`1↔l/I/i`、`5↔S/s`、`8↔B`、`6↔b/G`、`9↔g/q`、`2↔Z/z`、`✓↔√`、`●↔•`、`×↔x`
   （执行裁决 X1，2026-09-29：数字间相似如 `5↔9`、`3↔8` **不构成**混淆位——规则 2 直接否，
   设计稿早期示例已按本规范更正）；
3. **替换位数上限**：`len ≤ 6` 允许 1 位；`len > 6` 允许 2 位（阈值取较长串；长度差 1 时
   先试去尾再去首，被删字符不计替换位）。

**裁决**：满足 → 正常回填（琥珀）；不满足 → `text_mismatch`（红，入 review list，data 不动）。

### 4.3 效果与诚实边界

- **拦截的**：典型邻居值抽取——如 OCR `12,900.00` vs 邻居 `-250.00`（归一化 `1290000` vs
  `25000`，长度差 2 → 拒绝）、`3480.25` vs `12500`（长度差 + 非混淆位 → 拒绝）。
  失败模式从"静默错值"降级为"可复核红旗"。
- **拦不住的**：邻居值与 OCR 值恰好呈单字符混淆（如 `1284` vs `1281`）的极小概率情形——
  sanity 是强过滤器，不是等值证明；残余风险由 review list 兜底（该格出现在报告里可复核）。
- **绿格的对称限制**：错误对应若恰好内容一致（邻居值 == OCR 值），会标绿但标注位置错——
  数据无损、证据有偏；该情形只能靠 v1.9 tier-3 的位置语义消除，sanity 管不了。
- **实现位置**：已实现于 `table_alignment.is_ocr_confusion`，在 `table_backfill` 的琥珀分支
  （T2/T3 回填替换前）调用，绿格天然过闸不调用；属漏斗行为变更 → BACKFILL-001 云端重验。

## 5. v1.9 三层对应机制（已实现，P-002 / `table_alignment.py`）

对应机制决定"哪个文本层词属于哪个格子"。v1.9（P-002）起按精度降级三层，逐候选格依序求解：
T1 唯一命中（或碰撞消解唯一落位）→ T2 → T3，全部无果诚实红：

1. **值匹配 T1（`value_match`）**：表 bbox 邻域（外扩 8pt、剔除兄弟表）的文本层词中找与 OCR 值
   归一化相等的连续词 run，**行带 + 列窗双锚定**——run 的行簇须映射到该行、行内词组须指派到
   该列，缺一不采信（值印在他行/他列永不为解）；同值碰撞交列窗消解（最近未扩张列中心，
   平局降级 T2）。值相等由构造保证，天然过 sanity、data 不动。
2. **几何包含 T2（`geometric`）**：现状三关，逻辑零改动；琥珀分支（值替换）前置 sanity 闸（§4）。
3. **文本聚类映射 T3（`cluster`）**：复用布局模型（y1 聚行 + 行内词组分列 + 列窗指派），取
   「行 i 簇 × 列 j 词组」的 in-bbox 词集 join 比对；空集回落 T2 失败原因（诚实红，不静默错配）。

配套（已实现）：`cell_align_reason` 逐格 reason 网格（候选格 8 值之一、非候选格 null）+
`quality.table_backfill.align_reason_counts`（8 键恒在场、sum == candidates）+
`mismatch_details[].reason` 与 debug 记录 `reason` + review 表第 6 列（`col_reason` 双语）。
**reason 8 值** = 规格草案 6 值 + `cluster`（T3 解决）+ `sanity_reject`（对齐成功但 sanity 拒绝）——
6 值枚举无法表示这两类结局（纯加法，向后兼容）。
**边界原则**：文本层管真值与对应，vision 结构管语义（行列含义、合并格）；扫描件无文本层，
本机制整体不适用，其信任叙事走引擎级指标（symbol_benchmark 等），两条叙事不混。

**验收**：本地门禁全绿（G1 单测 442 passed；G2 golden 三件套 pin：bank 12×value_match /
symbol 4×value_match / 非等宽金样 5 绿 + 2 诚实红；G3 audit/lint/docs_refs 0 违规）。
云端（2026-09-29）：**G4 判据 1-6/9 PASS**（bank 12×value_match、symbol 全绿）；**G5 INV-A1/A2/A3
零违规、候选格恒等，p12 红率 58.2%→0.8%、p29 97%→25.4%**（硬线按设计口径 p12/p29 判，双 PASS；
sanity 上界改观察口径——设计稿裁决 X5：T1/T3 使旧红格新对齐成功后内容非混淆即诚实红，且实测
拦截了旧漏斗对 mamba p12 四格的静默错填 '89.48'→'ppl ↓' 等，正确性修复实证）；p34 100%→57.1%
为已知局限（R10/R11 结构性成因，改进另立项）。**G6 WTW 哨兵 PASS**（5 单 no-op 强断言逐键
复现旧缓存；本机重判分 `wtw_metrics.csv` sha256 与 P-027 GB2 基线逐位一致）。

## 6. 证据产物速查

| 层 | 产物 | 消费方 |
|---|---|---|
| 表格 | `cell_provenance` / `cell_ocr_text` / `cell_word_bbox` | 证明包渲染、机读客户 |
| 质量 | `quality.table_backfill.*`（含 `mismatch_details[]`、`page_verdicts[]`） | 报告指标卡、review list |
| 报告 | `report.json`（review_list 全量、backfill_demo、annotation_summary）+ `annotated.pdf`（绿/琥珀锚定框 + 蓝表框） | 客户 / 程序核验 |
| 调试 | `debug/backfill_alignment.json`（DEBUG_MODE 时逐候选对齐证据，P-002 起含 reason） | 排障 |

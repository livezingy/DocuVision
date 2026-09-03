# PP-StructureV3 修复规划

> **Status**: in-progress — F1/F2/F4 已实施（2026-09-03，本机纯逻辑单测 18/18 绿，待 Cloud 验证）；F3 待实施。基于 [pp-structurev3-official-findings.md](pp-structurev3-official-findings.md) 的官方依据。
> **权威**: 实施时以代码为准；本规划用于拆解任务、定优先级、给可验证目标。
> **前置约束**: 本地未装 Paddle 栈（见 `004-project.mdc`），所有涉及 `import paddle`/`import paddlex`/推理的验证在 Cloud Studio GPU 跑；本地可跑纯逻辑单测与契约 mock。

## 修复总览

| ID | 问题点 | 官方依据 | 优先级 | 本机可测 | Cloud 专属 | 状态 |
|----|--------|----------|--------|----------|-----------|------|
| F1 | parsing_res_list 阅读顺序未用 `block_order` | findings §1 | P0 | ✅ 纯逻辑 | 推理验证 | ✅ 已实施 |
| F2 | LAYOUT_TYPES 漏 12 类，footnote 缺失 | findings §2 | P0 | ✅ 纯逻辑 | 推理验证 | ✅ 已实施 |
| F3 | figure_caption 与 figure 未关联 | findings §3 | P1 | ✅ 纯逻辑 | 推理验证 | ⏳ 待实施 |
| F4 | 表头关系层级丢失 | findings §4 | P1 | ✅ 纯逻辑 | 推理验证 | ✅ 已实施 |

P0 = 影响 JD 硬指标（阅读顺序/footnote），且改的是纯解析逻辑，本机可测。
P1 = 影响 JD 硬指标（caption/header），但依赖官方 postprocessing 或需谨慎改 HTML 解析。

---

## F1 — parsing_res_list 阅读顺序改用 `block_order`

### 现状（`backend/app/services/layout_service.py`）
- `layout_service.py:728` 读 `block_index = block.get('index', idx)`，仅作 element id。
- `layout_service.py:949` `elements.sort(key=lambda e: (e['bbox']['y'], e['bbox']['x']))` —— 朴素 (y,x) 排序。
- `backend/app/orchestration/envelope_builder.py:288` 给递增 `reading_order` 计数器。

### 官方依据
- `parsing_res_list` 列表顺序即阅读顺序（[PP-StructureV3.en.md](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md)）。
- 每个块带 `block_order` 字段（[PaddleX 文档示例](https://paddlepaddle.github.io/PaddleX/3.3/en/pipeline_usage/tutorials/ocr_pipelines/PP-StructureV3.html)）。
- Enhanced XYCut + Region Detection 支持多栏（[PaddleOCR 3.0 Report §3](https://arxiv.org/html/2507.05595v1)）。

### 修复步骤
1. **`layout_service._parse_result` 的 `parsing_res_list` 分支**（约 `layout_service.py:720-780`）：
   - 读 `block_order = block.get('block_order')`（对象样式则 `getattr(block, 'order_index', None)`）。
   - 写入 element：`element['reading_order'] = block_order if block_order is not None else idx`。
   - **保留** `(y,x)` 排序作为 `block_order` 缺失时的回退，但仅在 `block_order` 全为 None 时启用。
2. **`envelope_builder.build_view_layer`**（`envelope_builder.py:263-298`）：
   - 优先用 fused block 已带的 `reading_order`，而非无条件递增计数器。
   - 回退：block 无 `reading_order` 字段时用当前递增逻辑。
3. **Region detection 开关**（`layout_service.py:96-101`）：
   - 在 init_params 显式 `use_region_detection=True`（需先确认 PP-DocBlockLayout 模型在 paddleocr 3.3.2 是否随 PPStructureV3 默认加载；若不支持则跳过此步，仅靠 `block_order`）。
   - 依据：`PP-StructureV3.yaml` 的 `RegionDetection` 子模块配置。

### 验证
- **本机纯逻辑单测**（新增 `backend/tests/test_layout_reading_order.py`）：
  - 构造 mock `parsing_res_list`，含双栏 4 块（左栏上/下、右栏上/下），`block_order` 标注正确阅读顺序。
  - 断言 `_parse_result` 输出的 `reading_order` 按 `block_order` 排列，不被 (y,x) 打乱。
  - 断言 `block_order` 全 None 时回退到 (y,x)。
- **Cloud 推理验证**（`test_live_api.py` 或手动）：
  - 用 `test_data/testfiles/PDF_Parsing/03_paper_arxiv-mamba_multicolumn_glyph-tables.pdf` 双栏页。
  - 期望：layout 输出 reading_order 按列内从上到下、左列先于右列。

### 风险/反例
- PP-StructureV3 升级后 `block_order` 字段名变化 → 回退到 (y,x) 并告警。
- Region detection 模型未加载时多栏报纸仍会交错 → 如实告知，不阻塞 F1 主路径。

---

## F2 — LAYOUT_TYPES 扩展到官方 23 类

### 现状（`layout_service.py:23-32`）
仅 11 类映射，`title` 混淆 `paragraph_title`/`doc_title`，`footnote` 缺失。

### 官方依据
- [PP-DocLayout-L 23 类](https://huggingface.co/PaddlePaddle/PP-DocLayout-L)。
- [PP-StructureV3.yaml `markdown_ignore_labels`](https://github.com/PaddlePaddle/PaddleX/blob/41b695b2/paddlex/configs/pipelines/PP-StructureV3.yaml)。

### 修复步骤
1. **扩展 `LAYOUT_TYPES` 字典**（`layout_service.py:23-32`）补全 23 类，参考 findings §2 表格的"建议处理"列。
2. **拆分 `title`**：`paragraph_title` → "Paragraph Title"，`doc_title` → "Document Title"，不再统一映射 `title`。
3. **`equation` 对齐**：保留 `equation` 作别名，但 `LAYOUT_TYPES` 主键用官方 `formula`；`formula_number` 单独映射。
4. **`_parse_result` 保留原 label**：当前 `element_type = str(block.get('label', 'unknown')).lower()` 已保留原值，确认下游 `envelope_builder._map_block_type_to_kind` 不会把 `footnote`/`abstract`/`algorithm` 错误泛化为 paragraph。
5. **markdown_ignore 策略**：参考官方但**不忽略 footnote**（JD 高价值）；忽略 `number`/`header`/`footer`/`header_image`/`footer_image`/`aside_text`。

### 验证
- **本机纯逻辑单测**（扩展 `test_layout_reading_order.py` 或新建 `test_layout_types.py`）：
  - 构造含 `footnote`/`abstract`/`algorithm`/`formula_number` label 的 mock parsing_res_list。
  - 断言 `_parse_result` 输出 `type` 保留原 label，`type_name` 正确映射。
- **Cloud 推理验证**：
  - 用 `01_patent_us8582862b2`（含页眉页脚）+ `03_paper_arxiv-mamba`（含脚注）。
  - 期望：footnote 块独立输出，不被混入 text。

### 风险
- 下游 view 层 `_map_block_type_to_kind` 若只认旧 label，新 label 会落入 default → 需同步检查 envelope_builder。

---

## F3 — figure_caption 与 figure 关联

### 现状
- `figure_service._figure_elements`（`figure_service.py:33-40`）只挑 figure/image/chart/flowchart，忽略 caption。
- 本项目未调官方 `restructure_pages()` / `update_vision_child_blocks`。

### 官方依据
- caption 绑定是 postprocessing 内置（[PaddleOCR 3.0 Report §3](https://arxiv.org/html/2507.05595v1)），通过 `update_vision_child_blocks` 实现（DeepWiki 源码）。
- 跨页表合并用 `restructure_pages(merge_table=True)`（`merge_table.py:30-250`）。

### 修复步骤（两档，先 A 后 B）

**A 档（轻量，不依赖官方 postprocessing）——推荐先做**
1. 在 `figure_service` 加 `_bind_captions(figures, all_elements)`：
   - 从 `all_elements` 筛 `figure_caption`/`figure_title`/`table_caption`/`figure_table_chart_title` 块。
   - 按 bbox 邻接绑定到最近的 figure/table：caption 紧贴 figure 下方或上方，横向重叠 ≥0.5，距离 < page_height*0.05。
   - 写入 figure 的 `payload.caption` 和 `payload.caption_id`。
2. `figure_service.crop_figures` 调用时传入完整 `layout_result["elements"]`（当前已传，但 `_figure_elements` 过滤掉了 caption）。
3. 同步在 `table_service._extract_from_layout_elements` 给 table 绑 `table_caption`。

**B 档（重，依赖官方调用路径升级）——后续评估**
- 评估把 `layout_service` 从 per-page `predict()` 升级到 `predict()` + `restructure_pages()`，直接拿带 caption 绑定 + 跨页表合并的结果。
- 风险：`restructure_pages` 是 PP-StructureV3 内部方法，API 稳定性需验证；且需多页输入，本项目当前 per-page 渲染流程需重构。
- **B 档不在本轮实施**，记录为 v1.6+ 候选。

### 跨页表合并修复（独立子任务 F3b）
- 当前 `packages/docuvision-core/.../table_stitch.py` 的 `stitch_tables_by_header` 仅看首行表头完全相等。
- 修复：放宽匹配为"表头子集匹配 OR `Continued` 关键词 OR 列数一致"，并支持"空格继承上一格"语义。
- 依据：官方 `merge_tables_across_pages` 做对齐+列数+语义连续性三重校验（findings §3）。
- 本任务归 core 包，本机可跑纯逻辑单测。

### 验证
- **本机纯逻辑单测**（`test_figure_caption_binding.py`）：
  - 构造 mock elements：1 个 figure + 1 个 figure_caption（bbox 紧贴下方）。
  - 断言 `_bind_captions` 把 caption 挂到 figure.payload.caption。
  - 反例：caption 离 figure 远（距离 > 阈值）→ 不绑定。
- **Cloud 推理验证**：`02_datasheet_ti-lm358`（含 schematic + caption）+ `03_paper_arxiv-mamba`（含 table caption）。

### 风险
- A 档是官方 `update_vision_child_blocks` 的简化复刻，约 40 行，属"造轻轮子"，但避免改调用路径的大风险。
- bbox 邻接阈值对不规则版面（caption 在图侧边）可能漏绑 → 设可配置阈值。

---

## F4 — 表头关系（header relationships）层级保留

### 现状（`backend/app/services/table_service.py`）
- `_extract_html_structure`（`table_service.py:988-1040`）只判 `cell.name=='th'` 标 `is_header`。
- `_html_to_data`（`table_service.py:820-940`）展平为 `List[List[str]]`，丢失多级表头层级。
- PP-StructureV3 表 HTML 常把表头写 `<td>` → `is_header` 全 false。

### 官方依据
- SLANeXt HTML 原生 `<thead>`/`<th rowspan>`/`<th colspan>` 表达多级表头（[Table Recognition v2 文档](https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/table_recognition_v2.html)）。
- `rowspan`/`colspan` 在结构预测阶段产出（[`ppstructure/table/README.md`](https://github.com/PaddlePaddle/PaddleOCR/blob/main/ppstructure/table/README.md)）。

### 修复步骤
1. **`_extract_html_structure` 增强**（`table_service.py:988-1040`）：
   - 识别 `<thead>` 块：整段 thead 内的行标 `is_header=true`，不论 td/th。
   - 无 `<thead>` 时启发式：前 N 行（N≤3）中 ≥50% 单元格为空或短文本（≤20 字）且后续行引用其值 → 标 header。
   - 输出 `header_rows: int`（表头行数）+ `header_span_map: [{row, col, rowspan, colspan}]`（多级表头 span 树）。
2. **`_html_to_data` 保留 header 标记**：输出 `data` 同时输出 `header_data: List[List[str]]`（仅表头）+ `body_data`（表体），避免展平后无法区分。
3. **`is_header` 判断放宽**：`cell.name in ('th',)` OR（在 thead 内的 td）。

### 验证
- **本机纯逻辑单测**（扩展 `test_table_strategy_meta.py` 或新建 `test_table_header_structure.py`）：
  - 构造含 `<thead><tr><th colspan="2">A</th><th rowspan="2">B</th></tr><tr><th>A1</th><th>A2</th></tr></thead>` 的 HTML。
  - 断言 `header_rows==2`，`header_span_map` 含 colspan=2 / rowspan=2。
  - 构造表头写成 `<td>` 但在 `<thead>` 内的 HTML → 断言 `is_header=true`。
- **Cloud 推理验证**：`03_paper_arxiv-mamba` p29 Table 11（二级表头跨 14 列）。

### 风险/限制
- SLANeXt 对无线表多级表头识别准确率官方未公布 → 解析层做对，模型层仍可能漏 span，需人工复核兜底（如实告知客户）。

---

## 实施顺序与门禁

| 阶段 | 任务 | 依赖 | 门禁 |
|------|------|------|------|
| 1 | F1 + F2（纯 layout_service 解析逻辑） | 无 | 本机纯逻辑单测绿 |
| 2 | F4（table_service HTML 解析） | 无 | 本机纯逻辑单测绿 |
| 3 | F3 A 档（figure_service caption 绑定） | F2（需识别 figure_caption label） | 本机纯逻辑单测绿 |
| 4 | F3b（core table_stitch 跨页放宽） | 无 | 本机纯逻辑单测绿 |
| 5 | Cloud 推理验证全部 | 1-4 | Cloud `test_live_api` + PDF_Parsing 三样本 |

**硬门槛**（按 `004-project.mdc`）：F1/F2 改的是 layout 契约输出字段（新增 `reading_order`/扩展 `type`），属契约字段变更 → 须 Cloud 通过再继续下游。

## Doc sync
- 实施时同步 `docs/architecture/docuvision-system-design.md`（reading order / LAYOUT_TYPES / caption 段）。
- 同步 `docs/README.md` 索引（新增本文件 + findings 文件）。
- F3b 改 core 包 → 同步 `packages/docuvision-core/README.md`。

## Adversarial check
- F1：`block_order` 字段名跨版本不稳定 → 已设回退到 (y,x) + 告警。
- F3 A 档：bbox 邻接阈值对 caption 在图侧边的不规则版面会漏绑 → 阈值可配置，且不阻塞主流程（caption 缺失不报错）。
- F4：无线表多级表头模型层漏 span → 解析层无法补救，需人工复核，如实告知。
- 整体：本地无 Paddle 栈，纯逻辑单测用 mock parsing_res_list，可能与真实 PP-StructureV3 输出结构有偏差 → Cloud 验证阶段用真实样本校准 mock。

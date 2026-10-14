# PP-StructureV3 官方能力依据

> **Status**: living reference — 改 `backend/app/services/layout_service.py`、`table_service.py`、`figure_service.py`、`table_cell_confidence.py` 或升级 paddleocr/paddlex 版本时同步。
> **最近对照**: paddleocr 3.3.2 / paddlex 3.3.12（2026-09-03）
> **最近增补**: §6 表格几何与方向校正（180° 类）——对照 paddlex `release/3.3` 源码逐行 + 本机探针实测（2026-10-11）
> **权威**: 本文为人工整理的官方依据派生视图；代码实现以 `backend/app/services/*` 为准，本文用于解释"官方支持什么 vs 本项目用了什么"。

## 1. parsing_res_list 阅读顺序

### 官方依据
- **PaddleOCR 官方文档** [PP-StructureV3.en.md](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md)：
  > `parsing_res_list`: `(List[Dict])` A list of parsing results, each element is a dictionary, and **the list order is the reading order after parsing**.
  每个元素字段：`block_bbox`、`block_label`、`block_content`、`block_id`、`block_order`。
- **PaddleX 官方示例输出**（[PP-StructureV3 文档](https://paddlepaddle.github.io/PaddleX/3.3/en/pipeline_usage/tutorials/ocr_pipelines/PP-StructureV3.html)）：
  `block_order` = Enhanced XYCut 分配的阅读顺序号；`block_id` = 检测原始序号。`block_order` 可为 `None`（image/figure_title 等非正文流块）。
- **DeepWiki（源码 `layout_objects.py`）**：`LayoutBlock` 对象属性 `order_index`（XYCut 分配）与 `index`（原始检测序号）是两个独立属性。
- **PaddleOCR 3.0 Technical Report** [arXiv 2507.05595](https://arxiv.org/html/2507.05595v1) §3：Enhanced XYCut + Region Detection 专门针对多栏杂志/报纸、多表报告、考试、手写、日文竖排优化。

### 关键结论
| 项 | 官方支持 | 本项目现状 |
|----|----------|-----------|
| 阅读顺序字段 | `block_order` / `order_index`（XYCut 分配） | `layout_service.py` 读 `block.get('index', idx)` 仅作 element id，**未读 `block_order`** |
| 排序逻辑 | Enhanced XYCut + Region Detection | `layout_service.py:949` 用 `(y, x)` 朴素排序，`envelope_builder.py:288` 给递增计数器 |
| 多栏支持 | 需 `use_region_detection=True` 加载 PP-DocBlockLayout | `layout_service.py:96-101` init_params 未显式开启 region detection |
| 跨页合并 | `restructure_pages()` | 本项目 per-page 独立分析，未调用 |

### 失败模式
- 双栏论文：左栏第 2 段会被 (y,x) 排到右栏第 1 段之后 → 错序。
- 单页多篇文章（报纸）：无 region detection 时 XYCut 仍会交错；本项目连 `block_order` 都没用，回到原始 (y,x)。

---

## 2. LAYOUT_TYPES 官方完整 23 类

### 官方依据
- **PP-DocLayout-L HuggingFace 模型卡** [link](https://huggingface.co/PaddlePaddle/PP-DocLayout-L)：23 common categories。
- **PP-DocLayout arXiv** [2503.17213](https://arxiv.org/html/2503.17213v1) Table 1：完整类别 ID 映射。
- **PP-StructureV3.yaml** [link](https://github.com/PaddlePaddle/PaddleX/blob/41b695b2/paddlex/configs/pipelines/PP-StructureV3.yaml)：`markdown_ignore_labels` + 每类 threshold/merge 模式。

### 官方 23 类（PP-DocLayout-L）
| ID | label | 本项目 `LAYOUT_TYPES` | 建议处理 |
|----|-------|----------------------|----------|
| 0 | paragraph_title | ❌（混入 `title`） | 显式映射，view 层保留 |
| 1 | image | ✅ | 保留 |
| 2 | text | ✅ | 保留 |
| 3 | number | ❌ | 检测但 markdown 忽略 |
| 4 | abstract | ❌ | 显式映射 |
| 5 | content | ❌ | 显式映射 |
| 6 | figure_table_chart_title | ❌ | 合并到 figure/table caption |
| 7 | formula | ✅（项目用 `equation`） | 对齐官方 label `formula` |
| 8 | table | ✅ | 保留 |
| 9 | reference | ✅ | 保留 |
| 10 | doc_title | ❌（混入 `title`） | 显式映射 |
| 11 | footnote | ❌ | **必补**（JD 点名） |
| 12 | header | ✅ | 保留（markdown 忽略） |
| 13 | algorithm | ❌ | 显式映射 |
| 14 | footer | ✅ | 保留（markdown 忽略） |
| 15 | seal | ❌（走单独 service） | layout 层映射，识别由 seal_service |
| 16 | chart | ❌ | 映射为 figure 子类 |
| 17 | formula_number | ❌ | 显式映射 |
| 18 | aside_text | ❌ | 检测但 markdown 忽略 |
| 19 | reference_content | ❌ | 合并到 reference |
| — | figure_caption | ✅ | 合并到 figure payload.caption |
| — | table_caption | ✅ | 合并到 table payload.caption |
| — | figure_title / header_image / footer_image | ❌ | figure_title→caption；header/footer_image 忽略 |

### 关键结论
本项目 `layout_service.py:23-32` 只映射 11 类，且 `title` 同时承接 `paragraph_title` 和 `doc_title`（语义混淆），`footnote` 完全缺失。官方 `markdown_ignore_labels` 定义了不进正文的类（number/header/footer/header_image/footer_image/aside_text/footnote），本项目可参考但不强制照搬——footnote 对 JD 需求是高价值，不应忽略。

---

## 3. figure_caption 与 figure 的关联

### 官方依据
- **PaddleOCR 3.0 Technical Report** [arXiv 2507.05595](https://arxiv.org/html/2507.05595v1) §3 Post-processing：
  > The post-processing module then reconstructs the relationships among elements, **such as linking figures and tables with their captions** and recovering the correct reading order.
- **DeepWiki（源码 `pipeline_v2.py` / `xycut_enhanced/xycuts.py`）**：caption 绑定发生在 `update_vision_child_blocks` 函数，把 `figure_title`/`table_title`/`chart_title`/`vision_footnote` 匹配到 parent vision block（image/table/chart），通过 bbox 邻接 + XYCut 分组实现，关系保存在 `LayoutBlock` child blocks 层级。**非独立公开 API**。
- **`result_v2.py` markdown 格式化**：有 `figure_title`/`table_title`/`chart_title`/`vision_footnote` 专门 label handler，证明官方内部已建立父子关系。
- **跨页表合并**：`merge_tables_across_pages()`（`merge_table.py:30-250`）由 `restructure_pages(merge_table=True)` 调用，做对齐+列数+语义连续性三重校验。

### 关键结论
| 项 | 官方支持 | 本项目现状 |
|----|----------|-----------|
| caption 绑定 | `update_vision_child_blocks`（postprocessing 内置） | `figure_service._figure_elements` 忽略 `figure_caption`/`figure_title`，未绑定 |
| 跨页表合并 | `restructure_pages(merge_table=True)` | `table_stitch.py` 自写，仅看首行表头完全相等（弱于官方） |
| 调用路径 | `predict()` + `restructure_pages()` | 本项目只取 `predict()` 单页原始结果 |

### 失败模式
- 题注与图分离输出，下游无法知道"这段文字是图 1 的 caption"。
- TI 数据手册 `continued` 页表头省略或写 "Continued" 时，本项目 `table_stitch` 必挂（实测确认）。

---

## 4. 表头关系（header relationships）

### 官方依据
- **General Table Recognition v2 文档** [link](https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/table_recognition_v2.html)：PP-TableMagic（SLANeXt wired/wireless）输出 HTML，**用标准 `<thead>`/`<th rowspan>`/`<th colspan>` 表达多级表头**。开关 `use_table_recognition=True`。
- **`ppstructure/table/README.md`** [link](https://github.com/PaddlePaddle/PaddleOCR/blob/main/ppstructure/table/README.md)：表结构 + 单元格坐标 + OCR 文本组合成 HTML，`rowspan`/`colspan` 在结构预测阶段产出。
- **DeepWiki**：Table Recognition "generates HTML output", "support for complex spanning headers using standard HTML tags"。

### 关键结论
| 项 | 官方支持 | 本项目现状 |
|----|----------|-----------|
| 多级表头 | SLANeXt HTML 原生 `<thead>`/`rowspan`/`colspan` | `table_service._extract_html_structure` 只判 `cell.name=='th'` 标 `is_header` |
| 表头层级树 | HTML 结构保留 | 本项目展平为 `data: List[List[str]]`，丢失层级 |
| th 检测 | 官方输出常把表头写 `<td>` | 本项目只认 `<th>` → `is_header` 全 false |

### 失败模式
- arXiv Mamba p29 Table 11（二级表头跨 14 列）层级关系完全丢失。
- PP-StructureV3 表 HTML 表头写成 `<td>` 时，本项目 `is_header` 判断失效。

### 限制（如实告知）
- SLANeXt 对**无线表**多级表头识别准确率官方未公布分项指标；即便解析层做对，无线表多级表头仍可能漏 span → 需人工复核兜底。

---

## 5. 特殊字形（✓ ⊗ ● ○）

### 官方依据
- **PP-OCR 字典机制** [Text Recognition 文档](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version2.x/ppocr/model_train/recognition.en.md)：
  > 字典需包含所有要正确识别的字符。默认字典：`ppocr_keys_v1.txt`（6623 中文）、`en_dict.txt`（96 英文）、`ic15_dict.txt`（36）。
  > If the character set significantly differs from pre-trained distributions, re-training the model from scratch is recommended.
- **Qwen2.5-VL Technical Report** [arXiv 2502.13923](https://arxiv.org/pdf/2502.13923) §OCR 数据：大规模多语言 + 合成数据，不依赖固定字符字典，通过 multimodal 理解识别任意视觉符号。
- **Qwen2.5-VL-7B HuggingFace 模型卡** [link](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct)：
  > Qwen2.5-VL is ... highly capable of analyzing texts, **charts, icons, graphics**, and layouts within images.
  OCRBench 864，DocVQA 95.7%。明确点名 icons——✓/⊗/●/○ 属于 icon 范畴。

### 关键结论
| 引擎 | ✓/⊗/●/○ 支持 | 依据 |
|------|------|------|
| PP-OCR（默认字典） | ❌ 不支持，会丢/替换 | 默认字典无这些字符 |
| PP-OCR（自定义字典） | ⚠️ 需重训才可靠 | 官方建议字符集差异大时重训 |
| Qwen2.5-VL | ✅ 原生支持 | multimodal 理解，无字典限制，官方点名 icons |

### 实测补充（本项目 memory 2026-09-02）
- ● (U+25CF) / ○ (U+25CB) 在真实文档文本层几乎不存在（30+ 份全扫，仅 unicode.org 字符表有），多为图形图元/栅格。
- ✓/✗ 常见于 arXiv 方法对比表（Mamba 2312.00752 p29 Table 11 同时命中合并单元格+表头+字形+脚注）。
- ⊗ 罕见（仅 Transformers Survey p12/13）。

---

## 6. 表格几何：两套坐标系与方向校正（180° 类）

> **增补**: 2026-10-11。对照 **paddlex `release/3.3`（3.3.12）源码逐行** + 本机探针实测。
> **性质**：本节记录的是**产出几何错误**类缺陷（可致导出数据整体翻转），**不是精度问题**——它不会被"模型更准"修好，
> 也不会被"命中率/覆盖率"类自检发现。
> **版本分工**：本节只留**结论 + 合成最小复现**；含夹具读数与逐格复算通路的**完整实测版**为 local-only，不入库
> （见文末「版本分工」）。

### 官方依据

- **PaddleX `release/3.3` 源码**（表格识别后处理）
  `paddlex/inference/pipelines/table_recognition/table_recognition_post_processing_v2.py`：
  `get_ori_image_coordinate` / `convert_table_structure_pred_bbox` / `match_table_and_ocr` / `get_html_result`。
- **PaddleX `release/3.3` 源码**（表格识别管道）
  `paddlex/inference/pipelines/table_recognition/pipeline_v2.py`：
  `map_cells_to_original_image` / `split_ocr_bboxes_by_table_cells` / `cells_split_ocr`。
- **PaddleX `release/3.3` 源码**（版面解析工具）
  `paddlex/inference/pipelines/layout_parsing/utils.py::get_sub_regions_ocr_res`。
- **官方字段表**（[Table Recognition v2](https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/table_recognition_v2.html)）：
  `table_res_list[i]` 同时给出 `cell_box_list`（结构侧格框）与 `table_ocr_pred.{rec_boxes, rec_polys, rec_texts, rec_scores}`（识别侧文本行条目）。
- **次级来源**（官方说明转述，主源本次抓取超时）：`use_table_orientation_classify` **默认 True**，
  「启用后对存在 **90/180/270** 度旋转的表格先校正方向再识别」。
- **上游 issue**：[PaddleOCR#17133](https://github.com/PaddlePaddle/PaddleOCR/issues/17133)（多表图单元格错位；
  报告环境 paddlex 3.2.1 + 昇腾 910B；维护者无法复现，2026-03-11 因 stale 关闭）。与本项目"单表单页"现象**不同因**，仅作渠道查证。

### 关键结论

| 项 | 官方支持 | 本项目现状 / 消费方式 |
|----|----------|----------------------|
| 两套几何 | `cell_box_list` = 结构侧格框，**平移+裁剪回整图**（`offset` + `np.clip`）；`table_ocr_pred.rec_boxes` = 整图文本行条目，**只筛选、不平移** | `backend/app/services/table_cell_confidence.py` 按"条目中心落入格"做归属聚合 |
| 方向校正覆盖面 | 覆盖 **90/180/270**；但 `map_cells_to_original_image`（守卫 `use_table_orientation_classify and table_angle != "0"`）**只重映射 `cell_box_list`**，`table_ocr_pred` 不动 | 消费侧默认两套几何同帧——**该前提在触发方向校正时不成立** |
| `pred_html` 文本来源 | `match_table_and_ocr(table_cells_result, ocr_dt_boxes = table_ocr_pred["rec_boxes"], …)`，判据 `compute_inter > 0.7`（cell 框为基准键，OCR 框为被匹配项） | `backend/app/services/table_service.py` 解析 `<td>` 为 `data` |
| per-cell 置信度 | **无任何单元格级/表格级置信度**。文档把 `rec_scores` 写作"单元格识别置信度"属**措辞误导**：它与 `rec_polys/rec_texts/rec_boxes` 同长度一一对应，一格可含多条 | D8 自建（几何归属 → 格内取 `min` → 命中率哨兵 + `measured`） |
| 合并格补偿 | `match_table_and_ocr` 内确有"补空单元 / 合并单元"分支，但调用处第 3、4 实参传入**同一个** `table_cells_flag` ⇒ 两分支恒假（**死代码**） | 消费侧按严格索引比对 `<td>` 序（在含 colspan/rowspan 的表上不成立） |
| `rec_scores` 与 `rec_boxes` 同步性 | `cells_split_ocr` 为**硬编码 True** ⇒ 走切分分支，而 `split_ocr_bboxes_by_table_cells` 结尾**只回写 `rec_boxes` / `rec_texts`** | 本项目按索引 zip 两数组，需长度守卫 |

### 失败模式

- **两套几何差 180°**（触发方向校正时）：每格被挂上**镜像列**的文本；且 `raw` / 仅 y 翻转 / 180° 三个候选帧**命中数相同**（180° 是页面双射）
  ⇒ **命中率、覆盖率类自检结构性失明**，不会报警。
- **`<td>` token 序仍是旋转序**：`pred_html` 的阅读序未被反旋转 ⇒ 由它解析出的 `data` **整表 180°**
  （**表头落在最后一行**、每行列序反向）。导出数据"看起来完整"，属**静默错误**，比缺失更危险。
- **合并格表**：`td_index` 按 `table_cells_flag` 每行重置、补偿分支又是死代码 ⇒ 与真实 cell 序**分段漂移**，并产出空 `<td>`。
- **切分场景**：`rec_scores` / `rec_polys` 长度可能与 `rec_boxes` 不等 ⇒ 按索引配对会静默错配。

### ISSUE 格式问题点（内部草稿，**未提交上游**）

> 提交红线：对外提交属"公开发布"，需先问；对外版**只保留合成最小复现**，剥离全部夹具读数与内部语料字段。

#### ISSUE-1（P0）表格方向校正后 `table_ocr_pred` 未同步反旋转，`cell_box_list` 与 `rec_boxes` 落入不同坐标系

- **Summary**：启用 `use_table_orientation_classify`（默认 True）后，`cell_box_list` 被反旋转回原图帧，而
  `table_ocr_pred.{rec_boxes, rec_polys, rec_texts, rec_scores}` **保持旋转帧**，净差恰为 180°。下游任何"按几何归属把文本行配对到格"的实现
  都会把**镜像列**文本挂到该格，且**命中率类自检无法发现**。
- **Environment**：PaddleX `release/3.3`（paddlex 3.3.12）；PP-StructureV3；`use_table_orientation_classify=True`（默认）；
  `use_ocr_results_with_table_cells=True`（默认）；单表单页即可复现；与设备无关（纯几何逻辑）。
- **Steps（合成最小复现，无真实文档）**：① 造 A4@150dpi（1224×1584）页面，画 2×2 表格，四格分别印 `R1`(右上) `L1`(左上) `R2`(右下) `L2`(左下)；
  ② 整页旋转 180° 后送入 PP-StructureV3；③ dump `table_res_list[0]`，对 `cell_box_list` 与 `table_ocr_pred.rec_boxes` 做归属统计。
- **Expected**：两套几何同帧；每格文本为其**几何位置的真值**。
- **Actual**：三候选帧命中数**相同且都满**，命中率无法判别；只有"逐格文本 vs `<td>` 序"能判别，而**仅 180° 帧一致**。
- **Evidence（源码）**：`pipeline_v2.py` 中 `single_table_res["cell_box_list"] = self.map_cells_to_original_image(...)`
  （守卫 `use_table_orientation_classify == True and table_angle != "0"`，**只改 `cell_box_list`**）；
  `get_sub_regions_ocr_res` 对 `rec_boxes` 只筛选；`convert_table_structure_pred_bbox` 只加 offset+clip。
- **Root cause（已闭合到调用方一层，2026-10-11）**：结构模型在 180° 帧内推理（token 序与 cell 框皆旋转序；引擎的 `compute_inter` 匹配发生在**反旋转之前**，故 `pred_html` 自洽），
  返回时只把 `cell_box_list` 反旋转 ⇒ 与未动的 `table_ocr_pred` 净差 180°。
  **触发条件已核实**：产品引擎构造参数在 `backend/app/services/layout_service.py` 的 `PPStructureEngine._init_engine`
  （`init_params` 只含 `device` / `lang` / `use_doc_unwarping`，另加按签名门控的 `use_formula_recognition` /
  `use_seal_recognition` / `use_chart_parsing` / `use_chart_recognition` / `use_table_recognition`），
  **未传 `use_table_orientation_classify`** ⇒ 取 PaddleX 默认（True）⇒ **180° 校正路径确实处于开启状态**。
  **剩余不可观测项**：**逐表 `table_angle` 的实际取值**——结果 JSON 不暴露它（已核 `result_item_keys` /
  `table_res_list[i].keys` / `model_settings` 三处均无角度类字段），故只能由调用方记录。
- **Workaround**：消费侧**不要**信任命中率满分；改用列序判据（见 ISSUE-3 的 Workaround），并**合并格感知**；
  保守方案是把"两套几何不同帧"作为 anomaly 上报、不参与 pass/fail。**不建议**关闭 `use_table_orientation_classify`（会同时失去 90/270 校正）。

#### ISSUE-2（P0）方向校正后 `pred_html` 的 `<td>` 阅读序仍为旋转序，导出表格整表 180°

- **Summary**：即便几何侧修好，`<td>` **token 序**本身仍是 180° 序（行自下而上、列自右向左）⇒ 由 `pred_html` 解析的表格整体翻转：
  **表头出现在最后一行，且每行列序反向**。与 ISSUE-1 独立：这是**内容正确性**问题，不是几何一致性问题。
- **Environment / Steps**：同 ISSUE-1。
- **Expected**：`<td>` 序 = 纸面阅读序（自左上到右下，表头在第一行）。
- **Actual**：cell 索引序与 `<td>` 序**一致**，但两者都是 180° 序。
- **Evidence**：cell 索引序 ≡ `<td>` token 序；逐格文本与其几何位置相符 ⇒ **引擎匹配自洽，错的是 token 序本身**。
- **Impact**：导出数据"看起来完整"但整体翻转 ⇒ 对账/比对**静默出错**；若消费侧为对齐而采用 180° 帧，会与 `data` **一致地错**，
  用"已对齐"的假象掩盖内容错误。
- **Workaround**：输出层做表头检测 + 序反转，或把"整表 180°"作为 anomaly 上报而非静默校正。

#### ISSUE-3（P1）合并格补偿为死代码，致 `td_index` 错位与空 `<td>`

- **Summary**：`match_table_and_ocr(...)` 第 3、4 实参传入**同一个** `table_cells_flag` ⇒ "补空单元 / 合并单元"两分支恒假；
  `get_html_result` 的 `td_index` 又按 `table_cells_flag[matched_list_index + 1]` **每行重置** ⇒ 一旦存在 colspan/rowspan，
  `td_index` 与真实 cell 序漂移，并伴随空 `<td></td>`。
- **Evidence（源码）**：两处（调用实参相同；`if td_index in matched_index.keys(): if len(...) == 0: continue` 而 **tag 仍被追加**）。
  受控复现（含 colspan/rowspan 的表）显示偏移**无常数平移可解释**，属**分段递增**漂移。
- **Impact**：合并格表格 HTML 文本错位 + 空单元格；下游按 `<td>` 序解析的字段整体偏移（随合并带数量累积）。
- **Workaround**：消费侧对含合并格的表**抑制**严格索引比对；先按 colspan/rowspan 重建网格再比对（D8 的列序哨兵必须**合并格感知**）。

#### ISSUE-4（P1）`split_ocr_bboxes_by_table_cells` 只回写 `rec_boxes` / `rec_texts`

- **Summary**：`cells_split_ocr` 硬编码 True ⇒ 走切分分支，而该函数结尾只写回 `rec_boxes`、`rec_texts`
  ⇒ 一旦有条目被切分（覆盖率 > 0.5、最多 k=2），`len(rec_boxes) > len(rec_scores)`，**索引语义错位**。
- **Evidence（源码）**：赋值处；本批受测夹具**未触发** ⇒ **潜在**隐患，需跨格长条目才能复现。
- **Workaround**：以 `rec_polys` 与 `rec_scores` 配对（保持原始 1:1），或以长度相等为前置守卫。

#### ISSUE-5（feature/docs）无单元格级置信度；文档措辞与实现不符

- **Summary**：`cell_box_list`、`pred_html` 均无分数；`rec_scores` 与 `rec_polys/rec_texts/rec_boxes` **同长度一一对应**，
  文档"单元格识别置信度"易被读成 per-cell。
- **Request**：① 文档更正措辞，明确 `rec_scores` 是**文本行级识别分、非结构正确性分**；
  ② 若要 per-cell，请在文档给出官方聚合口径；否则明确"由消费方自建"。
- **Evidence**：字段表 + `match_table_and_ocr` / `get_html_result` 的用法（文本按 `matched_index[td]` 聚合，**无分数参与**）。

### 限制与未确证

1. **方向字段与页面尺寸**：探针已记录页尺寸与方向属性的**有界采集**（只读 `dir`、不求值，避免触发懒加载）。
   **开关一侧已闭合**（调用方未传 ⇒ 默认 True）；**逐表 `table_angle` 仍不可观测**——它不是结果字段而是构造 / 运行期参数。
2. "引擎为何在未反旋转的帧内仍能填出正确 `<td>`"为**高置信推断**，未 dump 内部 `matched_index` 直接证实。
3. 本项目按"条目中心是否落入格"判归属，与上游 `compute_inter > 0.7`（交集/OCR 框面积）**判据不同**——两者在边角情形可能不一致，属**未对照项**。
4. 项目内**无**单元格级正确性标注（GT 只有行级）⇒ 无法把 `rec_scores` 校准成"该格正确的概率"，任何 per-cell 阈值都属启发式。

### 版本分工

- **本节（入库版）**：结论 + 合成最小复现 + 源码依据，**不含夹具读数与内部语料字段**。
- **完整实测版（local-only，不入库）**：含夹具读数、逐格读数与可复算通路，保存在本地知识库
  `docs/R&D/knowledge/pp-structurev3-official-findings-full.md`（该目录被 `.gitignore` 忽略）。

---

## 参考链接汇总
- PaddleOCR PP-StructureV3 文档: https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md
- PaddleX PP-StructureV3 文档: https://paddlepaddle.github.io/PaddleX/3.3/en/pipeline_usage/tutorials/ocr_pipelines/PP-StructureV3.html
- PP-StructureV3.yaml 配置: https://github.com/PaddlePaddle/PaddleX/blob/41b695b2/paddlex/configs/pipelines/PP-StructureV3.yaml
- PP-DocLayout-L 模型卡: https://huggingface.co/PaddlePaddle/PP-DocLayout-L
- PP-DocLayout arXiv: https://arxiv.org/html/2503.17213v1
- PaddleOCR 3.0 Technical Report: https://arxiv.org/html/2507.05595v1
- DeepWiki PP-StructureV3: https://deepwiki.com/PaddlePaddle/PaddleX/4.2-layout-parsing-(pp-structurev3)
- Table Recognition v2: https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/table_recognition_v2.html
- PP-OCR Text Recognition 文档: https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version2.x/ppocr/model_train/recognition.en.md
- Qwen2.5-VL Technical Report: https://arxiv.org/pdf/2502.13923
- Qwen2.5-VL-7B 模型卡: https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct
- PaddleX 表格识别后处理源码 (release/3.3): https://raw.githubusercontent.com/PaddlePaddle/PaddleX/release/3.3/paddlex/inference/pipelines/table_recognition/table_recognition_post_processing_v2.py
- PaddleX 表格识别管道源码 (release/3.3): https://raw.githubusercontent.com/PaddlePaddle/PaddleX/release/3.3/paddlex/inference/pipelines/table_recognition/pipeline_v2.py
- PaddleX 版面解析工具源码 (release/3.3): https://raw.githubusercontent.com/PaddlePaddle/PaddleX/release/3.3/paddlex/inference/pipelines/layout_parsing/utils.py
- PaddleOCR issue #17133（多表图单元格错位）: https://github.com/PaddlePaddle/PaddleOCR/issues/17133

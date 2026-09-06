# PP-StructureV3 官方能力依据

> **Status**: living reference — 改 `backend/app/services/layout_service.py`、`table_service.py`、`figure_service.py` 或升级 paddleocr/paddlex 版本时同步。
> **最近对照**: paddleocr 3.3.2 / paddlex 3.3.12（2026-09-03）
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

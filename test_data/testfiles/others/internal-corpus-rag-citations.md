# REQ-RAG01 — 内部 4000 份 PDF/DOCX：带页码引用的 RAG + 评测

| 字段 | 值 |
|------|-----|
| **REQ ID** | REQ-RAG01 |
| **标题** | Senior AI Engineer - RAG pipeline with source citations over internal document corpus |
| **来源** | [Upwork 链接](https://www.upwork.com/jobs/Senior-Engineer-RAG-pipeline-with-source-citations-over-internal-document-corpus_~022090739374681629312/) · Job ID `~022090739374681629312` · 收录 2026-08-23 |
| **intake 原文** | [_intake/2026-08-23_internal-corpus-rag.md](_intake/2026-08-23_internal-corpus-rag.md) |
| **附件** | 无 |
| **回写目标** | **摄取/版面/页码：层1 可回写 DocuVision。** 带引用的问答服务部署在客户 AWS，不把 DocuVision 当聊天产品。评测集与拒答策略可沉淀为 IDP 评测惯例 |
| **DocuVision 对接** | 待补 — `DocuVision/docs/R&D/upwork/internal-corpus-rag-citations.md` |
| **分类标签** | TaskType: **T11**（RAG）· **T1/T2**（PDF/DOCX 摄取）· **T6**（扫描件 OCR，若有） · DataShape: **D3** · Scale: **L**（$45–65/hr，>30h/周，3–6 月） |
| **Cluster** | **G: IDP**（摄取）+ T11 问答层 |
| **判定** | **建议投（P1，有真实落地 RAG/评测案例则可当 P0）。** 问题定义清楚：现成 chatbot 会自信说错。50+ 提案；无「无引用不答 + 怎么测」的具体写法会被当成套壳 API。语料不在手 → **专用 demo 待补** |

---

## 1. 结论

约 4000 份内部文档（规格、供应商合同、流程，跨约 8 年）。现成工具已经试过：答得像那么回事，但会错。他们要的不是再包一层 Claude。

四件必须同时成立：

1. 摄取管道（PDF + DOCX）  
2. 检索要拿到**对的段落**，不是向量近邻凑合  
3. 每条回答带**文件 + 页码**；没有引用就不答  
4. 能测对不对，加文档后能看出质量有没有掉  
5. 跑在他们自己的 AWS  

商业上这是本批里最像样的单之一：时薪公开 **$45–65**，Expert，3–6 个月。和 REQ-D01 的 $16/hr、REQ-FI01 的 $750 全产品不是一类。

难的是 **IR + 拒答 + 回归评测**，不是做聊天 UI。

---

## 2. 技术要点（投标讲取舍，本仓不实现）

客户已经否定「语义近 = 对」。提案里要能讲清（用你真实做过的系统，不要背名词表）：

| 点 | 为何需要 |
|----|----------|
| 按页/块切分并保留 `doc_id, page` | 否则无法引用页码 |
| 混合检索（关键词/BM25 + 向量）+ 重排序 | 规格号、合同条款、流程名经常是精确匹配，纯向量会漂到「看起来像」的段 |
| 元数据过滤（文种：规格 vs 合同 vs SOP、日期、现行/废止） | 8 年语料里旧版会赢过现行版 |
| 生成只许用检索到的 span；无高置信 span → 拒答 | 对应「No citation, no answer」 |
| 引用必须能点回那一页 | 防模型随口编文件名 |
| 黄金问答集 + 加库后回归 | 对应「加新文档后质量是否下降」 |

扫描件/双栏/页眉页脚会把页码对齐打烂——摄取质量决定 RAG 上限。这是 DocuVision/版面解析能帮忙的部分，不是 LangChain 模板能跳过的部分。

技能栏有 Claude API：生成侧可以用 Claude，检索与评测不要绑死一家。AWS 自建 = 向量库、解析、密钥都在他们账号，合同类文档不应出域。

---

## 3. 与 DocuVision / 现有需求

| 能力 | 关系 |
|------|------|
| PDF/DOCX 解析、页码、OCR | DocuVision / DocStruct **相邻**；交付仍是客户 AWS 管道 |
| 聊天 UI | 不是 DocuVision 产品目标 |
| [REQ-G01](gaeb-x83-pipeline.md) | 也是进知识库；G01 是 X83→Dify，本单是 4000 混合文档 + 强制引用 |
| [REQ-D01](document-idp-system.md) / [REQ-D02](talent-agency-pdf-extraction.md) | 同「JSON 合法 ≠ 正确」；D02 是图谱，本单是带引用问答 |
| [REQ-AR01](ar-g2-cheatsheet-dify.md) | 有 Dify/RAG；场景是眼镜 cue，不是合同检索 |
| [REQ-R01](erp-report-matching.md) | 语义近邻不够，要可解释匹配；精神同，栈不同 |

不要推销「把语料导入 DocuVision 聊天」。提案讲：摄取与页级块在文档栈，问答与评测在 AWS 服务。

---

## 4. 切片（接单后）

| 阶段 | 交付 |
|------|------|
| M0 | 文档类型抽样、扫描占比、现行版规则；20–50 条黄金问答（客户出题） |
| M1 | 摄取 + 页级块 + 能打开出处的检索（先可以没有畅聊） |
| M2 | 只根据 span 作答 + 无 span 拒答 + Claude（或他们指定） |
| M3 | 评测报表；加一批文档后复跑黄金集 |
| M4 | AWS 加固、权限（合同 vs 流程可见范围） |

先做检索命中率，再做「会聊天」。和他们已经失败的 off-the-shelf 路径相反。

工时量级：3–6 月 × >30h/周，与 L 级相符。不要压成两周 demo 合同。

---

## 5. 是否值得投

| 因素 | 评估 |
|------|------|
| 问题 | 真，可验收（引用、拒答、评测） |
| 价 | **$45–65/hr** 与 Expert 匹配 |
| 竞争 | **50+**，0 面试。筛选题是滤网 |
| 履历 | 必须有「上过线的检索/问答 + 如何测对」；没有则按 REQ-IOT01 同样不编 |
| Demo | 没有他们的 4000 份；最多用 3 份公开 PDF 演示「无引用不答」。标 **demo 待补** |

**优先级：P1。** 有生产级 RAG/评测案例 → 当天短提案只答两问，可升 P0。

提案不要写：LangChain 包一下、全向量、温度调低就能防幻觉。

---

## 6. 风险

| 风险 | 说明 |
|------|------|
| 旧版赢过现行版 | 无文档生命周期则「引用正确、建议过期」 |
| 合同条款近义 | 语义近邻会张冠李戴；必须混合检索 |
| 黄金集谁出 | 客户不出题就无法测「对」；要写进开工条件 |
| 权限 | 供应商协议不能被全员问答打出 |
| 扫描 PDF | 页码错则引用无意义 |
| 50+ | 客户可能已看疲劳；短、具体、带一次真实事故 |

亏本条件：按「两周做个 chatbot」接，却按 4000 份合同级正确率验收，且没有黄金集。

---

## 关联文档

- [_intake/2026-08-23_internal-corpus-rag.md](_intake/2026-08-23_internal-corpus-rag.md)
- [05-docintel-idp.md](../projects/05-docintel-idp.md)
- [gaeb-x83-pipeline.md](gaeb-x83-pipeline.md)

---

*记录日期：2026-08-23*

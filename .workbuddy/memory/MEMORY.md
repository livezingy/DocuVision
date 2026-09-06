# DocuVision 项目长期记忆

## 定位与边界（已定）
- DocuVision 死守"文档"边界：PDF/扫描件/票据/合同/名片。
- 工程图 → DrawVision（CV02/PL01）；科学图像 → SciVision（IB01）。
- **暂不建 DrawVision/SciVision 独立仓**：各仅 1-2 需求，过早抽象；先塞 DocuVision 实验区，等 5+ 同类需求再拆。
- 非文档类（RPA/爬虫/小程序/情报/AR/YOLO）不进任何仓，是别的工具栈。

## 能力暴露形态（2026-08-23 多轮讨论定方向）
当前问题：FastAPI 单体，能力锁在 `backend/app/services`；`packages/docuvision-core` 是空壳（只覆盖 Lite 表格/OCR）；`main.py` 顶层吞 paddle/paddlex 全局单例，无法 import 即用。

改造方向（收缩版，非全套积木库）：
- **最小 SDK 4 函数**：`ocr(engine=)` / `extract_layout()` / `extract_fields()` / `confidence_route()`——跨需求高频且有自托管差异化。
- **云 API 适配层**：Azure DI/Textract/Docling 统一薄封装；不和云 API 竞争它擅长的（名片、标准发票）。
- **脚本模板库**（starter repos，非库）：每类需求一个可 fork 模板（PDF→CSV锚点、票据OCR+校验、RAG切片）。
- **渐进库化**：被 3 个不同需求调过才升级成正式 SDK 函数（YAGNI）。
- 不破坏现有仓库：Pro service 拆成 core(纯算法)+service(读配置)，FastAPI 业务逻辑不改。Lite 已是范本（`lite_builder.py:34` 调 docuvision_core）。

## 三条技术判断（对抗审查结论，2026-08-23）
1. **胶水复用做"可拷贝模板"不做 SDK**：校验闭环/置信度路由/golden set 的骨架可复用，语义每需求不同；做 SDK 会强迫套同一语义。形态 = `templates/xxx/` 一个骨架 py + README 写"语义怎么填"，新单 `cp -r` 改，不 `import`。
2. **表格准确率靠"锚点+降级链"不靠自适应参数**：PDF 表格失败根因是列粘连/变长行/跨页/无ruling。`pdfplumber.find_tables()` 无 ruling 时返回 1 列整页，调参救不回。优先文本层 word 坐标 + 语义锚点(如 Log ID/单号作记录起点重置)；无文本层才上视觉(PP-Structure > Camelot > find_tables)；变长行用唯一键探测；跨页用唯一键重置。自适应参数有过拟合样例风险。
3. **OCR 靠"混合路由"不靠单一引擎优化**：印刷体→PaddleOCR/Azure；手写/隐私/疑难→Qwen2.5-VL本地；按置信度路由切换。Tesseract 只作零依赖兜底，不为它做预处理（预处理对印刷扫描有效对手写无效，且 PaddleOCR 自带预处理更强）。Qwen本地 vs Azure 成本：日处理 > ~6000 页且 GPU 利用率 > 50% 时本地略优；真正优势是数据不出境+无限并发+手写准确率，非纯成本。

## 复用资产不止代码
代码库只是其一；Demo产物、方案模板、golden set 评测集同等重要，维护成本更低。

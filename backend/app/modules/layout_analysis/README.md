# Layout Analysis Module

## 模块概述

Layout Analysis模块用于检测文档的结构元素，包括文本块、标题、表格、图片、页眉页脚、公式等。

## 使用的模型/库

### 主引擎：PP-StructureV3
- **库**: paddleocr (>=3.0.0), paddlex[ocr] (>=3.0.0)
- **版本**: PP-StructureV3
- **特点**:
  - 支持10+种元素类型检测
  - 表格结构识别准确率>90%
  - 公式识别（LaTeX输出）
  - 文档方向校正
  - 百度开源，社区活跃

### 备选引擎：LayoutParser
- **库**: layoutparser (>=0.3.4)
- **模型**: PubLayNet (Detectron2)
- **特点**:
  - 基于Detectron2
  - 适合学术论文和报告
  - 需要detectron2依赖

## 安装与配置

### 依赖安装

```bash
# PP-StructureV3 (主引擎)
pip install paddleocr>=3.0.0 paddlepaddle>=3.0.0 paddlex[ocr]>=3.0.0

# LayoutParser (可选)
pip install layoutparser
# 注意：需要安装detectron2，参考：https://detectron2.readthedocs.io/tutorials/install.html
```

### 配置说明

在模块配置中设置：

```python
{
    "enabled": True,
    "engine": "ppstructure",  # 或 "layoutparser"
    "use_gpu": False,
    "recovery": True,
    "lang": "ch"
}
```

### 模型准备

PP-Structure模型会在首次使用时自动下载，无需手动准备。

## 使用方法

### 独立使用

```python
from app.modules.layout_analysis import LayoutAnalysisModule

# 初始化模块
module = LayoutAnalysisModule(config={
    "engine": "ppstructure",
    "use_gpu": False
})
module.initialize()

# 处理文档
result = await module.process("document.pdf")
print(result["elements"])  # 布局元素列表
print(result["summary"])   # 文档摘要
```

### API接口说明

- `process(file_path, **kwargs)`: 处理文档
  - `file_path`: PDF或图片文件路径
  - `engine`: 指定引擎（可选）
  - `fallback`: 是否使用备选引擎（默认True）

### 返回结果格式

```json
{
    "engine": "PP-StructureV3",
    "total_pages": 1,
    "elements": [
        {
            "id": "p1_e0",
            "page": 1,
            "type": "title",
            "type_name": "Title",
            "bbox": {"x": 100, "y": 50, "width": 200, "height": 30},
            "confidence": 0.95,
            "text": "文档标题"
        }
    ],
    "page_layouts": [...],
    "summary": {
        "total_elements": 10,
        "type_counts": {"title": 1, "text": 5, "table": 2},
        "has_tables": true,
        "has_figures": false,
        "has_formulas": true
    }
}
```

## 移植指南

### 如何复制到其他项目

1. **复制模块目录**:
   ```
   app/modules/layout_analysis/
   ```

2. **复制基础模块**:
   ```
   app/modules/base/
   ```

3. **安装依赖**:
   ```bash
   pip install paddleocr>=3.0.0 paddlepaddle>=3.0.0 paddlex[ocr]>=3.0.0
   ```

4. **使用模块**:
   ```python
   from modules.layout_analysis import LayoutAnalysisModule
   module = LayoutAnalysisModule()
   module.initialize()
   result = await module.process("file.pdf")
   ```

### 依赖管理

- **必需**: paddleocr>=3.0.0, paddlepaddle>=3.0.0, paddlex[ocr]>=3.0.0
- **可选**: layoutparser, detectron2

### 配置迁移

将配置从旧版本迁移到新模块：

```python
# 旧版本
layout_service = LayoutService(use_gpu=False)
result = await layout_service.analyze("file.pdf", engine="ppstructure")

# 新版本
module = LayoutAnalysisModule(config={"use_gpu": False})
module.initialize()
result = await module.process("file.pdf", engine="ppstructure")
```

## 改进方向

### 性能优化建议

1. **GPU加速**: 启用GPU可显著提升处理速度（5-10倍）
2. **批量处理**: 支持批量文档处理
3. **缓存机制**: 对相同文档缓存结果

### 功能扩展方向

1. **更多元素类型**: 支持更多文档元素类型检测
2. **阅读顺序优化**: 改进元素排序算法
3. **多语言支持**: 扩展语言支持范围

### 已知限制

1. LayoutParser仅支持PDF和图片，不支持其他格式
2. PP-Structure对复杂布局的处理可能需要调整参数
3. 公式识别需要结合Formula Recognition模块使用

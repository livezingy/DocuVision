# 测试文档

## 概述

本目录包含项目的单元测试和集成测试。

## 目录结构

```
tests/
├── __init__.py
├── conftest.py          # Pytest配置和fixtures
├── extractors/          # 提取器测试
│   ├── test_camelot_extractor.py
│   ├── test_pdfplumber_extractor.py
│   └── test_factory.py
├── engines/             # 引擎测试
│   ├── test_easyocr_engine.py
│   ├── test_transformer_engine.py
│   └── test_factory.py
└── processing/          # 处理模块测试（待添加）
```

## 运行测试

### 安装测试依赖

```bash
pip install -r requirements-test.txt
```

### 运行所有测试

```bash
pytest
```

### 运行特定测试文件

```bash
pytest tests/extractors/test_camelot_extractor.py
```

### 运行特定测试类

```bash
pytest tests/extractors/test_camelot_extractor.py::TestCamelotExtractor
```

### 运行特定测试方法

```bash
pytest tests/extractors/test_camelot_extractor.py::TestCamelotExtractor::test_name_property
```

### 运行并生成覆盖率报告

```bash
pytest --cov=core --cov-report=html
```

覆盖率报告将生成在 `htmlcov/index.html`

## 测试标记

使用pytest标记来分类测试：

```python
@pytest.mark.unit
def test_something():
    ...

@pytest.mark.slow
def test_slow_operation():
    ...

@pytest.mark.requires_camelot
def test_camelot_feature():
    ...
```

### 运行特定标记的测试

```bash
# 只运行单元测试
pytest -m unit

# 跳过慢速测试
pytest -m "not slow"

# 运行需要Camelot的测试
pytest -m requires_camelot
```

## 测试Fixtures

在`conftest.py`中定义了以下fixtures：

- `mock_page`: 模拟的pdfplumber.Page对象
- `mock_feature_analyzer`: 模拟的PageFeatureAnalyzer对象
- `sample_image`: 示例PIL Image对象
- `sample_pdf_path`: 示例PDF路径
- `mock_camelot_table`: 模拟的Camelot Table对象
- `mock_pdfplumber_table`: 模拟的PDFPlumber Table对象

## 编写新测试

### 示例：测试提取器

```python
import pytest
from core.extractors.factory import ExtractorFactory

class TestMyExtractor:
    def test_name_property(self):
        extractor = ExtractorFactory.create('camelot')
        assert extractor.name == "camelot"
    
    def test_extract_tables(self, mock_page, mock_feature_analyzer):
        extractor = ExtractorFactory.create('camelot')
        # 测试代码...
```

### 示例：测试引擎

```python
import pytest
from core.engines.factory import EngineFactory

class TestMyEngine:
    def test_recognize_text(self, sample_image):
        engine = EngineFactory.create_ocr('easyocr')
        # 测试代码...
```

## 持续集成

测试可以在CI/CD流程中运行：

```yaml
# .github/workflows/test.yml 示例
- name: Run tests
  run: |
    pip install -r requirements-test.txt
    pytest --cov=core --cov-report=xml
```

## 注意事项

1. **模拟外部依赖**：使用`unittest.mock`模拟外部库（如camelot、easyocr）
2. **避免真实文件**：使用临时文件和模拟对象
3. **测试隔离**：每个测试应该是独立的
4. **性能测试**：标记慢速测试，避免影响开发流程

## 覆盖率目标

- 单元测试覆盖率目标：>80%
- 关键模块覆盖率目标：>90%

# Barcode Recognition Module

## 模块概述

Barcode Recognition模块用于检测和识别文档中的条形码和二维码，支持多种条码格式。模块集成了先进的预处理技术，包括区域检测、图像增强、倾斜校正和多尺度处理，显著提升了识别准确率。

## 使用的模型/库

### 主引擎：PyZBar
- **库**: pyzbar (==0.1.9)
- **底层库**: ZBar
- **支持的格式**:
  - QR Code
  - Code128
  - EAN-13/EAN-8
  - UPC-A/UPC-E
  - Code39
  - ITF
  - DataBar

### 备选引擎：OpenCV
- **库**: opencv-python (==4.8.1.78)
- **限制**: 仅支持QR Code
- **特点**: 轻量级，无需额外系统库

### 预处理技术
- **区域检测**: OpenCV边缘检测和轮廓分析
- **图像增强**: CLAHE对比度增强、锐化、去噪
- **倾斜校正**: Hough变换、轮廓分析、投影分析
- **多尺度处理**: 多尺度缩放识别

## 安装与配置

### 依赖安装

```bash
# PyZBar (主引擎)
pip install pyzbar==0.1.9

# 系统库依赖
# Windows: 下载zbar DLL，参考 https://github.com/mchehab/zbar/releases
# Linux: sudo apt-get install libzbar0
# Mac: brew install zbar

# OpenCV (备选引擎)
pip install opencv-python==4.8.1.78
```

### 配置说明

```python
{
    "enabled": True,
    "engine": "pyzbar",  # 或 "opencv"
    "formats": ["QR_CODE", "CODE128", "EAN13"],  # 可选：过滤特定格式
    
    # 预处理选项（新增）
    "enable_region_detection": True,      # 启用区域检测
    "enable_preprocessing": True,          # 启用图像预处理
    "enable_skew_correction": True,        # 启用倾斜校正
    "enable_multiscale": True,             # 启用多尺度处理
    
    # 预处理参数
    "contrast_clip_limit": 2.0,            # CLAHE对比度限制
    "sharpen_strength": 1.0,               # 锐化强度
    "denoise_strength": 9,                 # 去噪强度（必须为奇数）
    "skew_threshold": 2.0,                 # 倾斜角度阈值（度）
    "multiscale_factors": [0.5, 0.75, 1.0, 1.5, 2.0],  # 多尺度因子
    
    # 区域检测参数
    "region_min_area": 100,                # 最小区域面积
    "region_max_area": 1000000             # 最大区域面积
}
```

## 使用方法

### 独立使用

```python
from app.modules.barcode_recognition import BarcodeRecognitionModule

# 初始化模块（启用所有预处理功能）
module = BarcodeRecognitionModule(config={
    "engine": "pyzbar",
    "formats": ["QR_CODE", "CODE128"],
    "enable_region_detection": True,
    "enable_preprocessing": True,
    "enable_skew_correction": True,
    "enable_multiscale": True
})
module.initialize()

# 处理文档
result = await module.process("document.pdf")
print(result["barcodes"])  # 条码列表
print(result["count"])    # 检测到的条码数量
```

### 预处理流程说明

模块采用智能预处理流程提升识别准确率：

1. **区域检测**（可选）:
   - 使用OpenCV检测QR码和条形码区域
   - 对检测到的区域单独处理，提高效率

2. **图像增强**:
   - CLAHE对比度增强：改善低对比度图像
   - 锐化处理：增强边缘清晰度
   - 双边滤波去噪：减少噪声同时保留边缘

3. **倾斜校正**:
   - 自动检测倾斜角度（Hough变换/轮廓分析）
   - 旋转图像到水平/垂直方向

4. **多尺度处理**:
   - 如果首次识别失败，尝试不同缩放比例
   - 支持0.5x到2.0x的缩放范围

5. **强化处理**:
   - 如果标准预处理失败，应用更强的增强参数
   - 多策略组合尝试

### API接口说明

- `process(file_path, **kwargs)`: 处理文档
  - `file_path`: PDF或图片文件路径
  - `engine`: 指定引擎（可选）
  - `fallback`: 是否使用备选引擎（默认True）

### 返回结果格式

```json
{
    "barcodes": [
        {
            "id": "barcode_p1_0",
            "page": 1,
            "type": "QRCODE",
            "data": "https://example.com",
            "format": "QR_CODE",
            "bbox": {"x": 100, "y": 200, "width": 150, "height": 150},
            "polygon": [{"x": 100, "y": 200}, ...],
            "confidence": 1.0,
            "engine": "PyZBar"
        }
    ],
    "count": 1,
    "module": "barcode_recognition"
}
```

## 移植指南

### 如何复制到其他项目

1. **复制模块目录**:
   ```
   app/modules/barcode_recognition/
   app/modules/base/
   ```

2. **安装依赖**:
   ```bash
   pip install pyzbar opencv-python
   # 安装系统库zbar
   ```

3. **使用模块**:
   ```python
   from modules.barcode_recognition import BarcodeRecognitionModule
   module = BarcodeRecognitionModule()
   module.initialize()
   result = await module.process("file.pdf")
   ```

## 预处理功能详解

### 区域检测

**QR码检测**:
- 使用OpenCV的`QRCodeDetector.detectAndDecodeMulti()`
- 可以同时检测多个QR码区域
- 返回检测框和置信度

**条形码检测**:
- 基于Canny边缘检测
- 轮廓查找和筛选
- 筛选条件：
  - 长宽比 > 2:1（条形码特征）
  - 面积在合理范围内
  - 轮廓近似为矩形

### 图像增强

**CLAHE对比度增强**:
- 自适应直方图均衡化
- 改善低对比度图像的识别率
- 可配置clip_limit参数

**锐化处理**:
- 使用Unsharp Masking技术
- 增强条码边缘清晰度
- 可配置锐化强度

**去噪处理**:
- 双边滤波：保留边缘的同时减少噪声
- 非局部均值去噪（可选）
- 可配置去噪强度

### 倾斜校正

**角度检测方法**:
1. Hough直线变换：检测主要直线方向
2. 最小外接矩形：计算轮廓角度
3. 投影分析：分析水平/垂直投影

**校正方法**:
- 旋转图像到水平/垂直
- 保持原始分辨率
- 使用双线性插值避免锯齿

### 多尺度处理

**处理策略**:
- 默认尝试5个尺度：0.5x, 0.75x, 1.0x, 1.5x, 2.0x
- 优先使用原始尺寸（1.0x）
- 失败后依次尝试其他尺度
- 上采样使用INTER_CUBIC，下采样使用INTER_AREA

## 改进方向

### 性能优化建议

1. **智能区域检测**: 只在全图识别失败时启用区域检测
2. **预处理缓存**: 缓存预处理结果，避免重复计算
3. **并行处理**: 多区域并行处理
4. **早期退出**: 识别成功后立即返回

### 功能扩展方向

1. **深度学习模型**: 集成YOLO等目标检测模型进行区域检测
2. **更多预处理方法**: 添加更多图像增强技术
3. **置信度评估**: 实现条码识别置信度评估
4. **批量识别优化**: 优化批量文档处理性能

### 已知限制

1. PyZBar需要系统库zbar支持
2. OpenCV仅支持QR Code（备选引擎）
3. 区域检测可能产生误检，需要后续验证
4. 预处理会增加处理时间，但显著提升准确率
5. 极端倾斜（>45度）可能无法正确校正

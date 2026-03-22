"""
Barcode Recognition Module Configuration
"""

from pydantic import BaseModel
from typing import List


class BarcodeRecognitionConfig(BaseModel):
    """Barcode Recognition模块配置"""
    enabled: bool = True
    engine: str = "pyzbar"  # pyzbar, opencv
    formats: List[str] = ["QR_CODE", "CODE128", "EAN13", "EAN8", "UPC_A", "UPC_E", "CODE39", "ITF", "DATABAR"]
    
    # 预处理选项
    enable_region_detection: bool = True      # 启用区域检测
    enable_preprocessing: bool = True          # 启用预处理
    enable_skew_correction: bool = True        # 启用倾斜校正
    enable_multiscale: bool = True             # 启用多尺度处理
    
    # 预处理参数
    contrast_clip_limit: float = 2.0           # CLAHE对比度限制
    sharpen_strength: float = 1.0              # 锐化强度
    denoise_strength: int = 9                   # 去噪强度
    skew_threshold: float = 2.0                 # 倾斜角度阈值（度）
    multiscale_factors: List[float] = [0.5, 0.75, 1.0, 1.5, 2.0]  # 多尺度因子
    
    # 区域检测参数
    region_min_area: int = 100                  # 最小区域面积
    region_max_area: int = 1000000             # 最大区域面积
    
    class Config:
        extra = "allow"

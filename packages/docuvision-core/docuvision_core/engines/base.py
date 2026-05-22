# core/engines/base.py
"""
OCR/检测引擎基�?

定义所有OCR和检测引擎必须实现的接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from PIL import Image
import numpy as np


class BaseOCREngine(ABC):
    """OCR引擎基类"""
    
    @abstractmethod
    def recognize_text(self, image: Image.Image, **kwargs) -> List[Dict]:
        """
        识别文本
        
        Args:
            image: PIL Image对象
            **kwargs: 其他参数（如语言、置信度阈值等�?
            
        Returns:
            List[Dict]: OCR结果列表，每个元素包含：
                - text: 文本内容
                - bbox: 边界�?[x1, y1, x2, y2] �?[[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                - confidence: 置信�?(0-1)
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """引擎名称"""
        pass
    
    def initialize(self, **kwargs) -> bool:
        """
        初始化引擎（可选实现）
        
        Args:
            **kwargs: 初始化参�?
            
        Returns:
            bool: 初始化是否成�?
        """
        return True
    
    def is_available(self) -> bool:
        """
        检查引擎是否可用（可选实现）
        
        Returns:
            bool: 引擎是否可用
        """
        return True


class BaseDetectionEngine(ABC):
    """表格检测引擎基�?""
    
    @abstractmethod
    def detect_tables(self, image: Image.Image, **kwargs) -> List[Dict]:
        """
        检测表�?
        
        Args:
            image: PIL Image对象
            **kwargs: 其他参数（如置信度阈值等�?
            
        Returns:
            List[Dict]: 检测结果列表，每个元素包含�?
                - bbox: 边界�?[x1, y1, x2, y2]
                - confidence: 置信�?(0-1)
                - 其他检测相关信�?
        """
        pass
    
    @abstractmethod
    def recognize_structure(self, image: Image.Image, table_bbox: Optional[List] = None, **kwargs) -> Dict:
        """
        识别表格结构
        
        Args:
            image: PIL Image对象（表格区域）
            table_bbox: 表格边界�?[x1, y1, x2, y2]（可选）
            **kwargs: 其他参数
            
        Returns:
            Dict: 结构识别结果，包含：
                - cells: 单元格列�?
                - rows: 行信�?
                - columns: 列信�?
                - 其他结构信息
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """引擎名称"""
        pass
    
    def load_models(self, **kwargs) -> bool:
        """
        加载模型（可选实现）
        
        Args:
            **kwargs: 模型配置参数
            
        Returns:
            bool: 加载是否成功
        """
        return True
    
    def is_available(self) -> bool:
        """
        检查引擎是否可用（可选实现）
        
        Returns:
            bool: 引擎是否可用
        """
        return True

# core/extractors/base.py
"""
表格提取器基籀

定义所有表格提取器必须实现的接又
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class BaseExtractor(ABC):
    """表格提取器基籀"""
    
    @abstractmethod
    def extract_tables(self, page, feature_analyzer, params: Dict) -> List[Dict]:
        """
        提取表格
        
        Args:
            page: pdfplumber.Page对象
            feature_analyzer: PageFeatureAnalyzer实例
            params: 参数字典，包含：
                - flavor: 提取模式（如'lattice', 'stream', 'lines', 'text'！
                - param_mode: 参数模式！default', 'auto', 'custom'！
                - custom_params: 自定义参数（当param_mode='custom'时使用）
                - score_threshold: 评分阈倀
                - 其他提取器特定参敀
            
        Returns:
            List[Dict]: 表格结果列表，每个元素包含：
                - table: 表格对象
                - bbox: 边界桀[x0, y0, x1, y1]
                - score: 评分 (0-1)
                - details: 详细信息字典
                - domain: 表格域类垀
                - source: 来源标识（如'camelot_lattice', 'pdfplumber_lines'！
        """
        pass
    
    @abstractmethod
    def calculate_params(self, feature_analyzer, table_type: str, **kwargs) -> Dict:
        """
        计算参数
        
        Args:
            feature_analyzer: PageFeatureAnalyzer实例
            table_type: 'bordered' 成'unbordered'
            **kwargs: 其他参数（如image_shape用于Camelot lattice！
            
        Returns:
            Dict: 参数字典
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """提取器名秀"""
        pass
    
    @property
    @abstractmethod
    def supported_flavors(self) -> List[str]:
        """支持的flavor列表"""
        pass
    
    def validate_params(self, params: Dict) -> Dict:
        """
        验证和修正参数（可选实现）
        
        Args:
            params: 参数字典
            
        Returns:
            Dict: 验证后的参数字典
        """
        return params

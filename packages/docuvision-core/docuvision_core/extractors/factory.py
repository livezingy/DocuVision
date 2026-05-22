# core/extractors/factory.py
"""
提取器工厂类

用于创建和管理表格提取器实例
"""

from typing import Dict, List, Type
from docuvision_core.extractors.base import BaseExtractor
from docuvision_core.utils.logger import AppLogger


class ExtractorFactory:
    """提取器工厂类"""
    
    _extractors: Dict[str, Type[BaseExtractor]] = {}
    _logger = AppLogger.get_logger()
    
    @classmethod
    def register(cls, name: str, extractor_class: Type[BaseExtractor]):
        """
        注册提取�?
        
        Args:
            name: 提取器名称（�?camelot', 'pdfplumber'�?
            extractor_class: 提取器类（必须继承BaseExtractor�?
        """
        if not issubclass(extractor_class, BaseExtractor):
            raise TypeError(f"Extractor class must inherit from BaseExtractor")
        
        name_lower = name.lower()
        cls._extractors[name_lower] = extractor_class
        cls._logger.debug(f"Registered extractor: {name_lower}")
    
    @classmethod
    def create(cls, name: str, **kwargs) -> BaseExtractor:
        """
        创建提取器实�?
        
        Args:
            name: 提取器名�?
            **kwargs: 传递给提取器构造函数的参数
            
        Returns:
            BaseExtractor: 提取器实�?
            
        Raises:
            ValueError: 如果提取器未注册
        """
        name_lower = name.lower()
        if name_lower not in cls._extractors:
            available = ', '.join(cls._extractors.keys())
            raise ValueError(
                f"Unknown extractor: {name}. "
                f"Available extractors: {available}"
            )
        
        extractor_class = cls._extractors[name_lower]
        return extractor_class(**kwargs)
    
    @classmethod
    def list_available(cls) -> List[str]:
        """
        列出可用的提取器
        
        Returns:
            List[str]: 提取器名称列�?
        """
        return list(cls._extractors.keys())
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """
        检查提取器是否已注�?
        
        Args:
            name: 提取器名�?
            
        Returns:
            bool: 是否已注�?
        """
        return name.lower() in cls._extractors

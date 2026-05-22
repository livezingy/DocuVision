# core/engines/factory.py
"""
引擎工厂籀

用于创建和管理OCR和检测引擎实侀
"""

from typing import Dict, List, Type, Optional
from docuvision_core.engines.base import BaseOCREngine, BaseDetectionEngine
from docuvision_core.utils.logger import AppLogger


class EngineFactory:
    """引擎工厂籀"""
    
    _ocr_engines: Dict[str, Type[BaseOCREngine]] = {}
    _detection_engines: Dict[str, Type[BaseDetectionEngine]] = {}
    _logger = AppLogger.get_logger()
    
    @classmethod
    def register_ocr(cls, name: str, engine_class: Type[BaseOCREngine]):
        """
        注册OCR引擎
        
        Args:
            name: 引擎名称（如'easyocr', 'tesseract'！
            engine_class: 引擎类（必须继承BaseOCREngine！
        """
        if not issubclass(engine_class, BaseOCREngine):
            raise TypeError(f"OCR engine class must inherit from BaseOCREngine")
        
        name_lower = name.lower()
        cls._ocr_engines[name_lower] = engine_class
        cls._logger.debug(f"Registered OCR engine: {name_lower}")
    
    @classmethod
    def register_detection(cls, name: str, engine_class: Type[BaseDetectionEngine]):
        """
        注册检测引擀
        
        Args:
            name: 引擎名称（如'transformer'！
            engine_class: 引擎类（必须继承BaseDetectionEngine！
        """
        if not issubclass(engine_class, BaseDetectionEngine):
            raise TypeError(f"Detection engine class must inherit from BaseDetectionEngine")
        
        name_lower = name.lower()
        cls._detection_engines[name_lower] = engine_class
        cls._logger.debug(f"Registered detection engine: {name_lower}")
    
    @classmethod
    def create_ocr(cls, name: str, **kwargs) -> BaseOCREngine:
        """
        创建OCR引擎实例
        
        Args:
            name: 引擎名称
            **kwargs: 传递给引擎构造函数的参数
            
        Returns:
            BaseOCREngine: OCR引擎实例
            
        Raises:
            ValueError: 如果引擎未注军
        """
        name_lower = name.lower()
        if name_lower not in cls._ocr_engines:
            available = ', '.join(cls._ocr_engines.keys())
            raise ValueError(
                f"Unknown OCR engine: {name}. "
                f"Available OCR engines: {available}"
            )
        
        engine_class = cls._ocr_engines[name_lower]
        return engine_class(**kwargs)
    
    @classmethod
    def create_detection(cls, name: str, **kwargs) -> BaseDetectionEngine:
        """
        创建检测引擎实侀
        
        Args:
            name: 引擎名称
            **kwargs: 传递给引擎构造函数的参数
            
        Returns:
            BaseDetectionEngine: 检测引擎实侀
            
        Raises:
            ValueError: 如果引擎未注军
        """
        name_lower = name.lower()
        if name_lower not in cls._detection_engines:
            available = ', '.join(cls._detection_engines.keys())
            raise ValueError(
                f"Unknown detection engine: {name}. "
                f"Available detection engines: {available}"
            )
        
        engine_class = cls._detection_engines[name_lower]
        return engine_class(**kwargs)
    
    @classmethod
    def list_available_ocr(cls) -> List[str]:
        """
        列出可用的OCR引擎
        
        Returns:
            List[str]: OCR引擎名称列表
        """
        return list(cls._ocr_engines.keys())
    
    @classmethod
    def list_available_detection(cls) -> List[str]:
        """
        列出可用的检测引擀
        
        Returns:
            List[str]: 检测引擎名称列行
        """
        return list(cls._detection_engines.keys())
    
    @classmethod
    def is_ocr_registered(cls, name: str) -> bool:
        """
        检查OCR引擎是否已注军
        
        Args:
            name: 引擎名称
            
        Returns:
            bool: 是否已注军
        """
        return name.lower() in cls._ocr_engines
    
    @classmethod
    def is_detection_registered(cls, name: str) -> bool:
        """
        检查检测引擎是否已注册
        
        Args:
            name: 引擎名称
            
        Returns:
            bool: 是否已注军
        """
        return name.lower() in cls._detection_engines

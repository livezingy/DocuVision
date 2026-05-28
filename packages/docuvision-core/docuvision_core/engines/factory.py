# core/engines/factory.py
"""factory module."""

from typing import Dict, List, Type, Optional
from docuvision_core.engines.base import BaseOCREngine, BaseDetectionEngine
from docuvision_core.utils.logger import AppLogger


class EngineFactory:
    """Docstring."""
    
    _ocr_engines: Dict[str, Type[BaseOCREngine]] = {}
    _detection_engines: Dict[str, Type[BaseDetectionEngine]] = {}
    _logger = AppLogger.get_logger()

    @classmethod
    def _ensure_registered(cls) -> None:
        from docuvision_core.engines import _lazy_register

        _lazy_register()
    
    @classmethod
    def register_ocr(cls, name: str, engine_class: Type[BaseOCREngine]):
        """Docstring."""
        if not issubclass(engine_class, BaseOCREngine):
            raise TypeError(f"OCR engine class must inherit from BaseOCREngine")
        
        name_lower = name.lower()
        cls._ocr_engines[name_lower] = engine_class
        cls._logger.debug(f"Registered OCR engine: {name_lower}")
    
    @classmethod
    def register_detection(cls, name: str, engine_class: Type[BaseDetectionEngine]):
        """Docstring."""
        if not issubclass(engine_class, BaseDetectionEngine):
            raise TypeError(f"Detection engine class must inherit from BaseDetectionEngine")
        
        name_lower = name.lower()
        cls._detection_engines[name_lower] = engine_class
        cls._logger.debug(f"Registered detection engine: {name_lower}")
    
    @classmethod
    def create_ocr(cls, name: str, **kwargs) -> BaseOCREngine:
        """Docstring."""
        cls._ensure_registered()
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
        """Docstring."""
        cls._ensure_registered()
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
        """Docstring."""
        cls._ensure_registered()
        return list(cls._ocr_engines.keys())
    
    @classmethod
    def list_available_detection(cls) -> List[str]:
        """Docstring."""
        cls._ensure_registered()
        return list(cls._detection_engines.keys())
    
    @classmethod
    def is_ocr_registered(cls, name: str) -> bool:
        """Docstring."""
        cls._ensure_registered()
        return name.lower() in cls._ocr_engines
    
    @classmethod
    def is_detection_registered(cls, name: str) -> bool:
        """Docstring."""
        cls._ensure_registered()
        return name.lower() in cls._detection_engines

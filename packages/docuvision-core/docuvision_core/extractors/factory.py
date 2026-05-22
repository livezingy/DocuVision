# core/extractors/factory.py
"""factory module."""

from typing import Dict, List, Type
from docuvision_core.extractors.base import BaseExtractor
from docuvision_core.utils.logger import AppLogger


class ExtractorFactory:
    """Docstring."""
    
    _extractors: Dict[str, Type[BaseExtractor]] = {}
    _logger = AppLogger.get_logger()
    
    @classmethod
    def register(cls, name: str, extractor_class: Type[BaseExtractor]):
        """Docstring."""
        if not issubclass(extractor_class, BaseExtractor):
            raise TypeError(f"Extractor class must inherit from BaseExtractor")
        
        name_lower = name.lower()
        cls._extractors[name_lower] = extractor_class
        cls._logger.debug(f"Registered extractor: {name_lower}")
    
    @classmethod
    def create(cls, name: str, **kwargs) -> BaseExtractor:
        """Docstring."""
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
        """Docstring."""
        return list(cls._extractors.keys())
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Docstring."""
        return name.lower() in cls._extractors

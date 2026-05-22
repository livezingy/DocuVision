# core/extractors/base.py
"""base module."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class BaseExtractor(ABC):
    """Docstring."""
    
    @abstractmethod
    def extract_tables(self, page, feature_analyzer, params: Dict) -> List[Dict]:
        """Docstring."""
        pass
    
    @abstractmethod
    def calculate_params(self, feature_analyzer, table_type: str, **kwargs) -> Dict:
        """Docstring."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Docstring."""
        pass
    
    @property
    @abstractmethod
    def supported_flavors(self) -> List[str]:
        """Docstring."""
        pass
    
    def validate_params(self, params: Dict) -> Dict:
        """Docstring."""
        return params

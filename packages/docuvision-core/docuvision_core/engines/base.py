# core/engines/base.py
"""base module."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from PIL import Image
import numpy as np


class BaseOCREngine(ABC):
    """Docstring."""
    
    @abstractmethod
    def recognize_text(self, image: Image.Image, **kwargs) -> List[Dict]:
        """Docstring."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Docstring."""
        pass
    
    def initialize(self, **kwargs) -> bool:
        """Docstring."""
        return True
    
    def is_available(self) -> bool:
        """Docstring."""
        return True


class BaseDetectionEngine(ABC):
    """Docstring."""
    
    @abstractmethod
    def detect_tables(self, image: Image.Image, **kwargs) -> List[Dict]:
        """Docstring."""
        pass
    
    @abstractmethod
    def recognize_structure(self, image: Image.Image, table_bbox: Optional[List] = None, **kwargs) -> Dict:
        """Docstring."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Docstring."""
        pass
    
    def load_models(self, **kwargs) -> bool:
        """Docstring."""
        return True
    
    def is_available(self) -> bool:
        """Docstring."""
        return True

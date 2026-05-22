# core/engines/easyocr_engine.py
"""easyocr engine module."""

import numpy as np
from typing import Dict, List, Optional, Any
from PIL import Image
from docuvision_core.engines.base import BaseOCREngine
from docuvision_core.utils.easyocr_config import get_easyocr_reader, get_easyocr_config
from docuvision_core.utils.logger import AppLogger


class EasyOCREngine(BaseOCREngine):
    """Docstring."""
    
    def __init__(self, languages: List[str] = None, gpu: bool = False, **kwargs):
        """Docstring."""
        self.logger = AppLogger.get_logger()
        self.languages = languages or ['en']
        self.gpu = gpu
        self._reader = None
        # Comment.
        self._config = None
        self._initialized = False
    
    def _get_config(self):
        """Docstring."""
        if self._config is None:
            self._config = get_easyocr_config()
        return self._config
    
    @property
    def name(self) -> str:
        """Docstring."""
        return "easyocr"
    
    def initialize(self, **kwargs) -> bool:
        """Docstring."""
        if self._initialized and self._reader is not None:
            return True
        
        try:
            languages = kwargs.get('languages', self.languages)
            gpu = kwargs.get('gpu', self.gpu)
            
            # Comment.
            self._get_config()
            
            self._reader = get_easyocr_reader(languages, gpu)
            self._initialized = True
            self.logger.info(f"EasyOCR engine initialized with languages: {languages}, GPU: {gpu}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize EasyOCR engine: {e}")
            return False
    
    def recognize_text(self, image: Image.Image, **kwargs) -> List[Dict]:
        """Docstring."""
        if not self._initialized:
            if not self.initialize():
                return []
        
        if self._reader is None:
            self.logger.error("EasyOCR reader is not available")
            return []
        
        try:
            # Comment.
            img_array = np.array(image)
            
            # Comment.
            min_confidence = kwargs.get('min_confidence', 0.0)
            ocr_results = self._reader.readtext(img_array)
            
            # Comment.
            results = []
            for item in ocr_results:
                bbox_points = item[0]  # List of 4 corner points
                text = item[1]         # Text content
                confidence = item[2]   # Confidence score
                
                # Comment.
                if confidence < min_confidence:
                    continue
                
                # Comment.
                x_coords = [point[0] for point in bbox_points]
                y_coords = [point[1] for point in bbox_points]
                x1, x2 = min(x_coords), max(x_coords)
                y1, y2 = min(y_coords), max(y_coords)
                
                results.append({
                    'text': text,
                    'bbox': bbox_points,
                    'bbox_rect': [x1, y1, x2, y2],
                    'confidence': float(confidence)
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"EasyOCR recognition failed: {e}")
            return []
    
    def get_reader(self):
        """Docstring."""
        if not self._initialized:
            self.initialize()
        return self._reader
    
    def is_available(self) -> bool:
        """Docstring."""
        try:
            import easyocr
            return True
        except ImportError:
            return False
    
    def recognize_text_in_region(self, image: Image.Image, bbox: List, **kwargs) -> List[Dict]:
        """Docstring."""
        try:
            # Comment.
            x1, y1, x2, y2 = bbox
            cropped = image.crop((x1, y1, x2, y2))
            
            # Comment.
            results = self.recognize_text(cropped, **kwargs)
            
            # Comment.
            for result in results:
                if 'bbox' in result:
                    # Comment.
                    adjusted_bbox = []
                    for point in result['bbox']:
                        adjusted_bbox.append([point[0] + x1, point[1] + y1])
                    result['bbox'] = adjusted_bbox
                
                if 'bbox_rect' in result:
                    # Comment.
                    rect = result['bbox_rect']
                    result['bbox_rect'] = [rect[0] + x1, rect[1] + y1, rect[2] + x1, rect[3] + y1]
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to recognize text in region: {e}")
            return []

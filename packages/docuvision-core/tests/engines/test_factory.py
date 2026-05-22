# tests/engines/test_factory.py
"""test factory module."""

import pytest
from unittest.mock import Mock
import sys
from pathlib import Path

#
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from docuvision_core.engines.factory import EngineFactory
from docuvision_core.engines.base import BaseOCREngine, BaseDetectionEngine
from docuvision_core.engines.easyocr_engine import EasyOCREngine
from docuvision_core.engines.transformer_engine import TransformerEngine


class TestEngineFactory:
    
    def test_list_available_ocr(self):
        available = EngineFactory.list_available_ocr()
        assert 'easyocr' in available
    
    def test_list_available_detection(self):
        available = EngineFactory.list_available_detection()
        assert 'transformer' in available
    
    def test_is_ocr_registered(self):
        assert EngineFactory.is_ocr_registered('easyocr') is True
        assert EngineFactory.is_ocr_registered('nonexistent') is False
    
    def test_is_detection_registered(self):
        assert EngineFactory.is_detection_registered('transformer') is True
        assert EngineFactory.is_detection_registered('nonexistent') is False
    
    def test_create_ocr_easyocr(self):
        engine = EngineFactory.create_ocr('easyocr')
        assert isinstance(engine, EasyOCREngine)
    
    def test_create_detection_transformer(self):
        engine = EngineFactory.create_detection('transformer')
        assert isinstance(engine, TransformerEngine)
    
    def test_create_unknown_ocr(self):
        with pytest.raises(ValueError, match="Unknown OCR engine"):
            EngineFactory.create_ocr('unknown')
    
    def test_create_unknown_detection(self):
        with pytest.raises(ValueError, match="Unknown detection engine"):
            EngineFactory.create_detection('unknown')
    
    def test_register_custom_ocr(self):
        class CustomOCREngine(BaseOCREngine):
            def recognize_text(self, image, **kwargs):
                return []
            
            @property
            def name(self):
                return "custom_ocr"
        
        EngineFactory.register_ocr('custom_ocr', CustomOCREngine)
        assert EngineFactory.is_ocr_registered('custom_ocr')
        
        engine = EngineFactory.create_ocr('custom_ocr')
        assert isinstance(engine, CustomOCREngine)
        
        #
        del EngineFactory._ocr_engines['custom_ocr']
    
    def test_register_custom_detection(self):
        class CustomDetectionEngine(BaseDetectionEngine):
            def detect_tables(self, image, **kwargs):
                return []
            
            def recognize_structure(self, image, table_bbox=None, **kwargs):
                return {}
            
            @property
            def name(self):
                return "custom_detection"
        
        EngineFactory.register_detection('custom_detection', CustomDetectionEngine)
        assert EngineFactory.is_detection_registered('custom_detection')
        
        engine = EngineFactory.create_detection('custom_detection')
        assert isinstance(engine, CustomDetectionEngine)
        
        #
        del EngineFactory._detection_engines['custom_detection']

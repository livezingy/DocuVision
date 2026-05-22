# tests/engines/test_easyocr_engine.py
"""test easyocr engine module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path
import numpy as np
from PIL import Image

#
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from docuvision_core.engines.easyocr_engine import EasyOCREngine
from docuvision_core.engines.factory import EngineFactory


class TestEasyOCREngine:
    
    def test_name_property(self):
        engine = EasyOCREngine()
        assert engine.name == "easyocr"
    
    @patch('docuvision_core.engines.easyocr_engine.get_easyocr_reader')
    def test_initialize_success(self, mock_get_reader):
        mock_reader = Mock()
        mock_get_reader.return_value = mock_reader
        
        engine = EasyOCREngine(languages=['en'], gpu=False)
        result = engine.initialize()
        
        assert result is True
        assert engine._initialized is True
        assert engine._reader is not None
    
    @patch('docuvision_core.engines.easyocr_engine.get_easyocr_reader')
    def test_initialize_failure(self, mock_get_reader):
        mock_get_reader.side_effect = Exception("Failed to initialize")
        
        engine = EasyOCREngine()
        result = engine.initialize()
        
        assert result is False
    
    @patch('docuvision_core.engines.easyocr_engine.get_easyocr_reader')
    def test_recognize_text_success(self, mock_get_reader, sample_image):
        #
        mock_reader = Mock()
        mock_reader.readtext.return_value = [
            ([[10, 10], [100, 10], [100, 30], [10, 30]], 'Hello', 0.95),
            ([[10, 40], [100, 40], [100, 60], [10, 60]], 'World', 0.90)
        ]
        mock_get_reader.return_value = mock_reader
        
        engine = EasyOCREngine()
        engine._reader = mock_reader
        engine._initialized = True
        
        results = engine.recognize_text(sample_image, min_confidence=0.5)
        
        assert len(results) == 2
        assert results[0]['text'] == 'Hello'
        assert results[0]['confidence'] == 0.95
        assert 'bbox' in results[0]
        assert 'bbox_rect' in results[0]
    
    @patch('docuvision_core.engines.easyocr_engine.get_easyocr_reader')
    def test_recognize_text_min_confidence_filter(self, mock_get_reader, sample_image):
        #
        mock_reader = Mock()
        mock_reader.readtext.return_value = [
            ([[10, 10], [100, 10], [100, 30], [10, 30]], 'High', 0.95),
            ([[10, 40], [100, 40], [100, 60], [10, 60]], 'Low', 0.30)
        ]
        mock_get_reader.return_value = mock_reader
        
        engine = EasyOCREngine()
        engine._reader = mock_reader
        engine._initialized = True
        
        results = engine.recognize_text(sample_image, min_confidence=0.5)
        
        assert len(results) == 1
        assert results[0]['text'] == 'High'
    
    @patch('docuvision_core.engines.easyocr_engine.get_easyocr_reader')
    def test_recognize_text_in_region(self, mock_get_reader, sample_image):
        mock_reader = Mock()
        mock_reader.readtext.return_value = [
            ([[5, 5], [50, 5], [50, 15], [5, 15]], 'Text', 0.95)
        ]
        mock_get_reader.return_value = mock_reader
        
        engine = EasyOCREngine()
        engine._reader = mock_reader
        engine._initialized = True
        
        #
        results = engine.recognize_text_in_region(
            sample_image,
            bbox=[100, 100, 200, 200],
            min_confidence=0.5
        )
        
        assert len(results) > 0
        #
        assert results[0]['bbox_rect'][0] >= 100
    
    def test_is_available(self):
        with patch('docuvision_core.engines.easyocr_engine.easyocr', create=True):
            engine = EasyOCREngine()
            assert engine.is_available() is True
        
        with patch.dict('sys.modules', {'easyocr': None}):
            engine = EasyOCREngine()
            #
            #
    
    def test_get_reader(self):
        mock_reader = Mock()
        engine = EasyOCREngine()
        engine._reader = mock_reader
        engine._initialized = True
        
        reader = engine.get_reader()
        assert reader is mock_reader
    
    def test_factory_registration(self):
        assert EngineFactory.is_ocr_registered('easyocr')
        engine = EngineFactory.create_ocr('easyocr')
        assert isinstance(engine, EasyOCREngine)

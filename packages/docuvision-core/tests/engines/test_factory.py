# tests/engines/test_factory.py
"""
EngineFactory单元测试
"""

import pytest
from unittest.mock import Mock
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from docuvision_core.engines.factory import EngineFactory
from docuvision_core.engines.base import BaseOCREngine, BaseDetectionEngine
from docuvision_core.engines.easyocr_engine import EasyOCREngine
from docuvision_core.engines.transformer_engine import TransformerEngine


class TestEngineFactory:
    """EngineFactory测试类"""
    
    def test_list_available_ocr(self):
        """测试列出可用OCR引擎"""
        available = EngineFactory.list_available_ocr()
        assert 'easyocr' in available
    
    def test_list_available_detection(self):
        """测试列出可用检测引擎"""
        available = EngineFactory.list_available_detection()
        assert 'transformer' in available
    
    def test_is_ocr_registered(self):
        """测试检查OCR引擎注册状态"""
        assert EngineFactory.is_ocr_registered('easyocr') is True
        assert EngineFactory.is_ocr_registered('nonexistent') is False
    
    def test_is_detection_registered(self):
        """测试检查检测引擎注册状态"""
        assert EngineFactory.is_detection_registered('transformer') is True
        assert EngineFactory.is_detection_registered('nonexistent') is False
    
    def test_create_ocr_easyocr(self):
        """测试创建EasyOCR引擎"""
        engine = EngineFactory.create_ocr('easyocr')
        assert isinstance(engine, EasyOCREngine)
    
    def test_create_detection_transformer(self):
        """测试创建Transformer引擎"""
        engine = EngineFactory.create_detection('transformer')
        assert isinstance(engine, TransformerEngine)
    
    def test_create_unknown_ocr(self):
        """测试创建未知OCR引擎"""
        with pytest.raises(ValueError, match="Unknown OCR engine"):
            EngineFactory.create_ocr('unknown')
    
    def test_create_unknown_detection(self):
        """测试创建未知检测引擎"""
        with pytest.raises(ValueError, match="Unknown detection engine"):
            EngineFactory.create_detection('unknown')
    
    def test_register_custom_ocr(self):
        """测试注册自定义OCR引擎"""
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
        
        # 清理
        del EngineFactory._ocr_engines['custom_ocr']
    
    def test_register_custom_detection(self):
        """测试注册自定义检测引擎"""
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
        
        # 清理
        del EngineFactory._detection_engines['custom_detection']

# tests/extractors/test_factory.py
"""
ExtractorFactory单元测试
"""

import pytest
from unittest.mock import Mock
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from docuvision_core.extractors.factory import ExtractorFactory
from docuvision_core.extractors.base import BaseExtractor
from docuvision_core.extractors.camelot_extractor import CamelotExtractor
from docuvision_core.extractors.pdfplumber_extractor import PDFPlumberExtractor


class TestExtractorFactory:
    """ExtractorFactory测试�?""
    
    def test_list_available(self):
        """测试列出可用提取�?""
        available = ExtractorFactory.list_available()
        assert 'camelot' in available
        assert 'pdfplumber' in available
    
    def test_is_registered(self):
        """测试检查注册状�?""
        assert ExtractorFactory.is_registered('camelot') is True
        assert ExtractorFactory.is_registered('pdfplumber') is True
        assert ExtractorFactory.is_registered('nonexistent') is False
    
    def test_create_camelot(self):
        """测试创建Camelot提取�?""
        extractor = ExtractorFactory.create('camelot')
        assert isinstance(extractor, CamelotExtractor)
    
    def test_create_pdfplumber(self):
        """测试创建PDFPlumber提取�?""
        extractor = ExtractorFactory.create('pdfplumber')
        assert isinstance(extractor, PDFPlumberExtractor)
    
    def test_create_unknown_extractor(self):
        """测试创建未知提取�?""
        with pytest.raises(ValueError, match="Unknown extractor"):
            ExtractorFactory.create('unknown')
    
    def test_register_custom_extractor(self):
        """测试注册自定义提取器"""
        class CustomExtractor(BaseExtractor):
            def extract_tables(self, page, feature_analyzer, params):
                return []
            
            def calculate_params(self, feature_analyzer, table_type, **kwargs):
                return {}
            
            @property
            def name(self):
                return "custom"
            
            @property
            def supported_flavors(self):
                return ['custom']
        
        ExtractorFactory.register('custom', CustomExtractor)
        assert ExtractorFactory.is_registered('custom')
        
        extractor = ExtractorFactory.create('custom')
        assert isinstance(extractor, CustomExtractor)
        
        # 清理
        del ExtractorFactory._extractors['custom']

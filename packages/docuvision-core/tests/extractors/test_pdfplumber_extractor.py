# tests/extractors/test_pdfplumber_extractor.py
"""
PDFPlumberExtractor单元测试
"""

import pytest
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from docuvision_core.extractors.pdfplumber_extractor import PDFPlumberExtractor
from docuvision_core.extractors.factory import ExtractorFactory


class TestPDFPlumberExtractor:
    """PDFPlumberExtractor测试�?""
    
    def test_name_property(self):
        """测试name属�?""
        extractor = PDFPlumberExtractor()
        assert extractor.name == "pdfplumber"
    
    def test_supported_flavors(self):
        """测试supported_flavors属�?""
        extractor = PDFPlumberExtractor()
        flavors = extractor.supported_flavors
        assert 'lines' in flavors
        assert 'text' in flavors
        assert len(flavors) == 2
    
    @patch('core.extractors.pdfplumber_extractor.TableParamsCalculator')
    def test_calculate_params(self, mock_calculator_class, mock_feature_analyzer):
        """测试计算参数"""
        extractor = PDFPlumberExtractor()
        
        # 模拟计算�?
        mock_calculator = Mock()
        mock_calculator.get_pdfplumber_params.return_value = {
            'snap_tolerance': 2.0,
            'join_tolerance': 2.0,
            'vertical_strategy': 'lines',
            'horizontal_strategy': 'lines'
        }
        mock_calculator_class.return_value = mock_calculator
        
        # 测试计算参数
        params = extractor.calculate_params(mock_feature_analyzer, 'bordered')
        
        assert 'snap_tolerance' in params
        mock_calculator.get_pdfplumber_params.assert_called_once_with('bordered')
    
    @patch('core.extractors.pdfplumber_extractor.TableEvaluator')
    def test_extract_lines_success(self, mock_evaluator_class, mock_page, mock_feature_analyzer, mock_pdfplumber_table):
        """测试lines模式提取成功"""
        extractor = PDFPlumberExtractor()
        
        # 模拟page.find_tables
        mock_page.find_tables.return_value = [mock_pdfplumber_table]
        
        # 模拟评估�?
        mock_evaluator = Mock()
        mock_evaluator.evaluate.return_value = (0.85, {'accuracy': 0.9}, 'unstructured')
        mock_evaluator_class.return_value = mock_evaluator
        
        # 模拟参数计算
        with patch.object(extractor, 'calculate_params') as mock_calc:
            mock_calc.return_value = {
                'vertical_strategy': 'lines',
                'horizontal_strategy': 'lines',
                'snap_tolerance': 2.0
            }
            
            params = {
                'flavor': 'lines',
                'param_mode': 'auto',
                'score_threshold': 0.5
            }
            
            results = extractor.extract_tables(mock_page, mock_feature_analyzer, params)
            
            assert len(results) > 0
            assert results[0]['source'] == 'pdfplumber_lines'
            assert 'score' in results[0]
    
    @patch('core.extractors.pdfplumber_extractor.TableEvaluator')
    def test_extract_text_success(self, mock_evaluator_class, mock_page, mock_feature_analyzer, mock_pdfplumber_table):
        """测试text模式提取成功"""
        extractor = PDFPlumberExtractor()
        
        # 模拟page.find_tables
        mock_page.find_tables.return_value = [mock_pdfplumber_table]
        
        # 模拟评估�?
        mock_evaluator = Mock()
        mock_evaluator.evaluate.return_value = (0.85, {'accuracy': 0.9}, 'unstructured')
        mock_evaluator_class.return_value = mock_evaluator
        
        # 模拟参数计算
        with patch.object(extractor, 'calculate_params') as mock_calc:
            mock_calc.return_value = {
                'vertical_strategy': 'text',
                'horizontal_strategy': 'text',
                'text_x_tolerance': 3.0
            }
            
            params = {
                'flavor': 'text',
                'param_mode': 'auto',
                'score_threshold': 0.5
            }
            
            results = extractor.extract_tables(mock_page, mock_feature_analyzer, params)
            
            assert len(results) > 0
            assert results[0]['source'] == 'pdfplumber_text'
    
    def test_extract_tables_auto_flavor(self, mock_page, mock_feature_analyzer):
        """测试自动选择flavor"""
        extractor = PDFPlumberExtractor()
        
        with patch.object(extractor, '_extract_lines') as mock_lines:
            mock_lines.return_value = []
            
            # 模拟bordered类型自动选择lines
            mock_feature_analyzer.predict_table_type.return_value = 'bordered'
            
            params = {
                'param_mode': 'auto',
                'score_threshold': 0.5
            }
            
            extractor.extract_tables(mock_page, mock_feature_analyzer, params)
            mock_lines.assert_called_once()
    
    def test_factory_registration(self):
        """测试工厂注册"""
        assert ExtractorFactory.is_registered('pdfplumber')
        extractor = ExtractorFactory.create('pdfplumber')
        assert isinstance(extractor, PDFPlumberExtractor)

# tests/extractors/test_camelot_extractor.py
"""
CamelotExtractor单元测试
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from docuvision_core.extractors.camelot_extractor import CamelotExtractor
from docuvision_core.extractors.factory import ExtractorFactory


class TestCamelotExtractor:
    """CamelotExtractor测试类"""
    
    def test_name_property(self):
        """测试name属性"""
        extractor = CamelotExtractor()
        assert extractor.name == "camelot"
    
    def test_supported_flavors(self):
        """测试supported_flavors属性"""
        extractor = CamelotExtractor()
        flavors = extractor.supported_flavors
        assert 'lattice' in flavors
        assert 'stream' in flavors
        assert len(flavors) == 2
    
    @patch('core.extractors.camelot_extractor.TableParamsCalculator')
    def test_calculate_lattice_params(self, mock_calculator_class, mock_feature_analyzer):
        """测试计算lattice参数"""
        extractor = CamelotExtractor()
        
        # 模拟计算器
        mock_calculator = Mock()
        mock_calculator.get_camelot_lattice_params.return_value = {
            'flavor': 'lattice',
            'line_scale': 40,
            'line_tol': 2.0,
            'joint_tol': 2.0
        }
        mock_calculator_class.return_value = mock_calculator
        
        # 测试计算参数
        params = extractor._calculate_lattice_params(
            mock_feature_analyzer,
            image_shape=(1200, 800)
        )
        
        assert params['flavor'] == 'lattice'
        assert 'line_scale' in params
        mock_calculator.get_camelot_lattice_params.assert_called_once()
    
    @patch('core.extractors.camelot_extractor.TableParamsCalculator')
    def test_calculate_stream_params(self, mock_calculator_class, mock_feature_analyzer):
        """测试计算stream参数"""
        extractor = CamelotExtractor()
        
        # 模拟计算器
        mock_calculator = Mock()
        mock_calculator.get_camelot_stream_params.return_value = {
            'flavor': 'stream',
            'edge_tol': 50.0,
            'row_tol': 2.0,
            'column_tol': 0.0
        }
        mock_calculator_class.return_value = mock_calculator
        
        # 测试计算参数
        params = extractor._calculate_stream_params(mock_feature_analyzer)
        
        assert params['flavor'] == 'stream'
        assert 'edge_tol' in params
        mock_calculator.get_camelot_stream_params.assert_called_once()
    
    def test_calculate_params_auto_flavor(self, mock_feature_analyzer):
        """测试自动选择flavor"""
        extractor = CamelotExtractor()
        
        with patch.object(extractor, '_calculate_lattice_params') as mock_lattice:
            mock_lattice.return_value = {'flavor': 'lattice'}
            
            # 测试bordered类型自动选择lattice
            params = extractor.calculate_params(
                mock_feature_analyzer,
                table_type='bordered'
            )
            
            mock_lattice.assert_called_once()
    
    @patch('core.extractors.camelot_extractor.camelot')
    def test_extract_tables_missing_params(self, mock_camelot, mock_page, mock_feature_analyzer):
        """测试缺少必需参数的情况"""
        extractor = CamelotExtractor()
        
        # 缺少pdf_path和page_num
        params = {
            'flavor': 'lattice',
            'param_mode': 'auto'
        }
        
        results = extractor.extract_tables(mock_page, mock_feature_analyzer, params)
        assert results == []
    
    @patch('core.extractors.camelot_extractor.camelot')
    @patch('core.extractors.camelot_extractor.TableEvaluator')
    def test_extract_lattice_success(self, mock_evaluator_class, mock_camelot, 
                                     mock_page, mock_feature_analyzer, mock_camelot_table):
        """测试lattice模式提取成功"""
        extractor = CamelotExtractor()
        
        # 模拟camelot
        mock_camelot.read_pdf.return_value = [mock_camelot_table]
        
        # 模拟评估器
        mock_evaluator = Mock()
        mock_evaluator.enhance_camelot_features.return_value = mock_camelot_table
        mock_evaluator.evaluate.return_value = (0.85, {'accuracy': 0.9}, 'unstructured')
        mock_evaluator_class.return_value = mock_evaluator
        
        # 模拟参数计算
        with patch.object(extractor, '_calculate_lattice_params') as mock_calc:
            mock_calc.return_value = {
                'flavor': 'lattice',
                'line_scale': 40,
                'line_tol': 2.0,
                'joint_tol': 2.0
            }
            
            params = {
                'pdf_path': 'test.pdf',
                'page_num': 1,
                'flavor': 'lattice',
                'param_mode': 'auto',
                'score_threshold': 0.5
            }
            
            results = extractor.extract_tables(mock_page, mock_feature_analyzer, params)
            
            assert len(results) > 0
            assert results[0]['source'] == 'camelot_lattice'
            assert 'score' in results[0]
    
    def test_extract_tables_camelot_not_available(self, mock_page, mock_feature_analyzer):
        """测试Camelot不可用的情况"""
        extractor = CamelotExtractor()
        extractor._camelot = None  # 模拟camelot不可用
        
        params = {
            'pdf_path': 'test.pdf',
            'page_num': 1,
            'flavor': 'lattice'
        }
        
        results = extractor.extract_tables(mock_page, mock_feature_analyzer, params)
        assert results == []
    
    def test_factory_registration(self):
        """测试工厂注册"""
        assert ExtractorFactory.is_registered('camelot')
        extractor = ExtractorFactory.create('camelot')
        assert isinstance(extractor, CamelotExtractor)

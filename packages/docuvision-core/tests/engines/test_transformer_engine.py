# tests/engines/test_transformer_engine.py
"""
TransformerEngine单元测试
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path
import torch
from PIL import Image

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from docuvision_core.engines.transformer_engine import TransformerEngine
from docuvision_core.engines.factory import EngineFactory


class TestTransformerEngine:
    """TransformerEngine测试�?""
    
    def test_name_property(self):
        """测试name属�?""
        engine = TransformerEngine()
        assert engine.name == "transformer"
    
    @patch('core.engines.transformer_engine.TableTransformerForObjectDetection')
    @patch('core.engines.transformer_engine.AutoImageProcessor')
    def test_load_models_success(self, mock_processor_class, mock_model_class):
        """测试模型加载成功"""
        # 模拟模型和处理器
        mock_model = Mock()
        mock_processor = Mock()
        mock_model_class.from_pretrained.return_value = mock_model
        mock_processor_class.from_pretrained.return_value = mock_processor
        
        engine = TransformerEngine(
            detection_model_path='test/detection',
            structure_model_path='test/structure',
            device='cpu'
        )
        
        result = engine.load_models()
        
        assert result is True
        assert engine._initialized is True
        assert 'detection' in engine.models
        assert 'structure' in engine.models
    
    @patch('core.engines.transformer_engine.TableTransformerForObjectDetection')
    @patch('core.engines.transformer_engine.AutoImageProcessor')
    def test_detect_tables_success(self, mock_processor_class, mock_model_class, sample_image):
        """测试表格检测成�?""
        # 模拟模型和处理器
        mock_model = Mock()
        mock_processor = Mock()
        
        # 模拟输出
        mock_outputs = Mock()
        mock_outputs.logits = torch.randn(1, 100, 2)  # 2个类�?
        mock_outputs.pred_boxes = torch.randn(1, 100, 4)
        
        mock_model.return_value = mock_outputs
        mock_model.eval = Mock()
        
        # 模拟后处理结�?
        mock_results = {
            'boxes': torch.tensor([[100, 100, 200, 200], [300, 300, 400, 400]]),
            'scores': torch.tensor([0.95, 0.85]),
            'labels': torch.tensor([1, 1])
        }
        mock_processor.post_process_object_detection.return_value = [mock_results]
        mock_processor.return_value = {'pixel_values': torch.randn(1, 3, 800, 800)}
        
        mock_model_class.from_pretrained.return_value = mock_model
        mock_processor_class.from_pretrained.return_value = mock_processor
        
        engine = TransformerEngine(
            detection_model_path='test/detection',
            device='cpu'
        )
        engine.models['detection'] = mock_model
        engine.processors['detection'] = mock_processor
        engine._initialized = True
        
        results = engine.detect_tables(sample_image, confidence_threshold=0.5)
        
        assert len(results) == 2
        assert results[0]['confidence'] == 0.95
        assert 'bbox' in results[0]
    
    @patch('core.engines.transformer_engine.TableTransformerForObjectDetection')
    @patch('core.engines.transformer_engine.AutoImageProcessor')
    def test_recognize_structure_success(self, mock_processor_class, mock_model_class, sample_image):
        """测试结构识别成功"""
        # 模拟模型和处理器
        mock_model = Mock()
        mock_processor = Mock()
        
        # 模拟输出
        mock_outputs = Mock()
        mock_outputs.logits = torch.randn(1, 100, 20)  # 20个类�?
        
        mock_model.return_value = mock_outputs
        mock_processor.return_value = {'pixel_values': torch.randn(1, 3, 1000, 1000)}
        
        mock_model_class.from_pretrained.return_value = mock_model
        mock_processor_class.from_pretrained.return_value = mock_processor
        
        engine = TransformerEngine(
            structure_model_path='test/structure',
            device='cpu'
        )
        engine.models['structure'] = mock_model
        engine.processors['structure'] = mock_processor
        engine._initialized = True
        
        result = engine.recognize_structure(sample_image, return_raw_outputs=True)
        
        assert 'model' in result
        assert 'outputs' in result
        assert 'image_size' in result
        assert 'processor' in result
    
    def test_detect_tables_not_initialized(self, sample_image):
        """测试未初始化时检测表�?""
        engine = TransformerEngine()
        
        with patch.object(engine, 'load_models', return_value=False):
            results = engine.detect_tables(sample_image)
            assert results == []
    
    def test_is_available(self):
        """测试可用性检�?""
        with patch('core.engines.transformer_engine.torch', create=True):
            with patch('core.engines.transformer_engine.TableTransformerForObjectDetection', create=True):
                engine = TransformerEngine()
                assert engine.is_available() is True
    
    def test_get_model(self):
        """测试获取模型实例"""
        mock_model = Mock()
        engine = TransformerEngine()
        engine.models['detection'] = mock_model
        engine._initialized = True
        
        model = engine.get_model('detection')
        assert model is mock_model
    
    def test_get_processor(self):
        """测试获取处理器实�?""
        mock_processor = Mock()
        engine = TransformerEngine()
        engine.processors['detection'] = mock_processor
        engine._initialized = True
        
        processor = engine.get_processor('detection')
        assert processor is mock_processor
    
    def test_factory_registration(self):
        """测试工厂注册"""
        assert EngineFactory.is_detection_registered('transformer')
        engine = EngineFactory.create_detection('transformer')
        assert isinstance(engine, TransformerEngine)

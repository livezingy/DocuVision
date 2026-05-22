# tests/engines/test_transformer_engine.py
"""test transformer engine module."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path
import torch
from PIL import Image

#
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from docuvision_core.engines.transformer_engine import TransformerEngine
from docuvision_core.engines.factory import EngineFactory


class TestTransformerEngine:
    
    def test_name_property(self):
        engine = TransformerEngine()
        assert engine.name == "transformer"
    
    @patch('docuvision_core.engines.transformer_engine.TableTransformerForObjectDetection')
    @patch('docuvision_core.engines.transformer_engine.AutoImageProcessor')
    def test_load_models_success(self, mock_processor_class, mock_model_class):
        #
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
    
    @patch('docuvision_core.engines.transformer_engine.TableTransformerForObjectDetection')
    @patch('docuvision_core.engines.transformer_engine.AutoImageProcessor')
    def test_detect_tables_success(self, mock_processor_class, mock_model_class, sample_image):
        #
        mock_model = Mock()
        mock_processor = Mock()
        
        #
        mock_outputs = Mock()
        mock_outputs.logits = torch.randn(1, 100, 2)
        mock_outputs.pred_boxes = torch.randn(1, 100, 4)
        
        mock_model.return_value = mock_outputs
        mock_model.eval = Mock()
        
        #
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
    
    @patch('docuvision_core.engines.transformer_engine.TableTransformerForObjectDetection')
    @patch('docuvision_core.engines.transformer_engine.AutoImageProcessor')
    def test_recognize_structure_success(self, mock_processor_class, mock_model_class, sample_image):
        #
        mock_model = Mock()
        mock_processor = Mock()
        
        #
        mock_outputs = Mock()
        mock_outputs.logits = torch.randn(1, 100, 20)
        
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
        engine = TransformerEngine()
        
        with patch.object(engine, 'load_models', return_value=False):
            results = engine.detect_tables(sample_image)
            assert results == []
    
    def test_is_available(self):
        with patch('docuvision_core.engines.transformer_engine.torch', create=True):
            with patch('docuvision_core.engines.transformer_engine.TableTransformerForObjectDetection', create=True):
                engine = TransformerEngine()
                assert engine.is_available() is True
    
    def test_get_model(self):
        mock_model = Mock()
        engine = TransformerEngine()
        engine.models['detection'] = mock_model
        engine._initialized = True
        
        model = engine.get_model('detection')
        assert model is mock_model
    
    def test_get_processor(self):
        mock_processor = Mock()
        engine = TransformerEngine()
        engine.processors['detection'] = mock_processor
        engine._initialized = True
        
        processor = engine.get_processor('detection')
        assert processor is mock_processor
    
    def test_factory_registration(self):
        assert EngineFactory.is_detection_registered('transformer')
        engine = EngineFactory.create_detection('transformer')
        assert isinstance(engine, TransformerEngine)

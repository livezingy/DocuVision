# core/engines/transformer_engine.py
"""transformer engine module."""

import os
import torch
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from PIL import Image
import numpy as np
from torchvision import transforms
from transformers import (
    AutoImageProcessor,
    TableTransformerForObjectDetection
)
from docuvision_core.engines.base import BaseDetectionEngine
from docuvision_core.utils.logger import AppLogger
from docuvision_core.utils.model_paths import (
    is_offline_mode,
    local_model_ready,
    table_transformer_detection_dir,
    table_transformer_structure_dir,
)
from docuvision_core.utils.path_utils import get_app_dir


# Comment.
class MaxResize(object):
    """Docstring."""
    def __init__(self, max_size=800):
        self.max_size = max_size

    def __call__(self, image):
        width, height = image.size
        current_max_size = max(width, height)
        scale = self.max_size / current_max_size
        resized_image = image.resize((int(round(scale*width)), int(round(scale*height))))
        return resized_image

detection_transform = transforms.Compose([
    MaxResize(800),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

structure_transform = transforms.Compose([
    MaxResize(1000),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])


class TransformerEngine(BaseDetectionEngine):
    """Docstring."""
    
    def __init__(self, 
                 detection_model_path: Optional[str] = None,
                 structure_model_path: Optional[str] = None,
                 device: str = 'cpu',
                 detection_confidence: float = 0.5,
                 structure_confidence: float = 0.5,
                 **kwargs):
        """
        
        Args:
        """
        self.logger = AppLogger.get_logger()
        self.detection_model_path = detection_model_path
        self.structure_model_path = structure_model_path
        self.device = device
        self.detection_confidence = detection_confidence
        self.structure_confidence = structure_confidence
        
        self.models = {}
        self.processors = {}
        self._initialized = False
    
    @property
    def name(self) -> str:
        """Docstring."""
        return "transformer"
    
    def load_models(self, **kwargs) -> bool:
        """Docstring."""
        if self._initialized:
            return True
        
        try:
            detection_path = kwargs.get('detection_model_path', self.detection_model_path)
            structure_path = kwargs.get('structure_model_path', self.structure_model_path)
            device = kwargs.get('device', self.device)
            
            # Comment.
            if detection_path:
                det_model, det_proc = self._load_model_and_processor(detection_path, 'detection', device)
                self.models['detection'] = det_model
                self.processors['detection'] = det_proc
            
            # Comment.
            if structure_path:
                str_model, str_proc = self._load_model_and_processor(structure_path, 'structure', device)
                self.models['structure'] = str_model
                self.processors['structure'] = str_proc
            
            # Comment.
            for model in self.models.values():
                model.eval()
            
            self.device = device
            self._initialized = True
            self.logger.info(f"Transformer engine initialized with models: {list(self.models.keys())}, device: {device}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load Transformer models: {e}")
            return False
    
    def _load_model_and_processor(self, path_or_id: str, kind: str, device: str) -> Tuple:
        """Docstring."""
        def _resolve_model_id(local_path: str, kind: str) -> str:
            """Docstring."""
            if kind == 'detection':
                return "microsoft/table-transformer-detection"
            return "microsoft/table-transformer-structure-recognition"
        
        def _normalize_path(path: str) -> str:
            """Docstring."""
            if not path:
                return path
            normalized = os.path.normpath(path)
            if not os.path.isabs(normalized):
                base_dir = get_app_dir()
                normalized = os.path.join(base_dir, normalized)
            return os.path.normpath(normalized)
        
        def _is_valid_local_path(path: str) -> bool:
            """Docstring."""
            if not path:
                return False
            if os.path.isabs(path) or os.path.sep in path or '/' in path:
                return True
            if '\\' in path or path.startswith('./') or path.startswith('../'):
                return True
            return False
        
        def _local_dir_for_kind(kind: str) -> str:
            if kind == "detection":
                return str(table_transformer_detection_dir())
            return str(table_transformer_structure_dir())

        normalized_path = _normalize_path(path_or_id) if _is_valid_local_path(path_or_id) else _local_dir_for_kind(kind)
        if not _is_valid_local_path(path_or_id):
            normalized_path = _local_dir_for_kind(kind)

        if local_model_ready(Path(normalized_path)):
            try:
                model = TableTransformerForObjectDetection.from_pretrained(
                    normalized_path,
                    local_files_only=True
                ).to(device)
                processor = AutoImageProcessor.from_pretrained(
                    normalized_path,
                    local_files_only=True
                )
                self.logger.info(f"[TransformerEngine] Loaded {kind} from local path: {normalized_path}")
                return model, processor
            except Exception as e_local:
                self.logger.warning(f"[TransformerEngine] Local {kind} at {normalized_path} failed: {e_local}")
                if is_offline_mode():
                    raise RuntimeError(
                        f"Offline mode: failed to load {kind} from {normalized_path}"
                    ) from e_local

        if is_offline_mode():
            raise RuntimeError(
                f"Offline mode: {kind} model not found at {normalized_path}"
            )

        self.logger.warning(f"[TransformerEngine] Local {kind} not found, downloading from Hugging Face Hub")
        model_id = _resolve_model_id(path_or_id, kind)
        os.makedirs(normalized_path, exist_ok=True)
        model = TableTransformerForObjectDetection.from_pretrained(model_id).to(device)
        processor = AutoImageProcessor.from_pretrained(model_id)
        model.save_pretrained(normalized_path)
        processor.save_pretrained(normalized_path)
        self.logger.info(f"[TransformerEngine] Downloaded {kind} and saved to {normalized_path}")
        return model, processor
    
    def detect_tables(self, image: Image.Image, **kwargs) -> List[Dict]:
        """Docstring."""
        if not self._initialized:
            if not self.load_models():
                return []
        
        if 'detection' not in self.models:
            self.logger.error("Detection model is not loaded")
            return []
        
        try:
            confidence_threshold = kwargs.get('confidence_threshold', self.detection_confidence)
            
            processor = self.processors['detection']
            model = self.models['detection']
            
            # Comment.
            inputs = processor(
                images=image,
                return_tensors="pt",
                size={"shortest_edge": 1024, "longest_edge": 1024}
            )
            
            # Comment.
            with torch.no_grad():
                outputs = model(**inputs)
            
            # Comment.
            target_sizes = torch.tensor([image.size[::-1]])
            results = processor.post_process_object_detection(
                outputs,
                threshold=confidence_threshold,
                target_sizes=target_sizes
            )[0]
            
            # Comment.
            boxes = results["boxes"].cpu().numpy()
            scores = results["scores"].cpu().numpy()
            labels = results["labels"].cpu().numpy()
            
            detection_results = []
            for box, score, label in zip(boxes, scores, labels):
                # Comment.
                x1, y1, x2, y2 = box
                detection_results.append({
                    'bbox': [float(x1), float(y1), float(x2), float(y2)],
                    'confidence': float(score),
                    'label': int(label)
                })
            
            return detection_results
            
        except Exception as e:
            self.logger.error(f"Table detection failed: {e}")
            return []
    
    def recognize_structure(self, image: Image.Image, table_bbox: Optional[List] = None, **kwargs) -> Dict:
        """Docstring."""
        if not self._initialized:
            if not self.load_models():
                return {}
        
        if 'structure' not in self.models:
            self.logger.error("Structure model is not loaded")
            return {}
        
        try:
            processor = self.processors['structure']
            model = self.models['structure']
            
            # Comment.
            if table_bbox:
                x1, y1, x2, y2 = table_bbox
                image = image.crop((x1, y1, x2, y2))
            
            # Comment.
            inputs = processor(
                images=image,
                return_tensors="pt",
                size={"shortest_edge": 1000, "longest_edge": 1000}
            )
            
            # Comment.
            with torch.no_grad():
                outputs = model(**inputs)
            
            # Comment.
            if kwargs.get('return_raw_outputs', False):
                return {
                    'model': model,
                    'outputs': outputs,
                    'image_size': image.size,
                    'processor': processor
                }
            else:
                # Comment.
                return {
                    'image_size': image.size,
                    'model': model,
                    'outputs': outputs,
                    'processor': processor
                }
            
        except Exception as e:
            self.logger.error(f"Structure recognition failed: {e}")
            return {}
    
    def is_available(self) -> bool:
        """Docstring."""
        try:
            import torch
            from transformers import TableTransformerForObjectDetection
            return True
        except ImportError:
            return False
    
    def get_model(self, kind: str):
        """Docstring."""
        if not self._initialized:
            self.load_models()
        return self.models.get(kind)
    
    def get_processor(self, kind: str):
        """Docstring."""
        if not self._initialized:
            self.load_models()
        return self.processors.get(kind)

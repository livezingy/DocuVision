# core/engines/transformer_engine.py
"""
Transformer表格检测和结构识别引擎

封装Transformer模型的加载和推理，提供表格检测和结构识别接口
"""

import os
import torch
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
from docuvision_core.utils.path_utils import get_app_dir


# 图像预处理变�?
class MaxResize(object):
    """最大尺寸调整变�?""
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
    """Transformer表格检测和结构识别引擎"""
    
    def __init__(self, 
                 detection_model_path: Optional[str] = None,
                 structure_model_path: Optional[str] = None,
                 device: str = 'cpu',
                 detection_confidence: float = 0.5,
                 structure_confidence: float = 0.5,
                 **kwargs):
        """
        初始化Transformer引擎
        
        Args:
            detection_model_path: 检测模型路径或HuggingFace模型ID
            structure_model_path: 结构识别模型路径或HuggingFace模型ID
            device: 设备�?cpu'�?cuda'�?
            detection_confidence: 检测置信度阈�?
            structure_confidence: 结构识别置信度阈�?
            **kwargs: 其他参数（预留）
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
        """引擎名称"""
        return "transformer"
    
    def load_models(self, **kwargs) -> bool:
        """
        加载模型
        
        Args:
            **kwargs: 模型配置参数
                - detection_model_path: 检测模型路�?
                - structure_model_path: 结构识别模型路径
                - device: 设备
                
        Returns:
            bool: 加载是否成功
        """
        if self._initialized:
            return True
        
        try:
            detection_path = kwargs.get('detection_model_path', self.detection_model_path)
            structure_path = kwargs.get('structure_model_path', self.structure_model_path)
            device = kwargs.get('device', self.device)
            
            # 加载检测模�?
            if detection_path:
                det_model, det_proc = self._load_model_and_processor(detection_path, 'detection', device)
                self.models['detection'] = det_model
                self.processors['detection'] = det_proc
            
            # 加载结构识别模型
            if structure_path:
                str_model, str_proc = self._load_model_and_processor(structure_path, 'structure', device)
                self.models['structure'] = str_model
                self.processors['structure'] = str_proc
            
            # 设置为评估模�?
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
        """
        加载模型和处理器
        
        Args:
            path_or_id: 模型路径或HuggingFace模型ID
            kind: 模型类型�?detection'�?structure'�?
            device: 设备
            
        Returns:
            Tuple: (model, processor)
        """
        def _resolve_model_id(local_path: str, kind: str) -> str:
            """解析模型ID"""
            if kind == 'detection':
                return "microsoft/table-transformer-detection"
            return "microsoft/table-transformer-structure-recognition"
        
        def _normalize_path(path: str) -> str:
            """规范化路�?""
            if not path:
                return path
            normalized = os.path.normpath(path)
            if not os.path.isabs(normalized):
                base_dir = get_app_dir()
                normalized = os.path.join(base_dir, normalized)
            return os.path.normpath(normalized)
        
        def _is_valid_local_path(path: str) -> bool:
            """检查是否是有效的本地路�?""
            if not path:
                return False
            if os.path.isabs(path) or os.path.sep in path or '/' in path:
                return True
            if '\\' in path or path.startswith('./') or path.startswith('../'):
                return True
            return False
        
        # 规范化路�?
        normalized_path = _normalize_path(path_or_id) if _is_valid_local_path(path_or_id) else path_or_id
        
        # 优先尝试本地文件
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
            self.logger.warning(f"[TransformerEngine] Local {kind} not found, fallback to HuggingFace Hub")
            # 回落到HuggingFace Hub
            model_id = _resolve_model_id(path_or_id, kind)
            model = TableTransformerForObjectDetection.from_pretrained(model_id).to(device)
            processor = AutoImageProcessor.from_pretrained(model_id)
            self.logger.info(f"[TransformerEngine] Downloaded {kind} model from HF Hub: {model_id}")
            return model, processor
    
    def detect_tables(self, image: Image.Image, **kwargs) -> List[Dict]:
        """
        检测表�?
        
        Args:
            image: PIL Image对象
            **kwargs: 其他参数
                - confidence_threshold: 置信度阈值（覆盖初始化时的设置）
                
        Returns:
            List[Dict]: 检测结果列表，每个元素包含�?
                - bbox: 边界�?[x1, y1, x2, y2]
                - confidence: 置信�?(0-1)
                - label: 标签
        """
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
            
            # 预处�?
            inputs = processor(
                images=image,
                return_tensors="pt",
                size={"shortest_edge": 1024, "longest_edge": 1024}
            )
            
            # 推理
            with torch.no_grad():
                outputs = model(**inputs)
            
            # 后处�?
            target_sizes = torch.tensor([image.size[::-1]])
            results = processor.post_process_object_detection(
                outputs,
                threshold=confidence_threshold,
                target_sizes=target_sizes
            )[0]
            
            # 格式化结�?
            boxes = results["boxes"].cpu().numpy()
            scores = results["scores"].cpu().numpy()
            labels = results["labels"].cpu().numpy()
            
            detection_results = []
            for box, score, label in zip(boxes, scores, labels):
                # 转换box格式：从[x1, y1, x2, y2]格式
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
        """
        识别表格结构
        
        Args:
            image: PIL Image对象（表格区域）
            table_bbox: 表格边界�?[x1, y1, x2, y2]（可选）
            **kwargs: 其他参数
                - return_raw_outputs: 是否返回原始输出（用于高级用法）
                
        Returns:
            Dict: 结构识别结果，包含：
                - model: 模型对象（如果return_raw_outputs=True�?
                - outputs: 原始输出（如果return_raw_outputs=True�?
                - image_size: 图像尺寸
                - 或者处理后的结构数�?
        """
        if not self._initialized:
            if not self.load_models():
                return {}
        
        if 'structure' not in self.models:
            self.logger.error("Structure model is not loaded")
            return {}
        
        try:
            processor = self.processors['structure']
            model = self.models['structure']
            
            # 如果指定了table_bbox，裁剪图�?
            if table_bbox:
                x1, y1, x2, y2 = table_bbox
                image = image.crop((x1, y1, x2, y2))
            
            # 预处�?
            inputs = processor(
                images=image,
                return_tensors="pt",
                size={"shortest_edge": 1000, "longest_edge": 1000}
            )
            
            # 推理
            with torch.no_grad():
                outputs = model(**inputs)
            
            # 根据参数决定返回格式
            if kwargs.get('return_raw_outputs', False):
                return {
                    'model': model,
                    'outputs': outputs,
                    'image_size': image.size,
                    'processor': processor
                }
            else:
                # 返回基本信息（实际的结构解析由调用者完成）
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
        """
        检查引擎是否可�?
        
        Returns:
            bool: 引擎是否可用
        """
        try:
            import torch
            from transformers import TableTransformerForObjectDetection
            return True
        except ImportError:
            return False
    
    def get_model(self, kind: str):
        """
        获取模型实例（用于高级用法）
        
        Args:
            kind: 模型类型�?detection'�?structure'�?
            
        Returns:
            模型实例，如果未加载则返回None
        """
        if not self._initialized:
            self.load_models()
        return self.models.get(kind)
    
    def get_processor(self, kind: str):
        """
        获取处理器实例（用于高级用法�?
        
        Args:
            kind: 处理器类型（'detection'�?structure'�?
            
        Returns:
            处理器实例，如果未加载则返回None
        """
        if not self._initialized:
            self.load_models()
        return self.processors.get(kind)

# core/engines/easyocr_engine.py
"""
EasyOCR引擎

封装EasyOCR的初始化和调用，提供标准OCR接口
"""

import numpy as np
from typing import Dict, List, Optional, Any
from PIL import Image
from docuvision_core.engines.base import BaseOCREngine
from docuvision_core.utils.easyocr_config import get_easyocr_reader, get_easyocr_config
from docuvision_core.utils.logger import AppLogger


class EasyOCREngine(BaseOCREngine):
    """EasyOCR引擎"""
    
    def __init__(self, languages: List[str] = None, gpu: bool = False, **kwargs):
        """
        初始化EasyOCR引擎
        
        Args:
            languages: 支持的语言列表，默认为['en']
            gpu: 是否使用GPU，默认为False
            **kwargs: 其他参数（预留）
        """
        self.logger = AppLogger.get_logger()
        self.languages = languages or ['en']
        self.gpu = gpu
        self._reader = None
        # 延迟加载配置，优化初始化性能
        self._config = None
        self._initialized = False
    
    def _get_config(self):
        """懒加载配�?""
        if self._config is None:
            self._config = get_easyocr_config()
        return self._config
    
    @property
    def name(self) -> str:
        """引擎名称"""
        return "easyocr"
    
    def initialize(self, **kwargs) -> bool:
        """
        初始化引�?
        
        Args:
            **kwargs: 初始化参�?
                - languages: 语言列表
                - gpu: 是否使用GPU
                
        Returns:
            bool: 初始化是否成�?
        """
        if self._initialized and self._reader is not None:
            return True
        
        try:
            languages = kwargs.get('languages', self.languages)
            gpu = kwargs.get('gpu', self.gpu)
            
            # 确保配置已加�?
            self._get_config()
            
            self._reader = get_easyocr_reader(languages, gpu)
            self._initialized = True
            self.logger.info(f"EasyOCR engine initialized with languages: {languages}, GPU: {gpu}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize EasyOCR engine: {e}")
            return False
    
    def recognize_text(self, image: Image.Image, **kwargs) -> List[Dict]:
        """
        识别文本
        
        Args:
            image: PIL Image对象
            **kwargs: 其他参数
                - languages: 语言列表（可选，覆盖初始化时的设置）
                - min_confidence: 最小置信度阈值（默认0.0�?
                
        Returns:
            List[Dict]: OCR结果列表，每个元素包含：
                - text: 文本内容
                - bbox: 边界�?[[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                - confidence: 置信�?(0-1)
        """
        if not self._initialized:
            if not self.initialize():
                return []
        
        if self._reader is None:
            self.logger.error("EasyOCR reader is not available")
            return []
        
        try:
            # 转换PIL Image为numpy array
            img_array = np.array(image)
            
            # 执行OCR
            min_confidence = kwargs.get('min_confidence', 0.0)
            ocr_results = self._reader.readtext(img_array)
            
            # 转换结果格式
            results = []
            for item in ocr_results:
                bbox_points = item[0]  # List of 4 corner points
                text = item[1]         # Text content
                confidence = item[2]   # Confidence score
                
                # 过滤低置信度结果
                if confidence < min_confidence:
                    continue
                
                # 转换bbox格式：从角点列表转换为[x1, y1, x2, y2]格式（用于兼容性）
                x_coords = [point[0] for point in bbox_points]
                y_coords = [point[1] for point in bbox_points]
                x1, x2 = min(x_coords), max(x_coords)
                y1, y2 = min(y_coords), max(y_coords)
                
                results.append({
                    'text': text,
                    'bbox': bbox_points,  # 保留原始角点格式
                    'bbox_rect': [x1, y1, x2, y2],  # 添加矩形格式用于兼容
                    'confidence': float(confidence)
                })
            
            return results
            
        except Exception as e:
            self.logger.error(f"EasyOCR recognition failed: {e}")
            return []
    
    def get_reader(self):
        """
        获取EasyOCR reader实例（用于高级用法）
        
        Returns:
            easyocr.Reader: EasyOCR reader实例，如果未初始化则返回None
        """
        if not self._initialized:
            self.initialize()
        return self._reader
    
    def is_available(self) -> bool:
        """
        检查引擎是否可�?
        
        Returns:
            bool: 引擎是否可用
        """
        try:
            import easyocr
            return True
        except ImportError:
            return False
    
    def recognize_text_in_region(self, image: Image.Image, bbox: List, **kwargs) -> List[Dict]:
        """
        识别指定区域的文�?
        
        Args:
            image: PIL Image对象
            bbox: 区域边界�?[x1, y1, x2, y2]
            **kwargs: 其他参数
            
        Returns:
            List[Dict]: OCR结果列表
        """
        try:
            # 裁剪区域
            x1, y1, x2, y2 = bbox
            cropped = image.crop((x1, y1, x2, y2))
            
            # 识别文本
            results = self.recognize_text(cropped, **kwargs)
            
            # 调整bbox坐标到原图坐标系
            for result in results:
                if 'bbox' in result:
                    # 调整角点坐标
                    adjusted_bbox = []
                    for point in result['bbox']:
                        adjusted_bbox.append([point[0] + x1, point[1] + y1])
                    result['bbox'] = adjusted_bbox
                
                if 'bbox_rect' in result:
                    # 调整矩形坐标
                    rect = result['bbox_rect']
                    result['bbox_rect'] = [rect[0] + x1, rect[1] + y1, rect[2] + x1, rect[3] + y1]
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to recognize text in region: {e}")
            return []

import os
import torch
from typing import Dict, Optional, Tuple, List
from torchvision import transforms
from transformers import (
    AutoImageProcessor,
    TableTransformerForObjectDetection
)
from PIL import Image
import numpy as np
import pytesseract
import easyocr
from docuvision_core.utils.easyocr_config import get_easyocr_reader
from tqdm.auto import tqdm
from docuvision_core.utils.logger import AppLogger
from docuvision_core.utils.path_utils import get_app_dir

#preprocessing for transformer detection and structure recognition
class MaxResize(object):
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



def prepare_image(image, device):
    pixel_values = detection_transform(image).unsqueeze(0)
    pixel_values = pixel_values.to(device)
    return pixel_values

def prepare_cropped_image(cropped_image, device):
    pixel_values = structure_transform(cropped_image).unsqueeze(0)
    pixel_values = pixel_values.to(device)
    return pixel_values
    

class TableModels:
    """Unified model manager for table detection, structure recognition, and OCR."""
    _instance = None
    _initialized = False

    def __new__(cls, config=None):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_cfg: Optional[Dict] = None):
        self.logger = AppLogger.get_logger()
        
        self.detection_model_path = model_cfg.get('detection_model_path')
        self.structure_model_path = model_cfg.get('structure_model_path')
        self.ocr_model_path = model_cfg.get('ocr_model_path')
        self.device = model_cfg.get('device', 'cpu')
        self.detection_confidence = model_cfg.get('detection_confidence', 0.5)
        self.structure_confidence = model_cfg.get('structure_confidence', 0.5)
        self.ocr_confidence = model_cfg.get('ocr_confidence', 0.5)
        # 调试信息：打印模型路径和参数
        self.logger.debug(f"[TableModels] detection_model_path: {self.detection_model_path}")
        self.logger.debug(f"[TableModels] structure_model_path: {self.structure_model_path}")
        self.logger.debug(f"[TableModels] ocr_model_path: {self.ocr_model_path}")
        self.logger.debug(f"[TableModels] device: {self.device}")
        self.logger.debug(f"[TableModels] detection_confidence: {self.detection_confidence}")
        self.logger.debug(f"[TableModels] structure_confidence: {self.structure_confidence}")
        self.logger.debug(f"[TableModels] ocr_confidence: {self.ocr_confidence}")

        self.models = {}
        self.processors = {}
        self._init()
        self._initialized = True
        
        pytesseract.pytesseract.tesseract_cmd = self.ocr_model_path

    def _init(self):
        try:
            # Helper to resolve HF model id when local path is unavailable
            def _resolve_model_id(local_path: str, kind: str) -> str:
                # 默认映射：detection / structure
                if kind == 'detection':
                    return "microsoft/table-transformer-detection"
                return "microsoft/table-transformer-structure-recognition"

            def _normalize_path(path: str) -> str:
                """规范化路径，移除相对路径符号"""
                if not path:
                    return path
                # 规范化路径（移除 .\ �?..\ 等）
                normalized = os.path.normpath(path)
                # 如果是相对路径，转换为绝对路�?
                if not os.path.isabs(normalized):
                    base_dir = get_app_dir()
                    normalized = os.path.join(base_dir, normalized)
                # 再次规范化，确保路径格式正确
                return os.path.normpath(normalized)

            def _is_valid_local_path(path: str) -> bool:
                """检查路径是否是有效的本地路径（不是 HuggingFace repo ID�?""
                if not path:
                    return False
                # 检查是否是绝对路径或相对路�?
                # HuggingFace repo ID 格式：不包含路径分隔符或只包含斜杠（用于组织/仓库名）
                # 本地路径通常包含反斜杠（Windows）或正斜杠（Unix），且不以字母开�?
                if os.path.isabs(path) or os.path.sep in path or '/' in path:
                    return True
                # 如果路径看起来像 repo ID（如 "microsoft/table-transformer-detection"�?
                # 但包含路径分隔符，可能是相对路径
                if '\\' in path or path.startswith('./') or path.startswith('../'):
                    return True
                return False

            def _load_model_and_processor(path_or_id: str, kind: str):
                # 规范化路�?
                normalized_path = _normalize_path(path_or_id) if _is_valid_local_path(path_or_id) else path_or_id
                
                # #region agent log
                from docuvision_core.utils.debug_utils import write_debug_log
                try:
                    write_debug_log(
                        location="table_models.py:100",
                        message="loading model and processor",
                        data={
                            "kind": kind,
                            "original_path": path_or_id,
                            "normalized_path": normalized_path,
                            "is_valid_local": _is_valid_local_path(path_or_id),
                            "path_exists": os.path.exists(normalized_path) if normalized_path else False
                        },
                        hypothesis_id="L"
                    )
                except Exception as e:
                    self.logger.warning(f"Debug log write failed: {e}")
                # #endregion
                
                # 优先尝试本地文件
                try:
                    # 使用规范化后的路�?
                    model = TableTransformerForObjectDetection.from_pretrained(
                        normalized_path,
                        local_files_only=True
                    ).to(self.device)
                    processor = AutoImageProcessor.from_pretrained(
                        normalized_path,
                        local_files_only=True
                    )
                    self.logger.info(f"[TableModels] Loaded {kind} from local path: {normalized_path}")
                    return model, processor
                except Exception as e_local:
                    self.logger.warning(f"[TableModels] Local {kind} not found at {normalized_path}, fallback to Hugging Face Hub. Reason: {e_local}")
                    # 回落�?Hugging Face Hub
                    model_id = _resolve_model_id(path_or_id, kind)
                    
                    # #region agent log
                    try:
                        write_debug_log(
                            location="table_models.py:114",
                            message="falling back to HuggingFace Hub",
                            data={
                                "kind": kind,
                                "local_path": normalized_path,
                                "hf_model_id": model_id,
                                "local_error": str(e_local)
                            },
                            hypothesis_id="L"
                        )
                    except Exception as e:
                        self.logger.warning(f"Debug log write failed: {e}")
                    # #endregion
                    
                    model = TableTransformerForObjectDetection.from_pretrained(model_id).to(self.device)
                    processor = AutoImageProcessor.from_pretrained(model_id)
                    self.logger.info(f"[TableModels] Downloaded {kind} model from HF Hub: {model_id}")
                    return model, processor

            # Detection model
            det_model, det_proc = _load_model_and_processor(self.detection_model_path, 'detection')
            self.models['detection'] = det_model
            self.processors['detection'] = det_proc

            # Structure model
            str_model, str_proc = _load_model_and_processor(self.structure_model_path, 'structure')
            self.models['structure'] = str_model
            self.processors['structure'] = str_proc

            # Set eval mode
            for model in self.models.values():
                model.eval()
            self.logger.info("Models initialized successfully", {
                "models": list(self.models.keys()),
                "device": self.device
            })
        except Exception as e:
            self.logger.error(f"Model initialization failed: {str(e)}", exc_info=True)
            raise

    def detect_tables(self, image: Image.Image):
        """Detect tables in image, return boxes, scores, labels."""
        try:
            inputs = self.processors['detection'](
                images=image,
                return_tensors="pt",
                size={"shortest_edge": 1024, "longest_edge": 1024}
            )
            with torch.no_grad():
                outputs = self.models['detection'](**inputs)
            target_sizes = torch.tensor([image.size[::-1]])
            results = self.processors['detection'].post_process_object_detection(
                outputs,
                threshold=self.detection_confidence,
                target_sizes=target_sizes
            )[0]
            return (
                results["boxes"].cpu().numpy(),
                results["scores"].cpu().numpy(),
                results["labels"].cpu().numpy()
            )
        except Exception as e:
            self.logger.error(f"Table detection failed: {str(e)}", exc_info=True)
            raise

    

    def recognize_structure(self, image: Image.Image):
        """
        Recognize table structure using direct detection method (similar to table_parser_direct.py).
        Return tuple: (model, outputs, image_size)
        - model: structure detection model
        - outputs: raw model outputs (not post-processed)
        - image_size: original image size for coordinate scaling
        """
        try:
            processor = self.processors['structure']
            model = self.models['structure']
            
            # Use the same preprocessing as table_parser_direct.py
            inputs = processor(
                images=image,
                return_tensors="pt",
                size={"shortest_edge": 1000, "longest_edge": 1000}
            )
            
            with torch.no_grad():
                outputs = model(**inputs)
            
            # Return raw outputs instead of post-processed results
            # This allows table_parser.py to use the same coordinate processing as table_parser_direct.py
            return model, outputs, image.size
            
        except Exception as e:
            self.logger.error(f"Structure recognition failed: {str(e)}", exc_info=True)
            raise

    

    def ocr_cell(self, image: Image.Image, lang: str = 'eng') -> Tuple[str, float]:
        """
        OCR for a single cell image using Tesseract.
        Returns tuple: (text, confidence_score)
        """
        try:
            ocr_data = pytesseract.image_to_data(
            image, lang=lang, config='--psm 6 preserve_interword_spaces', output_type=pytesseract.Output.DICT
            )
            # 以单词为单位聚合
            words = []
            confidences = []
            for i, word in enumerate(ocr_data['text']):
                conf = ocr_data['conf'][i]
                if word.strip() and conf > -1:
                    words.append(word)
                    confidences.append(conf)
            text = ' '.join(words).strip()
            avg_confidence = np.mean(confidences) / 100.0 if confidences else 0.0
                    
            # Apply confidence threshold
            if avg_confidence < self.ocr_confidence:
                return "", avg_confidence
                
            return text, avg_confidence
            
        except Exception as e:
            self.logger.error(f"OCR failed: {str(e)}", exc_info=True)
            return "", 0.0




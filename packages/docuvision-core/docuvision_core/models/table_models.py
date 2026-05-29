import os
import torch
from pathlib import Path
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
from docuvision_core.utils.model_paths import (
    is_offline_mode,
    local_model_ready,
    table_transformer_detection_dir,
    table_transformer_structure_dir,
)
from docuvision_core.utils.path_utils import get_app_dir, resolve_tesseract_cmd

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
    """Docstring."""
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
        # Comment.
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
        
        pytesseract.pytesseract.tesseract_cmd = resolve_tesseract_cmd(self.ocr_model_path)

    def _init(self):
        try:
            # Helper to resolve HF model id when local path is unavailable
            def _resolve_model_id(local_path: str, kind: str) -> str:
                # Comment.
                if kind == 'detection':
                    return "microsoft/table-transformer-detection"
                return "microsoft/table-transformer-structure-recognition"

            def _normalize_path(path: str) -> str:
                """Docstring."""
                if not path:
                    return path
                # Comment.
                normalized = os.path.normpath(path)
                # Comment.
                if not os.path.isabs(normalized):
                    base_dir = get_app_dir()
                    normalized = os.path.join(base_dir, normalized)
                # Comment.
                return os.path.normpath(normalized)

            def _is_valid_local_path(path: str) -> bool:
                """Docstring."""
                if not path:
                    return False
                # Comment.
                # Comment.
                # Comment.
                if os.path.isabs(path) or os.path.sep in path or '/' in path:
                    return True
                # Comment.
                # Comment.
                if '\\' in path or path.startswith('./') or path.startswith('../'):
                    return True
                return False

            def _local_dir_for_kind(kind: str) -> str:
                if kind == "detection":
                    return str(table_transformer_detection_dir())
                return str(table_transformer_structure_dir())

            def _load_model_and_processor(path_or_id: str, kind: str):
                local_dir = _local_dir_for_kind(kind)
                normalized_path = _normalize_path(path_or_id) if _is_valid_local_path(path_or_id) else local_dir
                if not _is_valid_local_path(path_or_id):
                    normalized_path = local_dir

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

                if local_model_ready(Path(normalized_path)):
                    try:
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
                        self.logger.warning(
                            f"[TableModels] Local {kind} at {normalized_path} failed to load: {e_local}"
                        )
                        if is_offline_mode():
                            raise RuntimeError(
                                f"Offline mode: failed to load {kind} from {normalized_path}"
                            ) from e_local

                if is_offline_mode():
                    raise RuntimeError(
                        f"Offline mode: {kind} model not found at {normalized_path}. "
                        "Run bootstrap_lite_models or copy models/ from another host."
                    )

                self.logger.warning(
                    f"[TableModels] Local {kind} not found at {normalized_path}, downloading from Hugging Face Hub"
                )
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
                        },
                        hypothesis_id="L"
                    )
                except Exception as e:
                    self.logger.warning(f"Debug log write failed: {e}")
                # #endregion

                os.makedirs(normalized_path, exist_ok=True)
                model = TableTransformerForObjectDetection.from_pretrained(model_id).to(self.device)
                processor = AutoImageProcessor.from_pretrained(model_id)
                model.save_pretrained(normalized_path)
                processor.save_pretrained(normalized_path)
                self.logger.info(
                    f"[TableModels] Downloaded {kind} from HF Hub and saved to {normalized_path}"
                )
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
        """Docstring."""
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
        """Docstring."""
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
        """Docstring."""
        try:
            ocr_data = pytesseract.image_to_data(
            image, lang=lang, config='--psm 6 preserve_interword_spaces', output_type=pytesseract.Output.DICT
            )
            # Comment.
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




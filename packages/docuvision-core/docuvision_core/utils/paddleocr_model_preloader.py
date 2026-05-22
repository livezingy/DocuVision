# core/utils/paddleocr_model_preloader.py
"""paddleocr model preloader module."""

import os
import threading
from typing import Optional
from docuvision_core.utils.logger import AppLogger


class PaddleOCRModelPreloader:
    """Docstring."""
    
    _instance: Optional['PaddleOCRModelPreloader'] = None
    _lock = threading.Lock()
    _preload_started = False
    _preload_completed = False
    _preload_error: Optional[Exception] = None
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.logger = AppLogger.get_logger()
        return cls._instance
    
    def preload_models(self, background: bool = True) -> bool:
        """Docstring."""
        if self._preload_started:
            self.logger.info("Log message")
            return True
        
        with self._lock:
            if self._preload_started:
                return True
            
            self._preload_started = True
            
            if background:
                # Comment.
                thread = threading.Thread(
                    target=self._preload_models_worker,
                    daemon=True,
                    name="PaddleOCRModelPreloader"
                )
                thread.start()
                self.logger.info("Log message")
                return True
            else:
                # Comment.
                return self._preload_models_worker()
    
    def _preload_models_worker(self) -> bool:
        """Docstring."""
        try:
            self.logger.info("Log message")
            
            # Comment.
            try:
                from paddleocr import PPStructureV3
                ppstructure_v3_available = True
            except ImportError:
                self.logger.info("Log message")
                self._preload_completed = True
                return True
            
            if not ppstructure_v3_available:
                self._preload_completed = True
                return True
            
            # Comment.
            # Comment.
            try:
                self.logger.info("Log message")
                structure_engine = PPStructureV3(
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    use_seal_recognition=False,
                    use_formula_recognition=False,
                    use_chart_recognition=False,
                    use_region_detection=False,
                    use_table_recognition=True
                )
                self.logger.info("Log message")
                self._preload_completed = True
                return True
                
            except Exception as e:
                error_msg = str(e)
                # Comment.
                if "DependencyError" in error_msg or "paddlex" in error_msg.lower():
                    self.logger.warning(f"Log message {e}")
                    self._preload_completed = True
                    return False
                else:
                    self.logger.error(f"Log message {e}")
                    self._preload_error = e
                    self._preload_completed = True
                    return False
                    
        except Exception as e:
            self.logger.error(f"Log message {e}")
            self._preload_error = e
            self._preload_completed = True
            return False
    
    def is_preload_completed(self) -> bool:
        """Docstring."""
        return self._preload_completed
    
    def get_preload_error(self) -> Optional[Exception]:
        """Docstring."""
        return self._preload_error
    
    def check_models_exist(self) -> bool:
        """Docstring."""
        try:
            # Comment.
            # Comment.
            home_dir = os.path.expanduser("~")
            paddlex_models_dir = os.path.join(home_dir, ".paddlex", "official_models")
            
            if not os.path.exists(paddlex_models_dir):
                self.logger.info(f"Log message {paddlex_models_dir}")
                return False
            
            # Comment.
            # Comment.
            table_models = [
                "PP-LCNet_x1_0_table_cls",
                "SLANeXt_wired",
                "SLANet_plus",
                "RT-DETR-L_wired_table_cell_det",
                "RT-DETR-L_wireless_table_cell_det",
            ]
            
            # Comment.
            ocr_models = [
                "PP-OCRv5_server_det",
                "PP-OCRv5_server_rec",
            ]
            
            # Comment.
            layout_models = [
                "PP-DocBlockLayout",
                "PP-DocLayout_plus-L",
            ]
            
            all_models = table_models + ocr_models + layout_models
            
            # Comment.
            existing_models = []
            for model_name in all_models:
                model_dir = os.path.join(paddlex_models_dir, model_name)
                if os.path.exists(model_dir):
                    # Comment.
                    if os.path.isdir(model_dir) and os.listdir(model_dir):
                        existing_models.append(model_name)
            
            # Comment.
            required_table_models = ["PP-LCNet_x1_0_table_cls", "SLANeXt_wired", "SLANet_plus"]
            required_ocr_models = ["PP-OCRv5_server_det", "PP-OCRv5_server_rec"]
            
            has_table_models = any(m in existing_models for m in required_table_models)
            has_ocr_models = any(m in existing_models for m in required_ocr_models)
            
            if has_table_models and has_ocr_models and len(existing_models) >= 5:
                self.logger.info(f"Log message {len(existing_models)}")
                return True
            else:
                self.logger.info(f"Log message {len(existing_models)}")
                self.logger.info(f"Log message {has_table_models} {has_ocr_models}")
                return False
                
        except Exception as e:
            self.logger.warning(f"Log message {e}")
            return False


def preload_paddleocr_models(background: bool = True) -> bool:
    """Docstring."""
    preloader = PaddleOCRModelPreloader()
    return preloader.preload_models(background=background)


def check_paddleocr_models_exist() -> bool:
    """Docstring."""
    preloader = PaddleOCRModelPreloader()
    return preloader.check_models_exist()

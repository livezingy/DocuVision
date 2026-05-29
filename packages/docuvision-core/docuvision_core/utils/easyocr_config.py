# core/utils/easyocr_config.py
"""easyocr config module."""
import os
import easyocr
from pathlib import Path
from typing import List, Optional
from docuvision_core.utils.logger import AppLogger
from docuvision_core.utils.model_paths import easyocr_model_dir


class EasyOCRConfig:
    """Docstring."""
    
    def __init__(self):
        self.logger = AppLogger.get_logger()
        self.model_dir = str(easyocr_model_dir())
        
        # Comment.
        os.makedirs(self.model_dir, exist_ok=True)
        
        # Comment.
        self._setup_model_path()
    
    def _setup_model_path(self):
        """Docstring."""
        try:
            # Comment.
            os.environ['EASYOCR_MODULE_PATH'] = self.model_dir
            
            # Comment.
            cache_dir = os.path.join(self.model_dir, 'cache')
            os.makedirs(cache_dir, exist_ok=True)
            os.environ['EASYOCR_CACHE_DIR'] = cache_dir
            
            self.logger.info(f"Log message {self.model_dir}")
            
        except Exception as e:
            self.logger.error(f"Log message {str(e)}")
    
    def get_reader(self, languages: List[str] = ['en'], gpu: bool = False, 
                   model_storage_directory: Optional[str] = None, 
                   download_enabled: bool = True) -> easyocr.Reader:
        """
        
        Args:
            
        Returns:
        """
        try:
            # Comment.
            if model_storage_directory is None:
                model_storage_directory = self.model_dir
            
            # Comment.
            local_models_exist = self._check_local_models(languages)
            
            if local_models_exist:
                self.logger.info(f"Log message {model_storage_directory}")
                download_enabled = False
            else:
                self.logger.info("Log message")
                download_enabled = True
            
            # Comment.
            reader = easyocr.Reader(
                languages,
                gpu=gpu,
                model_storage_directory=model_storage_directory,
                download_enabled=download_enabled
            )
            
            self.logger.info(f"Log message {languages} {gpu}")
            return reader
            
        except Exception as e:
            self.logger.error(f"Log message {str(e)}")
            # Comment.
            try:
                self.logger.warning("Log message")
                return easyocr.Reader(languages, gpu=gpu, download_enabled=True)
            except Exception as fallback_error:
                self.logger.error(f"Log message {str(fallback_error)}")
                raise fallback_error
    
    def _check_local_models(self, languages: List[str]) -> bool:
        """Docstring."""
        try:
            # Comment.
            craft_model = os.path.join(self.model_dir, 'craft_mlt_25k.pth')
            if not os.path.exists(craft_model):
                self.logger.debug("Log message")
                return False
            
            # Comment.
            for lang in languages:
                if lang == 'en':
                    recog_model = os.path.join(self.model_dir, 'english_g2.pth')
                else:
                    # Comment.
                    recog_model = os.path.join(self.model_dir, f'{lang}_g2.pth')
                
                if not os.path.exists(recog_model):
                    self.logger.debug(f"Log message {recog_model}")
                    return False
            
            self.logger.debug("Log message")
            return True
            
        except Exception as e:
            self.logger.error(f"Log message {str(e)}")
            return False
    
    def download_models(self, languages: List[str] = ['en']) -> bool:
        """Docstring."""
        try:
            self.logger.info(f"Log message {languages}")
            
            # Comment.
            reader = easyocr.Reader(
                languages,
                model_storage_directory=self.model_dir,
                download_enabled=True
            )
            
            # Comment.
            import numpy as np
            test_image = np.ones((100, 100, 3), dtype=np.uint8) * 255
            _ = reader.readtext(test_image)
            
            self.logger.info("Log message")
            return True
            
        except Exception as e:
            self.logger.error(f"Log message {str(e)}")
            return False
    
    def get_model_info(self) -> dict:
        """Docstring."""
        try:
            model_info = {
                'model_directory': self.model_dir,
                'craft_model': {
                    'path': os.path.join(self.model_dir, 'craft_mlt_25k.pth'),
                    'exists': os.path.exists(os.path.join(self.model_dir, 'craft_mlt_25k.pth'))
                },
                'recognition_models': {}
            }
            
            # Comment.
            languages = ['en', 'ch_sim', 'ch_tra', 'ja', 'ko', 'th', 'vi', 'ar', 'hi']
            for lang in languages:
                if lang == 'en':
                    model_path = os.path.join(self.model_dir, 'english_g2.pth')
                else:
                    model_path = os.path.join(self.model_dir, f'{lang}_g2.pth')
                
                model_info['recognition_models'][lang] = {
                    'path': model_path,
                    'exists': os.path.exists(model_path)
                }
            
            return model_info
            
        except Exception as e:
            self.logger.error(f"Log message {str(e)}")
            return {'error': str(e)}


# Comment.
_easyocr_config = None

def get_easyocr_config() -> EasyOCRConfig:
    """Docstring."""
    global _easyocr_config
    if _easyocr_config is None:
        _easyocr_config = EasyOCRConfig()
    return _easyocr_config

def get_easyocr_reader(languages: List[str] = ['en'], gpu: bool = False) -> easyocr.Reader:
    """Docstring."""
    config = get_easyocr_config()
    return config.get_reader(languages, gpu)

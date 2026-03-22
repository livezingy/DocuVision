"""
OCR Recognition Module - Text recognition from images and PDFs
"""

from typing import Dict, Any, Optional, List
from loguru import logger
from ..base.base_module import BaseModule
from .config import OCRRecognitionConfig
from .engines.paddleocr_engine import PaddleOCREngine
# PaddleOCR-only version: Tesseract and EasyOCR disabled
# from .engines.tesseract_engine import TesseractOCREngine
# from .engines.easyocr_engine import EasyOCREngine


class OCRRecognitionModule(BaseModule):
    """OCR Recognition Module"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._config_obj = OCRRecognitionConfig(**self.config)
        self.engines: Dict[str, Any] = {}
        self.default_engine = self._config_obj.engine
    
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize module with engines"""
        if config:
            self.update_config(config)
            self._config_obj = OCRRecognitionConfig(**self.config)
        
        if not self._config_obj.enabled:
            logger.info("OCR Recognition module is disabled")
            return False
        
        # Initialize engines
        paddle_engine = PaddleOCREngine(
            use_gpu=self._config_obj.use_gpu,
            lang=self._config_obj.language
        )
        if paddle_engine.is_ready():
            self.engines["paddleocr"] = paddle_engine
        
        # PaddleOCR-only version: Tesseract and EasyOCR disabled
        # tess_engine = TesseractOCREngine()
        # if tess_engine.is_ready():
        #     self.engines["tesseract"] = tess_engine
        
        # easy_engine = EasyOCREngine(use_gpu=self._config_obj.use_gpu)
        # if easy_engine.is_ready():
        #     self.engines["easyocr"] = easy_engine
        
        self._ready = len(self.engines) > 0
        
        if self._ready:
            logger.info(f"OCR Recognition module initialized with engines: {list(self.engines.keys())}")
        else:
            logger.warning("OCR Recognition module: No engines available")
        
        return self._ready
    
    def is_ready(self) -> bool:
        return self._ready and len(self.engines) > 0
    
    async def process(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        """
        Process document for OCR recognition
        
        Args:
            input_data: File path (str) to PDF or image
            **kwargs: Additional options:
                - engine: Specific engine to use
                - language: Language code (en, ch, etc.)
                - fallback: Whether to try fallback engines
        """
        if not self.is_ready():
            raise RuntimeError("OCR Recognition module not ready")
        
        file_path = str(input_data)
        engine_name = kwargs.get("engine", self.default_engine)
        language = kwargs.get("language", self._config_obj.language)
        fallback = kwargs.get("fallback", True)
        
        engines_to_try = []
        if engine_name and engine_name in self.engines:
            engines_to_try.append(engine_name)
        else:
            # PaddleOCR-only version: Only use PaddleOCR
            for eng in ["paddleocr"]:  # Only PaddleOCR in PaddleOCR-only version
                if eng in self.engines:
                    engines_to_try.append(eng)
        
        last_error = None
        for eng_name in engines_to_try:
            try:
                eng = self.engines[eng_name]
                logger.info(f"Trying OCR with {eng.get_name()}...")
                result = await eng.recognize(file_path, language)
                result["engine_used"] = eng_name
                result["module"] = "ocr_recognition"
                return result
            except Exception as e:
                logger.warning(f"{eng_name} failed: {e}")
                last_error = e
                if not fallback:
                    raise
        
        raise RuntimeError(f"All OCR engines failed. Last error: {last_error}")
    
    def get_name(self) -> str:
        return "OCR Recognition"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_dependencies(self) -> List[str]:
        deps = []
        if "paddleocr" in self.engines:
            deps.extend(["paddleocr", "paddlepaddle"])
        if "tesseract" in self.engines:
            deps.append("pytesseract")
        if "easyocr" in self.engines:
            deps.append("easyocr")
        return deps
    
    def get_available_engines(self) -> List[str]:
        return list(self.engines.keys())

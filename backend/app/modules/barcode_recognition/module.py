"""
Barcode Recognition Module - Detect and decode barcodes and QR codes
"""

from typing import Dict, Any, Optional, List
from loguru import logger
from ..base.base_module import BaseModule
from .config import BarcodeRecognitionConfig
from .engines.pyzbar_engine import PyZBarEngine
from .engines.opencv_engine import OpenCVBarcodeEngine


class BarcodeRecognitionModule(BaseModule):
    """Barcode Recognition Module"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._config_obj = BarcodeRecognitionConfig(**self.config)
        self.engines: Dict[str, Any] = {}
        self.default_engine = self._config_obj.engine
    
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize module with engines"""
        if config:
            self.update_config(config)
            self._config_obj = BarcodeRecognitionConfig(**self.config)
        
        if not self._config_obj.enabled:
            logger.info("Barcode Recognition module is disabled")
            return False
        
        # Initialize PyZBar engine with preprocessing config
        pyzbar_config = {
            "enable_region_detection": self._config_obj.enable_region_detection,
            "enable_preprocessing": self._config_obj.enable_preprocessing,
            "enable_skew_correction": self._config_obj.enable_skew_correction,
            "enable_multiscale": self._config_obj.enable_multiscale,
            "contrast_clip_limit": self._config_obj.contrast_clip_limit,
            "sharpen_strength": self._config_obj.sharpen_strength,
            "denoise_strength": self._config_obj.denoise_strength,
            "skew_threshold": self._config_obj.skew_threshold,
            "multiscale_factors": self._config_obj.multiscale_factors,
            "region_min_area": self._config_obj.region_min_area,
            "region_max_area": self._config_obj.region_max_area,
        }
        pyzbar_engine = PyZBarEngine(config=pyzbar_config)
        if pyzbar_engine.is_ready():
            self.engines["pyzbar"] = pyzbar_engine
        
        # Initialize OpenCV engine
        opencv_engine = OpenCVBarcodeEngine()
        if opencv_engine.is_ready():
            self.engines["opencv"] = opencv_engine
        
        self._ready = len(self.engines) > 0
        
        if self._ready:
            logger.info(f"Barcode Recognition module initialized with engines: {list(self.engines.keys())}")
        else:
            logger.warning("Barcode Recognition module: No engines available")
        
        return self._ready
    
    def is_ready(self) -> bool:
        return self._ready and len(self.engines) > 0
    
    async def process(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        """
        Process document for barcode recognition
        
        Args:
            input_data: File path (str) to PDF or image
            **kwargs: Additional options:
                - engine: Specific engine to use (pyzbar, opencv)
                - fallback: Whether to try fallback engines
        """
        if not self.is_ready():
            raise RuntimeError("Barcode Recognition module not ready")
        
        file_path = str(input_data)
        engine_name = kwargs.get("engine", self.default_engine)
        fallback = kwargs.get("fallback", True)
        
        engines_to_try = []
        if engine_name and engine_name in self.engines:
            engines_to_try.append(engine_name)
        else:
            for eng in ["pyzbar", "opencv"]:
                if eng in self.engines:
                    engines_to_try.append(eng)
        
        last_error = None
        all_barcodes = []
        
        for eng_name in engines_to_try:
            try:
                eng = self.engines[eng_name]
                logger.info(f"Trying barcode recognition with {eng.get_name()}...")
                barcodes = await eng.recognize(file_path)
                all_barcodes.extend(barcodes)
                # Use first successful engine
                break
            except Exception as e:
                logger.warning(f"{eng_name} failed: {e}")
                last_error = e
                if not fallback:
                    raise
        
        # Filter by requested formats if specified
        if self._config_obj.formats:
            filtered = []
            for barcode in all_barcodes:
                if barcode.get("format") in self._config_obj.formats:
                    filtered.append(barcode)
            all_barcodes = filtered
        
        return {
            "barcodes": all_barcodes,
            "count": len(all_barcodes),
            "module": "barcode_recognition"
        }
    
    def get_name(self) -> str:
        return "Barcode Recognition"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_dependencies(self) -> List[str]:
        deps = []
        if "pyzbar" in self.engines:
            deps.append("pyzbar")
        if "opencv" in self.engines:
            deps.append("opencv-python")
        return deps
    
    def get_available_engines(self) -> List[str]:
        return list(self.engines.keys())

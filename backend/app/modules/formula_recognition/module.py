"""
Formula Recognition Module - Mathematical formula recognition
"""

from typing import Dict, Any, Optional, List
from loguru import logger
from ..base.base_module import BaseModule
from .config import FormulaRecognitionConfig


class FormulaRecognitionModule(BaseModule):
    """Formula Recognition Module - Extract mathematical formulas"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._config_obj = FormulaRecognitionConfig(**self.config)
        self.engines: Dict[str, Any] = {}
        self.default_engine = self._config_obj.engine
    
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize module with engines"""
        if config:
            self.update_config(config)
            self._config_obj = FormulaRecognitionConfig(**self.config)
        
        if not self._config_obj.enabled:
            logger.info("Formula Recognition module is disabled")
            return False
        
        # Initialize PP-Structure formula engine (extracts equations from layout)
        try:
            from ..layout_analysis.engines.ppstructure_engine import PPStructureEngine
            pp_engine = PPStructureEngine(
                use_gpu=self._config_obj.use_gpu,
                recovery=True,
                lang="ch"
            )
            if pp_engine.is_ready():
                self.engines["ppstructure"] = pp_engine
        except Exception as e:
            logger.warning(f"PP-Structure formula engine not available: {e}")
        
        # LaTeX-OCR engine (optional, requires separate installation)
        try:
            from .engines.latexocr_engine import LaTeXOCREngine
            latex_engine = LaTeXOCREngine()
            if latex_engine.is_ready():
                self.engines["latexocr"] = latex_engine
        except Exception as e:
            logger.debug(f"LaTeX-OCR engine not available: {e}")
        
        self._ready = len(self.engines) > 0
        
        if self._ready:
            logger.info(f"Formula Recognition module initialized with engines: {list(self.engines.keys())}")
        else:
            logger.warning("Formula Recognition module: No engines available")
        
        return self._ready
    
    def is_ready(self) -> bool:
        return self._ready and len(self.engines) > 0
    
    async def process(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        """
        Process document for formula recognition
        
        Args:
            input_data: File path (str) or layout analysis result dict
            **kwargs: Additional options
        """
        if not self.is_ready():
            raise RuntimeError("Formula Recognition module not ready")
        
        engine_name = kwargs.get("engine", self.default_engine)
        
        # If input is layout result, extract formulas from it
        if isinstance(input_data, dict) and "elements" in input_data:
            return self._extract_from_layout(input_data)
        
        # Otherwise process file
        file_path = str(input_data)
        
        if engine_name == "ppstructure" and "ppstructure" in self.engines:
            eng = self.engines["ppstructure"]
            layout_result = await eng.analyze(file_path)
            return self._extract_from_layout(layout_result)
        
        # Try LaTeX-OCR if available
        if "latexocr" in self.engines:
            eng = self.engines["latexocr"]
            return await eng.recognize(file_path)
        
        return {"formulas": [], "count": 0, "module": "formula_recognition"}
    
    def _extract_from_layout(self, layout_result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract formulas from layout analysis result"""
        formulas = []
        elements = layout_result.get("elements", [])
        
        for elem in elements:
            if elem.get("type") == "equation":
                formula = {
                    "id": elem.get("id", ""),
                    "page": elem.get("page", 1),
                    "bbox": elem.get("bbox", {}),
                    "latex": elem.get("text", ""),  # PP-Structure may provide LaTeX
                    "confidence": elem.get("confidence", 0.0),
                    "engine": "ppstructure"
                }
                formulas.append(formula)
        
        return {
            "formulas": formulas,
            "count": len(formulas),
            "module": "formula_recognition"
        }
    
    def get_name(self) -> str:
        return "Formula Recognition"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_dependencies(self) -> List[str]:
        deps = []
        if "ppstructure" in self.engines:
            deps.extend(["paddleocr", "paddlepaddle"])
        if "latexocr" in self.engines:
            deps.append("latex-ocr")  # Optional
        return deps
    
    def get_available_engines(self) -> List[str]:
        return list(self.engines.keys())

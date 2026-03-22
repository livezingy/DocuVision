"""
Layout Analysis Module - Document layout structure detection
"""

from typing import Dict, Any, Optional, List
from loguru import logger
from ..base.base_module import BaseModule
from .config import LayoutAnalysisConfig
from .engines.ppstructure_engine import PPStructureEngine
from .engines.layoutparser_engine import LayoutParserEngine


class LayoutAnalysisModule(BaseModule):
    """
    Layout Analysis Module
    
    Detects document structure elements such as:
    - Text blocks
    - Titles
    - Tables
    - Figures
    - Headers/Footers
    - Equations
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._config_obj = LayoutAnalysisConfig(**self.config)
        self.engines: Dict[str, Any] = {}
        self.default_engine = self._config_obj.engine
    
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize module with engines"""
        if config:
            self.update_config(config)
            self._config_obj = LayoutAnalysisConfig(**self.config)
        
        if not self._config_obj.enabled:
            logger.info("Layout Analysis module is disabled")
            return False
        
        # Initialize PP-Structure engine
        pp_engine = PPStructureEngine(
            use_gpu=self._config_obj.use_gpu,
            recovery=self._config_obj.recovery,
            lang=self._config_obj.lang
        )
        if pp_engine.is_ready():
            self.engines["ppstructure"] = pp_engine
        
        # Initialize LayoutParser engine
        lp_engine = LayoutParserEngine()
        if lp_engine.is_ready():
            self.engines["layoutparser"] = lp_engine
        
        self._ready = len(self.engines) > 0
        
        if self._ready:
            logger.info(f"Layout Analysis module initialized with engines: {list(self.engines.keys())}")
        else:
            logger.warning("Layout Analysis module: No engines available")
        
        return self._ready
    
    def is_ready(self) -> bool:
        """Check if module is ready"""
        return self._ready and len(self.engines) > 0
    
    async def process(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        """
        Process document for layout analysis
        
        Args:
            input_data: File path (str) to PDF or image
            **kwargs: Additional options:
                - engine: Specific engine to use (ppstructure, layoutparser)
                - fallback: Whether to try fallback engines on failure (default: True)
        
        Returns:
            Layout analysis result dictionary
        """
        if not self.is_ready():
            raise RuntimeError("Layout Analysis module not ready")
        
        file_path = str(input_data)
        engine_name = kwargs.get("engine", self.default_engine)
        fallback = kwargs.get("fallback", True)
        
        engines_to_try = []
        
        if engine_name and engine_name in self.engines:
            engines_to_try.append(engine_name)
        else:
            # Default order: ppstructure -> layoutparser
            for eng in ["ppstructure", "layoutparser"]:
                if eng in self.engines:
                    engines_to_try.append(eng)
        
        last_error = None
        
        for eng_name in engines_to_try:
            try:
                eng = self.engines[eng_name]
                logger.info(f"Trying layout analysis with {eng.get_name()}...")
                result = await eng.analyze(file_path)
                result["engine_used"] = eng_name
                result["module"] = "layout_analysis"
                return result
            except Exception as e:
                logger.warning(f"{eng_name} failed: {e}")
                last_error = e
                if not fallback:
                    raise
        
        raise RuntimeError(f"All layout engines failed. Last error: {last_error}")
    
    def get_name(self) -> str:
        """Get module name"""
        return "Layout Analysis"
    
    def get_version(self) -> str:
        """Get module version"""
        return "1.0.0"
    
    def get_dependencies(self) -> List[str]:
        """Get required dependencies"""
        deps = []
        if "ppstructure" in self.engines:
            deps.extend(["paddleocr", "paddlepaddle"])
        if "layoutparser" in self.engines:
            deps.append("layoutparser")
        return deps
    
    def get_available_engines(self) -> List[str]:
        """Get list of available engines"""
        return list(self.engines.keys())

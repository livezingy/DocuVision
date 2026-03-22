"""
Table Extraction Module - Extract structured table data from documents
"""

from typing import Dict, Any, Optional, List
from loguru import logger
from ..base.base_module import BaseModule
from .config import TableExtractionConfig
# Import engines will be done dynamically to avoid import errors


class TableExtractionModule(BaseModule):
    """Table Extraction Module"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._config_obj = TableExtractionConfig(**self.config)
        self.engines: Dict[str, Any] = {}
        self.default_engine = self._config_obj.engine
    
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize module with engines"""
        if config:
            self.update_config(config)
            self._config_obj = TableExtractionConfig(**self.config)
        
        if not self._config_obj.enabled:
            logger.info("Table Extraction module is disabled")
            return False
        
        # Initialize PP-Structure engine
        try:
            from .engines.ppstructure_table_engine import PPStructureTableEngine
            pp_engine = PPStructureTableEngine(use_gpu=self._config_obj.use_gpu)
            if pp_engine.is_ready():
                self.engines["ppstructure"] = pp_engine
        except Exception as e:
            logger.warning(f"PP-Structure Table engine not available: {e}")
        
        # Initialize Camelot engine
        try:
            from .engines.camelot_engine import CamelotTableEngine
            camelot_engine = CamelotTableEngine()
            if camelot_engine.is_ready():
                self.engines["camelot"] = camelot_engine
        except Exception as e:
            logger.warning(f"Camelot engine not available: {e}")
        
        # Initialize Tabula engine
        try:
            from .engines.tabula_engine import TabulaTableEngine
            tabula_engine = TabulaTableEngine()
            if tabula_engine.is_ready():
                self.engines["tabula"] = tabula_engine
        except Exception as e:
            logger.warning(f"Tabula engine not available: {e}")
        
        self._ready = len(self.engines) > 0
        
        if self._ready:
            logger.info(f"Table Extraction module initialized with engines: {list(self.engines.keys())}")
        else:
            logger.warning("Table Extraction module: No engines available")
        
        return self._ready
    
    def is_ready(self) -> bool:
        return self._ready and len(self.engines) > 0
    
    async def process(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        """
        Process document for table extraction
        
        Args:
            input_data: File path (str) to PDF or image
            **kwargs: Additional options:
                - engine: Specific engine to use
                - fallback: Whether to try fallback engines
        """
        if not self.is_ready():
            raise RuntimeError("Table Extraction module not ready")
        
        file_path = str(input_data)
        engine_name = kwargs.get("engine", self.default_engine)
        fallback = kwargs.get("fallback", True)
        
        engines_to_try = []
        if engine_name and engine_name in self.engines:
            engines_to_try.append(engine_name)
        else:
            import os
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.pdf':
                for eng in ["ppstructure", "camelot", "tabula"]:
                    if eng in self.engines:
                        engines_to_try.append(eng)
            else:
                if "ppstructure" in self.engines:
                    engines_to_try.append("ppstructure")
        
        last_error = None
        for eng_name in engines_to_try:
            try:
                eng = self.engines[eng_name]
                logger.info(f"Trying table extraction with {eng.get_name()}...")
                result = await eng.extract(file_path)
                for table in result:
                    table["engine_used"] = eng_name
                return {
                    "tables": result,
                    "count": len(result),
                    "module": "table_extraction"
                }
            except Exception as e:
                logger.warning(f"{eng_name} failed: {e}")
                last_error = e
                if not fallback:
                    raise
        
        logger.warning(f"All table engines failed. Last error: {last_error}")
        return {"tables": [], "count": 0, "module": "table_extraction"}
    
    def get_name(self) -> str:
        return "Table Extraction"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_dependencies(self) -> List[str]:
        deps = []
        if "ppstructure" in self.engines:
            deps.extend(["paddleocr", "paddlepaddle"])
        if "camelot" in self.engines:
            deps.append("camelot-py")
        if "tabula" in self.engines:
            deps.append("tabula-py")
        return deps
    
    def get_available_engines(self) -> List[str]:
        return list(self.engines.keys())

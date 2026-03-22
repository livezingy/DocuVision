"""
NLP Analysis Module - Keyword extraction and Named Entity Recognition
"""

from typing import Dict, Any, Optional, List
from loguru import logger
from ..base.base_module import BaseModule
from .config import NLPAnalysisConfig


class NLPAnalysisModule(BaseModule):
    """NLP Analysis Module"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._config_obj = NLPAnalysisConfig(**self.config)
        self.engines: Dict[str, Any] = {}
        self.default_engine = self._config_obj.engine
    
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize module with engines"""
        if config:
            self.update_config(config)
            self._config_obj = NLPAnalysisConfig(**self.config)
        
        if not self._config_obj.enabled:
            logger.info("NLP Analysis module is disabled")
            return False
        
        # Initialize engines dynamically
        # PaddleOCR-only version: spaCy and HanLP disabled
        # try:
        #     from .engines.spacy_engine import SpaCyEngine
        #     spacy_engine = SpaCyEngine(language=self._config_obj.language)
        #     if spacy_engine.is_ready():
        #         self.engines["spacy"] = spacy_engine
        # except Exception as e:
        #     logger.warning(f"SpaCy engine not available: {e}")
        
        # if self._config_obj.language in ["zh", "ch"]:
        #     try:
        #         from .engines.hanlp_engine import HanLPEngine
        #         hanlp_engine = HanLPEngine()
        #         if hanlp_engine.is_ready():
        #             self.engines["hanlp"] = hanlp_engine
        #     except Exception as e:
        #         logger.debug(f"HanLP engine not available: {e}")
        
        # Simple engine is always available
        try:
            from .engines.simple_engine import SimpleNLPEngine
            self.engines["simple"] = SimpleNLPEngine()
        except Exception as e:
            logger.warning(f"Simple NLP engine failed: {e}")
        
        self._ready = len(self.engines) > 0
        
        if self._ready:
            logger.info(f"NLP Analysis module initialized with engines: {list(self.engines.keys())}")
        else:
            logger.warning("NLP Analysis module: No engines available")
        
        return self._ready
    
    def is_ready(self) -> bool:
        return self._ready and len(self.engines) > 0
    
    async def process(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        """
        Process text for NLP analysis
        
        Args:
            input_data: Text string or dict with 'text' key
            **kwargs: Additional options:
                - engine: Specific engine to use
                - top_k_keywords: Number of keywords to extract
                - extract_entities: Whether to extract entities
        """
        if not self.is_ready():
            raise RuntimeError("NLP Analysis module not ready")
        
        # Extract text from input
        if isinstance(input_data, str):
            text = input_data
        elif isinstance(input_data, dict):
            text = input_data.get("text", "")
        else:
            raise ValueError("Input must be string or dict with 'text' key")
        
        engine_name = kwargs.get("engine", self.default_engine)
        top_k = kwargs.get("top_k_keywords", 10)
        extract_entities = kwargs.get("extract_entities", True)
        
        engines_to_try = []
        if engine_name and engine_name in self.engines:
            engines_to_try.append(engine_name)
        else:
            # PaddleOCR-only version: Only use Simple engine
            for eng in ["simple"]:  # Only Simple engine in PaddleOCR-only version
                if eng in self.engines:
                    engines_to_try.append(eng)
        
        last_error = None
        for eng_name in engines_to_try:
            try:
                eng = self.engines[eng_name]
                logger.info(f"Processing NLP with {eng.get_name()}...")
                
                keywords = await eng.extract_keywords(text, top_k)
                entities = []
                if extract_entities:
                    entities = await eng.extract_entities(text)
                
                return {
                    "keywords": keywords,
                    "entities": entities,
                    "engine_used": eng_name,
                    "module": "nlp_analysis"
                }
            except Exception as e:
                logger.warning(f"{eng_name} failed: {e}")
                last_error = e
        
        raise RuntimeError(f"All NLP engines failed. Last error: {last_error}")
    
    def get_name(self) -> str:
        return "NLP Analysis"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_dependencies(self) -> List[str]:
        deps = []
        if "spacy" in self.engines:
            deps.append("spacy")
        if "hanlp" in self.engines:
            deps.append("hanlp")
        return deps
    
    def get_available_engines(self) -> List[str]:
        return list(self.engines.keys())

"""
Template Matching Module - Document template matching and field extraction
"""

from typing import Dict, Any, Optional, List
from loguru import logger
from ..base.base_module import BaseModule
from .config import TemplateMatchingConfig


class TemplateMatchingModule(BaseModule):
    """Template Matching Module"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._config_obj = TemplateMatchingConfig(**self.config)
        self._template_service = None
    
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Initialize module with template service"""
        if config:
            self.update_config(config)
            self._config_obj = TemplateMatchingConfig(**self.config)
        
        if not self._config_obj.enabled:
            logger.info("Template Matching module is disabled")
            return False
        
        try:
            # Import template service from services
            from ...services.template_service import TemplateService
            self._template_service = TemplateService(templates_dir=self._config_obj.templates_dir)
            self._ready = True
            logger.info("Template Matching module initialized successfully")
        except Exception as e:
            logger.error(f"Template Matching module initialization failed: {e}")
            self._ready = False
        
        return self._ready
    
    def is_ready(self) -> bool:
        return self._ready and self._template_service is not None
    
    async def process(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        """
        Process document for template matching
        
        Args:
            input_data: Dict containing:
                - text: Document text
                - text_blocks: OCR text blocks (optional)
                - tables: Extracted tables (optional)
                - layout_elements: Layout elements (optional)
            **kwargs: Additional options:
                - template_id: Specific template to use
                - auto_detect: Whether to auto-detect template
        """
        if not self.is_ready():
            raise RuntimeError("Template Matching module not ready")
        
        template_id = kwargs.get("template_id")
        auto_detect = kwargs.get("auto_detect", False)
        
        if isinstance(input_data, dict):
            text = input_data.get("text", "")
            text_blocks = input_data.get("text_blocks", [])
            tables = input_data.get("tables", [])
            layout_elements = input_data.get("layout_elements", [])
        else:
            raise ValueError("Input must be dict with 'text' key")
        
        if auto_detect or not template_id:
            # Auto-detect template
            result = await self._template_service.auto_extract(
                text, text_blocks, tables
            )
            return {
                **result,
                "module": "template_matching"
            }
        else:
            # Use specific template
            result = await self._template_service.extract_fields(
                template_id, text, text_blocks, tables, layout_elements
            )
            return {
                "success": True,
                "result": result,
                "module": "template_matching"
            }
    
    def get_name(self) -> str:
        return "Template Matching"
    
    def get_version(self) -> str:
        return "1.0.0"
    
    def get_dependencies(self) -> List[str]:
        return []  # No external dependencies, uses existing template service
    
    def get_available_engines(self) -> List[str]:
        if self._template_service:
            templates = self._template_service.list_templates()
            return [t["template_id"] for t in templates]
        return []
    
    def list_templates(self) -> List[Dict[str, Any]]:
        """List available templates"""
        if self._template_service:
            return self._template_service.list_templates()
        return []

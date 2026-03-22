"""
Base Module Interface - Abstract base class for all processing modules
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseModule(ABC):
    """模块基类，定义统一接口"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize module with configuration
        
        Args:
            config: Module configuration dictionary
        """
        self.config = config or {}
        self._ready = False
    
    @abstractmethod
    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Initialize module
        
        Args:
            config: Optional configuration to override default config
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    def is_ready(self) -> bool:
        """
        Check if module is ready to process
        
        Returns:
            True if module is ready, False otherwise
        """
        pass
    
    @abstractmethod
    async def process(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        """
        Process input data
        
        Args:
            input_data: Input data (file path, text, etc.)
            **kwargs: Additional processing options
        
        Returns:
            Processing result dictionary
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Get module name
        
        Returns:
            Module name string
        """
        pass
    
    @abstractmethod
    def get_version(self) -> str:
        """
        Get module version
        
        Returns:
            Version string
        """
        pass
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get current module configuration
        
        Returns:
            Configuration dictionary
        """
        return self.config.copy()
    
    def get_dependencies(self) -> List[str]:
        """
        Get list of required Python packages
        
        Returns:
            List of package names
        """
        return []
    
    def get_available_engines(self) -> List[str]:
        """
        Get list of available engines/implementations
        
        Returns:
            List of engine names
        """
        return []
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """
        Update module configuration
        
        Args:
            config: Configuration dictionary to merge
        """
        self.config.update(config)

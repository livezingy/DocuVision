"""
Module Registry - Central registry for all processing modules
"""

from typing import Dict, Type, Optional
from loguru import logger
from .base_module import BaseModule


class ModuleRegistry:
    """模块注册器，管理所有可用模块"""
    
    _modules: Dict[str, Type[BaseModule]] = {}
    _instances: Dict[str, BaseModule] = {}
    
    @classmethod
    def register(cls, module_name: str, module_class: Type[BaseModule]) -> None:
        """
        Register a module class
        
        Args:
            module_name: Unique module identifier
            module_class: Module class that inherits from BaseModule
        """
        if not issubclass(module_class, BaseModule):
            raise TypeError(f"{module_class} must inherit from BaseModule")
        
        cls._modules[module_name] = module_class
        logger.info(f"Registered module: {module_name}")
    
    @classmethod
    def get_module(cls, module_name: str, config: Optional[Dict] = None, create_instance: bool = True) -> Optional[BaseModule]:
        """
        Get module instance
        
        Args:
            module_name: Module identifier
            config: Optional configuration for module initialization
            create_instance: Whether to create new instance if not exists
        
        Returns:
            Module instance or None if not found
        """
        if module_name not in cls._modules:
            logger.warning(f"Module not found: {module_name}")
            return None
        
        # Return existing instance if available
        if module_name in cls._instances:
            return cls._instances[module_name]
        
        # Create new instance if requested
        if create_instance:
            module_class = cls._modules[module_name]
            try:
                instance = module_class(config=config)
                if instance.initialize(config):
                    cls._instances[module_name] = instance
                    return instance
                else:
                    logger.warning(f"Module {module_name} initialization failed")
            except Exception as e:
                logger.error(f"Failed to create module {module_name}: {e}")
        
        return None
    
    @classmethod
    def list_modules(cls) -> List[str]:
        """
        List all registered module names
        
        Returns:
            List of module names
        """
        return list(cls._modules.keys())
    
    @classmethod
    def unregister(cls, module_name: str) -> bool:
        """
        Unregister a module
        
        Args:
            module_name: Module identifier
        
        Returns:
            True if unregistered, False if not found
        """
        if module_name in cls._modules:
            del cls._modules[module_name]
            if module_name in cls._instances:
                del cls._instances[module_name]
            logger.info(f"Unregistered module: {module_name}")
            return True
        return False
    
    @classmethod
    def clear_instances(cls) -> None:
        """Clear all module instances"""
        cls._instances.clear()
        logger.info("Cleared all module instances")

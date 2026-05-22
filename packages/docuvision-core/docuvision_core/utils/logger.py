# core/utils/logger.py
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
import os
import sys
import traceback
from typing import Optional, Dict, Any
from docuvision_core.utils.path_utils import get_output_paths

class AppLogger:
    """Application log manager
    
    Provides centralized logging functionality.
    Supports file and console logging with rotation.
    """
    
    _instance = None
    _logger = None
    
    @classmethod
    def get_logger(cls, config: Dict = None) -> 'AppLogger':
        """Get logger instance with optional configuration

        Args:
            config: Configuration dictionary (optional)
        
        Returns:
            AppLogger instance
        """
        if cls._instance is None:
            cls._instance = cls(config)
        elif config is not None:
            # Update config if provided
            cls._instance.update_config(config)
        return cls._instance

    def __init__(self, config: Dict = None):
        """Initialize logger with optional configuration"""
        if AppLogger._instance is not None:
            raise Exception("This class is a singleton!")
        AppLogger._instance = self
        self.config = config if config is not None else {}  # Initialize config dictionary
        self._init_logger()
    
    def update_config(self, config: Dict):
        """Update logger configuration
        
        Args:
            config: New configuration dictionary
        """
        self.config.update(config)
        self._init_logger()  # Reinitialize logger with new config
            
    def _init_logger(self):
        """Initialize logger configuration"""
        # Create logger
        self._logger = logging.getLogger('PDFExtractor')
        self._logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )

         # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        self._logger.addHandler(console_handler)        
        
        # Create file handler
        output_path = self.config.get('output_path', None)
        log_dir = ''
        if output_path:
            paths = get_output_paths(output_path)
            log_dir = paths['debug']
        else:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')

        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
                os.path.join(log_dir, 'app.log'),
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        self._logger.addHandler(file_handler)         
        
        # Set class logger
        AppLogger._logger = self._logger

        
    def debug(self, message: str, data: Optional[Dict] = None):
        """Log debug message
        
        Args:
            message: Log message
            data: Additional data
        """
        if data:
            message = f"{message} - {data}"
        self._logger.debug(message)
        
    def info(self, message: str, data: Optional[Dict] = None):
        """Log info message
        
        Args:
            message: Log message
            data: Additional data
        """
        if data:
            message = f"{message} - {data}"
        self._logger.info(message)
        
    def warning(self, message: str, data: Optional[Dict] = None):
        """Log warning message
        
        Args:
            message: Log message
            data: Additional data
        """
        if data:
            message = f"{message} - {data}"
        self._logger.warning(message)
        
    def error(self, message: str, exc_info: bool = False):
        """Log error message
        
        Args:
            message: Error message
            exc_info: Whether to include exception info
        """
        if exc_info:
            self._logger.error(message, exc_info=True)
        else:
            self._logger.error(message)
        
    def critical(self, message: str, data: Optional[Dict] = None):
        """Log critical message
        
        Args:
            message: Log message
            data: Additional data
        """
        if data:
            message = f"{message} - {data}"
        self._logger.critical(message)
        
    def log_exception(self, exception: Exception, data: Optional[Dict] = None):
        """Log exception
        
        Args:
            exception: Exception object
            data: Additional data
        """
        message = f"Exception: {str(exception)}"
        if data:
            message = f"{message} - {data}"
        self._logger.exception(message)
        
    def log_operation(self, operation: str, data: Optional[Dict] = None):
        """Log operation
        
        Args:
            operation: Operation name
            data: Additional data
        """
        message = f"Operation: {operation}"
        if data:
            message = f"{message} - {data}"
        self._logger.info(message)
        
    def log_performance(self, operation: str, duration: float, data: Optional[Dict] = None):
        """Log performance
        
        Args:
            operation: Operation name
            duration: Duration in seconds
            data: Additional data
        """
        message = f"Performance: {operation} - {duration:.2f}s"
        if data:
            message = f"{message} - {data}"
        self._logger.info(message)
        
    def set_output_path(self, output_path: str):
        """Set output path and reinitialize logger
        
        Args:
            output_path: Path to output directory
        """
        self.config['output_path'] = output_path
        self._init_logger()  # Reinitialize logger with new path
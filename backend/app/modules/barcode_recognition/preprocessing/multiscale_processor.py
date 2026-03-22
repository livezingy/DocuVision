"""
Multi-Scale Processor - Process images at multiple scales for better recognition
"""

from typing import List, Dict, Any, Optional, Callable
from loguru import logger
import numpy as np


class MultiScaleProcessor:
    """
    Multi-Scale Processor for barcode recognition
    
    Processes images at different scales to improve recognition
    of barcodes that are too small or too large.
    """
    
    def __init__(self, scale_factors: Optional[List[float]] = None):
        """
        Initialize multi-scale processor
        
        Args:
            scale_factors: List of scale factors to try (default: [0.5, 0.75, 1.0, 1.5, 2.0])
        """
        if scale_factors is None:
            self.scale_factors = [0.5, 0.75, 1.0, 1.5, 2.0]
        else:
            self.scale_factors = sorted(scale_factors)
        
        self._opencv_available = False
        self._init_opencv()
    
    def _init_opencv(self):
        """Initialize OpenCV"""
        try:
            import cv2
            self._opencv_available = True
        except ImportError:
            logger.warning("OpenCV not available for multi-scale processing")
            self._opencv_available = False
    
    def process_multiscale(
        self,
        image: np.ndarray,
        recognition_func: Callable[[np.ndarray], List[Any]],
        start_scale: Optional[float] = None
    ) -> List[Any]:
        """
        Process image at multiple scales
        
        Args:
            image: Input image
            recognition_func: Function that takes image and returns recognition results
            start_scale: Starting scale factor (if None, uses original scale first)
        
        Returns:
            List of recognition results (from first successful scale)
        """
        if not self._opencv_available:
            return recognition_func(image)
        
        import cv2
        
        # Determine processing order
        if start_scale is not None and start_scale in self.scale_factors:
            # Start with specified scale
            scales = [start_scale] + [s for s in self.scale_factors if s != start_scale]
        else:
            # Start with original scale (1.0) if available, otherwise start from smallest
            if 1.0 in self.scale_factors:
                scales = [1.0] + [s for s in self.scale_factors if s != 1.0]
            else:
                scales = self.scale_factors
        
        for scale in scales:
            try:
                # Scale image
                if scale == 1.0:
                    scaled_img = image
                else:
                    h, w = image.shape[:2]
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    
                    # Use INTER_CUBIC for upscaling, INTER_AREA for downscaling
                    interp = cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA
                    scaled_img = cv2.resize(image, (new_w, new_h), interpolation=interp)
                
                # Try recognition
                results = recognition_func(scaled_img)
                
                # If successful, return results
                if results:
                    logger.debug(f"Multi-scale recognition succeeded at scale {scale}")
                    return results
            except Exception as e:
                logger.debug(f"Multi-scale processing failed at scale {scale}: {e}")
                continue
        
        # All scales failed
        return []
    
    def process_with_strategies(
        self,
        image: np.ndarray,
        recognition_func: Callable[[np.ndarray], List[Any]],
        enhancement_func: Optional[Callable[[np.ndarray, Dict], np.ndarray]] = None
    ) -> List[Any]:
        """
        Process image with multiple enhancement strategies at different scales
        
        Args:
            image: Input image
            recognition_func: Recognition function
            enhancement_func: Optional enhancement function (img, params) -> enhanced_img
        
        Returns:
            Recognition results
        """
        # Strategy 1: Original image
        results = recognition_func(image)
        if results:
            return results
        
        # Strategy 2: Multi-scale with original image
        results = self.process_multiscale(image, recognition_func)
        if results:
            return results
        
        # Strategy 3: Enhanced + multi-scale
        if enhancement_func:
            strategies = [
                {"contrast": 2.0, "sharpen": 1.0},
                {"contrast": 3.0, "sharpen": 1.5},
                {"contrast": 1.5, "sharpen": 0.5},
            ]
            
            for strategy in strategies:
                enhanced = enhancement_func(image, strategy)
                results = self.process_multiscale(enhanced, recognition_func)
                if results:
                    return results
        
        return []
    
    def get_optimal_scale(
        self,
        image: np.ndarray,
        recognition_func: Callable[[np.ndarray], List[Any]],
        min_size: int = 100,
        max_size: int = 2000
    ) -> Optional[float]:
        """
        Find optimal scale factor for recognition
        
        Args:
            image: Input image
            recognition_func: Recognition function
            min_size: Minimum dimension size
            max_size: Maximum dimension size
        
        Returns:
            Optimal scale factor or None if not found
        """
        h, w = image.shape[:2]
        current_size = max(h, w)
        
        # If image is already in good size range, return 1.0
        if min_size <= current_size <= max_size:
            results = recognition_func(image)
            if results:
                return 1.0
        
        # Try different scales
        for scale in self.scale_factors:
            scaled_size = int(current_size * scale)
            if min_size <= scaled_size <= max_size:
                import cv2
                new_w = int(w * scale)
                new_h = int(h * scale)
                interp = cv2.INTER_CUBIC if scale > 1.0 else cv2.INTER_AREA
                scaled_img = cv2.resize(image, (new_w, new_h), interpolation=interp)
                
                results = recognition_func(scaled_img)
                if results:
                    return scale
        
        return None

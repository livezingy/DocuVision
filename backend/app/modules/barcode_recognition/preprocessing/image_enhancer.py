"""
Image Enhancer - Enhance image quality for better barcode recognition
"""

from typing import Optional, Tuple
from loguru import logger
import numpy as np


class ImageEnhancer:
    """
    Image Enhancer for barcode recognition
    
    Provides various image enhancement techniques:
    - Contrast enhancement (CLAHE)
    - Sharpening
    - Denoising
    - Binarization
    """
    
    def __init__(
        self,
        contrast_clip_limit: float = 2.0,
        sharpen_strength: float = 1.0,
        denoise_strength: int = 9
    ):
        """
        Initialize image enhancer
        
        Args:
            contrast_clip_limit: CLAHE clip limit for contrast enhancement
            sharpen_strength: Sharpening kernel strength
            denoise_strength: Denoising filter size (must be odd)
        """
        self.contrast_clip_limit = contrast_clip_limit
        self.sharpen_strength = sharpen_strength
        self.denoise_strength = denoise_strength if denoise_strength % 2 == 1 else denoise_strength + 1
        self._opencv_available = False
        self._init_opencv()
    
    def _init_opencv(self):
        """Initialize OpenCV"""
        try:
            import cv2
            self._opencv_available = True
        except ImportError:
            logger.warning("OpenCV not available for image enhancement")
            self._opencv_available = False
    
    def enhance(
        self,
        image: np.ndarray,
        enable_contrast: bool = True,
        enable_sharpen: bool = True,
        enable_denoise: bool = True,
        enable_binarize: bool = False
    ) -> np.ndarray:
        """
        Apply comprehensive image enhancement
        
        Args:
            image: Input image (BGR or grayscale)
            enable_contrast: Enable contrast enhancement
            enable_sharpen: Enable sharpening
            enable_denoise: Enable denoising
            enable_binarize: Enable binarization
        
        Returns:
            Enhanced image
        """
        if not self._opencv_available:
            return image
        
        import cv2
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        enhanced = gray.copy()
        
        # 1. Contrast enhancement
        if enable_contrast:
            enhanced = self.enhance_contrast(enhanced)
        
        # 2. Denoising (before sharpening to avoid amplifying noise)
        if enable_denoise:
            enhanced = self.denoise(enhanced)
        
        # 3. Sharpening
        if enable_sharpen:
            enhanced = self.sharpen(enhanced)
        
        # 4. Binarization (optional, for some barcode types)
        if enable_binarize:
            enhanced = self.binarize(enhanced)
        
        return enhanced
    
    def enhance_contrast(self, image: np.ndarray, clip_limit: Optional[float] = None) -> np.ndarray:
        """
        Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
        
        Args:
            image: Grayscale image
            clip_limit: CLAHE clip limit (uses default if None)
        
        Returns:
            Contrast-enhanced image
        """
        if not self._opencv_available:
            return image
        
        import cv2
        
        clip_limit = clip_limit or self.contrast_clip_limit
        
        try:
            clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
            enhanced = clahe.apply(image)
            return enhanced
        except Exception as e:
            logger.warning(f"Contrast enhancement failed: {e}")
            return image
    
    def sharpen(self, image: np.ndarray, strength: Optional[float] = None) -> np.ndarray:
        """
        Apply sharpening filter
        
        Args:
            image: Grayscale image
            strength: Sharpening strength (uses default if None)
        
        Returns:
            Sharpened image
        """
        if not self._opencv_available:
            return image
        
        import cv2
        
        strength = strength or self.sharpen_strength
        
        try:
            # Unsharp masking kernel
            # Kernel: [[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]]
            # Adjust center value based on strength
            center = 8 + strength
            kernel = np.array([
                [-strength, -strength, -strength],
                [-strength, center, -strength],
                [-strength, -strength, -strength]
            ], dtype=np.float32)
            
            sharpened = cv2.filter2D(image, -1, kernel)
            
            # Clip values to valid range
            sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
            
            return sharpened
        except Exception as e:
            logger.warning(f"Sharpening failed: {e}")
            return image
    
    def denoise(self, image: np.ndarray, strength: Optional[int] = None) -> np.ndarray:
        """
        Apply denoising using bilateral filter
        
        Args:
            image: Grayscale image
            strength: Filter size (uses default if None)
        
        Returns:
            Denoised image
        """
        if not self._opencv_available:
            return image
        
        import cv2
        
        strength = strength or self.denoise_strength
        if strength % 2 == 0:
            strength += 1
        
        try:
            # Bilateral filter preserves edges while reducing noise
            denoised = cv2.bilateralFilter(image, strength, 75, 75)
            return denoised
        except Exception as e:
            logger.warning(f"Denoising failed: {e}")
            return image
    
    def binarize(self, image: np.ndarray, method: str = "adaptive") -> np.ndarray:
        """
        Apply binarization (thresholding)
        
        Args:
            image: Grayscale image
            method: Binarization method ("adaptive", "otsu", "simple")
        
        Returns:
            Binary image
        """
        if not self._opencv_available:
            return image
        
        import cv2
        
        try:
            if method == "adaptive":
                # Adaptive thresholding - good for varying lighting
                binary = cv2.adaptiveThreshold(
                    image, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY,
                    11, 2
                )
            elif method == "otsu":
                # Otsu's method - automatic threshold selection
                _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            else:
                # Simple thresholding
                _, binary = cv2.threshold(image, 127, 255, cv2.THRESH_BINARY)
            
            return binary
        except Exception as e:
            logger.warning(f"Binarization failed: {e}")
            return image
    
    def enhance_aggressive(self, image: np.ndarray) -> np.ndarray:
        """
        Apply aggressive enhancement for difficult cases
        
        Args:
            image: Input image
        
        Returns:
            Aggressively enhanced image
        """
        # Higher contrast
        enhanced = self.enhance_contrast(image, clip_limit=3.0)
        
        # Stronger denoising
        enhanced = self.denoise(enhanced, strength=15)
        
        # Stronger sharpening
        enhanced = self.sharpen(enhanced, strength=1.5)
        
        return enhanced
    
    def auto_enhance(self, image: np.ndarray) -> np.ndarray:
        """
        Automatically enhance image based on quality assessment
        
        Args:
            image: Input image
        
        Returns:
            Auto-enhanced image
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            import cv2
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Assess image quality
        contrast_score = self._assess_contrast(gray)
        blur_score = self._assess_blur(gray)
        noise_score = self._assess_noise(gray)
        
        enhanced = gray.copy()
        
        # Apply enhancements based on quality scores
        if contrast_score < 0.3:  # Low contrast
            enhanced = self.enhance_contrast(enhanced, clip_limit=3.0)
        elif contrast_score < 0.5:
            enhanced = self.enhance_contrast(enhanced, clip_limit=2.0)
        
        if noise_score > 0.5:  # High noise
            enhanced = self.denoise(enhanced, strength=15)
        elif noise_score > 0.3:
            enhanced = self.denoise(enhanced, strength=9)
        
        if blur_score > 0.5:  # High blur
            enhanced = self.sharpen(enhanced, strength=1.5)
        elif blur_score > 0.3:
            enhanced = self.sharpen(enhanced, strength=1.0)
        
        return enhanced
    
    def _assess_contrast(self, image: np.ndarray) -> float:
        """Assess image contrast (0-1, higher is better)"""
        if not self._opencv_available:
            return 0.5
        
        import cv2
        
        # Calculate standard deviation of pixel values
        std = np.std(image)
        # Normalize to 0-1 range (assuming max std ~100 for good contrast)
        contrast_score = min(1.0, std / 100.0)
        return contrast_score
    
    def _assess_blur(self, image: np.ndarray) -> float:
        """Assess image blur (0-1, higher is more blurred)"""
        if not self._opencv_available:
            return 0.5
        
        import cv2
        
        # Laplacian variance method
        laplacian_var = cv2.Laplacian(image, cv2.CV_64F).var()
        # Lower variance = more blur
        # Normalize (assuming threshold ~100)
        blur_score = max(0.0, 1.0 - (laplacian_var / 100.0))
        return blur_score
    
    def _assess_noise(self, image: np.ndarray) -> float:
        """Assess image noise (0-1, higher is more noisy)"""
        if not self._opencv_available:
            return 0.5
        
        import cv2
        
        # Calculate local variance (high variance = high noise)
        kernel = np.ones((5, 5), np.float32) / 25
        local_mean = cv2.filter2D(image.astype(np.float32), -1, kernel)
        local_var = cv2.filter2D((image.astype(np.float32) - local_mean) ** 2, -1, kernel)
        avg_var = np.mean(local_var)
        
        # Normalize (assuming threshold ~500)
        noise_score = min(1.0, avg_var / 500.0)
        return noise_score

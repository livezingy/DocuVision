"""
Skew Corrector - Detect and correct skew/rotation in barcode images
"""

from typing import Optional, Tuple
from loguru import logger
import numpy as np


class SkewCorrector:
    """
    Skew Corrector for barcode images
    
    Detects rotation angle and corrects skew to improve recognition accuracy.
    """
    
    def __init__(self, angle_threshold: float = 2.0):
        """
        Initialize skew corrector
        
        Args:
            angle_threshold: Minimum angle (degrees) to trigger correction
        """
        self.angle_threshold = angle_threshold
        self._opencv_available = False
        self._init_opencv()
    
    def _init_opencv(self):
        """Initialize OpenCV"""
        try:
            import cv2
            self._opencv_available = True
        except ImportError:
            logger.warning("OpenCV not available for skew correction")
            self._opencv_available = False
    
    def detect_skew_angle(self, image: np.ndarray, method: str = "auto") -> float:
        """
        Detect skew angle in image
        
        Args:
            image: Grayscale image
            method: Detection method ("hough", "contour", "projection", "auto")
        
        Returns:
            Skew angle in degrees (positive = counterclockwise)
        """
        if not self._opencv_available:
            return 0.0
        
        import cv2
        
        if method == "auto":
            # Try multiple methods and return most consistent result
            angles = []
            
            # Method 1: Hough lines
            try:
                angle1 = self._detect_skew_hough(image)
                if angle1 is not None:
                    angles.append(angle1)
            except:
                pass
            
            # Method 2: Contour-based
            try:
                angle2 = self._detect_skew_contour(image)
                if angle2 is not None:
                    angles.append(angle2)
            except:
                pass
            
            # Method 3: Projection-based
            try:
                angle3 = self._detect_skew_projection(image)
                if angle3 is not None:
                    angles.append(angle3)
            except:
                pass
            
            if angles:
                # Return median angle (most robust)
                angles.sort()
                return angles[len(angles) // 2]
            else:
                return 0.0
        
        elif method == "hough":
            return self._detect_skew_hough(image) or 0.0
        elif method == "contour":
            return self._detect_skew_contour(image) or 0.0
        elif method == "projection":
            return self._detect_skew_projection(image) or 0.0
        else:
            return 0.0
    
    def _detect_skew_hough(self, image: np.ndarray) -> Optional[float]:
        """Detect skew using Hough line transform"""
        import cv2
        
        # Edge detection
        edges = cv2.Canny(image, 50, 150, apertureSize=3)
        
        # Hough line detection
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)
        
        if lines is None or len(lines) == 0:
            return None
        
        angles = []
        for line in lines:
            rho, theta = line[0]
            # Convert to degrees
            angle_deg = np.degrees(theta) - 90
            
            # Normalize to -45 to 45 degrees
            if angle_deg > 45:
                angle_deg -= 90
            elif angle_deg < -45:
                angle_deg += 90
            
            angles.append(angle_deg)
        
        if not angles:
            return None
        
        # Return median angle
        angles.sort()
        return angles[len(angles) // 2]
    
    def _detect_skew_contour(self, image: np.ndarray) -> Optional[float]:
        """Detect skew using contour analysis"""
        import cv2
        
        # Binarize image
        _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # Find largest contour (likely the barcode)
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Get minimum area rectangle
        rect = cv2.minAreaRect(largest_contour)
        angle = rect[2]
        
        # Normalize angle
        if angle < -45:
            angle += 90
        elif angle > 45:
            angle -= 90
        
        return angle
    
    def _detect_skew_projection(self, image: np.ndarray) -> Optional[float]:
        """Detect skew using projection profile analysis"""
        import cv2
        
        # Binarize
        _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Try different angles and find maximum variance
        best_angle = 0.0
        max_variance = 0.0
        
        angles_to_try = np.arange(-45, 46, 0.5)
        
        for angle in angles_to_try:
            # Rotate image
            h, w = binary.shape
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(binary, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            
            # Calculate horizontal projection variance
            projection = np.sum(rotated, axis=1)
            variance = np.var(projection)
            
            if variance > max_variance:
                max_variance = variance
                best_angle = angle
        
        return best_angle if max_variance > 0 else None
    
    def correct_skew(
        self,
        image: np.ndarray,
        angle: Optional[float] = None,
        method: str = "auto"
    ) -> Tuple[np.ndarray, float]:
        """
        Correct skew in image
        
        Args:
            image: Input image
            angle: Skew angle in degrees (if None, will detect automatically)
            method: Detection method if angle is None
        
        Returns:
            Tuple of (corrected_image, actual_angle_used)
        """
        if not self._opencv_available:
            return image, 0.0
        
        import cv2
        
        # Detect angle if not provided
        if angle is None:
            angle = self.detect_skew_angle(image, method=method)
        
        # Check if correction is needed
        if abs(angle) < self.angle_threshold:
            return image, 0.0
        
        # Perform rotation
        h, w = image.shape[:2]
        center = (w // 2, h // 2)
        
        # Get rotation matrix
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Calculate new image dimensions
        cos = np.abs(M[0, 0])
        sin = np.abs(M[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))
        
        # Adjust rotation matrix for new dimensions
        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]
        
        # Apply rotation
        corrected = cv2.warpAffine(
            image, M, (new_w, new_h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        
        return corrected, angle
    
    def needs_correction(self, image: np.ndarray) -> bool:
        """
        Check if image needs skew correction
        
        Args:
            image: Input image
        
        Returns:
            True if correction is needed
        """
        angle = self.detect_skew_angle(image)
        return abs(angle) >= self.angle_threshold

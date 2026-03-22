"""
Region Detector - Detect barcode and QR code regions in images
"""

from typing import List, Dict, Any, Tuple, Optional
from loguru import logger
import numpy as np


class RegionDetector:
    """
    Region Detector for barcodes and QR codes
    
    Uses OpenCV-based methods to detect potential barcode regions
    before recognition, improving accuracy and performance.
    """
    
    def __init__(self, min_area: int = 100, max_area: int = 1000000):
        """
        Initialize region detector
        
        Args:
            min_area: Minimum area for detected regions
            max_area: Maximum area for detected regions
        """
        self.min_area = min_area
        self.max_area = max_area
        self._qr_detector = None
        self._init_detectors()
    
    def _init_detectors(self):
        """Initialize OpenCV detectors"""
        try:
            import cv2
            self._qr_detector = cv2.QRCodeDetector()
            self._opencv_available = True
        except ImportError:
            logger.warning("OpenCV not available for region detection")
            self._opencv_available = False
    
    def detect_regions(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect all barcode and QR code regions in image
        
        Args:
            image: Input image (BGR format)
        
        Returns:
            List of detected regions with bbox and type
        """
        if not self._opencv_available:
            return []
        
        regions = []
        
        # Detect QR codes
        qr_regions = self.detect_qr_regions(image)
        regions.extend(qr_regions)
        
        # Detect barcodes
        barcode_regions = self.detect_barcode_regions(image)
        regions.extend(barcode_regions)
        
        return regions
    
    def detect_qr_regions(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect QR code regions using OpenCV QRCodeDetector
        
        Args:
            image: Input image (BGR format)
        
        Returns:
            List of QR code regions
        """
        if not self._opencv_available or self._qr_detector is None:
            return []
        
        import cv2
        
        try:
            # Detect multiple QR codes
            retval, decoded_info, points, straight_qrcode = self._qr_detector.detectAndDecodeMulti(image)
            
            regions = []
            if retval and points is not None:
                for idx, (info, qr_points) in enumerate(zip(decoded_info, points)):
                    if info:  # Successfully decoded
                        # Already decoded, skip region detection
                        continue
                    
                    # Extract bounding box
                    qr_points = qr_points.astype(int)
                    x_coords = qr_points[:, 0]
                    y_coords = qr_points[:, 1]
                    
                    bbox = {
                        "x": int(min(x_coords)),
                        "y": int(min(y_coords)),
                        "width": int(max(x_coords) - min(x_coords)),
                        "height": int(max(y_coords) - min(y_coords))
                    }
                    
                    # Check area constraints
                    area = bbox["width"] * bbox["height"]
                    if self.min_area <= area <= self.max_area:
                        regions.append({
                            "type": "qr_code",
                            "bbox": bbox,
                            "polygon": qr_points.tolist(),
                            "confidence": 0.8  # OpenCV detection confidence
                        })
            
            return regions
        except Exception as e:
            logger.warning(f"QR code region detection failed: {e}")
            return []
    
    def detect_barcode_regions(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect barcode regions using edge detection and contour analysis
        
        Args:
            image: Input image (BGR format)
        
        Returns:
            List of barcode regions
        """
        if not self._opencv_available:
            return []
        
        import cv2
        
        try:
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Edge detection
            edges = cv2.Canny(blurred, 50, 150)
            
            # Morphological operations to connect nearby edges
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3))
            dilated = cv2.dilate(edges, kernel, iterations=2)
            
            # Find contours
            contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            regions = []
            for contour in contours:
                # Filter by area
                area = cv2.contourArea(contour)
                if area < self.min_area or area > self.max_area:
                    continue
                
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter by aspect ratio (barcodes are typically long and narrow)
                aspect_ratio = w / float(h) if h > 0 else 0
                
                # Barcode characteristics:
                # - Aspect ratio > 2:1 (longer than tall)
                # - Reasonable size
                if aspect_ratio < 2.0:
                    continue
                
                # Calculate solidity (ratio of contour area to bounding box area)
                rect_area = w * h
                solidity = area / float(rect_area) if rect_area > 0 else 0
                
                # Barcodes should have reasonable solidity
                if solidity < 0.3:
                    continue
                
                # Get rotated bounding box for better fit
                rect = cv2.minAreaRect(contour)
                box_points = cv2.boxPoints(rect)
                box_points = np.int0(box_points)
                
                regions.append({
                    "type": "barcode",
                    "bbox": {
                        "x": int(x),
                        "y": int(y),
                        "width": int(w),
                        "height": int(h)
                    },
                    "polygon": box_points.tolist(),
                    "angle": rect[2],  # Rotation angle
                    "confidence": min(0.7, solidity * 1.5)  # Confidence based on solidity
                })
            
            # Sort by confidence (highest first)
            regions.sort(key=lambda r: r["confidence"], reverse=True)
            
            # Remove overlapping regions (keep highest confidence)
            filtered_regions = self._filter_overlapping(regions)
            
            return filtered_regions
        except Exception as e:
            logger.warning(f"Barcode region detection failed: {e}")
            return []
    
    def _filter_overlapping(self, regions: List[Dict[str, Any]], iou_threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Filter overlapping regions, keeping highest confidence ones
        
        Args:
            regions: List of detected regions
            iou_threshold: IoU threshold for considering overlap
        
        Returns:
            Filtered list of regions
        """
        if not regions:
            return []
        
        filtered = []
        used = set()
        
        for i, region1 in enumerate(regions):
            if i in used:
                continue
            
            bbox1 = region1["bbox"]
            overlap_found = False
            
            for j, region2 in enumerate(filtered):
                bbox2 = region2["bbox"]
                iou = self._calculate_iou(bbox1, bbox2)
                
                if iou > iou_threshold:
                    # Overlap found, keep the one with higher confidence
                    if region1["confidence"] > region2["confidence"]:
                        filtered.remove(region2)
                        filtered.append(region1)
                    overlap_found = True
                    break
            
            if not overlap_found:
                filtered.append(region1)
            
            used.add(i)
        
        return filtered
    
    def _calculate_iou(self, bbox1: Dict, bbox2: Dict) -> float:
        """Calculate Intersection over Union (IoU) of two bounding boxes"""
        x1 = max(bbox1["x"], bbox2["x"])
        y1 = max(bbox1["y"], bbox2["y"])
        x2 = min(bbox1["x"] + bbox1["width"], bbox2["x"] + bbox2["width"])
        y2 = min(bbox1["y"] + bbox1["height"], bbox2["y"] + bbox2["height"])
        
        if x2 <= x1 or y2 <= y1:
            return 0.0
        
        intersection = (x2 - x1) * (y2 - y1)
        area1 = bbox1["width"] * bbox1["height"]
        area2 = bbox2["width"] * bbox2["height"]
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0
    
    def extract_roi(self, image: np.ndarray, region: Dict[str, Any], padding: int = 10) -> np.ndarray:
        """
        Extract Region of Interest (ROI) from image
        
        Args:
            image: Input image
            region: Region dictionary with bbox
            padding: Padding pixels around region
        
        Returns:
            Extracted ROI image
        """
        import cv2
        
        bbox = region["bbox"]
        h, w = image.shape[:2]
        
        # Add padding
        x1 = max(0, bbox["x"] - padding)
        y1 = max(0, bbox["y"] - padding)
        x2 = min(w, bbox["x"] + bbox["width"] + padding)
        y2 = min(h, bbox["y"] + bbox["height"] + padding)
        
        roi = image[y1:y2, x1:x2]
        return roi

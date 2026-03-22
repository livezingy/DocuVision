"""
PyZBar Barcode Engine - Primary engine for barcode recognition with preprocessing
"""

from typing import Dict, Any, List, Optional
from loguru import logger
import os
import numpy as np


class PyZBarEngine:
    """
    Primary Barcode Engine - PyZBar with advanced preprocessing
    
    Supports:
    - QR Code
    - Code128
    - EAN-13/EAN-8
    - UPC-A/UPC-E
    - Code39
    - ITF
    - DataBar
    
    Features:
    - Region detection
    - Image enhancement
    - Skew correction
    - Multi-scale processing
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize PyZBar engine with preprocessing
        
        Args:
            config: Configuration dictionary for preprocessing options
        """
        self.config = config or {}
        self._ready = False
        self._preprocessing_components = None
        self._init_engine()
        self._init_preprocessing()
    
    def _init_engine(self):
        """Initialize PyZBar library"""
        try:
            from pyzbar import pyzbar
            from PIL import Image
            self._ready = True
            logger.info("PyZBar engine initialized successfully")
        except ImportError as e:
            logger.warning(f"PyZBar not installed: {e}")
            self._ready = False
        except Exception as e:
            logger.warning(f"PyZBar initialization failed: {e}")
            self._ready = False
    
    def _init_preprocessing(self):
        """Initialize preprocessing components"""
        try:
            from ..preprocessing import RegionDetector, ImageEnhancer, SkewCorrector, MultiScaleProcessor
            
            enable_region = self.config.get("enable_region_detection", True)
            enable_preprocessing = self.config.get("enable_preprocessing", True)
            enable_skew = self.config.get("enable_skew_correction", True)
            enable_multiscale = self.config.get("enable_multiscale", True)
            
            self._preprocessing_components = {}
            
            if enable_region:
                min_area = self.config.get("region_min_area", 100)
                max_area = self.config.get("region_max_area", 1000000)
                self._preprocessing_components["region_detector"] = RegionDetector(
                    min_area=min_area, max_area=max_area
                )
            
            if enable_preprocessing:
                contrast_limit = self.config.get("contrast_clip_limit", 2.0)
                sharpen_strength = self.config.get("sharpen_strength", 1.0)
                denoise_strength = self.config.get("denoise_strength", 9)
                self._preprocessing_components["image_enhancer"] = ImageEnhancer(
                    contrast_clip_limit=contrast_limit,
                    sharpen_strength=sharpen_strength,
                    denoise_strength=denoise_strength
                )
            
            if enable_skew:
                skew_threshold = self.config.get("skew_threshold", 2.0)
                self._preprocessing_components["skew_corrector"] = SkewCorrector(
                    angle_threshold=skew_threshold
                )
            
            if enable_multiscale:
                scale_factors = self.config.get("multiscale_factors", [0.5, 0.75, 1.0, 1.5, 2.0])
                self._preprocessing_components["multiscale_processor"] = MultiScaleProcessor(
                    scale_factors=scale_factors
                )
            
            logger.info(f"Preprocessing components initialized: {list(self._preprocessing_components.keys())}")
        except Exception as e:
            logger.warning(f"Preprocessing initialization failed: {e}")
            self._preprocessing_components = {}
    
    def is_ready(self) -> bool:
        return self._ready
    
    def get_name(self) -> str:
        return "PyZBar"
    
    async def recognize(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Recognize barcodes from image or PDF
        
        Args:
            file_path: Path to image or PDF file
        
        Returns:
            List of detected barcodes
        """
        if not self._ready:
            raise RuntimeError("PyZBar engine not ready")
        
        from pyzbar import pyzbar
        from PIL import Image
        import fitz
        
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            return await self._process_pdf(file_path)
        else:
            return await self._process_image(file_path)
    
    async def _process_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        import fitz
        import cv2
        
        doc = fitz.open(pdf_path)
        all_barcodes = []
        
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                mat = fitz.Matrix(2, 2)  # 2x scale for better quality
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to numpy array directly (more efficient)
                img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                    pix.height, pix.width, pix.n
                )
                
                # Convert RGBA to BGR if needed
                if pix.n == 4:
                    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
                elif pix.n == 3:
                    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                else:
                    img_bgr = img_array
                
                # Process with preprocessing
                if self._preprocessing_components:
                    barcodes = self._detect_with_preprocessing(img_bgr, page_num + 1)
                else:
                    barcodes = self._detect_barcodes_standard(img_bgr, page_num + 1)
                
                all_barcodes.extend(barcodes)
        finally:
            doc.close()
        
        return all_barcodes
    
    async def _process_image(self, img_path: str) -> List[Dict[str, Any]]:
        """Process single image file"""
        return self._detect_barcodes(img_path, 1)
    
    def _detect_barcodes(self, img_path: str, page_num: int) -> List[Dict[str, Any]]:
        """
        Detect barcodes with optional preprocessing
        
        Args:
            img_path: Path to image file
            page_num: Page number
        
        Returns:
            List of detected barcodes
        """
        import cv2
        from pyzbar import pyzbar
        from PIL import Image
        
        # Load image
        img_cv = cv2.imread(img_path)
        if img_cv is None:
            # Fallback to PIL
            img = Image.open(img_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            return self._detect_barcodes_pil(img, page_num)
        
        # Try with preprocessing first
        if self._preprocessing_components:
            results = self._detect_with_preprocessing(img_cv, page_num)
            if results:
                return results
        
        # Fallback to standard detection
        return self._detect_barcodes_standard(img_cv, page_num)
    
    def _detect_with_preprocessing(self, img_cv: np.ndarray, page_num: int) -> List[Dict[str, Any]]:
        """Detect barcodes with preprocessing pipeline"""
        all_results = []
        
        # Step 1: Try region detection
        region_detector = self._preprocessing_components.get("region_detector")
        if region_detector:
            regions = region_detector.detect_regions(img_cv)
            
            if regions:
                # Process each region
                for region in regions:
                    roi = region_detector.extract_roi(img_cv, region, padding=10)
                    roi_results = self._process_region(roi, page_num, region)
                    all_results.extend(roi_results)
                
                if all_results:
                    return all_results
        
        # Step 2: Process full image with preprocessing
        return self._process_region(img_cv, page_num, None)
    
    def _process_region(
        self,
        img_cv: np.ndarray,
        page_num: int,
        region: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Process a region (or full image) with preprocessing"""
        import cv2
        from pyzbar import pyzbar
        from PIL import Image
        
        processed_img = img_cv.copy()
        
        # Step 1: Image enhancement
        image_enhancer = self._preprocessing_components.get("image_enhancer")
        if image_enhancer:
            processed_img = image_enhancer.enhance(
                processed_img,
                enable_contrast=True,
                enable_sharpen=True,
                enable_denoise=True,
                enable_binarize=False
            )
        
        # Step 2: Skew correction
        skew_corrector = self._preprocessing_components.get("skew_corrector")
        if skew_corrector:
            if skew_corrector.needs_correction(processed_img):
                processed_img, angle = skew_corrector.correct_skew(processed_img)
                logger.debug(f"Applied skew correction: {angle:.2f} degrees")
        
        # Step 3: Convert to PIL Image for PyZBar
        if len(processed_img.shape) == 2:
            # Grayscale
            img_pil = Image.fromarray(processed_img, mode='L').convert('RGB')
        else:
            # BGR to RGB
            img_rgb = cv2.cvtColor(processed_img, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img_rgb)
        
        # Step 4: Try recognition
        barcodes = pyzbar.decode(img_pil)
        
        if barcodes:
            return self._parse_barcodes(barcodes, page_num, region)
        
        # Step 5: If failed, try multi-scale processing
        multiscale_processor = self._preprocessing_components.get("multiscale_processor")
        if multiscale_processor:
            def recognition_func(img_array):
                import cv2
                from pyzbar import pyzbar
                from PIL import Image
                if len(img_array.shape) == 2:
                    img_pil = Image.fromarray(img_array, mode='L').convert('RGB')
                else:
                    img_rgb = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
                    img_pil = Image.fromarray(img_rgb)
                return pyzbar.decode(img_pil)
            
            # Convert PIL back to numpy for multiscale
            img_np = np.array(img_pil)
            if len(img_np.shape) == 3:
                img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            
            barcodes = multiscale_processor.process_multiscale(img_np, recognition_func)
            
            if barcodes:
                return self._parse_barcodes(barcodes, page_num, region)
        
        # Step 6: Try aggressive enhancement
        if image_enhancer:
            enhanced = image_enhancer.enhance_aggressive(img_cv)
            if len(enhanced.shape) == 2:
                img_pil = Image.fromarray(enhanced, mode='L').convert('RGB')
            else:
                img_rgb = cv2.cvtColor(enhanced, cv2.COLOR_BGR2RGB)
                img_pil = Image.fromarray(img_rgb)
            
            barcodes = pyzbar.decode(img_pil)
            if barcodes:
                return self._parse_barcodes(barcodes, page_num, region)
        
        return []
    
    def _detect_barcodes_standard(self, img_cv: np.ndarray, page_num: int) -> List[Dict[str, Any]]:
        """Standard detection without preprocessing"""
        import cv2
        from pyzbar import pyzbar
        from PIL import Image
        
        # Convert to PIL
        img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        img_pil = Image.fromarray(img_rgb)
        
        barcodes = pyzbar.decode(img_pil)
        return self._parse_barcodes(barcodes, page_num, None)
    
    def _detect_barcodes_pil(self, img: Image.Image, page_num: int) -> List[Dict[str, Any]]:
        """Fallback detection using PIL Image directly"""
        from pyzbar import pyzbar
        
        barcodes = pyzbar.decode(img)
        return self._parse_barcodes(barcodes, page_num, None)
    
    def _parse_barcodes(
        self,
        barcodes: List,
        page_num: int,
        region: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Parse PyZBar results into standard format"""
        results = []
        
        for idx, barcode in enumerate(barcodes):
            try:
                barcode_data = barcode.data.decode('utf-8')
            except:
                continue
            
            barcode_type = barcode.type
            
            # Extract polygon points
            points = []
            if barcode.polygon:
                for point in barcode.polygon:
                    points.append({"x": point.x, "y": point.y})
            
            result = {
                "id": f"barcode_p{page_num}_{idx}",
                "page": page_num,
                "type": barcode_type,
                "data": barcode_data,
                "format": self._format_name(barcode_type),
                "polygon": points,
                "confidence": 1.0,  # PyZBar doesn't provide confidence scores
                "engine": "PyZBar"
            }
            
            # Add preprocessing info if available
            if region:
                result["detected_region"] = region.get("type", "unknown")
                result["region_confidence"] = region.get("confidence", 0.0)
            
            # Calculate bounding box
            if points:
                x_coords = [p["x"] for p in points]
                y_coords = [p["y"] for p in points]
                result["bbox"] = {
                    "x": min(x_coords),
                    "y": min(y_coords),
                    "width": max(x_coords) - min(x_coords),
                    "height": max(y_coords) - min(y_coords)
                }
            
            results.append(result)
        
        return results
    
    def _format_name(self, barcode_type: str) -> str:
        """Convert barcode type to readable format name"""
        format_map = {
            "QRCODE": "QR_CODE",
            "CODE128": "CODE128",
            "EAN13": "EAN13",
            "EAN8": "EAN8",
            "UPC_A": "UPC_A",
            "UPC_E": "UPC_E",
            "CODE39": "CODE39",
            "ITF": "ITF",
            "DATABAR": "DATABAR",
            "DATABAR_EXP": "DATABAR_EXP"
        }
        return format_map.get(barcode_type, barcode_type)

"""
OpenCV Barcode Engine - Alternative engine using OpenCV
"""

from typing import Dict, Any, List
from loguru import logger
import os


class OpenCVBarcodeEngine:
    """Alternative Barcode Engine using OpenCV"""
    
    def __init__(self):
        self._detector = None
        self._ready = False
        self._init_engine()
    
    def _init_engine(self):
        try:
            import cv2
            # OpenCV has QRCodeDetector but limited barcode support
            self._detector = cv2.QRCodeDetector()
            self._ready = True
            logger.info("OpenCV Barcode engine initialized successfully")
        except ImportError as e:
            logger.warning(f"OpenCV not installed: {e}")
            self._ready = False
        except Exception as e:
            logger.warning(f"OpenCV initialization failed: {e}")
            self._ready = False
    
    def is_ready(self) -> bool:
        return self._ready
    
    def get_name(self) -> str:
        return "OpenCV"
    
    async def recognize(self, file_path: str) -> List[Dict[str, Any]]:
        """Recognize QR codes using OpenCV (limited to QR codes only)"""
        if not self._ready:
            raise RuntimeError("OpenCV engine not ready")
        
        import cv2
        
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
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_path = f"{pdf_path}_opencv_{page_num}.png"
                pix.save(img_path)
                
                barcodes = self._detect_qrcodes(img_path, page_num + 1)
                all_barcodes.extend(barcodes)
                
                if os.path.exists(img_path):
                    os.remove(img_path)
        finally:
            doc.close()
        
        return all_barcodes
    
    async def _process_image(self, img_path: str) -> List[Dict[str, Any]]:
        return self._detect_qrcodes(img_path, 1)
    
    def _detect_qrcodes(self, img_path: str, page_num: int) -> List[Dict[str, Any]]:
        import cv2
        import numpy as np
        
        img = cv2.imread(img_path)
        if img is None:
            return []
        
        # OpenCV QRCodeDetector only supports QR codes
        data, bbox, _ = self._detector.detectAndDecodeMulti(img)
        
        results = []
        if bbox is not None and len(bbox) > 0:
            for idx, (qr_data, qr_bbox) in enumerate(zip(data, bbox)):
                if qr_data:
                    # Convert bbox to polygon points
                    points = []
                    for point in qr_bbox:
                        points.append({"x": float(point[0]), "y": float(point[1])})
                    
                    x_coords = [p["x"] for p in points]
                    y_coords = [p["y"] for p in points]
                    
                    result = {
                        "id": f"qrcode_p{page_num}_{idx}",
                        "page": page_num,
                        "type": "QRCODE",
                        "data": qr_data,
                        "format": "QR_CODE",
                        "polygon": points,
                        "bbox": {
                            "x": min(x_coords),
                            "y": min(y_coords),
                            "width": max(x_coords) - min(x_coords),
                            "height": max(y_coords) - min(y_coords)
                        },
                        "confidence": 1.0,
                        "engine": "OpenCV"
                    }
                    results.append(result)
        
        return results

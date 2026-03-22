"""
EasyOCR Engine
"""

from typing import Dict, Any, List
from loguru import logger
import os


class EasyOCREngine:
    """Alternative OCR Engine - EasyOCR"""
    
    def __init__(self, use_gpu: bool = False):
        self._reader = None
        self._ready = False
        self._use_gpu = use_gpu
        self._init_engine()
    
    def _init_engine(self):
        try:
            import easyocr
            self._reader = easyocr.Reader(['en', 'ch_sim'], gpu=self._use_gpu, verbose=False)
            self._ready = True
            logger.info("EasyOCR engine initialized successfully")
        except Exception as e:
            logger.warning(f"EasyOCR initialization failed: {e}")
            self._ready = False
    
    def is_ready(self) -> bool:
        return self._ready
    
    def get_name(self) -> str:
        return "EasyOCR"
    
    async def recognize(self, file_path: str, language: str = "en") -> Dict[str, Any]:
        if not self._ready:
            raise RuntimeError("EasyOCR engine not ready")
        
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            return await self._process_pdf(file_path)
        else:
            return await self._process_image(file_path)
    
    async def _process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        import fitz
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        all_blocks = []
        
        try:
            for page_num in range(page_count):
                page = doc[page_num]
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_path = f"{pdf_path}_easyocr_{page_num}.png"
                pix.save(img_path)
                
                result = self._reader.readtext(img_path)
                blocks = self._parse_result(result, page_num + 1)
                all_blocks.extend(blocks)
                
                if os.path.exists(img_path):
                    os.remove(img_path)
        finally:
            doc.close()
        
        return {
            "engine": "EasyOCR",
            "page_count": page_count,
            "text_blocks": all_blocks,
            "full_text": "\n".join([b["text"] for b in all_blocks])
        }
    
    async def _process_image(self, img_path: str) -> Dict[str, Any]:
        result = self._reader.readtext(img_path)
        blocks = self._parse_result(result, 1)
        
        return {
            "engine": "EasyOCR",
            "page_count": 1,
            "text_blocks": blocks,
            "full_text": "\n".join([b["text"] for b in blocks])
        }
    
    def _parse_result(self, result: List, page_num: int) -> List[Dict[str, Any]]:
        blocks = []
        for item in result:
            box, text, confidence = item
            x_coords = [p[0] for p in box]
            y_coords = [p[1] for p in box]
            block = {
                "text": text,
                "confidence": round(confidence, 4),
                "page": page_num,
                "bbox": {
                    "x": min(x_coords),
                    "y": min(y_coords),
                    "width": max(x_coords) - min(x_coords),
                    "height": max(y_coords) - min(y_coords)
                },
                "polygon": box
            }
            blocks.append(block)
        blocks.sort(key=lambda b: (b["bbox"]["y"], b["bbox"]["x"]))
        return blocks

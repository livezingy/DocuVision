"""
Tesseract OCR Engine
"""

from typing import Dict, Any, List
from loguru import logger
import os


class TesseractOCREngine:
    """Fallback OCR Engine - Tesseract"""
    
    def __init__(self):
        self._ready = False
        self._init_engine()
    
    def _init_engine(self):
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self._ready = True
            logger.info("Tesseract OCR engine initialized successfully")
        except Exception as e:
            logger.warning(f"Tesseract not available: {e}")
            self._ready = False
    
    def is_ready(self) -> bool:
        return self._ready
    
    def get_name(self) -> str:
        return "Tesseract"
    
    async def recognize(self, file_path: str, language: str = "en") -> Dict[str, Any]:
        if not self._ready:
            raise RuntimeError("Tesseract engine not ready")
        
        import pytesseract
        from PIL import Image
        import fitz
        import io
        
        lang_map = {
            "en": "eng", "ch": "chi_sim", "zh": "chi_sim",
            "ja": "jpn", "ko": "kor", "de": "deu", "fr": "fra", "es": "spa"
        }
        tess_lang = lang_map.get(language, "eng")
        
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            return await self._process_pdf(file_path, tess_lang)
        else:
            return await self._process_image(file_path, tess_lang)
    
    async def _process_pdf(self, pdf_path: str, tess_lang: str) -> Dict[str, Any]:
        import fitz
        import pytesseract
        from PIL import Image
        import io
        
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        all_blocks = []
        
        try:
            for page_num in range(page_count):
                page = doc[page_num]
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                data = pytesseract.image_to_data(img, lang=tess_lang, output_type=pytesseract.Output.DICT)
                blocks = self._parse_tesseract_data(data, page_num + 1)
                all_blocks.extend(blocks)
        finally:
            doc.close()
        
        return {
            "engine": "Tesseract",
            "page_count": page_count,
            "text_blocks": all_blocks,
            "full_text": "\n".join([b["text"] for b in all_blocks])
        }
    
    async def _process_image(self, img_path: str, tess_lang: str) -> Dict[str, Any]:
        import pytesseract
        from PIL import Image
        
        img = Image.open(img_path)
        data = pytesseract.image_to_data(img, lang=tess_lang, output_type=pytesseract.Output.DICT)
        blocks = self._parse_tesseract_data(data, 1)
        
        return {
            "engine": "Tesseract",
            "page_count": 1,
            "text_blocks": blocks,
            "full_text": "\n".join([b["text"] for b in blocks])
        }
    
    def _parse_tesseract_data(self, data: Dict, page_num: int) -> List[Dict[str, Any]]:
        blocks = []
        n_boxes = len(data['text'])
        for i in range(n_boxes):
            text = data['text'][i].strip()
            if not text or data['conf'][i] < 0:
                continue
            block = {
                "text": text,
                "confidence": data['conf'][i] / 100.0,
                "page": page_num,
                "bbox": {
                    "x": data['left'][i],
                    "y": data['top'][i],
                    "width": data['width'][i],
                    "height": data['height'][i]
                }
            }
            blocks.append(block)
        return self._merge_words_to_lines(blocks)
    
    def _merge_words_to_lines(self, blocks: List[Dict]) -> List[Dict]:
        if not blocks:
            return []
        blocks.sort(key=lambda b: (b["bbox"]["y"], b["bbox"]["x"]))
        merged = []
        current_line = [blocks[0]]
        for block in blocks[1:]:
            prev = current_line[-1]
            y_diff = abs(block["bbox"]["y"] - prev["bbox"]["y"])
            if y_diff < prev["bbox"]["height"] * 0.5:
                current_line.append(block)
            else:
                merged.append(self._merge_line(current_line))
                current_line = [block]
        if current_line:
            merged.append(self._merge_line(current_line))
        return merged
    
    def _merge_line(self, line_blocks: List[Dict]) -> Dict:
        if len(line_blocks) == 1:
            return line_blocks[0]
        text = " ".join([b["text"] for b in line_blocks])
        avg_conf = sum(b["confidence"] for b in line_blocks) / len(line_blocks)
        min_x = min(b["bbox"]["x"] for b in line_blocks)
        min_y = min(b["bbox"]["y"] for b in line_blocks)
        max_x = max(b["bbox"]["x"] + b["bbox"]["width"] for b in line_blocks)
        max_y = max(b["bbox"]["y"] + b["bbox"]["height"] for b in line_blocks)
        return {
            "text": text,
            "confidence": round(avg_conf, 4),
            "page": line_blocks[0]["page"],
            "bbox": {"x": min_x, "y": min_y, "width": max_x - min_x, "height": max_y - min_y}
        }

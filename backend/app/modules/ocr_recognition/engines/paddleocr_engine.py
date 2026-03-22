"""
PaddleOCR Engine
"""

from typing import Dict, Any, List
from loguru import logger
import os


class PaddleOCREngine:
    """Primary OCR Engine - PaddleOCR"""
    
    def __init__(self, use_gpu: bool = False, lang: str = "ch"):
        self._ocr = None
        self._ready = False
        self._use_gpu = use_gpu
        self._lang = lang
        self._init_engine()
    
    def _init_engine(self):
        try:
            from paddleocr import PaddleOCR
            import paddleocr
            
            # Log version for debugging
            try:
                version = paddleocr.__version__
                logger.info(f"PaddleOCR version: {version}")
            except:
                pass
            
            # PaddleOCR 3.x initialization parameters
            # Note: use_textline_orientation removed in 3.1.1 to avoid initialization errors
            # Device format: "cpu" or "gpu" (not "gpu:0")
            init_params = {
                "lang": self._lang,
                "device": "gpu" if self._use_gpu else "cpu"
            }
            
            self._ocr = PaddleOCR(**init_params)
            self._ready = True
            logger.info("PaddleOCR 3.x engine initialized successfully")
        except Exception as e:
            logger.warning(f"PaddleOCR initialization failed: {e}")
            self._ready = False
    
    def is_ready(self) -> bool:
        return self._ready
    
    def get_name(self) -> str:
        return "PaddleOCR"

    def _poly_to_list(self, poly: Any) -> List[List[float]]:
        """
        Convert a polygon-like object (numpy array/list/tuple) to a JSON-friendly list.

        Args:
            poly: Polygon points, typically shape (N, 2).

        Returns:
            List of [x, y] points as floats.
        """
        try:
            if hasattr(poly, "tolist"):
                poly = poly.tolist()
        except Exception:
            pass

        points: List[List[float]] = []
        if isinstance(poly, (list, tuple)):
            for p in poly:
                if isinstance(p, (list, tuple)) and len(p) >= 2:
                    try:
                        points.append([float(p[0]), float(p[1])])
                    except Exception:
                        continue
        return points

    def _bbox_from_poly(self, poly_points: List[List[float]]) -> Dict[str, float]:
        """Compute bbox from polygon points."""
        if not poly_points:
            return {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}
        xs = [p[0] for p in poly_points]
        ys = [p[1] for p in poly_points]
        x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        return {"x": x1, "y": y1, "width": max(0.0, x2 - x1), "height": max(0.0, y2 - y1)}

    def _convert_predict_dict(self, result_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convert PaddleOCR 3.x `predict()` dict output into unified per-line dict items.

        Expected keys (may vary by version):
        - rec_texts: List[str]
        - rec_scores: List[float]
        - rec_polys / dt_polys: List[polygon]
        - rec_boxes: ndarray (N, 4) (optional, may be used when polys are missing)
        """
        rec_texts = result_dict.get("rec_texts") or result_dict.get("rec_text") or []
        rec_scores = result_dict.get("rec_scores") or []
        polys = result_dict.get("rec_polys") or result_dict.get("dt_polys") or []

        if (not polys) and result_dict.get("rec_boxes") is not None:
            boxes = result_dict.get("rec_boxes")
            try:
                if hasattr(boxes, "tolist"):
                    boxes = boxes.tolist()
            except Exception:
                pass
            polys = []
            if isinstance(boxes, list):
                for b in boxes:
                    if isinstance(b, (list, tuple)) and len(b) >= 4:
                        x1, y1, x2, y2 = b[0], b[1], b[2], b[3]
                        polys.append([[x1, y1], [x2, y1], [x2, y2], [x1, y2]])

        items: List[Dict[str, Any]] = []
        if not isinstance(rec_texts, list):
            return items

        for i, text in enumerate(rec_texts):
            if text is None:
                continue
            text_str = str(text)
            if not text_str.strip():
                continue

            conf = 0.0
            if isinstance(rec_scores, list) and i < len(rec_scores):
                try:
                    conf = float(rec_scores[i])
                except Exception:
                    conf = 0.0

            poly_points: List[List[float]] = []
            if isinstance(polys, list) and i < len(polys):
                poly_points = self._poly_to_list(polys[i])

            items.append(
                {
                    "text": text_str,
                    "confidence": conf,
                    "polygon": poly_points,
                    "bbox": self._bbox_from_poly(poly_points),
                }
            )

        return items
    
    async def recognize(self, file_path: str, language: str = "en") -> Dict[str, Any]:
        if not self._ready:
            raise RuntimeError("PaddleOCR engine not ready")
        
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
                img_path = f"{pdf_path}_page_{page_num}.png"
                pix.save(img_path)
                
                result = self._call_ocr(img_path)
                if result:
                    blocks = self._parse_result(result, page_num + 1)
                    all_blocks.extend(blocks)
                
                if os.path.exists(img_path):
                    os.remove(img_path)
        finally:
            doc.close()
        
        return {
            "engine": "PaddleOCR",
            "page_count": page_count,
            "text_blocks": all_blocks,
            "full_text": "\n".join([b["text"] for b in all_blocks])
        }
    
    async def _process_image(self, img_path: str) -> Dict[str, Any]:
        result = self._call_ocr(img_path)
        blocks = self._parse_result(result, 1) if result else []
        
        return {
            "engine": "PaddleOCR",
            "page_count": 1,
            "text_blocks": blocks,
            "full_text": "\n".join([b["text"] for b in blocks])
        }
    
    def _call_ocr(self, img_path: str):
        """Call OCR using PaddleOCR 3.x predict() method"""
        try:
            # PaddleOCR 3.x predict() method
            result = self._ocr.predict(img_path)

            # PaddleOCR 3.x may return a dict with `rec_texts/rec_scores/rec_polys`.
            if isinstance(result, dict):
                return self._convert_predict_dict(result)
            
            # Convert Result objects to list format if needed
            if result and isinstance(result, list) and len(result) > 0:
                result_obj = result[0]
                # Some PaddleOCR builds return a dict inside a single-item list.
                if isinstance(result_obj, dict):
                    return self._convert_predict_dict(result_obj)
                # Check if it's a Result object with attributes
                if hasattr(result_obj, 'dt_polys') and hasattr(result_obj, 'rec_text'):
                    ocr_data = []
                    dt_polys = getattr(result_obj, 'dt_polys', [])
                    rec_text = getattr(result_obj, 'rec_text', [])
                    for poly, text_info in zip(dt_polys, rec_text):
                        if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                            text, confidence = text_info[0], text_info[1]
                        else:
                            text, confidence = str(text_info), 0.0
                        ocr_data.append([poly, (text, confidence)])
                    return ocr_data
                # If it's already in list format, return as is
                elif isinstance(result_obj, list):
                    return result_obj
            return result if result else []
        except Exception as e:
            logger.error(f"OCR prediction failed: {e}")
            raise
    
    def _parse_result(self, ocr_result: List, page_num: int) -> List[Dict[str, Any]]:
        """Parse PaddleOCR 3.x result format"""
        blocks = []
        
        for item in ocr_result:
            if isinstance(item, dict) and 'text' in item:
                # PaddleOCR 3.x format with dict structure
                block = {
                    "text": item.get('text', ''),
                    "confidence": round(item.get('confidence', 0.0), 4),
                    "page": page_num,
                    "bbox": item.get('bbox', {}),
                    "polygon": item.get('polygon', [])
                }
                blocks.append(block)
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                # Standard list format: [[box], (text, confidence)]
                box, text_info = item[0], item[1]
                if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                    text, confidence = text_info[0], text_info[1]
                else:
                    text, confidence = str(text_info), 0.0
                
                x_coords = [p[0] for p in box] if isinstance(box, list) else []
                y_coords = [p[1] for p in box] if isinstance(box, list) else []
                block = {
                    "text": text,
                    "confidence": round(confidence, 4),
                    "page": page_num,
                    "bbox": {
                        "x": min(x_coords) if x_coords else 0,
                        "y": min(y_coords) if y_coords else 0,
                        "width": (max(x_coords) - min(x_coords)) if x_coords else 0,
                        "height": (max(y_coords) - min(y_coords)) if y_coords else 0
                    },
                    "polygon": box
                }
                blocks.append(block)
        
        blocks.sort(key=lambda b: (b["bbox"]["y"], b["bbox"]["x"]))
        return blocks

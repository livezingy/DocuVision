"""
OCR Service - Multi-engine OCR with Primary (PaddleOCR) and Fallback (Tesseract) support
"""

from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from loguru import logger
import os
import paddle



class BaseOCREngine(ABC):
    """Abstract base class for OCR engines"""

    @abstractmethod
    def is_ready(self) -> bool:
        pass

    @abstractmethod
    async def recognize(self, file_path: str, language: str = "en") -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass


class PaddleOCREngine(BaseOCREngine):
    """
    Primary OCR Engine - PaddleOCR

    Advantages:
    - High accuracy for Chinese/English (>95%)
    - Lightweight PP-OCRv4 model
    - Built-in layout analysis
    - Active community support
    """

    def __init__(self, use_gpu: bool = False):
        self._ocr = None
        self._ready = False
        self._use_gpu = use_gpu
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
                "lang": 'ch',  # Default Chinese (supports English)
                "device": "gpu" if self._use_gpu else "cpu"
            }

            self._ocr = PaddleOCR(**init_params)
            self._ready = True
            logger.info("PaddleOCR 3.x engine initialized successfully")
        except ImportError as e:
            logger.warning(f"PaddleOCR not installed: {e}")
            self._ready = False
        except RuntimeError as e:
            # Handle PDX already initialized error - PaddleX should only be initialized once in main.py
            if "PDX has already been initialized" in str(e):
                logger.debug(f"PaddleOCR PDX initialization already done by main.py")
                # Still mark as ready since models are already loaded
                self._ready = True
            else:
                logger.error(f"PaddleOCR initialization failed: {e}")
                self._ready = False
        except Exception as e:
            logger.error(f"PaddleOCR initialization failed: {e}")
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

        # Try to use rec_boxes as a fallback polygon source.
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
                    # Common formats: [x1, y1, x2, y2] or [x1, y1, x2, y2, ...]
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

    def _save_visualization_outputs(self, result: Any, img_path: str) -> None:
        """Best-effort save_to_img for PaddleOCR prediction outputs."""
        # Use file-relative path to support both local and cloud environments
        # __file__ points to: {project_root}/backend/app/services/ocr_service.py
        # We need to go up 3 levels to reach project_root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_dir = os.path.join(project_root, "outputs", "paddleocr_visualizations")

        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to create PaddleOCR output directory {output_dir}: {e}")
            return

        candidates: List[Any] = []
        if isinstance(result, list):
            candidates = result
        else:
            candidates = [result]

        saved_any = False
        for idx, item in enumerate(candidates):
            if not hasattr(item, "save_to_img"):
                continue
            try:
                # save_to_img accepts a directory path and writes visualization files there.
                item.save_to_img(save_path=output_dir)
                saved_any = True
            except Exception as e:
                logger.debug(f"PaddleOCR save_to_img failed for candidate {idx}: {e}")

        if saved_any:
            logger.info(f"PaddleOCR visualization saved to: {output_dir} | source={img_path}")

    def _call_ocr(self, img_path: str):
        """Call OCR using PaddleOCR 3.x predict() method"""
        try:
            # PaddleOCR 3.x predict() method
            result = self._ocr.predict(img_path)
            self._save_visualization_outputs(result, img_path)

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

    async def recognize(self, file_path: str, language: str = "en") -> Dict[str, Any]:
        if not self._ready:
            raise RuntimeError("PaddleOCR engine not ready")

        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.pdf':
            return await self._process_pdf(file_path)
        else:
            return await self._process_image(file_path)

    async def _process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        page_count = len(doc)  # 保存页数，避免关闭后访问
        all_blocks = []

        try:
            for page_num in range(page_count):
                page = doc[page_num]

                # Render page to image
                mat = fitz.Matrix(2, 2)  # 2x scale for better accuracy
                pix = page.get_pixmap(matrix=mat)

                img_path = f"{pdf_path}_page_{page_num}.png"
                pix.save(img_path)

                # OCR recognition
                result = self._call_ocr(img_path)

                if result:
                    blocks = self._parse_result(result, page_num + 1)
                    all_blocks.extend(blocks)

                # Clean up temp file
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

        # Sort by position (top to bottom, left to right)
        blocks.sort(key=lambda b: (b["bbox"]["y"], b["bbox"]["x"]))

        return blocks


class TesseractOCREngine(BaseOCREngine):
    """
    Fallback OCR Engine - Tesseract

    Advantages:
    - Wide language support (100+ languages)
    - Well-established, mature project
    - Good for printed text
    - No GPU required
    """

    def __init__(self):
        self._ready = False
        self._init_engine()

    def _init_engine(self):
        try:
            import pytesseract
            from PIL import Image

            # Test if tesseract is installed
            pytesseract.get_tesseract_version()
            self._ready = True
            logger.info("Tesseract OCR engine initialized successfully")
        except ImportError as e:
            logger.warning(f"pytesseract not installed: {e}")
            self._ready = False
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

        # Language mapping
        lang_map = {
            "en": "eng",
            "ch": "chi_sim",
            "zh": "chi_sim",
            "ja": "jpn",
            "ko": "kor",
            "de": "deu",
            "fr": "fra",
            "es": "spa"
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
        page_count = len(doc)  # 保存页数，避免关闭后访问
        all_blocks = []

        try:
            for page_num in range(page_count):
                page = doc[page_num]

                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)

                # Convert to PIL Image
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))

                # Get detailed OCR data
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
            if not text:
                continue

            conf = data['conf'][i]
            if conf < 0:  # Tesseract returns -1 for non-text blocks
                continue

            block = {
                "text": text,
                "confidence": conf / 100.0,
                "page": page_num,
                "bbox": {
                    "x": data['left'][i],
                    "y": data['top'][i],
                    "width": data['width'][i],
                    "height": data['height'][i]
                }
            }
            blocks.append(block)

        # Merge adjacent words into lines
        blocks = self._merge_words_to_lines(blocks)

        return blocks

    def _merge_words_to_lines(self, blocks: List[Dict]) -> List[Dict]:
        if not blocks:
            return []

        # Simple line merging based on vertical position
        blocks.sort(key=lambda b: (b["bbox"]["y"], b["bbox"]["x"]))

        merged = []
        current_line = [blocks[0]]

        for block in blocks[1:]:
            prev = current_line[-1]

            # Check if on same line (similar y position)
            y_diff = abs(block["bbox"]["y"] - prev["bbox"]["y"])
            if y_diff < prev["bbox"]["height"] * 0.5:
                current_line.append(block)
            else:
                # Merge current line
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
            "bbox": {
                "x": min_x,
                "y": min_y,
                "width": max_x - min_x,
                "height": max_y - min_y
            }
        }


class EasyOCREngine(BaseOCREngine):
    """
    Alternative OCR Engine - EasyOCR

    Advantages:
    - Easy to use
    - Good multi-language support
    - GPU acceleration
    """

    def __init__(self, use_gpu: bool = False):
        self._reader = None
        self._ready = False
        self._use_gpu = use_gpu
        self._init_engine()

    def _init_engine(self):
        try:
            import easyocr

            self._reader = easyocr.Reader(
                ['en', 'ch_sim'],
                gpu=self._use_gpu,
                verbose=False
            )
            self._ready = True
            logger.info("EasyOCR engine initialized successfully")
        except ImportError as e:
            logger.warning(f"EasyOCR not installed: {e}")
            self._ready = False
        except Exception as e:
            logger.error(f"EasyOCR initialization failed: {e}")
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
        page_count = len(doc)  # 保存页数，避免关闭后访问
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


class OCRService:
    """
    OCR Service with multi-engine support

    Supports automatic fallback:
    1. PaddleOCR (Primary - Recommended)
    2. Tesseract (Fallback)
    3. EasyOCR (Alternative)
    """

    def __init__(self, use_gpu: bool = False):
        self.engines: Dict[str, BaseOCREngine] = {}
        self.default_engine = "paddleocr"
        self._use_gpu = use_gpu
        self._init_engines()

    def _init_engines(self):
        """Initialize all available OCR engines"""
        # Primary: PaddleOCR
        paddle_engine = PaddleOCREngine(use_gpu=self._use_gpu)
        if paddle_engine.is_ready():
            self.engines["paddleocr"] = paddle_engine

        # PaddleOCR-only version: Tesseract and EasyOCR disabled
        # Fallback: Tesseract
        # tess_engine = TesseractOCREngine()
        # if tess_engine.is_ready():
        #     self.engines["tesseract"] = tess_engine

        # Alternative: EasyOCR
        # easy_engine = EasyOCREngine(use_gpu=self._use_gpu)
        # if easy_engine.is_ready():
        #     self.engines["easyocr"] = easy_engine

        logger.info(f"Available OCR engines: {list(self.engines.keys())}")

    def is_ready(self) -> bool:
        """Check if any OCR engine is available"""
        return len(self.engines) > 0

    def get_available_engines(self) -> List[str]:
        """Get list of available engines"""
        return list(self.engines.keys())

    def get_engine(self, engine_name: Optional[str] = None) -> BaseOCREngine:
        """Get specified engine or default/fallback"""
        if engine_name and engine_name in self.engines:
            return self.engines[engine_name]

        # Try default engine
        if self.default_engine in self.engines:
            return self.engines[self.default_engine]

        # Use any available engine
        if self.engines:
            return list(self.engines.values())[0]

        raise RuntimeError("No OCR engine available")

    async def recognize(
        self,
        file_path: str,
        language: str = "en",
        engine: Optional[str] = None,
        fallback: bool = True
    ) -> Dict[str, Any]:
        """
        Recognize text from document

        Args:
            file_path: Path to PDF or image file
            language: Language code (en, ch, etc.)
            engine: Specific engine to use (paddleocr, tesseract, easyocr)
            fallback: Whether to try fallback engines on failure

        Returns:
            OCR result dictionary
        """
        engines_to_try = []

        if engine and engine in self.engines:
            engines_to_try.append(engine)
        else:
            # PaddleOCR-only version: Only use PaddleOCR
            # Default order: paddleocr -> tesseract -> easyocr
            for eng in ["paddleocr"]:  # Only PaddleOCR in PaddleOCR-only version
                if eng in self.engines:
                    engines_to_try.append(eng)

        last_error = None

        for eng_name in engines_to_try:
            try:
                eng = self.engines[eng_name]
                logger.info(f"Trying OCR with {eng.get_name()}...")
                result = await eng.recognize(file_path, language)
                result["engine_used"] = eng_name
                return result
            except Exception as e:
                logger.warning(f"{eng_name} failed: {e}")
                last_error = e
                if not fallback:
                    raise

        raise RuntimeError(f"All OCR engines failed. Last error: {last_error}")

"""PP-Structure table engines — abstract base + primary engine (batch-5 split).

``BaseTableEngine`` and ``PPStructureTableEngine`` moved verbatim from
``table_service.py`` (runs/split batch 5); the parse tail lives in
``table_pp_parse.TablePPParseMixin`` and is composed via the base list.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from loguru import logger
import os

from app.services.table_html import TableHtmlMixin
from app.services.table_ocr_blocks import TableOcrBlocksMixin
from app.services.table_pp_parse import TablePPParseMixin
from app.services.table_pseudo_filter import TablePseudoFilterMixin

class BaseTableEngine(ABC):
    """Abstract base class for Table Extraction engines"""

    @abstractmethod
    def is_ready(self) -> bool:
        pass

    @abstractmethod
    async def extract(self, file_path: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass


class PPStructureTableEngine(
    TablePPParseMixin,
    TablePseudoFilterMixin,
    TableHtmlMixin,
    TableOcrBlocksMixin,
    BaseTableEngine,
):
    """
    Primary Table Engine - PP-Structure

    Advantages:
    - High accuracy table structure recognition (>90%)
    - HTML output support
    - Handles complex tables with merged cells
    - Integrated with PaddleOCR for text extraction
    """

    def __init__(self, use_gpu: bool = False, lazy_init: bool = True):
        self._engine = None
        self._ready = False
        self._use_gpu = use_gpu
        self._lazy_init = lazy_init
        self._init_attempted = False
        if not self._lazy_init:
            self._init_engine()

    def _init_engine(self):
        self._init_attempted = True
        try:
            # Import PPStructureV3
            from paddleocr import PPStructureV3
            import paddleocr

            # Log version for debugging
            try:
                version = paddleocr.__version__
                logger.info(f"PaddleOCR version: {version}")
            except:
                pass

            # PPStructureV3 initialization
            init_params = {
                "device": "gpu" if self._use_gpu else "cpu"
            }

            self._engine = PPStructureV3(**init_params)
            self._is_v3 = True

            self._ready = True
            logger.info("PPStructureV3 Table engine initialized successfully")
        except ImportError as e:
            logger.warning(f"PPStructureV3 not installed: {e}")
            self._ready = False
        except RuntimeError as e:
            # Handle PDX already initialized error - PaddleX should only be initialized once in main.py
            if "PDX has already been initialized" in str(e):
                logger.debug(f"PPStructureV3 Table PDX initialization already done by main.py")
                # Still mark as ready since models are already loaded
                self._ready = True
            else:
                logger.error(f"PPStructureV3 Table initialization failed: {e}")
                self._ready = False
        except Exception as e:
            logger.error(f"PPStructureV3 Table initialization failed: {e}")
            import traceback

            traceback.print_exc()
            self._ready = False

    def _ensure_engine(self) -> bool:
        if self._engine is not None and self._ready:
            return True
        if self._ready and self._engine is None:
            return False
        self._init_engine()
        return self._engine is not None and self._ready

    def is_ready(self) -> bool:
        # In lazy mode, report available before first initialization attempt.
        return self._ready or not self._init_attempted

    def get_name(self) -> str:
        return "PP-Structure-Table"

    def _call_engine(self, img_path: str):
        """Call engine with version-compatible method"""
        if not self._ensure_engine():
            raise RuntimeError("PP-Structure Table engine not ready")

        if hasattr(self, '_is_v3') and self._is_v3:
            # PPStructureV3 uses predict() method
            return self._engine.predict(img_path)
        else:
            # PPStructure (2.x) uses direct call
            return self._engine(img_path)

    async def extract(
        self,
        file_path: str,
        layout_elements: Optional[List[Dict[str, Any]]] = None,
        ocr_text_blocks: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract tables from document or from layout elements

        Args:
            file_path: Path to PDF or image file (used as fallback if layout_elements not provided)
            layout_elements: Optional list of layout elements from Layout Service (preferred method)
            ocr_text_blocks: Optional list of OCR text blocks for table reconstruction

        Returns:
            List of extracted tables
        """
        # If layout elements are provided, extract tables from them (preferred method)
        if layout_elements:
            return self._extract_from_layout_elements(layout_elements, ocr_text_blocks)

        # Fallback: call PP-Structure directly (legacy method)
        if not self._ensure_engine():
            raise RuntimeError("PP-Structure Table engine not ready")

        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.pdf':
            return await self._extract_from_pdf(file_path)
        else:
            return await self._extract_from_image(file_path)

    async def _extract_from_pdf(self, pdf_path: str) -> List[Dict[str, Any]]:
        import fitz
        from PIL import Image

        doc = fitz.open(pdf_path)
        page_count = len(doc)  # 保存页数，避免关闭后访问
        all_tables = []

        try:
            for page_num in range(page_count):
                page = doc[page_num]

                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_path = f"{pdf_path}_table_{page_num}.png"

                # 确保图像是 RGB 格式（3通道）
                if pix.alpha:
                    img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
                    img = img.convert("RGB")
                    img.save(img_path)
                else:
                    pix.save(img_path)

                result = self._call_engine(img_path)
                tables = self._parse_tables(result, page_num + 1)
                all_tables.extend(tables)

                if os.path.exists(img_path):
                    os.remove(img_path)
        finally:
            doc.close()

        return all_tables

    async def _extract_from_image(self, img_path: str) -> List[Dict[str, Any]]:
        """Extract tables from image file, handling RGBA to RGB conversion if needed"""
        from PIL import Image

        # Ensure image is RGB format (PP-Structure requires RGB)
        try:
            img = Image.open(img_path)
            if img.mode == 'RGBA':
                # Convert RGBA to RGB with white background
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[3])  # Use alpha channel as mask
                temp_path = f"{img_path}_rgb.png"
                rgb_img.save(temp_path)
                try:
                    result = self._call_engine(temp_path)
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            elif img.mode != 'RGB':
                # Convert other modes to RGB
                img = img.convert('RGB')
                temp_path = f"{img_path}_rgb.png"
                img.save(temp_path)
                try:
                    result = self._call_engine(temp_path)
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            else:
                # Already RGB, use directly
                result = self._call_engine(img_path)
        except Exception as e:
            # If image processing fails, try direct call as fallback
            logger.warning(f"Image format conversion failed, trying direct call: {e}")
            result = self._call_engine(img_path)

        return self._parse_tables(result, 1)


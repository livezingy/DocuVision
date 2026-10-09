"""
Table Extraction Service - Multi-engine support with PP-Structure (Primary) and TableTransformer (Fallback)
"""

from typing import Dict, Any, List, Optional, Tuple
from abc import ABC, abstractmethod
from loguru import logger
import os
import io

from app.services.table_html import TableHtmlMixin
from app.services.table_ocr_blocks import TableOcrBlocksMixin
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
    TablePseudoFilterMixin, TableHtmlMixin, TableOcrBlocksMixin, BaseTableEngine
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

    def _extract_from_layout_elements(
        self,
        layout_elements: List[Dict[str, Any]],
        ocr_text_blocks: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract tables from layout elements (preferred method)
        This avoids duplicate PP-Structure calls and uses already-detected table elements

        Args:
            layout_elements: List of layout elements from Layout Service
            ocr_text_blocks: Optional list of OCR text blocks for table reconstruction

        Returns:
            List of extracted tables
        """
        tables = []
        table_idx = 0

        for element in layout_elements:
            # Only process elements with type='table'
            if element.get('type') != 'table':
                continue

            table_idx += 1
            page_num = element.get('page', 1)

            table = {
                "id": element.get('id', f"table_p{page_num}_{table_idx}"),
                "page": page_num,
                "engine": "PP-Structure-Table",
                "bbox": element.get('bbox', {}),
                "confidence": element.get('confidence', 0.0),
            }

            # Extract table data from element's content/html
            # Layout service stores table HTML in element['html'] or element['content']['html']
            table_html = None
            cell_bboxes = None
            if 'html' in element:
                table_html = element['html']
            elif 'content' in element and isinstance(element['content'], dict):
                if 'html' in element['content']:
                    table_html = element['content']['html']
                if 'cell_bbox' in element['content']:
                    cell_bboxes = element['content']['cell_bbox']

            # Try to reconstruct table using OCR text blocks and cell_bbox (preferred method)
            if ocr_text_blocks and cell_bboxes and len(cell_bboxes) > 0:
                try:
                    reconstructed_table = self._reconstruct_table_with_ocr(
                        table_bbox=table.get('bbox', {}),
                        cell_bboxes=cell_bboxes,
                        ocr_text_blocks=ocr_text_blocks,
                        page_num=page_num,
                        table_idx=table_idx
                    )
                    if reconstructed_table:
                        # Merge with existing table data
                        table.update(reconstructed_table)
                        logger.info(f"Table {table_idx}: Reconstructed using OCR text blocks and cell_bbox, rows: {table.get('rows', 0)}, cols: {table.get('columns', 0)}")
                except Exception as e:
                    logger.warning(f"Table {table_idx}: Failed to reconstruct with OCR and cell_bbox: {e}, falling back to HTML method")

            # Fallback: Use HTML method if OCR reconstruction failed or not available
            if table_html and (not table.get('data') or not table.get('html')):
                # Clean and parse HTML
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(table_html, 'html.parser')
                    table_elem = soup.find('table')
                    if table_elem:
                        # Extract only the table element
                        cleaned_soup = BeautifulSoup('', 'html.parser')
                        table_clone = BeautifulSoup(str(table_elem), 'html.parser').find('table')
                        if table_clone:
                            cleaned_soup.append(table_clone)
                            cleaned_html = str(cleaned_soup)

                            # Verify and clean the HTML
                            cleaned_html = self._clean_table_html(cleaned_html, table_idx)
                            table['html'] = cleaned_html
                            table['data'] = self._html_to_data(cleaned_html)
                            table['html_structure'] = self._extract_html_structure(cleaned_html)

                            if table.get('data'):
                                table['rows'] = len(table['data'])
                                table['columns'] = max(len(row) for row in table['data']) if table['data'] else 0

                            logger.info(f"Table {table_idx}: Extracted from layout element, rows: {table.get('rows', 0)}, cols: {table.get('columns', 0)}")
                except Exception as e:
                    logger.warning(f"Table {table_idx}: Failed to parse HTML from layout element: {e}")

            # If no HTML, try to extract from content dict
            if not table_html and 'content' in element:
                content = element['content']
                if isinstance(content, dict) and 'html' in content:
                    table_html = content['html']
                    # Process same as above
                    try:
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(table_html, 'html.parser')
                        table_elem = soup.find('table')
                        if table_elem:
                            cleaned_soup = BeautifulSoup('', 'html.parser')
                            table_clone = BeautifulSoup(str(table_elem), 'html.parser').find('table')
                            if table_clone:
                                cleaned_soup.append(table_clone)
                                cleaned_html = str(cleaned_soup)
                                cleaned_html = self._clean_table_html(cleaned_html, table_idx)
                                table['html'] = cleaned_html
                                table['data'] = self._html_to_data(cleaned_html)
                                table['html_structure'] = self._extract_html_structure(cleaned_html)

                                if table.get('data'):
                                    table['rows'] = len(table['data'])
                                    table['columns'] = max(len(row) for row in table['data']) if table['data'] else 0
                    except Exception as e:
                        logger.warning(f"Table {table_idx}: Failed to parse HTML from content: {e}")

            if not self._keep_layout_table(table):
                logger.info(
                    f"Table {table_idx}: dropped pseudo-table "
                    f"(empty/tiny or html-only with no parsed cells)"
                )
                continue

            self._strip_leading_caption_row(table)

            if table.get('data'):
                tables.append(table)
            else:
                logger.warning(f"Table {table_idx}: No data or HTML found in layout element")

        # F3: bind table_caption elements to tables (same-page bbox adjacency).
        self._bind_table_captions(tables, layout_elements)

        return tables

    def _parse_tables(self, result: List[Dict], page_num: int) -> List[Dict[str, Any]]:
        """
        Parse tables from PPStructureV3 result.

        CRITICAL FIX FOR PaddleOCR 3.3.2 / PaddleX 3.3.12:
        PPStructureV3 returns LayoutParsingResultV2 objects, NOT plain dicts.

        LayoutParsingResultV2 structure:
        - result[0]: LayoutParsingResultV2 object
        - result[0].html: DICT mapping table identifiers to HTML strings
          Example: {'table_0': '<table>...</table>', 'table_1': '...'}

        Args:
            result: List containing ONE LayoutParsingResultV2 object
            page_num: Page number for extracted tables

        Returns:
            List of extracted tables with structure: {id, page, engine, data, html, rows, columns, ...}
        """
        tables = []

        if not result or len(result) == 0:
            logger.warning(f"Page {page_num}: Empty result from PPStructureV3")
            return tables

        first_item = result[0]

        # Verify it's a LayoutParsingResultV2-like object
        if not hasattr(first_item, 'html'):
            logger.warning(f"Page {page_num}: Result item has no 'html' attribute, type={type(first_item)}")
            return tables

        # CRITICAL: first_item.html is a DICT, not a string
        # Example: {'table_0': '<table>...</table>', 'table_1': '...'}
        html_dict = first_item.html

        if not isinstance(html_dict, dict):
            logger.warning(f"Page {page_num}: Expected html to be dict, got {type(html_dict)}")
            return tables

        if not html_dict:
            logger.info(f"Page {page_num}: No tables detected in document")
            return tables

        logger.info(f"Page {page_num}: Found {len(html_dict)} table(s) in html dict")

        # Iterate through table entries in the html dict
        for table_idx, (table_key, table_html) in enumerate(html_dict.items(), start=1):
            # Validate HTML content
            if not isinstance(table_html, str):
                logger.warning(f"Table {table_idx}: HTML is not a string, type={type(table_html)}")
                continue

            if '<table' not in table_html.lower():
                logger.warning(f"Table {table_idx}: No <table> tag found in HTML")
                continue

            logger.info(f"Table {table_idx} ({table_key}): Processing HTML (length={len(table_html)})")

            table = {
                "id": f"table_p{page_num}_{table_idx}",
                "page": page_num,
                "engine": "PP-Structure-Table",
                "bbox": {},  # LayoutParsingResultV2 doesn't provide bbox for individual tables
                "confidence": 0.0,  # No confidence score available
                "table_key": table_key,  # Store the original table identifier
            }

            # Parse HTML and extract table data
            try:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(table_html, 'html.parser')
                table_elem = soup.find('table')

                if not table_elem:
                    logger.warning(f"Table {table_idx}: No <table> element found after parsing")
                    continue

                # Extract table rows and cells
                rows_data = []
                for row in table_elem.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    row_data = [cell.get_text(separator=' ', strip=True) for cell in cells]
                    if row_data:  # Only add non-empty rows
                        rows_data.append(row_data)

                if not rows_data:
                    logger.warning(f"Table {table_idx}: No row data extracted")
                    continue

                # Normalize all rows to same column count
                max_cols = max(len(row) for row in rows_data)
                normalized_data = [
                    row + [""] * (max_cols - len(row))
                    for row in rows_data
                ]

                table['data'] = normalized_data
                table['html'] = str(table_elem)  # Store cleaned HTML
                table['rows'] = len(normalized_data)
                table['columns'] = max_cols
                table['html_structure'] = self._extract_html_structure(str(table_elem))

                tables.append(table)
                logger.info(f"Table {table_idx}: Successfully extracted - rows={len(normalized_data)}, cols={max_cols}")

            except Exception as e:
                logger.error(f"Table {table_idx}: Failed to parse HTML: {e}")
                import traceback
                logger.debug(traceback.format_exc())

        logger.info(f"Page {page_num}: Total {len(tables)} table(s) extracted")
        return tables

    def _extract_bbox(self, bbox: List) -> Dict[str, float]:
        if len(bbox) >= 4:
            return {
                "x": float(bbox[0]),
                "y": float(bbox[1]),
                "width": float(bbox[2] - bbox[0]),
                "height": float(bbox[3] - bbox[1])
            }
        return {"x": 0, "y": 0, "width": 0, "height": 0}

class TableService:
    """
    Table Extraction Service.

    Only PP-Structure-Table is registered as a table engine. Pro routes
    all PDFs (born-digital and scanned) through the PP-StructureV3
    layout-first path: layout detection supplies table region bboxes and
    SLANeXt HTML, and this service parses that HTML into rows/data. The
    former docuvision-core born-digital branch (pdfplumber + camelot
    text-stream) is removed because its text-stream strategy produced
    pseudo-tables on two-column papers and reference pages. Lite keeps
    its own core-based table_pipeline; this service is Pro-only.
    An earlier design advertised Camelot/Tabula as fallback engines here,
    but they were never enabled and do not help on scanned inputs; the
    dead code has been removed.
    """

    def __init__(self, use_gpu: bool = False, allow_fullpage_fallback: bool = False):
        self.engines: Dict[str, BaseTableEngine] = {}
        self.default_engine = "ppstructure"
        self._use_gpu = use_gpu
        self._allow_fullpage_fallback = bool(allow_fullpage_fallback)
        self._init_engines()

    def _init_engines(self):
        """Initialize all available table engines"""
        # Primary: PP-Structure-Table (only registered table engine).
        # Camelot/Tabula fallback removed: they cannot process scanned/image
        # inputs (the only inputs that reach this engine after born-digital
        # PDFs are routed to docuvision-core TableProcessor upstream).
        pp_engine = PPStructureTableEngine(use_gpu=self._use_gpu, lazy_init=True)
        self.engines["ppstructure"] = pp_engine

        logger.info(
            "Available table engines: {} | allow_fullpage_fallback={}",
            list(self.engines.keys()),
            self._allow_fullpage_fallback,
        )

    def is_ready(self) -> bool:
        """Check if any table engine is available"""
        return len(self.engines) > 0

    def get_strategy_info(self) -> Dict[str, Any]:
        """Return current extraction strategy for observability endpoints."""
        return {
            "mode": "layout_first",
            "allow_fullpage_fallback": self._allow_fullpage_fallback,
            "default_engine": self.default_engine,
            "available_engines": self.get_available_engines(),
        }

    def get_available_engines(self) -> List[str]:
        """Get list of available engines"""
        return list(self.engines.keys())

    def get_engine(self, engine_name: Optional[str] = None) -> BaseTableEngine:
        """Get specified engine or default/fallback"""
        if engine_name and engine_name in self.engines:
            return self.engines[engine_name]

        if self.default_engine in self.engines:
            return self.engines[self.default_engine]

        if self.engines:
            return list(self.engines.values())[0]

        raise RuntimeError("No table engine available")

    async def extract(
        self,
        file_path: str,
        engine: Optional[str] = None,
        fallback: bool = True,
        layout_elements: Optional[List[Dict[str, Any]]] = None,
        ocr_text_blocks: Optional[List[Dict[str, Any]]] = None,
        allow_fullpage_fallback: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Backward-compatible table extraction API (tables only)."""
        tables, _meta = await self._extract_internal(
            file_path=file_path,
            engine=engine,
            fallback=fallback,
            layout_elements=layout_elements,
            ocr_text_blocks=ocr_text_blocks,
            allow_fullpage_fallback=allow_fullpage_fallback,
        )
        return tables

    async def extract_with_meta(
        self,
        file_path: str,
        engine: Optional[str] = None,
        fallback: bool = True,
        layout_elements: Optional[List[Dict[str, Any]]] = None,
        ocr_text_blocks: Optional[List[Dict[str, Any]]] = None,
        allow_fullpage_fallback: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Table extraction API with structured metadata for observability and audits."""
        tables, meta = await self._extract_internal(
            file_path=file_path,
            engine=engine,
            fallback=fallback,
            layout_elements=layout_elements,
            ocr_text_blocks=ocr_text_blocks,
            allow_fullpage_fallback=allow_fullpage_fallback,
        )
        return {
            "tables": tables,
            "meta": meta,
        }

    async def _extract_internal(
        self,
        file_path: str,
        engine: Optional[str] = None,
        fallback: bool = True,
        layout_elements: Optional[List[Dict[str, Any]]] = None,
        ocr_text_blocks: Optional[List[Dict[str, Any]]] = None,
        allow_fullpage_fallback: Optional[bool] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Extract tables from document or from layout elements

        Args:
            file_path: Path to PDF or image file (used as fallback if layout_elements not provided)
            engine: Specific engine to use; only ``ppstructure`` is registered.
                Pro routes all PDFs (born-digital and scanned) through the
                PP-StructureV3 layout-first path; the former docuvision-core
                born-digital branch is removed.
            fallback: Kept for API compatibility; no-op with a single engine
            layout_elements: Optional list of layout elements from Layout Service (preferred method)
            ocr_text_blocks: Optional list of OCR text blocks for table reconstruction
            allow_fullpage_fallback: Override service-level fallback strategy

        Returns:
            List of extracted tables
        """
        effective_allow_fullpage_fallback = (
            self._allow_fullpage_fallback
            if allow_fullpage_fallback is None
            else bool(allow_fullpage_fallback)
        )
        layout_table_count = 0
        if isinstance(layout_elements, list):
            layout_table_count = sum(1 for el in layout_elements if isinstance(el, dict) and el.get("type") == "table")

        meta: Dict[str, Any] = {
            "strategy": "layout_first",
            "engine_requested": engine or self.default_engine,
            "allow_fullpage_fallback": effective_allow_fullpage_fallback,
            "layout_elements": len(layout_elements) if isinstance(layout_elements, list) else 0,
            "layout_table_blocks": layout_table_count,
            "path": "unknown",
            "reason": "unknown",
            "fallback_activated": False,
            "engine_used": None,
            "tables_returned": 0,
        }

        logger.info(
            "Table extraction request | engine={} | layout_elements={} | layout_tables={} | allow_fullpage_fallback={}",
            engine or self.default_engine,
            len(layout_elements) if isinstance(layout_elements, list) else 0,
            layout_table_count,
            effective_allow_fullpage_fallback,
        )

        # Pro policy: all tables come from PP-StructureV3 layout detection.
        # The former born-digital branch (docuvision-core pdfplumber/camelot
        # text-stream) is removed because its text-stream strategy produced
        # many pseudo-tables on two-column papers and reference pages, while
        # the layout table blocks (with SLANeXt HTML) were discarded. Lite
        # keeps its own core-based table_pipeline; this change is Pro-only.
        # If layout elements are provided and using PP-Structure, extract from layout (preferred method)
        if layout_elements and (not engine or engine == "ppstructure"):
            if "ppstructure" in self.engines:
                eng = self.engines["ppstructure"]
                logger.info("Extracting tables from layout elements (layout-first path)")
                try:
                    result = await eng.extract(
                        file_path,
                        layout_elements=layout_elements,
                        ocr_text_blocks=ocr_text_blocks
                    )
                    # Add engine info to each table
                    for table in result:
                        table["engine_used"] = "ppstructure"
                    meta.update(
                        {
                            "path": "layout_first",
                            "reason": "layout_tables_consumed",
                            "engine_used": "ppstructure",
                            "tables_returned": len(result),
                        }
                    )
                    return result, meta
                except Exception as e:
                    if not effective_allow_fullpage_fallback:
                        logger.warning(
                            "Table role boundary hit | reason=layout_extract_failed_fallback_disabled | error={}",
                            e,
                        )
                        meta.update(
                            {
                                "path": "skipped",
                                "reason": "layout_extract_failed_fallback_disabled",
                                "tables_returned": 0,
                            }
                        )
                        return [], meta
                    logger.warning(
                        "Table fallback activated | reason=layout_extract_failed | error={}",
                        e,
                    )
                    meta.update(
                        {
                            "fallback_activated": True,
                            "path": "fullpage_fallback",
                            "reason": "layout_extract_failed",
                        }
                    )

        # Policy guard: disallow full-page inference unless explicitly enabled.
        if not effective_allow_fullpage_fallback:
            if layout_elements is None:
                logger.warning(
                    "Table role boundary hit | reason=missing_layout_input_fallback_disabled"
                )
                meta.update(
                    {
                        "path": "skipped",
                        "reason": "missing_layout_input_fallback_disabled",
                        "tables_returned": 0,
                    }
                )
            else:
                logger.warning(
                    "Table role boundary hit | reason=no_layout_table_blocks_fallback_disabled"
                )
                meta.update(
                    {
                        "path": "skipped",
                        "reason": "no_layout_table_blocks_fallback_disabled",
                        "tables_returned": 0,
                    }
                )
            return [], meta

        logger.warning(
            "Table fallback activated | reason=policy_allowed_fullpage_path"
        )
        meta.update(
            {
                "fallback_activated": True,
                "path": "fullpage_fallback",
                "reason": "policy_allowed_fullpage_path",
            }
        )

        # Fallback: direct extraction (legacy method)
        engines_to_try = []

        ext = os.path.splitext(file_path)[1].lower()

        if engine and engine in self.engines:
            engines_to_try.append(engine)
        elif ext == '.pdf':
            # PaddleOCR-only version: Only use PP-Structure
            # For PDFs, try all engines
            for eng in ["ppstructure"]:  # Only PP-Structure in PaddleOCR-only version
                if eng in self.engines:
                    engines_to_try.append(eng)
        else:
            # For images, only PP-Structure works
            if "ppstructure" in self.engines:
                engines_to_try.append("ppstructure")

        last_error = None

        for eng_name in engines_to_try:
            try:
                eng = self.engines[eng_name]
                logger.info(f"Trying table extraction with {eng.get_name()}...")
                result = await eng.extract(file_path)

                # Add engine info to each table
                for table in result:
                    table["engine_used"] = eng_name

                meta.update(
                    {
                        "engine_used": eng_name,
                        "tables_returned": len(result),
                    }
                )
                return result, meta
            except Exception as e:
                logger.warning(f"{eng_name} failed: {e}")
                last_error = e
                if not fallback:
                    raise

        # Return empty list if all engines fail (tables are optional)
        logger.warning(f"All table engines failed. Last error: {last_error}")
        meta.update(
            {
                "path": "failed",
                "reason": "all_engines_failed",
                "tables_returned": 0,
            }
        )
        return [], meta

    def to_csv(self, table_data: List[List[str]]) -> str:
        """Convert table data to CSV format"""
        import csv

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(table_data)
        return output.getvalue()

    def to_excel(self, tables: List[Dict], output_path: str) -> str:
        """Export tables to Excel file"""
        try:
            import pandas as pd

            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                for idx, table in enumerate(tables):
                    if 'data' in table and table['data']:
                        # Check if first row looks like headers
                        data = table['data']
                        if len(data) > 1:
                            df = pd.DataFrame(data[1:], columns=data[0])
                        else:
                            df = pd.DataFrame(data)

                        sheet_name = f"Table_{idx + 1}"
                        df.to_excel(writer, sheet_name=sheet_name, index=False)

            return output_path
        except Exception as e:
            logger.error(f"Excel export failed: {e}")
            raise

    def to_html(self, table_data: List[List[str]]) -> str:
        """Convert table data to HTML format"""
        if not table_data:
            return ""

        html = "<table border='1'>\n"

        # Header row
        html += "  <thead>\n    <tr>\n"
        for cell in table_data[0]:
            html += f"      <th>{cell}</th>\n"
        html += "    </tr>\n  </thead>\n"

        # Data rows
        html += "  <tbody>\n"
        for row in table_data[1:]:
            html += "    <tr>\n"
            for cell in row:
                html += f"      <td>{cell}</td>\n"
            html += "    </tr>\n"
        html += "  </tbody>\n</table>"

        return html

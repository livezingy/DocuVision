"""
Table Extraction Service - Multi-engine support with PP-Structure (Primary) and TableTransformer (Fallback)
"""

from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from loguru import logger
import os
import io
from app.compatibility_patches import apply_all_patches


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


class PPStructureTableEngine(BaseTableEngine):
    """
    Primary Table Engine - PP-Structure

    Advantages:
    - High accuracy table structure recognition (>90%)
    - HTML output support
    - Handles complex tables with merged cells
    - Integrated with PaddleOCR for text extraction
    """

    def __init__(self, use_gpu: bool = False):
        self._engine = None
        self._ready = False
        self._use_gpu = use_gpu
        self._init_engine()

    def _init_engine(self):
        try:
            # Apply version-gated compatibility patches (legacy-only).
            apply_all_patches()

            # Now import PPStructureV3
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

    def is_ready(self) -> bool:
        return self._ready

    def get_name(self) -> str:
        return "PP-Structure-Table"

    def _call_engine(self, img_path: str):
        """Call engine with version-compatible method"""
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
        if not self._ready:
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

            # Only add table if it has data or HTML
            if table.get('data') or table.get('html'):
                tables.append(table)
            else:
                logger.warning(f"Table {table_idx}: No data or HTML found in layout element")

        return tables

    def _reconstruct_table_with_ocr(
        self,
        table_bbox: Dict[str, float],
        cell_bboxes: List[List[float]],
        ocr_text_blocks: List[Dict[str, Any]],
        page_num: int,
        table_idx: int
    ) -> Optional[Dict[str, Any]]:
        """
        Reconstruct table structure using OCR text blocks and cell_bbox.

        This method:
        1. Filters OCR text blocks within table boundary
        2. Maps OCR text blocks to cells based on cell_bbox
        3. Determines row/column positions from cell_bbox centers
        4. Rebuilds table structure

        Args:
            table_bbox: Table bounding box {x, y, width, height}
            cell_bboxes: List of cell bounding boxes (8 numbers each)
            ocr_text_blocks: List of OCR text blocks with bbox information
            page_num: Page number
            table_idx: Table index for logging

        Returns:
            Dictionary with reconstructed table data, or None if reconstruction fails
        """
        try:
            # Parse all cell_bboxes
            parsed_cells = []
            for idx, cell_bbox in enumerate(cell_bboxes):
                parsed = self._parse_cell_bbox(cell_bbox)
                if 'error' in parsed:
                    logger.warning(f"Table {table_idx}: Invalid cell_bbox at index {idx}: {parsed['error']}")
                    continue
                parsed['index'] = idx
                parsed_cells.append(parsed)

            if not parsed_cells:
                logger.warning(f"Table {table_idx}: No valid cell_bboxes found")
                return None

            # Filter OCR text blocks within table boundary
            table_text_blocks = self._filter_text_blocks_in_bbox(ocr_text_blocks, table_bbox, page_num)

            if not table_text_blocks:
                logger.warning(f"Table {table_idx}: No OCR text blocks found within table boundary")
                return None

            # Map OCR text blocks to cells
            cell_texts = {}
            for cell_info in parsed_cells:
                cell_idx = cell_info['index']
                cell_bbox_dict = cell_info['bbox']

                # Find text blocks within this cell
                cell_text_blocks = self._find_text_blocks_in_cell(table_text_blocks, cell_bbox_dict)

                # Combine text blocks (sort by position for correct order)
                cell_text_blocks.sort(key=lambda b: (b.get('bbox', {}).get('y', 0), b.get('bbox', {}).get('x', 0)))
                cell_text = ' '.join([block.get('text', '').strip() for block in cell_text_blocks if block.get('text', '').strip()])
                cell_text = ' '.join(cell_text.split())  # Normalize whitespace

                if cell_text:
                    cell_texts[cell_idx] = cell_text

            if not cell_texts:
                logger.warning(f"Table {table_idx}: No text found in any cell")
                return None

            # Determine row/column positions from cell_bbox centers
            rows_dict = {}
            for cell_info in parsed_cells:
                cell_idx = cell_info['index']
                center_y = cell_info['center']['y']
                center_x = cell_info['center']['x']

                # Find row (group by similar y coordinates)
                row_key = self._find_row_for_y(center_y, rows_dict)
                if row_key not in rows_dict:
                    rows_dict[row_key] = []

                cell_text = cell_texts.get(cell_idx, '')
                rows_dict[row_key].append({
                    'col': center_x,
                    'text': cell_text,
                    'cell_idx': cell_idx,
                    'bbox': cell_info['bbox'],
                    'center': cell_info['center']
                })

            # Sort rows and columns
            sorted_rows = sorted(rows_dict.items())
            data = []
            for row_idx, (_, cells) in enumerate(sorted_rows):
                cells.sort(key=lambda x: x['col'])
                row_data = [cell['text'] for cell in cells]
                data.append(row_data)

            if not data:
                return None

            # Generate HTML structure
            html = self._generate_table_html(data)
            html_structure = self._extract_html_structure(html)

            return {
                'data': data,
                'html': html,
                'html_structure': html_structure,
                'rows': len(data),
                'columns': max(len(row) for row in data) if data else 0,
                'reconstruction_method': 'ocr_cell_bbox'
            }

        except Exception as e:
            logger.error(f"Table {table_idx}: Error reconstructing table with OCR: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def _parse_cell_bbox(self, cell_bbox: List[float]) -> Dict[str, Any]:
        """
        Parse cell_bbox (8 numbers) to extract cell boundary information.

        Args:
            cell_bbox: List of 8 numbers representing 4 points (x, y) each

        Returns:
            Dictionary with parsed cell boundary information
        """
        if len(cell_bbox) != 8:
            return {"error": f"Invalid cell_bbox length: {len(cell_bbox)}"}

        # Extract 4 points
        points = []
        for i in range(0, 8, 2):
            points.append((cell_bbox[i], cell_bbox[i + 1]))

        # Calculate bounding box
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]

        min_x = min(x_coords)
        max_x = max(x_coords)
        min_y = min(y_coords)
        max_y = max(y_coords)

        return {
            "points": points,
            "bbox": {
                "x": min_x,
                "y": min_y,
                "width": max_x - min_x,
                "height": max_y - min_y,
                "max_x": max_x,
                "max_y": max_y
            },
            "center": {
                "x": (min_x + max_x) / 2,
                "y": (min_y + max_y) / 2
            }
        }

    def _filter_text_blocks_in_bbox(
        self,
        text_blocks: List[Dict[str, Any]],
        bbox: Dict[str, float],
        page_num: int
    ) -> List[Dict[str, Any]]:
        """
        Filter OCR text blocks that are within the given bounding box.

        Args:
            text_blocks: List of OCR text blocks
            bbox: Bounding box {x, y, width, height}
            page_num: Page number to filter by

        Returns:
            Filtered list of text blocks
        """
        filtered = []
        bbox_x_min = bbox.get('x', 0)
        bbox_y_min = bbox.get('y', 0)
        bbox_x_max = bbox_x_min + bbox.get('width', 0)
        bbox_y_max = bbox_y_min + bbox.get('height', 0)

        for block in text_blocks:
            # Check page number
            if block.get('page') != page_num:
                continue

            block_bbox = block.get('bbox', {})
            if not block_bbox:
                continue

            block_x = block_bbox.get('x', 0)
            block_y = block_bbox.get('y', 0)
            block_width = block_bbox.get('width', 0)
            block_height = block_bbox.get('height', 0)
            block_x_max = block_x + block_width
            block_y_max = block_y + block_height

            # Check if block center is within bbox (more lenient than full overlap)
            block_center_x = block_x + block_width / 2
            block_center_y = block_y + block_height / 2

            if (bbox_x_min <= block_center_x <= bbox_x_max and
                bbox_y_min <= block_center_y <= bbox_y_max):
                filtered.append(block)

        return filtered

    def _find_text_blocks_in_cell(
        self,
        text_blocks: List[Dict[str, Any]],
        cell_bbox: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """
        Find OCR text blocks that fall within a cell's bounding box.

        Args:
            text_blocks: List of OCR text blocks
            cell_bbox: Cell bounding box {x, y, width, height, max_x, max_y}

        Returns:
            List of text blocks within the cell
        """
        cell_x_min = cell_bbox.get('x', 0)
        cell_y_min = cell_bbox.get('y', 0)
        cell_x_max = cell_bbox.get('max_x', cell_x_min + cell_bbox.get('width', 0))
        cell_y_max = cell_bbox.get('max_y', cell_y_min + cell_bbox.get('height', 0))

        matching_blocks = []

        for block in text_blocks:
            block_bbox = block.get('bbox', {})
            if not block_bbox:
                continue

            block_x = block_bbox.get('x', 0)
            block_y = block_bbox.get('y', 0)
            block_width = block_bbox.get('width', 0)
            block_height = block_bbox.get('height', 0)
            block_x_max = block_x + block_width
            block_y_max = block_y + block_height

            # Check if block center is within cell (more lenient than full overlap)
            block_center_x = block_x + block_width / 2
            block_center_y = block_y + block_height / 2

            if (cell_x_min <= block_center_x <= cell_x_max and
                cell_y_min <= block_center_y <= cell_y_max):
                matching_blocks.append(block)

        return matching_blocks

    def _find_row_for_y(self, y: float, rows_dict: Dict[float, List]) -> float:
        """
        Find the row key for a given y coordinate.
        Groups cells with similar y coordinates into the same row.

        Args:
            y: Y coordinate
            rows_dict: Dictionary of existing rows {y_key: [cells]}

        Returns:
            Row key (y coordinate)
        """
        tolerance = 5.0  # Pixels

        # Check if y is close to any existing row
        for row_key in rows_dict.keys():
            if abs(y - row_key) <= tolerance:
                return row_key

        # New row
        return y

    def _generate_table_html(self, data: List[List[str]]) -> str:
        """
        Generate HTML table from data array.

        Args:
            data: 2D list of table data

        Returns:
            HTML string
        """
        html = '<table><tbody>'
        for row in data:
            html += '<tr>'
            for cell_text in row:
                # Escape HTML special characters
                cell_text_escaped = cell_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                html += f'<td>{cell_text_escaped}</td>'
            html += '</tr>'
        html += '</tbody></table>'
        return html

    def _clean_table_html(self, html: str, table_idx: int) -> str:
        """
        Clean table HTML to ensure it only contains table content

        Args:
            html: Raw HTML string
            table_idx: Table index for logging

        Returns:
            Cleaned HTML string
        """
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            table_elem = soup.find('table')
            if not table_elem:
                return html

            # Remove any text nodes or elements outside of table cells
            for content in list(table_elem.contents):
                if not hasattr(content, 'name'):  # Text node
                    content.extract()
                elif hasattr(content, 'name') and content.name not in ['thead', 'tbody', 'tfoot', 'tr', 'colgroup', 'caption']:
                    content.extract()

            # Clean text nodes in rows
            for row in table_elem.find_all('tr'):
                for content in list(row.contents):
                    if not hasattr(content, 'name'):  # Text node
                        content.extract()
                    elif hasattr(content, 'name') and content.name not in ['td', 'th']:
                        content.extract()

            return str(table_elem)
        except Exception as e:
            logger.warning(f"Table {table_idx}: Failed to clean HTML: {e}")
            return html

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

    def _html_to_data(self, html: str) -> List[List[str]]:
        """
        Parse HTML table to extract data structure, preserving merged cells (rowspan/colspan).
        Returns a 2D list with proper handling of merged cells.
        Only extracts content from <table> tags, ignoring any other content.
        """
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, 'html.parser')
            # Only extract the first table element, ignore everything else
            table = soup.find('table')

            if not table:
                # If no table tag found, the HTML might be malformed
                # Try to find any table-like structure
                logger.warning("No <table> tag found in HTML, attempting to parse as raw HTML")
                return []

            # Extract all rows from the table only
            rows = table.find_all('tr')
            if not rows:
                return []

            # First pass: determine maximum columns by checking all rows
            max_cols = 0
            for row in rows:
                cells = row.find_all(['td', 'th'])
                col_count = 0
                for cell in cells:
                    colspan = int(cell.get('colspan', 1))
                    col_count += colspan
                max_cols = max(max_cols, col_count)

            if max_cols == 0:
                return []

            # Initialize data structure with empty strings
            data = []
            row_spans = {}  # Track rowspan cells: {(row, col): remaining_rows}

            for row_idx, row in enumerate(rows):
                cells = row.find_all(['td', 'th'])
                if not cells:
                    continue

                row_data = [''] * max_cols
                col_idx = 0

                # Skip columns that are occupied by rowspan from previous rows
                while col_idx < max_cols and (row_idx, col_idx) in row_spans:
                    col_idx += 1

                for cell in cells:
                    # Skip to next available column
                    while col_idx < max_cols and (row_idx, col_idx) in row_spans:
                        col_idx += 1

                    if col_idx >= max_cols:
                        break

                    # Get cell content - only text from this cell, not nested tables
                    # Remove any nested table content
                    cell_copy = BeautifulSoup(str(cell), 'html.parser')
                    # Find the actual cell element (td or th)
                    cell_elem = cell_copy.find(['td', 'th'])
                    if not cell_elem:
                        # If no td/th found, use the root
                        cell_elem = cell_copy

                    # Remove nested tables first
                    for nested_table in cell_elem.find_all('table'):
                        nested_table.decompose()

                    # Remove any other non-cell elements that might contain page text
                    # Only keep text content and basic formatting elements
                    allowed_tags = ['p', 'span', 'div', 'br', 'strong', 'em', 'b', 'i', 'u']
                    for elem in cell_elem.find_all():
                        if elem.name not in allowed_tags:
                            # Replace with its text content
                            if elem.string:
                                elem.replace_with(elem.string)
                            else:
                                elem.decompose()

                    # Extract text - only from the cell element
                    cell_text = cell_elem.get_text(separator=' ', strip=True)
                    # Normalize whitespace
                    cell_text = ' '.join(cell_text.split())

                    # Limit cell text length to prevent extremely long text (likely page content)
                    # Typical table cells should be relatively short
                    if len(cell_text) > 500:
                        logger.warning(f"Table {table_idx} row {row_idx} col {col_idx}: Cell text too long ({len(cell_text)} chars), truncating. May contain non-table content.")
                        # Try to find a reasonable break point (sentence end)
                        truncated = cell_text[:500]
                        last_period = truncated.rfind('.')
                        last_space = truncated.rfind(' ')
                        if last_period > 400:
                            cell_text = truncated[:last_period + 1]
                        elif last_space > 400:
                            cell_text = truncated[:last_space] + "..."
                        else:
                            cell_text = truncated + "..."

                    row_data[col_idx] = cell_text

                    # Handle colspan
                    colspan = int(cell.get('colspan', 1))
                    for c in range(1, colspan):
                        if col_idx + c < max_cols:
                            row_data[col_idx + c] = ''  # Mark as merged horizontally

                    # Handle rowspan
                    rowspan = int(cell.get('rowspan', 1))
                    if rowspan > 1:
                        for r in range(1, rowspan):
                            if row_idx + r < len(rows) + 10:  # Safety check
                                row_spans[(row_idx + r, col_idx)] = rowspan - r - 1
                                # Also mark colspan cells in rowspan
                                for c in range(1, colspan):
                                    if col_idx + c < max_cols:
                                        row_spans[(row_idx + r, col_idx + c)] = rowspan - r - 1

                    col_idx += colspan

                # Only add row if it has some content
                if any(cell.strip() for cell in row_data):
                    data.append(row_data)

            # Validate table data: ensure it looks like a table
            # Tables should have at least 2 columns and reasonable row/column counts
            if data:
                # Check if data looks like a table (not just a single column of text)
                max_cols = max(len(row) for row in data) if data else 0
                if max_cols < 2:
                    logger.warning(f"Table data has only {max_cols} column(s), may not be a valid table")
                    return []

                # Check if any row has too many columns (likely contains page text)
                if max_cols > 20:
                    logger.warning(f"Table data has {max_cols} columns, may contain non-table content. Filtering to 20 columns.")
                    # Filter rows to reasonable column count
                    data = [row[:20] for row in data]
                    max_cols = 20

                # Check if rows have consistent structure (typical of tables)
                if len(data) > 1:
                    first_row_cols = len(data[0])
                    consistent_rows = sum(1 for row in data if abs(len(row) - first_row_cols) <= 2)
                    consistency_ratio = consistent_rows / len(data) if data else 0
                    if consistency_ratio < 0.7:  # Less than 70% consistency
                        logger.warning(f"Table rows have inconsistent column counts ({consistency_ratio:.1%} consistency), may contain non-table content")
                        # Filter to only consistent rows
                        data = [row for row in data if abs(len(row) - first_row_cols) <= 2]

                # Additional validation: check if cells contain reasonable text (not entire page text)
                # If any cell has extremely long text (>500 chars), it might be page content
                for row_idx, row in enumerate(data):
                    for col_idx, cell in enumerate(row):
                        if isinstance(cell, str) and len(cell) > 500:
                            logger.warning(f"Table row {row_idx}, col {col_idx} has very long text ({len(cell)} chars), may contain non-table content")
                            # Truncate to prevent display issues
                            data[row_idx][col_idx] = cell[:500] + "..."

            return data
        except Exception as e:
            logger.warning(f"HTML table parsing failed: {e}")
            return []

    def _extract_html_structure(self, html: str) -> Dict[str, Any]:
        """
        Extract HTML table structure information including rowspan/colspan for frontend rendering.
        Only extracts from <table> tags, ignoring any other content.
        """
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, 'html.parser')
            # Only extract the first table element
            table = soup.find('table')

            if not table:
                return {}

            structure = {
                'rows': [],
                'has_merged_cells': False
            }

            rows = table.find_all('tr')
            for row_idx, row in enumerate(rows):
                row_info = {
                    'cells': []
                }
                cells = row.find_all(['td', 'th'])

                for cell in cells:
                    # Remove nested tables from cell content
                    cell_copy = BeautifulSoup(str(cell), 'html.parser')
                    for nested_table in cell_copy.find_all('table'):
                        nested_table.decompose()

                    cell_text = cell_copy.get_text(separator=' ', strip=True)
                    # Normalize whitespace
                    cell_text = ' '.join(cell_text.split())

                    cell_info = {
                        'text': cell_text,
                        'is_header': cell.name == 'th',
                        'rowspan': int(cell.get('rowspan', 1)),
                        'colspan': int(cell.get('colspan', 1))
                    }

                    if cell_info['rowspan'] > 1 or cell_info['colspan'] > 1:
                        structure['has_merged_cells'] = True

                    row_info['cells'].append(cell_info)

                # Only add row if it has cells
                if row_info['cells']:
                    structure['rows'].append(row_info)

            return structure
        except Exception as e:
            logger.warning(f"HTML structure extraction failed: {e}")
            return {}


class CamelotTableEngine(BaseTableEngine):
    """
    Fallback Table Engine - Camelot

    Advantages:
    - Excellent for text-based PDFs (not scanned)
    - Stream and Lattice modes
    - Handles complex table structures
    - Pure Python, no ML models needed
    """

    def __init__(self):
        self._ready = False
        self._init_engine()

    def _init_engine(self):
        try:
            import camelot
            self._ready = True
            logger.info("Camelot Table engine initialized successfully")
        except ImportError as e:
            logger.warning(f"Camelot not installed: {e}")
            self._ready = False
        except Exception as e:
            logger.warning(f"Camelot initialization failed: {e}")
            self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    def get_name(self) -> str:
        return "Camelot"

    async def extract(self, file_path: str) -> List[Dict[str, Any]]:
        if not self._ready:
            raise RuntimeError("Camelot engine not ready")

        import camelot

        ext = os.path.splitext(file_path)[1].lower()

        if ext != '.pdf':
            raise ValueError("Camelot only supports PDF files")

        all_tables = []

        try:
            # Try lattice mode first (for tables with borders)
            tables = camelot.read_pdf(file_path, pages='all', flavor='lattice')

            if len(tables) == 0:
                # Try stream mode (for tables without borders)
                tables = camelot.read_pdf(file_path, pages='all', flavor='stream')

            for idx, table in enumerate(tables):
                df = table.df

                table_dict = {
                    "id": f"table_{idx + 1}",
                    "page": table.page,
                    "engine": "Camelot",
                    "bbox": {
                        "x": table._bbox[0] if table._bbox else 0,
                        "y": table._bbox[1] if table._bbox else 0,
                        "width": table._bbox[2] - table._bbox[0] if table._bbox else 0,
                        "height": table._bbox[3] - table._bbox[1] if table._bbox else 0
                    },
                    "data": df.values.tolist(),
                    "rows": len(df),
                    "columns": len(df.columns),
                    "accuracy": table.accuracy,
                    "whitespace": table.whitespace
                }
                all_tables.append(table_dict)

        except Exception as e:
            logger.warning(f"Camelot extraction failed: {e}")
            raise

        return all_tables


class TabulaTableEngine(BaseTableEngine):
    """
    Alternative Table Engine - Tabula-py

    Advantages:
    - Good for simple tables
    - Fast processing
    - Based on tabula-java
    """

    def __init__(self):
        self._ready = False
        self._init_engine()

    def _init_engine(self):
        try:
            import tabula
            self._ready = True
            logger.info("Tabula Table engine initialized successfully")
        except ImportError as e:
            logger.warning(f"Tabula-py not installed: {e}")
            self._ready = False
        except Exception as e:
            logger.warning(f"Tabula initialization failed: {e}")
            self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    def get_name(self) -> str:
        return "Tabula"

    async def extract(self, file_path: str) -> List[Dict[str, Any]]:
        if not self._ready:
            raise RuntimeError("Tabula engine not ready")

        import tabula

        ext = os.path.splitext(file_path)[1].lower()

        if ext != '.pdf':
            raise ValueError("Tabula only supports PDF files")

        all_tables = []

        try:
            dfs = tabula.read_pdf(file_path, pages='all', multiple_tables=True)

            for idx, df in enumerate(dfs):
                if df.empty:
                    continue

                table_dict = {
                    "id": f"table_{idx + 1}",
                    "page": 1,  # Tabula doesn't provide page info easily
                    "engine": "Tabula",
                    "data": df.fillna('').values.tolist(),
                    "columns_header": df.columns.tolist(),
                    "rows": len(df),
                    "columns": len(df.columns)
                }
                all_tables.append(table_dict)

        except Exception as e:
            logger.warning(f"Tabula extraction failed: {e}")
            raise

        return all_tables


class TableService:
    """
    Table Extraction Service with multi-engine support

    Supports automatic fallback:
    1. PP-Structure-Table (Primary - Recommended for images/scanned PDFs)
    2. Camelot (Fallback - Good for text-based PDFs)
    3. Tabula (Alternative)
    """

    def __init__(self, use_gpu: bool = False):
        self.engines: Dict[str, BaseTableEngine] = {}
        self.default_engine = "ppstructure"
        self._use_gpu = use_gpu
        self._init_engines()

    def _init_engines(self):
        """Initialize all available table engines"""
        # Primary: PP-Structure-Table
        pp_engine = PPStructureTableEngine(use_gpu=self._use_gpu)
        if pp_engine.is_ready():
            self.engines["ppstructure"] = pp_engine

        # PaddleOCR-only version: Camelot and Tabula disabled
        # Fallback: Camelot
        # camelot_engine = CamelotTableEngine()
        # if camelot_engine.is_ready():
        #     self.engines["camelot"] = camelot_engine

        # Alternative: Tabula
        # tabula_engine = TabulaTableEngine()
        # if tabula_engine.is_ready():
        #     self.engines["tabula"] = tabula_engine

        logger.info(f"Available table engines: {list(self.engines.keys())}")

    def is_ready(self) -> bool:
        """Check if any table engine is available"""
        return len(self.engines) > 0

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
        ocr_text_blocks: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract tables from document or from layout elements

        Args:
            file_path: Path to PDF or image file (used as fallback if layout_elements not provided)
            engine: Specific engine to use (ppstructure, camelot, tabula)
            fallback: Whether to try fallback engines on failure
            layout_elements: Optional list of layout elements from Layout Service (preferred method)
            ocr_text_blocks: Optional list of OCR text blocks for table reconstruction

        Returns:
            List of extracted tables
        """
        # If layout elements are provided and using PP-Structure, extract from layout (preferred method)
        if layout_elements and (not engine or engine == "ppstructure"):
            if "ppstructure" in self.engines:
                eng = self.engines["ppstructure"]
                logger.info(f"Extracting tables from layout elements (preferred method)...")
                try:
                    result = await eng.extract(
                        file_path,
                        layout_elements=layout_elements,
                        ocr_text_blocks=ocr_text_blocks
                    )
                    # Add engine info to each table
                    for table in result:
                        table["engine_used"] = "ppstructure"
                    return result
                except Exception as e:
                    logger.warning(f"Failed to extract from layout elements: {e}, falling back to direct extraction")
                    # Fall through to direct extraction

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

                return result
            except Exception as e:
                logger.warning(f"{eng_name} failed: {e}")
                last_error = e
                if not fallback:
                    raise

        # Return empty list if all engines fail (tables are optional)
        logger.warning(f"All table engines failed. Last error: {last_error}")
        return []

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

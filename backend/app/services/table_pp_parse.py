"""Table parsing mixin — layout-elements extraction + PP-StructureV3 result parsing.

Split from ``table_service.py`` (runs/split batch 5, tier A verbatim move):
``_extract_from_layout_elements`` and ``_parse_tables`` were the tail of
``PPStructureTableEngine``; they only need the sibling-mixin methods via
``self`` (``_html_to_data`` / ``_extract_html_structure`` / ...), so they
become a fourth mixin the engine composes.
"""

from typing import Dict, Any, List, Optional
from loguru import logger

class TablePPParseMixin:
    """Layout-elements / PP-StructureV3 result parsing (P-028-style mixin split,
    runs/split batch 5; moved verbatim from table_service.PPStructureTableEngine)."""

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
                "confidence": element.get('confidence'),
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
                "confidence": None,  # No confidence score available (unmeasured != 0)
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

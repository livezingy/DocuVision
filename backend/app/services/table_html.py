"""F1 split: HTML table parsing / serialisation for PPStructureTableEngine.

Mechanical extraction out of ``table_service.py``, same shape as the P-028 F1 splits and
the ``table_ocr_blocks.py`` move: the four methods below are byte-identical to their
previous definitions, moved under :class:`TableHtmlMixin` and reached through the engine's
MRO, so the call sites and the ``test_table_header_structure.py`` path-loading test are
unchanged.

Pure ``bs4`` / stdlib logic (no ``self.*`` engine state); BeautifulSoup stays imported
lazily inside each method, exactly as it was. ``_parse_tables`` deliberately stays in
``table_service.py`` - it is the PP-StructureV3 result adapter, not HTML handling.
"""

from typing import Any, Dict, List, Optional, Tuple

from loguru import logger


class TableHtmlMixin:
    """HTML <table> parsing and serialisation helpers for the PP-Structure table engine."""

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
                        logger.warning(
                            f"Table cell row {row_idx} col {col_idx}: text too long ({len(cell_text)} chars), truncating. May contain non-table content."
                        )
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

        F4: preserve multi-level header relationships.
        - Rows inside <thead> are header rows (cells flagged is_header regardless
          of <th> vs <td>, since PP-StructureV3/SLANeXt often writes headers as <td>).
        - When <thead> is absent, apply a heuristic: the first up-to-3 rows where
          >=50% of cells are empty or short (<=20 chars) are treated as header rows.
        - Output ``header_rows`` (count) and ``header_span_map`` (per-header-cell
          span tree) so downstream can reconstruct multi-level header hierarchy
          instead of the flat ``data`` array which loses that structure.

        Official basis: SLANeXt outputs HTML with native <thead>/<th rowspan>/
        <th colspan> for multi-level headers
        (https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/table_recognition_v2.html).
        """
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, 'html.parser')
            # Only extract the first table element
            table = soup.find('table')

            if not table:
                return {}

            structure: Dict[str, Any] = {
                'rows': [],
                'has_merged_cells': False,
                'header_rows': 0,
                'header_span_map': [],
            }

            rows = table.find_all('tr')
            if not rows:
                return structure

            # F4: determine header rows.
            # 1) Explicit <thead>: every row inside thead is a header row.
            thead = table.find('thead')
            header_row_indices: set = set()
            if thead is not None:
                # A row is a header row if it is inside <thead>. Match by identity
                # against the full row list to get the correct row index.
                thead_rows = thead.find_all('tr')
                thead_row_ids = {id(r) for r in thead_rows}
                for r_idx, row in enumerate(rows):
                    if id(row) in thead_row_ids:
                        header_row_indices.add(r_idx)

            # 2) Heuristic fallback when no <thead>: first up to 3 rows where
            #    ALL cells are short text (<=20 chars, empty counts as short).
            #    A body row typically has at least one long cell, so this stops
            #    at the first body row. Catches PP-StructureV3 output that writes
            #    headers as <td> without <thead>.
            if not header_row_indices:
                max_header_probe = 3
                for r_idx, row in enumerate(rows):
                    if r_idx >= max_header_probe:
                        break
                    cells = row.find_all(['td', 'th'])
                    if not cells:
                        continue
                    all_short = True
                    for cell in cells:
                        cell_copy = BeautifulSoup(str(cell), 'html.parser')
                        for nested_table in cell_copy.find_all('table'):
                            nested_table.decompose()
                        text = ' '.join(cell_copy.get_text(separator=' ', strip=True).split())
                        if len(text) > 20:
                            all_short = False
                            break
                    if all_short:
                        header_row_indices.add(r_idx)
                    else:
                        # Stop at first non-header row: headers are leading rows.
                        break

            structure['header_rows'] = len(header_row_indices)

            for row_idx, row in enumerate(rows):
                row_info: Dict[str, Any] = {
                    'cells': [],
                    'is_header_row': row_idx in header_row_indices,
                }
                cells = row.find_all(['td', 'th'])

                # Track the column cursor for header_span_map (account for
                # colspan/rowspan of preceding cells in the same row).
                col_cursor = 0
                for cell in cells:
                    # Remove nested tables from cell content
                    cell_copy = BeautifulSoup(str(cell), 'html.parser')
                    for nested_table in cell_copy.find_all('table'):
                        nested_table.decompose()

                    cell_text = cell_copy.get_text(separator=' ', strip=True)
                    # Normalize whitespace
                    cell_text = ' '.join(cell_text.split())

                    rowspan = int(cell.get('rowspan', 1))
                    colspan = int(cell.get('colspan', 1))
                    is_header = (row_idx in header_row_indices) or (cell.name == 'th')

                    cell_info = {
                        'text': cell_text,
                        'is_header': is_header,
                        'rowspan': rowspan,
                        'colspan': colspan,
                    }

                    if rowspan > 1 or colspan > 1:
                        structure['has_merged_cells'] = True

                    # F4: record header span tree for multi-level header
                    # reconstruction downstream.
                    if is_header and (rowspan > 1 or colspan > 1):
                        structure['header_span_map'].append({
                            'row': row_idx,
                            'col': col_cursor,
                            'rowspan': rowspan,
                            'colspan': colspan,
                            'text': cell_text,
                        })

                    row_info['cells'].append(cell_info)
                    col_cursor += colspan

                # Only add row if it has cells
                if row_info['cells']:
                    structure['rows'].append(row_info)

            return structure
        except Exception as e:
            logger.warning(f"HTML structure extraction failed: {e}")
            return {}


"""F1 split (P-027 产品侧立项 D8 前置): OCR-block -> cell-grid reconstruction.

Mechanical extraction out of ``table_service.py`` with **zero behaviour change**: the five
methods below are byte-identical to their previous definitions, moved under
:class:`TableOcrBlocksMixin` and reached through the engine's MRO
(``class PPStructureTableEngine(TableOcrBlocksMixin, BaseTableEngine)``), so the method
surface that call sites and the existing path-loading tests rely on
(``_reconstruct_table_with_ocr`` / ``_parse_cell_bbox`` / ``_filter_text_blocks_in_bbox`` /
``_find_text_blocks_in_cell`` / ``_find_row_for_y``) is unchanged.

Why they moved: the whole cluster reads and writes **no** ``self.*`` attribute of
``PPStructureTableEngine`` - it only calls its own siblings plus the HTML helpers
``_generate_table_html`` / ``_extract_html_structure``, which stay in ``table_service.py``
(the dependency is one-way), and ``table_service.py`` is pinned at its 1613-line cap in
``scripts/file_size_allowlist.json``, so no line could be added there.

This is the landing zone for the D8 ``cell_confidence`` work (PaddleOCR ``rec_score``
propagated per cell - see PENDING P-027 「产品侧立项 D8」), which is why it lives in its
own, not-yet-ratcheted module.

Note: the OCR text-block dicts handled here do carry ``confidence``, but this module
deliberately does not read it yet - the current aggregation keeps ``text`` only.
"""

from typing import Any, Dict, List, Optional

from loguru import logger


class TableOcrBlocksMixin:
    """Stateless OCR-block / cell-geometry helpers for the PP-Structure table engine."""

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

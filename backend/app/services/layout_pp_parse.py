"""PP-StructureV3 parse + dedup mixin (S1 batch-6 verbatim extraction from the
PPStructureEngine class; natural mixin form like the batch-5 TablePPParseMixin).
Growth seam if this file nears the 500 cap: the html/preds fallback branches."""

from typing import Dict, Any, List
from loguru import logger
from app.services.table_cell_confidence import cell_confidence_from_table_item, page_height_of


class LayoutPPParseMixin:
    """Engine payload -> layout elements: parse, sort, table confidence, dedup."""

    def _parse_result(self, result: List[Dict], page_num: int) -> List[Dict[str, Any]]:
        """
        Parse layout elements from PPStructureV3 result.

        CRITICAL FIX FOR PaddleOCR 3.3.2 / PaddleX 3.3.12:
        PPStructureV3 returns LayoutParsingResultV2 objects, NOT plain dicts.

        LayoutParsingResultV2 structure:
        - result[0]: LayoutParsingResultV2 object
        - result[0].preds: List of predictions with type, bbox, score
        - result[0].boxes: Alternative attribute name for predictions (version-dependent)
        - result[0].html: Dict for table HTML (used by table_service)

        For layout analysis, we primarily use result[0].preds which contains:
        [
            {
                'type': 'text' | 'title' | 'table' | 'figure' | ...,
                'bbox': [x1, y1, x2, y2],
                'score': confidence_score
            },
            ...
        ]

        Args:
            result: List containing ONE LayoutParsingResultV2 object
            page_num: Page number

        Returns:
            List of parsed layout elements
        """
        elements = []

        if not result or len(result) == 0:
            logger.warning(f"Page {page_num}: Empty result from PPStructureV3")
            return elements

        first_item = result[0]
        # D8: page height in the engine frame, used for the per-table frame choice. 0.0
        # disables the flipped candidate (see table_cell_confidence.page_height_of).
        layout_page_height = page_height_of(first_item)

        # PaddleOCR 3.3.x / PaddleX 3.3.12 fast-path:
        # LayoutParsingResultV2 supports dict-style keys and provides structured
        # parsing_res_list blocks with accurate bbox/content.
        item_keys = []
        try:
            item_keys = list(first_item.keys())
        except (AttributeError, TypeError):
            item_keys = []

        if 'parsing_res_list' in item_keys:
            parsing_blocks = first_item.get('parsing_res_list') or []
            table_res_list = first_item.get('table_res_list') or []

            # NOTE: bboxes are kept in preprocessed coordinate space (output_img space).
            # The inverse rotation / coordinate restoration is handled by view_builder
            # (envelope_builder), not here.  This keeps the fused layer's
            # bbox_preprocessed semantically accurate regardless of rotation or unwarping.

            # Build stable table html list ordered by table_region_id.
            # D8: the same entry carries the OCR recognition scores needed for per-cell
            # confidence, so keep the whole item beside its html - a single map keeps the two
            # derived lists from diverging (same keyset, same sort order).
            table_payload_map = {}
            for t in table_res_list:
                if not isinstance(t, dict):
                    continue
                table_region_id = t.get('table_region_id')
                table_html = t.get('pred_html')
                if table_region_id is None or not isinstance(table_html, str):
                    continue
                if '<table' not in table_html.lower():
                    continue
                try:
                    table_payload_map[int(table_region_id)] = (table_html, t)
                except Exception:
                    continue

            ordered_table_items = [v for _, v in sorted(table_payload_map.items(), key=lambda kv: kv[0])]
            ordered_table_html = [h for h, _ in ordered_table_items]
            table_cursor = 0

            # Build a (bbox, score) list from layout_det_res.boxes so we can look up
            # the real detection confidence for each parsing block.
            # parsing_res_list items do not carry a score field themselves; the score
            # is only available in the upstream layout detection output.
            _det_score_pairs: list = []
            try:
                _layout_det = (
                    first_item.get('layout_det_res')
                    if isinstance(first_item, dict)
                    else getattr(first_item, 'layout_det_res', None)
                )
                _det_boxes = []
                if isinstance(_layout_det, dict):
                    _det_boxes = _layout_det.get('boxes', [])
                elif _layout_det is not None:
                    _det_boxes = getattr(_layout_det, 'boxes', [])
                for _box in _det_boxes:
                    if isinstance(_box, dict):
                        _coord = _box.get('coordinate', [])
                        _sc = _box.get('score', None)
                    else:
                        _coord = getattr(_box, 'coordinate', [])
                        _sc = getattr(_box, 'score', None)
                    norm_coord = self._normalize_bbox_coords(_coord)
                    if norm_coord and _sc is not None:
                        _det_score_pairs.append((norm_coord, float(_sc)))
            except Exception as _e:
                logger.debug(f"Page {page_num}: Could not build det score map: {_e}")

            for idx, block in enumerate(parsing_blocks):
                if isinstance(block, dict):
                    element_type = str(block.get('label', 'unknown')).lower()
                    bbox = block.get('bbox', [])
                    content = block.get('content', '')
                    block_text = block.get('text', '')
                    block_index = block.get('index', idx)
                    # F1: prefer official `block_order` (Enhanced XYCut reading
                    # order) over detection `index`. Falls back to idx when the
                    # field is absent (older PaddleOCR versions).
                    block_order = block.get('block_order', None)
                else:
                    element_type = str(getattr(block, 'label', 'unknown')).lower()
                    bbox = getattr(block, 'bbox', [])
                    content = getattr(block, 'content', '')
                    block_text = getattr(block, 'text', '')
                    block_index = getattr(block, 'index', idx)
                    block_order = getattr(block, 'order_index', None)
                    if block_order is None:
                        # dict-style fallback (LayoutParsingResultV2 exposes
                        # both attribute and dict access depending on version)
                        block_order = block.get('block_order', None) if isinstance(block, dict) else None

                block_text_str = str(block_text or "")
                content_str = str(content or "")
                logger.info(
                    f"[StructuredBlock] Page {page_num} Block {idx} ({element_type}): "
                    f"text='{block_text_str[:100]}' | content='{content_str[:100]}'"
                )

                norm_bbox = self._normalize_bbox_coords(bbox)
                if not norm_bbox:
                    continue

                raw_bbox = norm_bbox
                # Keep preprocessed-space bbox; view_builder applies inverse transform.
                bbox_dict = self._extract_bbox(raw_bbox)
                # Build flat polygon from bbox corners: [x0,y0, x1,y0, x1,y1, x0,y1]
                x0_p = raw_bbox[0]; y0_p = raw_bbox[1]; x1_p = raw_bbox[2]; y1_p = raw_bbox[3]
                polygon_prep = [x0_p, y0_p, x1_p, y0_p, x1_p, y1_p, x0_p, y1_p]

                # Look up the real layout detection score by bbox proximity.
                # Tolerance of 3px handles float rounding between parsing_res_list
                # and layout_det_res.boxes coordinate representations.
                _block_score = None
                for _det_coord, _det_sc in _det_score_pairs:
                    if all(abs(raw_bbox[i] - _det_coord[i]) < 3.0 for i in range(4)):
                        _block_score = _det_sc
                        break

                element = {
                    "id": f"p{page_num}_e{block_index}",
                    "page": page_num,
                    "type": element_type,
                    "type_name": self.LAYOUT_TYPES.get(element_type, element_type),
                    "bbox": bbox_dict,
                    "polygon_preprocessed": polygon_prep,
                    "confidence": float(_block_score) if _block_score is not None else None,  # None = 检测分未匹配（未测量 ≠ 0；P-027 (3) 批 2）
                    # F1: carry official reading order (block_order) downstream.
                    # None when the engine did not assign one (e.g. image/figure_title).
                    "reading_order": int(block_order) if block_order is not None else None,
                }

                if isinstance(content, str) and content.strip():
                    element['text'] = self._normalize_text(content)

                if element_type == 'table' and table_cursor < len(ordered_table_html):
                    table_html, table_item = ordered_table_items[table_cursor]
                    table_cursor += 1
                    element['html'] = table_html
                    # D8: per-cell confidence from this table's own OCR recognition scores.
                    # Compact (one float per cell + scalars) and not part of the view contract;
                    # the orchestrator copies it onto result["tables"] by id.
                    cell_confidence = cell_confidence_from_table_item(table_item, layout_page_height)
                    if cell_confidence:
                        element['cell_confidence'] = cell_confidence
                    if 'text' not in element:
                        element['text'] = self._extract_table_summary_text(table_html)

                elements.append(element)

            # F1: sort by official reading order (block_order) when present,
            # falling back to (y, x) bbox order. See _layout_order.py + findings §1.
            from app.services._layout_order import sort_elements_by_reading_order, has_reading_order
            if has_reading_order(elements):
                elements = sort_elements_by_reading_order(elements)
                logger.info(f"Page {page_num}: sorted {len(elements)} elements by reading_order (block_order)")
            else:
                elements.sort(key=lambda e: (e['bbox']['y'], e['bbox']['x']))
                logger.info(f"Page {page_num}: sorted {len(elements)} elements by (y, x) fallback (no block_order)")
            elements = self._deduplicate_elements(elements)
            logger.info(
                f"Page {page_num}: Parsed {len(elements)} elements from parsing_res_list "
                f"(tables_with_html={table_cursor})"
            )
            return elements

        # Parse table-only html output first. Some PaddleOCR/PaddleX versions
        # return html dict even when preds/boxes are empty.
        html_dict = None
        if hasattr(first_item, 'html'):
            html_dict = getattr(first_item, 'html', None)
        elif isinstance(first_item, dict):
            html_dict = first_item.get('html')

        if isinstance(html_dict, dict) and html_dict:
            page_bbox = self._infer_page_bbox(first_item)
            table_idx = 0
            for table_key, table_html in html_dict.items():
                if not isinstance(table_html, str) or '<table' not in table_html.lower():
                    continue
                table_idx += 1
                _pb = page_bbox
                _pbx0, _pby0 = float(_pb.get("x", 0)), float(_pb.get("y", 0))
                _pbx1 = _pbx0 + float(_pb.get("width", 0))
                _pby1 = _pby0 + float(_pb.get("height", 0))
                elements.append({
                    "id": f"p{page_num}_table_{table_idx}",
                    "page": page_num,
                    "type": "table",
                    "type_name": self.LAYOUT_TYPES.get("table", "Table"),
                    "bbox": page_bbox,
                    "polygon_preprocessed": [_pbx0, _pby0, _pbx1, _pby0, _pbx1, _pby1, _pbx0, _pby1],
                    "confidence": 0.01,
                    "text": self._extract_table_summary_text(table_html),
                    "html": table_html,
                    "table_key": table_key,
                    "inferred_bbox": True,
                    "overlay_excluded": True,
                })

            if table_idx > 0:
                logger.info(
                    f"Page {page_num}: Added {table_idx} table element(s) from html output "
                    f"with inferred bbox=({page_bbox['x']}, {page_bbox['y']}, "
                    f"{page_bbox['width']}, {page_bbox['height']})"
                )

        # Gather layout predictions from multiple possible fields.
        raw_predictions = None
        if hasattr(first_item, 'preds'):
            raw_predictions = first_item.preds
        elif hasattr(first_item, 'boxes'):
            raw_predictions = first_item.boxes
        elif hasattr(first_item, 'layout_dets'):
            raw_predictions = first_item.layout_dets
        elif isinstance(first_item, dict):
            raw_predictions = (
                first_item.get('preds')
                or first_item.get('boxes')
                or first_item.get('layout_dets')
                or []
            )
        elif isinstance(first_item, (list, tuple)):
            raw_predictions = list(first_item)

        layout_predictions = []
        if raw_predictions is not None:
            if isinstance(raw_predictions, list):
                layout_predictions = raw_predictions
            elif isinstance(raw_predictions, tuple):
                layout_predictions = list(raw_predictions)
            else:
                try:
                    layout_predictions = list(raw_predictions)
                except Exception:
                    logger.warning(
                        f"Page {page_num}: Predictions cannot be converted to list, type={type(raw_predictions)}"
                    )

        if not layout_predictions:
            if elements:
                logger.warning(
                    f"Page {page_num}: No layout predictions found, returning html-derived elements={len(elements)}"
                )
                return elements
            if isinstance(first_item, dict):
                logger.warning(
                    f"Page {page_num}: No layout predictions found | dict keys={list(first_item.keys())}"
                )
            else:
                logger.warning(
                    f"Page {page_num}: No layout predictions found | object type={type(first_item)}"
                )
            logger.warning(f"Page {page_num}: No layout predictions found")
            return elements

        logger.info(f"Page {page_num}: Processing {len(layout_predictions)} layout regions")

        for idx, item in enumerate(layout_predictions):
            # Handle both dict and object-style predictions
            if isinstance(item, dict):
                element_type = item.get('type', item.get('label', item.get('class_name', 'unknown')))
                bbox = item.get('bbox', item.get('coordinate', item.get('box', [])))
                score = item.get('score', 0)
                res = item.get('res', None)
            elif hasattr(item, 'type'):
                # Object-style prediction
                element_type = getattr(item, 'type', 'unknown')
                bbox = getattr(item, 'bbox', getattr(item, 'coordinate', getattr(item, 'box', [])))
                score = getattr(item, 'score', 0)
                res = getattr(item, 'res', None)
            else:
                logger.warning(f"Element {idx}: Cannot parse prediction item, type={type(item)}")
                continue

            # Skip invalid elements
            norm_bbox = self._normalize_bbox_coords(bbox)
            if not norm_bbox:
                logger.debug(f"Element {idx}: Invalid bbox {bbox}")
                continue

            _bbox_raw = norm_bbox
            _bbox_dict = self._extract_bbox(_bbox_raw)
            _bx0, _by0, _bx1, _by1 = _bbox_raw[0], _bbox_raw[1], _bbox_raw[2], _bbox_raw[3]
            element = {
                "id": f"p{page_num}_e{idx}",
                "page": page_num,
                "type": element_type,
                "type_name": self.LAYOUT_TYPES.get(element_type, element_type),
                "bbox": _bbox_dict,
                "polygon_preprocessed": [_bx0, _by0, _bx1, _by0, _bx1, _by1, _bx0, _by1],
                "confidence": float(score) if score else 0.0,
            }

            # Extract text content from OCR results
            if res is not None:
                if isinstance(res, list):
                    texts = []
                    for line in res:
                        if isinstance(line, dict) and 'text' in line:
                            texts.append(line['text'])
                        elif isinstance(line, tuple) and len(line) >= 1:
                            texts.append(line[0])
                        elif isinstance(line, str):
                            texts.append(line)

                    # Join texts appropriately based on element type
                    if element_type in ['text', 'paragraph']:
                        combined_text = ' '.join(texts)
                        element['text'] = self._normalize_text(combined_text)
                    else:
                        element['text'] = self._normalize_text('\n'.join(texts))

                elif isinstance(res, dict):
                    # For tables, store HTML separately
                    element['content'] = res
                    if 'html' in res:
                        element['html'] = res['html']
                    if 'text' in res:
                        element['text'] = self._normalize_text(res['text'])

            elements.append(element)

        # Sort by reading order (top to bottom, left to right)
        elements.sort(key=lambda e: (e['bbox']['y'], e['bbox']['x']))

        # Apply deduplication for text elements
        elements = self._deduplicate_elements(elements)

        logger.info(f"Page {page_num}: Final {len(elements)} layout elements after processing")

        return elements

    def _deduplicate_elements(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate elements where parent elements contain complete child elements.
        Only keep the most granular (child) elements.

        Args:
            elements: List of layout elements

        Returns:
            Deduplicated list of elements
        """
        if not elements:
            return elements

        # Only process text/paragraph elements
        text_elements = [e for e in elements if e.get('type') in ['text', 'paragraph'] and e.get('text')]
        other_elements = [e for e in elements if e.get('type') not in ['text', 'paragraph'] or not e.get('text')]

        if len(text_elements) <= 1:
            return elements

        logger.info(f"Deduplicating {len(text_elements)} text/paragraph elements")

        # Find elements to remove (parent elements that contain complete child elements)
        elements_to_remove = set()

        for i, parent_elem in enumerate(text_elements):
            if i in elements_to_remove:
                continue

            parent_bbox = parent_elem.get('bbox', {})
            parent_text = parent_elem.get('text', '')

            if not parent_text or not parent_bbox.get('width') or not parent_bbox.get('height'):
                continue

            # Find child elements contained in this parent
            contained_children = []
            for j, child_elem in enumerate(text_elements):
                if i == j or j in elements_to_remove:
                    continue

                child_bbox = child_elem.get('bbox', {})
                child_text = child_elem.get('text', '')

                if not child_text or not child_bbox.get('width') or not child_bbox.get('height'):
                    continue

                # Check if parent contains child (use lower threshold for bbox containment)
                contains = self._bbox_contains(parent_bbox, child_bbox, threshold=0.70)
                if contains:
                    # Check if child text appears in parent text
                    # Normalize both texts for comparison
                    parent_text_normalized = parent_text.lower().strip()
                    child_text_normalized = child_text.lower().strip()

                    # If child text is a substantial substring of parent text, it's likely contained
                    if child_text_normalized and len(child_text_normalized) > 20:
                        # Strategy 1: Direct substring match (most reliable)
                        if child_text_normalized in parent_text_normalized:
                            contained_children.append((j, child_elem))
                            logger.info(f"Element {i} contains element {j} (direct text match): parent_bbox={parent_bbox}, child_bbox={child_bbox}")
                        else:
                            # Strategy 2: Word-based matching for cases where text might be slightly different
                            child_words = child_text_normalized.split()
                            if len(child_words) > 5:
                                # Check if at least 60% of child words appear in parent (more lenient)
                                matching_words = sum(1 for word in child_words[:20] if word in parent_text_normalized)
                                word_match_ratio = matching_words / len(child_words[:20]) if child_words[:20] else 0
                                if word_match_ratio >= 0.6 and matching_words >= 8:
                                    contained_children.append((j, child_elem))
                                    logger.info(f"Element {i} contains element {j} (word match: {matching_words}/{len(child_words[:20])} words, {word_match_ratio:.1%}): parent_bbox={parent_bbox}, child_bbox={child_bbox}")

            # If parent contains multiple complete children, remove the parent
            # Keep only the child elements
            if len(contained_children) >= 2:
                # Verify children are complete (not just partial matches)
                complete_children = []
                for child_idx, child_elem in contained_children:
                    child_text = child_elem.get('text', '')
                    # Check if child text looks complete (ends with punctuation or is substantial)
                    # More lenient criteria: at least 30 chars and either ends with punctuation or has >8 words
                    if (len(child_text) > 30 and
                        (child_text[-1] in '.!?;' or
                         len(child_text.split()) > 8)):
                        complete_children.append(child_idx)
                        logger.debug(f"  Child {child_idx} is complete: length={len(child_text)}, words={len(child_text.split())}")

                # If we have at least 2 complete children, remove the parent
                if len(complete_children) >= 2:
                    elements_to_remove.add(i)
                    logger.info(f"Removing parent element {i} (text: {parent_text[:80]}...) that contains {len(complete_children)} complete child elements")
                    for child_idx in complete_children:
                        logger.info(f"  - Keeping child element {child_idx} (text: {text_elements[child_idx].get('text', '')[:80]}...)")

        # Remove parent elements and keep children
        filtered_elements = []
        for i, elem in enumerate(text_elements):
            if i not in elements_to_remove:
                filtered_elements.append(elem)

        logger.info(f"After deduplication: {len(filtered_elements)} text/paragraph elements (removed {len(elements_to_remove)} parent elements)")

        # Combine with other elements
        result = filtered_elements + other_elements

        # Sort again by reading order
        result.sort(key=lambda e: (e['bbox']['y'], e['bbox']['x']))

        return result

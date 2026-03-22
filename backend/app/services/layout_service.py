"""
Layout Analysis Service - Multi-engine support with PP-Structure (Primary) and LayoutParser (Fallback)
"""

from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
from loguru import logger
import os
import paddle

# Import compatibility patches FIRST
from app.compatibility_patches import apply_all_patches
apply_all_patches()


class BaseLayoutEngine(ABC):
    """Abstract base class for Layout Analysis engines"""

    # Layout element type mapping
    LAYOUT_TYPES = {
        'text': 'Text',
        'title': 'Title',
        'figure': 'Figure',
        'figure_caption': 'Figure Caption',
        'table': 'Table',
        'table_caption': 'Table Caption',
        'header': 'Header',
        'footer': 'Footer',
        'reference': 'Reference',
        'equation': 'Equation',
        'list': 'List'
    }

    @abstractmethod
    def is_ready(self) -> bool:
        pass

    @abstractmethod
    async def analyze(self, file_path: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass


class PPStructureEngine(BaseLayoutEngine):
    """
    Primary Layout Engine - PP-StructureV3

    Advantages:
    - 10+ element types detection
    - Table structure recognition >90% accuracy
    - Formula recognition (LaTeX output)
    - Document orientation correction
    - Active community support from Baidu
    """

    def __init__(self, use_gpu: bool = False, recovery: bool = True):
        self._engine = None
        self._ready = False
        self._use_gpu = use_gpu
        self._recovery = recovery
        self._init_engine()

    def _init_engine(self):
        try:
            from paddleocr import PPStructureV3
            import paddleocr

            # Log version for debugging
            try:
                version = paddleocr.__version__
                logger.info(f"PaddleOCR version: {version}")
            except:
                pass

            # PPStructureV3 (3.x) initialization
            # Use minimal parameters to match test script
            init_params = {
                "device": "gpu" if self._use_gpu else "cpu"
            }

            # Note: use_doc_orientation_classify may cause initialization errors in 3.1.1
            # Removed to match working test script configuration

            self._engine = PPStructureV3(**init_params)
            self._is_v3 = True

            self._ready = True
            logger.info("PPStructureV3 layout engine initialized successfully")
        except ImportError as e:
            logger.warning(f"PaddleOCR/PPStructure not installed: {e}")
            self._ready = False
        except RuntimeError as e:
            # Handle PDX already initialized error - PaddleX should only be initialized once in main.py
            if "PDX has already been initialized" in str(e):
                logger.debug(f"PPStructureV3 PDX initialization already done by main.py")
                # Still mark as ready since models are already loaded
                self._ready = True
            else:
                logger.error(f"PP-Structure initialization failed: {e}")
                self._ready = False
        except Exception as e:
            logger.error(f"PP-Structure initialization failed: {e}")
            self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    def get_name(self) -> str:
        return "PP-StructureV3"

    def _call_engine(self, img_path: str):
        """Call engine with version-compatible method"""
        if hasattr(self, '_is_v3') and self._is_v3:
            # PPStructureV3 uses predict() method
            return self._engine.predict(img_path)
        else:
            # PPStructure (2.x) uses direct call
            return self._engine(img_path)

    async def analyze(self, file_path: str) -> Dict[str, Any]:
        if not self._ready:
            raise RuntimeError("PP-Structure engine not ready")

        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.pdf':
            return await self._analyze_pdf(file_path)
        else:
            return await self._analyze_image(file_path)

    async def _analyze_pdf(self, pdf_path: str) -> Dict[str, Any]:
        import fitz
        from PIL import Image
        import numpy as np

        doc = fitz.open(pdf_path)
        page_count = len(doc)  # 保存页数，避免关闭后访问
        all_elements = []
        page_layouts = []

        try:
            for page_num in range(page_count):
                page = doc[page_num]

                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_path = f"{pdf_path}_layout_{page_num}.png"

                # 确保图像是 RGB 格式（3通道），而不是 RGBA（4通道）
                if pix.alpha:
                    # 如果有 alpha 通道，转换为 RGB
                    img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
                    img = img.convert("RGB")
                    img.save(img_path)
                else:
                    pix.save(img_path)

                result = self._call_engine(img_path)

                page_elements = self._parse_result(result, page_num + 1)
                all_elements.extend(page_elements)

                page_layout = self._get_page_summary(page_elements)
                page_layout["page"] = page_num + 1
                page_layouts.append(page_layout)

                if os.path.exists(img_path):
                    os.remove(img_path)
        finally:
            doc.close()

        return {
            "engine": "PP-StructureV3",
            "total_pages": len(page_layouts),
            "elements": all_elements,
            "page_layouts": page_layouts,
            "summary": self._get_document_summary(all_elements)
        }

    async def _analyze_image(self, img_path: str) -> Dict[str, Any]:
        from PIL import Image

        # 确保图像是 RGB 格式（3通道）
        img = Image.open(img_path)
        if img.mode == 'RGBA':
            # 转换为 RGB
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3])  # 使用 alpha 通道作为 mask
            temp_path = f"{img_path}_rgb.png"
            rgb_img.save(temp_path)
            result = self._call_engine(temp_path)
            if os.path.exists(temp_path):
                os.remove(temp_path)
        else:
            if img.mode != 'RGB':
                img = img.convert('RGB')
                temp_path = f"{img_path}_rgb.png"
                img.save(temp_path)
                result = self._call_engine(temp_path)
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            else:
                result = self._call_engine(img_path)

        elements = self._parse_result(result, 1)

        return {
            "engine": "PP-StructureV3",
            "total_pages": 1,
            "elements": elements,
            "page_layouts": [{"page": 1, **self._get_page_summary(elements)}],
            "summary": self._get_document_summary(elements)
        }

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

            # Build stable table html list ordered by table_region_id.
            table_html_map = {}
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
                    table_html_map[int(table_region_id)] = table_html
                except Exception:
                    continue

            ordered_table_html = [h for _, h in sorted(table_html_map.items(), key=lambda kv: kv[0])]
            table_cursor = 0

            for idx, block in enumerate(parsing_blocks):
                if isinstance(block, dict):
                    element_type = str(block.get('label', 'unknown')).lower()
                    bbox = block.get('bbox', [])
                    content = block.get('content', '')
                    block_index = block.get('index', idx)
                else:
                    element_type = str(getattr(block, 'label', 'unknown')).lower()
                    bbox = getattr(block, 'bbox', [])
                    content = getattr(block, 'content', '')
                    block_index = getattr(block, 'index', idx)

                if not bbox or len(bbox) < 4:
                    continue

                element = {
                    "id": f"p{page_num}_e{block_index}",
                    "page": page_num,
                    "type": element_type,
                    "type_name": self.LAYOUT_TYPES.get(element_type, element_type),
                    "bbox": self._extract_bbox(bbox),
                    "confidence": 0.9,
                }

                if isinstance(content, str) and content.strip():
                    element['text'] = self._normalize_text(content)

                if element_type == 'table' and table_cursor < len(ordered_table_html):
                    table_html = ordered_table_html[table_cursor]
                    table_cursor += 1
                    element['html'] = table_html
                    if 'text' not in element:
                        element['text'] = self._extract_table_summary_text(table_html)

                elements.append(element)

            elements.sort(key=lambda e: (e['bbox']['y'], e['bbox']['x']))
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
                elements.append({
                    "id": f"p{page_num}_table_{table_idx}",
                    "page": page_num,
                    "type": "table",
                    "type_name": self.LAYOUT_TYPES.get("table", "Table"),
                    "bbox": page_bbox,
                    "confidence": 0.0,
                    "text": self._extract_table_summary_text(table_html),
                    "html": table_html,
                    "table_key": table_key,
                    "inferred_bbox": True,
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
            if not bbox or len(bbox) < 4:
                logger.debug(f"Element {idx}: Invalid bbox {bbox}")
                continue

            element = {
                "id": f"p{page_num}_e{idx}",
                "page": page_num,
                "type": element_type,
                "type_name": self.LAYOUT_TYPES.get(element_type, element_type),
                "bbox": self._extract_bbox(bbox),
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

    def _infer_page_bbox(self, first_item: Any) -> Dict[str, float]:
        """Infer full-page bbox from result payload for html-only outputs."""
        width = 0.0
        height = 0.0

        img_obj = None
        if hasattr(first_item, 'img'):
            img_obj = getattr(first_item, 'img', None)
        elif isinstance(first_item, dict):
            img_obj = first_item.get('img')

        if img_obj is not None:
            try:
                # numpy-like image array
                if hasattr(img_obj, 'shape') and len(img_obj.shape) >= 2:
                    height = float(img_obj.shape[0])
                    width = float(img_obj.shape[1])
                # PIL-like image
                elif hasattr(img_obj, 'size') and isinstance(img_obj.size, tuple) and len(img_obj.size) >= 2:
                    width = float(img_obj.size[0])
                    height = float(img_obj.size[1])
            except Exception:
                pass

        if width <= 0 or height <= 0:
            # Keep non-zero fallback to ensure front-end can render visible annotation box.
            width = 1000.0
            height = 1400.0

        return {"x": 0.0, "y": 0.0, "width": width, "height": height}

    def _extract_table_summary_text(self, table_html: str) -> str:
        """Extract a short readable summary from table HTML for UI tooltip display."""
        if not table_html:
            return "Table detected"
        try:
            import re
            text = re.sub(r"<[^>]+>", " ", table_html)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:220] if text else "Table detected"
        except Exception:
            return "Table detected"

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text to ensure proper spacing between words.
        This fixes issues where OCR returns text without spaces between words.
        """
        if not text:
            return text

        import re

        # First, normalize whitespace: replace multiple spaces/newlines with single space
        # but preserve intentional line breaks (double newlines)
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Preserve paragraph breaks
        text = re.sub(r'[ \t]*\n[ \t]*', ' ', text)  # Single newlines to space

        # Pattern to detect word boundaries:
        # - Lowercase followed by uppercase (e.g., "FuelSaving" -> "Fuel Saving")
        # - Letter followed by number or vice versa
        # - But preserve existing spaces and punctuation

        # Add space between lowercase letter and uppercase letter (word boundary)
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)

        # Add space between letter and number (if not already spaced)
        text = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)
        text = re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)

        # Clean up multiple spaces (but preserve paragraph breaks)
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n\n+', '\n\n', text)  # Multiple paragraph breaks to double newline

        # Trim whitespace
        text = text.strip()

        return text

    def _extract_bbox(self, bbox: List) -> Dict[str, float]:
        if len(bbox) == 4:
            return {
                "x": float(bbox[0]),
                "y": float(bbox[1]),
                "width": float(bbox[2] - bbox[0]),
                "height": float(bbox[3] - bbox[1])
            }
        return {"x": 0, "y": 0, "width": 0, "height": 0}

    def _bbox_contains(self, parent_bbox: Dict[str, float], child_bbox: Dict[str, float], threshold: float = 0.9) -> bool:
        """
        Check if parent_bbox contains child_bbox.

        Args:
            parent_bbox: Parent bounding box with x, y, width, height
            child_bbox: Child bounding box with x, y, width, height
            threshold: Minimum overlap ratio to consider as contained (default 0.9)

        Returns:
            True if parent contains child (with threshold overlap)
        """
        # Calculate parent bounds
        parent_x1 = parent_bbox['x']
        parent_y1 = parent_bbox['y']
        parent_x2 = parent_x1 + parent_bbox['width']
        parent_y2 = parent_y1 + parent_bbox['height']

        # Calculate child bounds
        child_x1 = child_bbox['x']
        child_y1 = child_bbox['y']
        child_x2 = child_x1 + child_bbox['width']
        child_y2 = child_y1 + child_bbox['height']

        # Check if child is within parent bounds (with tolerance)
        # Use percentage-based tolerance (5% of parent dimensions)
        tolerance_x = max(parent_bbox['width'] * 0.05, 10.0)  # At least 10 pixels
        tolerance_y = max(parent_bbox['height'] * 0.05, 10.0)  # At least 10 pixels

        if (child_x1 >= parent_x1 - tolerance_x and
            child_y1 >= parent_y1 - tolerance_y and
            child_x2 <= parent_x2 + tolerance_x and
            child_y2 <= parent_y2 + tolerance_y):

            # Calculate overlap ratio (IoU - Intersection over Union of child)
            child_area = child_bbox['width'] * child_bbox['height']
            if child_area > 0:
                # Calculate intersection
                inter_x1 = max(parent_x1, child_x1)
                inter_y1 = max(parent_y1, child_y1)
                inter_x2 = min(parent_x2, child_x2)
                inter_y2 = min(parent_y2, child_y2)

                if inter_x2 > inter_x1 and inter_y2 > inter_y1:
                    inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
                    # Use intersection over child area (how much of child is covered by parent)
                    overlap_ratio = inter_area / child_area
                    if overlap_ratio >= threshold:
                        logger.debug(f"Bbox containment: parent={parent_bbox}, child={child_bbox}, overlap_ratio={overlap_ratio:.2%}")
                        return True

        return False

    def _extract_text_from_parent(self, parent_text: str, child_bbox: Dict[str, float], parent_bbox: Dict[str, float]) -> str:
        """
        Extract text for child element from parent text based on bbox position.
        This is a heuristic approach - tries to extract relevant text based on position.

        Args:
            parent_text: Full text from parent element
            child_bbox: Child element bbox
            parent_bbox: Parent element bbox

        Returns:
            Extracted text for child element
        """
        # For now, return the parent text if child text is incomplete
        # A more sophisticated approach would use OCR line positions
        # But since we're working with already extracted text, we'll use a simpler heuristic
        return parent_text

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

    def _get_page_summary(self, elements: List[Dict]) -> Dict[str, int]:
        summary = {}
        for elem in elements:
            elem_type = elem['type']
            summary[elem_type] = summary.get(elem_type, 0) + 1
        return summary

    def _get_document_summary(self, elements: List[Dict]) -> Dict[str, Any]:
        type_counts = {}
        for elem in elements:
            elem_type = elem['type']
            type_counts[elem_type] = type_counts.get(elem_type, 0) + 1

        return {
            "total_elements": len(elements),
            "type_counts": type_counts,
            "has_tables": type_counts.get('table', 0) > 0,
            "has_figures": type_counts.get('figure', 0) > 0,
            "has_formulas": type_counts.get('equation', 0) > 0
        }

    def _supplement_text_from_ocr(self, elements: List[Dict[str, Any]], ocr_text_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Supplement text for layout elements from OCR results based on bbox matching.
        This helps ensure complete text extraction when PP-Structure text is incomplete.

        Args:
            elements: Layout elements
            ocr_text_blocks: OCR text blocks with bbox information

        Returns:
            Elements with supplemented text
        """
        if not ocr_text_blocks:
            return elements

        # Create a spatial index for OCR blocks (simple list for now)
        for elem in elements:
            if elem.get('type') in ['text', 'paragraph'] and elem.get('text'):
                elem_bbox = elem.get('bbox', {})
                if not elem_bbox.get('width') or not elem_bbox.get('height'):
                    continue

                # Find OCR blocks that overlap with this element's bbox
                matching_ocr_blocks = []
                for ocr_block in ocr_text_blocks:
                    ocr_bbox = ocr_block.get('bbox', {})
                    if not ocr_bbox.get('width') or not ocr_bbox.get('height'):
                        continue

                    # Check if OCR block overlaps with element bbox
                    if self._bboxes_overlap(elem_bbox, ocr_bbox, threshold=0.5):
                        matching_ocr_blocks.append(ocr_block)

                # If we found matching OCR blocks, try to supplement text
                if matching_ocr_blocks:
                    # Sort by y position (top to bottom)
                    matching_ocr_blocks.sort(key=lambda b: b.get('bbox', {}).get('y', 0))

                    # Combine OCR text
                    ocr_texts = [b.get('text', '') for b in matching_ocr_blocks if b.get('text')]
                    if ocr_texts:
                        ocr_combined = ' '.join(ocr_texts)
                        current_text = elem.get('text', '')

                        # If OCR text is longer and contains current text, use OCR text
                        if len(ocr_combined) > len(current_text) * 1.2:
                            # Check if current text is a substring of OCR text
                            if current_text.lower().strip() in ocr_combined.lower():
                                logger.debug(f"Supplementing text for element {elem.get('id')}: {len(current_text)} -> {len(ocr_combined)} chars")
                                elem['text'] = self._normalize_text(ocr_combined)

        return elements

    def _bboxes_overlap(self, bbox1: Dict[str, float], bbox2: Dict[str, float], threshold: float = 0.5) -> bool:
        """
        Check if two bboxes overlap significantly.

        Args:
            bbox1: First bounding box
            bbox2: Second bounding box
            threshold: Minimum overlap ratio (IoU) to consider as overlapping

        Returns:
            True if bboxes overlap significantly
        """
        # Calculate bbox bounds
        x1_1, y1_1 = bbox1['x'], bbox1['y']
        x2_1, y2_1 = x1_1 + bbox1['width'], y1_1 + bbox1['height']

        x1_2, y1_2 = bbox2['x'], bbox2['y']
        x2_2, y2_2 = x1_2 + bbox2['width'], y1_2 + bbox2['height']

        # Calculate intersection
        inter_x1 = max(x1_1, x1_2)
        inter_y1 = max(y1_1, y1_2)
        inter_x2 = min(x2_1, x2_2)
        inter_y2 = min(y2_1, y2_2)

        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return False

        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        area1 = bbox1['width'] * bbox1['height']
        area2 = bbox2['width'] * bbox2['height']
        union_area = area1 + area2 - inter_area

        if union_area == 0:
            return False

        iou = inter_area / union_area
        return iou >= threshold


class LayoutParserEngine(BaseLayoutEngine):
    """
    Fallback Layout Engine - LayoutParser

    Advantages:
    - Easy to use API
    - Pre-trained models for various document types
    - Good for academic papers and reports
    - Built on top of Detectron2
    """

    def __init__(self):
        self._model = None
        self._ready = False
        self._init_engine()

    def _init_engine(self):
        try:
            import layoutparser as lp

            # Use PubLayNet model (good for general documents)
            self._model = lp.Detectron2LayoutModel(
                config_path='lp://PubLayNet/mask_rcnn_X_101_32x8d_FPN_3x/config',
                label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"},
                extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.5]
            )
            self._ready = True
            logger.info("LayoutParser engine initialized successfully")
        except ImportError as e:
            # LayoutParser is optional in PaddleOCR-only version, use INFO instead of WARNING
            logger.info(f"LayoutParser not installed (optional in PaddleOCR-only version): {e}")
            self._ready = False
        except Exception as e:
            logger.warning(f"LayoutParser initialization failed: {e}")
            self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    def get_name(self) -> str:
        return "LayoutParser"

    async def analyze(self, file_path: str) -> Dict[str, Any]:
        if not self._ready:
            raise RuntimeError("LayoutParser engine not ready")

        import layoutparser as lp
        import cv2

        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.pdf':
            return await self._analyze_pdf(file_path)
        else:
            return await self._analyze_image(file_path)

    async def _analyze_pdf(self, pdf_path: str) -> Dict[str, Any]:
        import fitz
        import cv2
        import numpy as np

        doc = fitz.open(pdf_path)
        all_elements = []
        page_layouts = []

        for page_num in range(len(doc)):
            page = doc[page_num]

            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)

            img_path = f"{pdf_path}_lp_{page_num}.png"
            pix.save(img_path)

            img = cv2.imread(img_path)
            img = img[..., ::-1]  # BGR to RGB

            layout = self._model.detect(img)

            page_elements = self._parse_layout(layout, page_num + 1)
            all_elements.extend(page_elements)

            page_layout = self._get_page_summary(page_elements)
            page_layout["page"] = page_num + 1
            page_layouts.append(page_layout)

            os.remove(img_path)

        doc.close()

        return {
            "engine": "LayoutParser",
            "total_pages": len(page_layouts),
            "elements": all_elements,
            "page_layouts": page_layouts,
            "summary": self._get_document_summary(all_elements)
        }

    async def _analyze_image(self, img_path: str) -> Dict[str, Any]:
        import cv2

        img = cv2.imread(img_path)
        img = img[..., ::-1]  # BGR to RGB

        layout = self._model.detect(img)
        elements = self._parse_layout(layout, 1)

        return {
            "engine": "LayoutParser",
            "total_pages": 1,
            "elements": elements,
            "page_layouts": [{"page": 1, **self._get_page_summary(elements)}],
            "summary": self._get_document_summary(elements)
        }

    def _parse_layout(self, layout, page_num: int) -> List[Dict[str, Any]]:
        elements = []

        type_mapping = {
            "Text": "text",
            "Title": "title",
            "List": "list",
            "Table": "table",
            "Figure": "figure"
        }

        for idx, block in enumerate(layout):
            element_type = type_mapping.get(block.type, block.type.lower())

            element = {
                "id": f"p{page_num}_e{idx}",
                "page": page_num,
                "type": element_type,
                "type_name": self.LAYOUT_TYPES.get(element_type, element_type),
                "bbox": {
                    "x": float(block.block.x_1),
                    "y": float(block.block.y_1),
                    "width": float(block.block.x_2 - block.block.x_1),
                    "height": float(block.block.y_2 - block.block.y_1)
                },
                "confidence": float(block.score) if hasattr(block, 'score') else 0.0
            }
            elements.append(element)

        elements.sort(key=lambda e: (e['bbox']['y'], e['bbox']['x']))

        return elements

    def _get_page_summary(self, elements: List[Dict]) -> Dict[str, int]:
        summary = {}
        for elem in elements:
            elem_type = elem['type']
            summary[elem_type] = summary.get(elem_type, 0) + 1
        return summary

    def _get_document_summary(self, elements: List[Dict]) -> Dict[str, Any]:
        type_counts = {}
        for elem in elements:
            elem_type = elem['type']
            type_counts[elem_type] = type_counts.get(elem_type, 0) + 1

        return {
            "total_elements": len(elements),
            "type_counts": type_counts,
            "has_tables": type_counts.get('table', 0) > 0,
            "has_figures": type_counts.get('figure', 0) > 0,
            "has_formulas": type_counts.get('equation', 0) > 0
        }


class LayoutService:
    """
    Layout Analysis Service with multi-engine support

    Supports automatic fallback:
    1. PP-StructureV3 (Primary - Recommended)
    2. LayoutParser (Fallback)
    """

    def __init__(self, use_gpu: bool = False):
        self.engines: Dict[str, BaseLayoutEngine] = {}
        self.default_engine = "ppstructure"
        self._use_gpu = use_gpu
        self._init_engines()

    def _init_engines(self):
        """Initialize all available layout engines"""
        # Primary: PP-StructureV3
        pp_engine = PPStructureEngine(use_gpu=self._use_gpu)
        if pp_engine.is_ready():
            self.engines["ppstructure"] = pp_engine

        # Fallback: LayoutParser
        lp_engine = LayoutParserEngine()
        if lp_engine.is_ready():
            self.engines["layoutparser"] = lp_engine

        logger.info(f"Available layout engines: {list(self.engines.keys())}")

    def is_ready(self) -> bool:
        """Check if any layout engine is available"""
        return len(self.engines) > 0

    def get_available_engines(self) -> List[str]:
        """Get list of available engines"""
        return list(self.engines.keys())

    def get_engine(self, engine_name: Optional[str] = None) -> BaseLayoutEngine:
        """Get specified engine or default/fallback"""
        if engine_name and engine_name in self.engines:
            return self.engines[engine_name]

        if self.default_engine in self.engines:
            return self.engines[self.default_engine]

        if self.engines:
            return list(self.engines.values())[0]

        raise RuntimeError("No layout engine available")

    async def analyze(
        self,
        file_path: str,
        engine: Optional[str] = None,
        fallback: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze document layout

        Args:
            file_path: Path to PDF or image file
            engine: Specific engine to use (ppstructure, layoutparser)
            fallback: Whether to try fallback engines on failure

        Returns:
            Layout analysis result dictionary
        """
        engines_to_try = []

        if engine and engine in self.engines:
            engines_to_try.append(engine)
        else:
            # Default order: ppstructure -> layoutparser
            for eng in ["ppstructure", "layoutparser"]:
                if eng in self.engines:
                    engines_to_try.append(eng)

        last_error = None

        for eng_name in engines_to_try:
            try:
                eng = self.engines[eng_name]
                logger.info(f"Trying layout analysis with {eng.get_name()}...")
                result = await eng.analyze(file_path)
                result["engine_used"] = eng_name
                return result
            except Exception as e:
                logger.warning(f"{eng_name} failed: {e}")
                last_error = e
                if not fallback:
                    raise

        raise RuntimeError(f"All layout engines failed. Last error: {last_error}")

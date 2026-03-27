"""
PP-StructureV3 Layout Engine
"""

from typing import Dict, Any, List
from loguru import logger
import os


class PPStructureEngine:
    """
    Primary Layout Engine - PP-StructureV3

    Advantages:
    - 10+ element types detection
    - Table structure recognition >90% accuracy
    - Formula recognition (LaTeX output)
    - Document orientation correction
    - Active community support from Baidu
    """

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

    def __init__(self, use_gpu: bool = False, recovery: bool = True, lang: str = "ch"):
        self._engine = None
        self._ready = False
        self._use_gpu = use_gpu
        self._recovery = recovery
        self._lang = lang
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
                "device": "gpu" if self._use_gpu else "cpu",
            }

            # Note: use_doc_orientation_classify removed to avoid initialization errors in 3.1.1

            self._engine = PPStructureV3(**init_params)
            self._is_v3 = True

            self._ready = True
            logger.info("PPStructureV3 layout engine initialized successfully")
        except ImportError as e:
            logger.warning(f"PPStructureV3 not installed: {e}")
            self._ready = False
        except Exception as e:
            logger.error(f"PPStructureV3 initialization failed: {e}")
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

        doc = fitz.open(pdf_path)
        page_count = len(doc)
        all_elements = []
        page_layouts = []

        try:
            for page_num in range(page_count):
                page = doc[page_num]

                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_path = f"{pdf_path}_layout_{page_num}.png"

                if pix.alpha:
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

        img = Image.open(img_path)
        if img.mode == 'RGBA':
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3])
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

        PaddleOCR 3.3.x returns LayoutParsingResultV2 objects that support dict-style
        access. Confirmed structure (verified with v3.3.2 probe):
          r['parsing_res_list']  — primary: structured blocks {label, bbox, content, ...}
          r['layout_det_res']    — raw detection boxes (fallback)
          r['table_res_list']    — table HTML via pred_html, keyed by table_region_id

        Args:
            result: List containing ONE LayoutParsingResultV2 object
            page_num: Page number (1-based)

        Returns:
            List of parsed layout elements
        """
        elements = []

        if not result or len(result) == 0:
            logger.warning(f"Page {page_num}: Empty result from PPStructureV3")
            return elements

        first_item = result[0]

        # ─────────────────────────────────────────────────────────────────────
        # PaddleOCR 3.3.x path — LayoutParsingResultV2 supports dict-style access
        # ─────────────────────────────────────────────────────────────────────
        item_keys: list = []
        try:
            item_keys = list(first_item.keys())
        except (AttributeError, TypeError):
            pass

        if 'parsing_res_list' in item_keys:
            # Build table_region_id → pred_html lookup (sorted by id for stable order)
            table_html_map: Dict[int, str] = {}
            for tbl in (first_item['table_res_list'] or []):
                t_id = tbl.get('table_region_id') if isinstance(tbl, dict) else getattr(tbl, 'table_region_id', None)
                html = tbl.get('pred_html', '') if isinstance(tbl, dict) else getattr(tbl, 'pred_html', '')
                if t_id is not None and html and '<table' in html.lower():
                    table_html_map[int(t_id)] = html
            # Ordered list of table HTMLs for sequential matching
            table_htmls = [h for _, h in sorted(table_html_map.items())]
            table_cursor = 0

            parsing_res = first_item['parsing_res_list'] or []
            for idx, block in enumerate(parsing_res):
                if isinstance(block, dict):
                    label = block.get('label', 'unknown')
                    bbox = block.get('bbox', [])
                    content = block.get('content', '') or ''
                    text_field = block.get('text', '') or ''
                    block_index = block.get('index', idx)
                else:
                    label = getattr(block, 'label', 'unknown')
                    bbox = getattr(block, 'bbox', [])
                    content = getattr(block, 'content', '') or ''
                    text_field = getattr(block, 'text', '') or ''
                    block_index = getattr(block, 'index', idx)

                # Log the structured block text/content for debugging
                debug_text = text_field or content
                logger.info(f"[StructuredBlock] Page {page_num} Block {idx} ({label}): text='{text_field[:100]}' | content='{content[:100]}'")

                if not bbox or len(bbox) < 4:
                    logger.debug(f"Page {page_num} block {idx}: Skipping invalid bbox {bbox}")
                    continue

                element = {
                    "id": f"p{page_num}_e{block_index}",
                    "page": page_num,
                    "type": label,
                    "type_name": self.LAYOUT_TYPES.get(label, label.replace('_', ' ').title()),
                    "bbox": self._extract_bbox(bbox),
                    "confidence": 0.9,
                    "text": content,
                }

                if label == 'table' and table_cursor < len(table_htmls):
                    element['html'] = table_htmls[table_cursor]
                    table_cursor += 1

                elements.append(element)

            logger.info(f"Page {page_num}: Extracted {len(elements)} elements from parsing_res_list")
            return elements

        # ─────────────────────────────────────────────────────────────────────
        # Legacy path: attribute-based access (PaddleOCR < 3.3)
        # ─────────────────────────────────────────────────────────────────────
        try:
            if hasattr(first_item, "html") and isinstance(getattr(first_item, "html"), dict):
                html_dict = getattr(first_item, "html")
                table_idx = 0
                for table_key, table_html in html_dict.items():
                    if not isinstance(table_html, str) or "<table" not in table_html.lower():
                        continue
                    table_idx += 1
                    elements.append({
                        "id": f"p{page_num}_table_{table_idx}",
                        "page": page_num,
                        "type": "table",
                        "type_name": "Table",
                        "bbox": self._extract_bbox([0, 0, 100, 100]),
                        "confidence": 0.9,
                        "html": table_html,
                        "table_key": table_key,
                    })
                logger.info(f"Page {page_num}: Extracted {len(elements)} table elements from legacy html attr")
        except Exception as e:
            logger.warning(f"Page {page_num}: Failed to parse legacy HTML tables: {e}")

        layout_predictions = None
        if hasattr(first_item, 'preds'):
            layout_predictions = first_item.preds
        elif hasattr(first_item, 'boxes'):
            layout_predictions = first_item.boxes
        elif isinstance(first_item, dict):
            layout_predictions = first_item.get('preds', first_item.get('boxes', []))
        elif isinstance(first_item, (list, tuple)):
            layout_predictions = list(first_item)

        if not layout_predictions:
            logger.warning(f"Page {page_num}: No layout predictions found (legacy path)")
            return elements

        if not isinstance(layout_predictions, list):
            logger.warning(f"Page {page_num}: Predictions not a list, type={type(layout_predictions)} (legacy path)")
            return elements

        logger.info(f"Page {page_num}: Processing {len(layout_predictions)} legacy layout regions")

        for idx, item in enumerate(layout_predictions):
            if isinstance(item, dict):
                element_type = item.get('type', 'unknown')
                bbox = item.get('bbox', [])
                score = item.get('score', 0)
                res = item.get('res', None)
            elif hasattr(item, 'type'):
                element_type = getattr(item, 'type', 'unknown')
                bbox = getattr(item, 'bbox', [])
                score = getattr(item, 'score', 0)
                res = getattr(item, 'res', None)
            else:
                logger.warning(f"Element {idx}: Cannot parse legacy prediction item, type={type(item)}")
                continue

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
                    element['text'] = '\n'.join(texts)
                elif isinstance(res, dict):
                    element['content'] = res
                    if 'html' in res:
                        element['html'] = res['html']

            elements.append(element)

        elements.sort(key=lambda e: (e['bbox']['y'], e['bbox']['x']))
        logger.info(f"Page {page_num}: Final {len(elements)} legacy layout elements")
        return elements

    def _extract_bbox(self, bbox: List) -> Dict[str, float]:
        if len(bbox) == 4:
            return {
                "x": float(bbox[0]),
                "y": float(bbox[1]),
                "width": float(bbox[2] - bbox[0]),
                "height": float(bbox[3] - bbox[1])
            }
        return {"x": 0, "y": 0, "width": 0, "height": 0}

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

"""
LayoutParser Layout Engine
"""

from typing import Dict, Any, List
from loguru import logger
import os


class LayoutParserEngine:
    """
    Fallback Layout Engine - LayoutParser
    
    Advantages:
    - Easy to use API
    - Pre-trained models for various document types
    - Good for academic papers and reports
    - Built on top of Detectron2
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
    
    def __init__(self):
        self._model = None
        self._ready = False
        self._init_engine()
    
    def _init_engine(self):
        try:
            import layoutparser as lp
            
            self._model = lp.Detectron2LayoutModel(
                config_path='lp://PubLayNet/mask_rcnn_X_101_32x8d_FPN_3x/config',
                label_map={0: "Text", 1: "Title", 2: "List", 3: "Table", 4: "Figure"},
                extra_config=["MODEL.ROI_HEADS.SCORE_THRESH_TEST", 0.5]
            )
            self._ready = True
            logger.info("LayoutParser engine initialized successfully")
        except ImportError as e:
            logger.warning(f"LayoutParser not installed: {e}")
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
        
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.pdf':
            return await self._analyze_pdf(file_path)
        else:
            return await self._analyze_image(file_path)
    
    async def _analyze_pdf(self, pdf_path: str) -> Dict[str, Any]:
        import fitz
        import cv2
        
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

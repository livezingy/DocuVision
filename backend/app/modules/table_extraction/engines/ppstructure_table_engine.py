"""
PP-Structure Table Engine
"""

from typing import Dict, Any, List
from loguru import logger
import os


class PPStructureTableEngine:
    """Primary Table Engine - PP-Structure"""
    
    def __init__(self, use_gpu: bool = False):
        self._engine = None
        self._ready = False
        self._use_gpu = use_gpu
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
            init_params = {
                "device": "gpu" if self._use_gpu else "cpu",
            }
            
            self._engine = PPStructureV3(**init_params)
            self._is_v3 = True
            
            self._ready = True
            logger.info("PPStructureV3 Table engine initialized successfully")
        except Exception as e:
            logger.warning(f"PPStructureV3 Table initialization failed: {e}")
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
    
    async def extract(self, file_path: str) -> List[Dict[str, Any]]:
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
        page_count = len(doc)
        all_tables = []
        try:
            for page_num in range(page_count):
                page = doc[page_num]
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_path = f"{pdf_path}_table_{page_num}.png"
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
    
    def _parse_tables(self, result: List[Dict], page_num: int) -> List[Dict[str, Any]]:
        """
        Parse tables from PPStructureV3 output.

        PaddleOCR 3.x can return either:
        - A list of dict items (each with type/bbox/res)
        - A list with one LayoutParsingResultV2-like object that has `html` as a dict
        """
        tables: List[Dict[str, Any]] = []

        if not result:
            return tables

        # Case A: LayoutParsingResultV2-like object with `.html` dict (common in PaddleOCR 3.3.x)
        try:
            first = result[0] if isinstance(result, list) else None
            if first is not None and hasattr(first, "html") and isinstance(getattr(first, "html"), dict):
                html_dict = getattr(first, "html")
                table_idx = 0
                for table_key, table_html in html_dict.items():
                    if not isinstance(table_html, str) or "<table" not in table_html.lower():
                        continue
                    table_idx += 1
                    data = self._html_to_data(table_html)
                    table: Dict[str, Any] = {
                        "id": f"table_p{page_num}_{table_idx}",
                        "page": page_num,
                        "engine": "PP-Structure-Table",
                        "bbox": {},  # No per-table bbox available in this output
                        "table_key": table_key,
                        "html": table_html,
                        "data": data,
                        "rows": len(data) if data else 0,
                        "columns": max((len(r) for r in data), default=0),
                    }
                    tables.append(table)
                return tables
        except Exception as e:
            logger.warning(f"Failed to parse PPStructureV3 html output: {e}")

        # Case B: list of dict items with 'type' == 'table'
        table_idx = 0
        if isinstance(result, list):
            for item in result:
                if not isinstance(item, dict):
                    continue
                if item.get("type") != "table":
                    continue

                table_idx += 1
                table: Dict[str, Any] = {
                    "id": f"table_p{page_num}_{table_idx}",
                    "page": page_num,
                    "engine": "PP-Structure-Table",
                    "bbox": self._extract_bbox(item.get("bbox", [])),
                }
                res = item.get("res", {})
                if isinstance(res, dict):
                    if "html" in res and isinstance(res.get("html"), str):
                        table["html"] = res["html"]
                        table["data"] = self._html_to_data(res["html"])
                    if "cell_bbox" in res:
                        table["cells"] = res["cell_bbox"]
                if table.get("data"):
                    data = table["data"]
                    table["rows"] = len(data)
                    table["columns"] = max((len(row) for row in data), default=0)
                tables.append(table)

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
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table')
            if not table:
                return []
            data = []
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                row_data = [cell.get_text(strip=True) for cell in cells]
                data.append(row_data)
            return data
        except Exception as e:
            logger.warning(f"HTML table parsing failed: {e}")
            return []

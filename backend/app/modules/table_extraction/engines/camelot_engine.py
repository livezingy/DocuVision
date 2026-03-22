"""
Camelot Table Engine (Optional)
"""

from typing import Dict, Any, List
from loguru import logger
import os


class CamelotTableEngine:
    """Fallback Table Engine - Camelot (for text-based PDFs)"""
    
    def __init__(self):
        self._ready = False
        self._init_engine()
    
    def _init_engine(self):
        try:
            import camelot
            self._ready = True
            logger.info("Camelot Table engine initialized successfully")
        except Exception as e:
            logger.debug(f"Camelot not available: {e}")
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
            tables = camelot.read_pdf(file_path, pages='all', flavor='lattice')
            if len(tables) == 0:
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

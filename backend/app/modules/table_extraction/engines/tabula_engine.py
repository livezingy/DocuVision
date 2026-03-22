"""
Tabula Table Engine (Optional)
"""

from typing import Dict, Any, List
from loguru import logger
import os


class TabulaTableEngine:
    """Alternative Table Engine - Tabula-py"""
    
    def __init__(self):
        self._ready = False
        self._init_engine()
    
    def _init_engine(self):
        try:
            import tabula
            self._ready = True
            logger.info("Tabula Table engine initialized successfully")
        except Exception as e:
            logger.debug(f"Tabula not available: {e}")
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
                    "page": 1,
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

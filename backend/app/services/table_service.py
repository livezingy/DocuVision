"""
Table Extraction Service - Multi-engine support with PP-Structure (Primary) and TableTransformer (Fallback)
"""

from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
import os
from app.services.table_engine_ppstructure import (  # noqa: F401 (re-export: tests import the engine from here)
    BaseTableEngine,
    PPStructureTableEngine,
)

class TableService:
    """
    Table Extraction Service.

    Only PP-Structure-Table is registered as a table engine. Pro routes
    all PDFs (born-digital and scanned) through the PP-StructureV3
    layout-first path: layout detection supplies table region bboxes and
    SLANeXt HTML, and this service parses that HTML into rows/data. The
    former docuvision-core born-digital branch (pdfplumber + camelot
    text-stream) is removed because its text-stream strategy produced
    pseudo-tables on two-column papers and reference pages. Lite keeps
    its own core-based table_pipeline; this service is Pro-only.
    An earlier design advertised Camelot/Tabula as fallback engines here,
    but they were never enabled and do not help on scanned inputs; the
    dead code has been removed.
    """

    def __init__(self, use_gpu: bool = False, allow_fullpage_fallback: bool = False):
        self.engines: Dict[str, BaseTableEngine] = {}
        self.default_engine = "ppstructure"
        self._use_gpu = use_gpu
        self._allow_fullpage_fallback = bool(allow_fullpage_fallback)
        self._init_engines()

    def _init_engines(self):
        """Initialize all available table engines"""
        # Primary: PP-Structure-Table (only registered table engine).
        # Camelot/Tabula fallback removed: they cannot process scanned/image
        # inputs (the only inputs that reach this engine after born-digital
        # PDFs are routed to docuvision-core TableProcessor upstream).
        pp_engine = PPStructureTableEngine(use_gpu=self._use_gpu, lazy_init=True)
        self.engines["ppstructure"] = pp_engine

        logger.info(
            "Available table engines: {} | allow_fullpage_fallback={}",
            list(self.engines.keys()),
            self._allow_fullpage_fallback,
        )

    def is_ready(self) -> bool:
        """Check if any table engine is available"""
        return len(self.engines) > 0

    def get_strategy_info(self) -> Dict[str, Any]:
        """Return current extraction strategy for observability endpoints."""
        return {
            "mode": "layout_first",
            "allow_fullpage_fallback": self._allow_fullpage_fallback,
            "default_engine": self.default_engine,
            "available_engines": self.get_available_engines(),
        }

    def get_available_engines(self) -> List[str]:
        """Get list of available engines"""
        return list(self.engines.keys())

    def get_engine(self, engine_name: Optional[str] = None) -> BaseTableEngine:
        """Get specified engine or default/fallback"""
        if engine_name and engine_name in self.engines:
            return self.engines[engine_name]

        if self.default_engine in self.engines:
            return self.engines[self.default_engine]

        if self.engines:
            return list(self.engines.values())[0]

        raise RuntimeError("No table engine available")

    async def extract(
        self,
        file_path: str,
        engine: Optional[str] = None,
        fallback: bool = True,
        layout_elements: Optional[List[Dict[str, Any]]] = None,
        ocr_text_blocks: Optional[List[Dict[str, Any]]] = None,
        allow_fullpage_fallback: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Backward-compatible table extraction API (tables only)."""
        tables, _meta = await self._extract_internal(
            file_path=file_path,
            engine=engine,
            fallback=fallback,
            layout_elements=layout_elements,
            ocr_text_blocks=ocr_text_blocks,
            allow_fullpage_fallback=allow_fullpage_fallback,
        )
        return tables

    async def extract_with_meta(
        self,
        file_path: str,
        engine: Optional[str] = None,
        fallback: bool = True,
        layout_elements: Optional[List[Dict[str, Any]]] = None,
        ocr_text_blocks: Optional[List[Dict[str, Any]]] = None,
        allow_fullpage_fallback: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Table extraction API with structured metadata for observability and audits."""
        tables, meta = await self._extract_internal(
            file_path=file_path,
            engine=engine,
            fallback=fallback,
            layout_elements=layout_elements,
            ocr_text_blocks=ocr_text_blocks,
            allow_fullpage_fallback=allow_fullpage_fallback,
        )
        return {
            "tables": tables,
            "meta": meta,
        }

    async def _extract_internal(
        self,
        file_path: str,
        engine: Optional[str] = None,
        fallback: bool = True,
        layout_elements: Optional[List[Dict[str, Any]]] = None,
        ocr_text_blocks: Optional[List[Dict[str, Any]]] = None,
        allow_fullpage_fallback: Optional[bool] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Extract tables from document or from layout elements

        Args:
            file_path: Path to PDF or image file (used as fallback if layout_elements not provided)
            engine: Specific engine to use; only ``ppstructure`` is registered.
                Pro routes all PDFs (born-digital and scanned) through the
                PP-StructureV3 layout-first path; the former docuvision-core
                born-digital branch is removed.
            fallback: Kept for API compatibility; no-op with a single engine
            layout_elements: Optional list of layout elements from Layout Service (preferred method)
            ocr_text_blocks: Optional list of OCR text blocks for table reconstruction
            allow_fullpage_fallback: Override service-level fallback strategy

        Returns:
            List of extracted tables
        """
        effective_allow_fullpage_fallback = (
            self._allow_fullpage_fallback
            if allow_fullpage_fallback is None
            else bool(allow_fullpage_fallback)
        )
        layout_table_count = 0
        if isinstance(layout_elements, list):
            layout_table_count = sum(1 for el in layout_elements if isinstance(el, dict) and el.get("type") == "table")

        meta: Dict[str, Any] = {
            "strategy": "layout_first",
            "engine_requested": engine or self.default_engine,
            "allow_fullpage_fallback": effective_allow_fullpage_fallback,
            "layout_elements": len(layout_elements) if isinstance(layout_elements, list) else 0,
            "layout_table_blocks": layout_table_count,
            "path": "unknown",
            "reason": "unknown",
            "fallback_activated": False,
            "engine_used": None,
            "tables_returned": 0,
        }

        logger.info(
            "Table extraction request | engine={} | layout_elements={} | layout_tables={} | allow_fullpage_fallback={}",
            engine or self.default_engine,
            len(layout_elements) if isinstance(layout_elements, list) else 0,
            layout_table_count,
            effective_allow_fullpage_fallback,
        )

        # Pro policy: all tables come from PP-StructureV3 layout detection.
        # The former born-digital branch (docuvision-core pdfplumber/camelot
        # text-stream) is removed because its text-stream strategy produced
        # many pseudo-tables on two-column papers and reference pages, while
        # the layout table blocks (with SLANeXt HTML) were discarded. Lite
        # keeps its own core-based table_pipeline; this change is Pro-only.
        # If layout elements are provided and using PP-Structure, extract from layout (preferred method)
        if layout_elements and (not engine or engine == "ppstructure"):
            if "ppstructure" in self.engines:
                eng = self.engines["ppstructure"]
                logger.info("Extracting tables from layout elements (layout-first path)")
                try:
                    result = await eng.extract(
                        file_path,
                        layout_elements=layout_elements,
                        ocr_text_blocks=ocr_text_blocks
                    )
                    # Add engine info to each table
                    for table in result:
                        table["engine_used"] = "ppstructure"
                    meta.update(
                        {
                            "path": "layout_first",
                            "reason": "layout_tables_consumed",
                            "engine_used": "ppstructure",
                            "tables_returned": len(result),
                        }
                    )
                    return result, meta
                except Exception as e:
                    if not effective_allow_fullpage_fallback:
                        logger.warning(
                            "Table role boundary hit | reason=layout_extract_failed_fallback_disabled | error={}",
                            e,
                        )
                        meta.update(
                            {
                                "path": "skipped",
                                "reason": "layout_extract_failed_fallback_disabled",
                                "tables_returned": 0,
                            }
                        )
                        return [], meta
                    logger.warning(
                        "Table fallback activated | reason=layout_extract_failed | error={}",
                        e,
                    )
                    meta.update(
                        {
                            "fallback_activated": True,
                            "path": "fullpage_fallback",
                            "reason": "layout_extract_failed",
                        }
                    )

        # Policy guard: disallow full-page inference unless explicitly enabled.
        if not effective_allow_fullpage_fallback:
            if layout_elements is None:
                logger.warning(
                    "Table role boundary hit | reason=missing_layout_input_fallback_disabled"
                )
                meta.update(
                    {
                        "path": "skipped",
                        "reason": "missing_layout_input_fallback_disabled",
                        "tables_returned": 0,
                    }
                )
            else:
                logger.warning(
                    "Table role boundary hit | reason=no_layout_table_blocks_fallback_disabled"
                )
                meta.update(
                    {
                        "path": "skipped",
                        "reason": "no_layout_table_blocks_fallback_disabled",
                        "tables_returned": 0,
                    }
                )
            return [], meta

        logger.warning(
            "Table fallback activated | reason=policy_allowed_fullpage_path"
        )
        meta.update(
            {
                "fallback_activated": True,
                "path": "fullpage_fallback",
                "reason": "policy_allowed_fullpage_path",
            }
        )

        # Fallback: direct extraction (legacy method)
        engines_to_try = []

        ext = os.path.splitext(file_path)[1].lower()

        if engine and engine in self.engines:
            engines_to_try.append(engine)
        elif ext == '.pdf':
            # PaddleOCR-only version: Only use PP-Structure
            # For PDFs, try all engines
            for eng in ["ppstructure"]:  # Only PP-Structure in PaddleOCR-only version
                if eng in self.engines:
                    engines_to_try.append(eng)
        else:
            # For images, only PP-Structure works
            if "ppstructure" in self.engines:
                engines_to_try.append("ppstructure")

        last_error = None

        for eng_name in engines_to_try:
            try:
                eng = self.engines[eng_name]
                logger.info(f"Trying table extraction with {eng.get_name()}...")
                result = await eng.extract(file_path)

                # Add engine info to each table
                for table in result:
                    table["engine_used"] = eng_name

                meta.update(
                    {
                        "engine_used": eng_name,
                        "tables_returned": len(result),
                    }
                )
                return result, meta
            except Exception as e:
                logger.warning(f"{eng_name} failed: {e}")
                last_error = e
                if not fallback:
                    raise

        # Return empty list if all engines fail (tables are optional)
        logger.warning(f"All table engines failed. Last error: {last_error}")
        meta.update(
            {
                "path": "failed",
                "reason": "all_engines_failed",
                "tables_returned": 0,
            }
        )
        return [], meta

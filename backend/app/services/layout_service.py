"""
Layout Analysis Service - PP-StructureV3 (single layout engine).

Note: An earlier design advertised a LayoutParser fallback engine, but it was
never implemented and a same-family DL fallback offers little value (GPU/CUDA
failures are correlated across DL engines). The multi-engine fallback path has
been removed; only PP-StructureV3 is registered. See
docs/architecture/pp-structurev3-fix-plan.md for rationale.

S1 batch-6 split: the engine core, the parse/dedup mixin, the visualization mixin
and the subprocess-isolation family live in sibling modules; this file keeps the
LayoutService facade and re-exports for import-path stability (runtime imports
LayoutService here; three tests load this file by path and reach the engine class
and the worker helpers through the names below).
"""

from typing import Any, Dict, List, Optional
from loguru import logger

# Batch-6 compat re-exports: engine family + worker helpers (tests load this file
# by path and take these names from here).
from app.services.layout_engine_ppstructure import BaseLayoutEngine, PPStructureEngine
from app.services.layout_engine_subprocess import (
    PPStructureSubprocessEngine,
    _build_pdf_layout_result,
    _invoke_worker_command,
    _truncate_error,
)


class LayoutService:
    """
    Layout Analysis Service powered by PP-StructureV3.
    """

    def __init__(self, use_gpu: bool = False):
        self.engines: Dict[str, BaseLayoutEngine] = {}
        self.default_engine = "ppstructure"
        self._use_gpu = use_gpu
        self._init_engines()

    def _init_engines(self):
        """Initialize all available layout engines"""
        # Primary: PP-StructureV3 — wrapped in a subprocess engine so CUDA context
        # corruption is isolated and recoverable without restarting the whole server.
        pp_engine = PPStructureSubprocessEngine(use_gpu=self._use_gpu)
        if pp_engine.is_ready():
            self.engines["ppstructure"] = pp_engine

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
        Analyze document layout.

        Only PP-StructureV3 is registered as a layout engine. The ``engine``
        and ``fallback`` parameters are kept for backward compatibility with
        callers (e.g. the orchestrator), but with a single engine there is no
        fallback path; a failure raises directly.

        Args:
            file_path: Path to PDF or image file
            engine: Specific engine name; only ``ppstructure`` is supported.
            fallback: Kept for API compatibility; no-op with a single engine.

        Returns:
            Layout analysis result dictionary
        """
        del fallback  # no alternative layout engine to fall back to

        if engine and engine not in self.engines:
            raise RuntimeError(
                f"Requested layout engine '{engine}' is not available. "
                f"Available: {list(self.engines.keys())}"
            )

        eng_name = engine or self.default_engine
        if eng_name not in self.engines:
            # No layout engine registered at all.
            raise RuntimeError(
                f"No layout engine available (requested='{engine}', "
                f"registered={list(self.engines.keys())})"
            )

        eng = self.engines[eng_name]
        logger.info(f"Trying layout analysis with {eng.get_name()}...")
        result = await eng.analyze(file_path)
        result["engine_used"] = eng_name
        return result

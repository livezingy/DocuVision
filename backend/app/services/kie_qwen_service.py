"""KIE backed by Qwen2.5-VL via KieManager (main pipeline; no PaddleNLP UIE)."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _resolve_kie_image_path(
    file_path: str,
    preprocessed_image_path: Optional[str],
) -> tuple[str, Optional[str]]:
    """
    Return (path_to_image_for_vl, temp_path_to_delete_or_none).

    Prefer layout preprocessor output; for PDF without it, rasterize page 1 to a temp PNG.
    """
    if preprocessed_image_path and os.path.isfile(preprocessed_image_path):
        return preprocessed_image_path, None

    ext = os.path.splitext(file_path or "")[1].lower()
    if ext == ".pdf":
        import fitz  # PyMuPDF
        from PIL import Image

        try:
            doc = fitz.open(file_path)
        except Exception:
            logger.warning("KIE Qwen: cannot open PDF for raster (missing or invalid): %s", file_path)
            return file_path, None
        try:
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            if pix.alpha:
                img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
                img = img.convert("RGB")
            else:
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="kie_pdf_page1_")
            os.close(fd)
            img.save(tmp_path, format="PNG")
            return tmp_path, tmp_path
        finally:
            doc.close()

    return file_path, None


def _items_count_from_fields(fields: Dict[str, Any]) -> int:
    if not isinstance(fields, dict):
        return 0
    items = fields.get("items")
    if isinstance(items, list):
        return len(items)
    return 0


class QwenDocumentKIEService:
    """Async facade: lazy HF load, serialized GPU inference, KieManager.extract."""

    def __init__(self) -> None:
        self._infer_lock = asyncio.Lock()
        self._manager: Any = None
        self._init_wall_ms: int = 0

    def _init_manager(self) -> None:
        if self._manager is not None:
            return

        import torch
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        from app.services.kie.KieManager import KieManager

        model_id = settings.KIE_QWEN_MODEL_ID
        dtype_key = (settings.KIE_QWEN_TORCH_DTYPE or "bfloat16").strip().lower()
        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        torch_dtype = dtype_map.get(dtype_key, torch.bfloat16)

        device_map = settings.KIE_QWEN_DEVICE_MAP or "auto"

        t0 = time.time()
        logger.info("KIE Qwen: loading model %s (dtype=%s device_map=%s)", model_id, dtype_key, device_map)
        processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model_id,
            torch_dtype=torch_dtype,
            device_map=device_map,
            trust_remote_code=True,
        )
        self._init_wall_ms = int((time.time() - t0) * 1000)
        self._manager = KieManager(model, processor)
        logger.info("KIE Qwen: model ready init_ms=%s", self._init_wall_ms)

    def _get_manager(self) -> Any:
        self._init_manager()
        assert self._manager is not None
        return self._manager

    def _sync_extract(self, image_path: str, document_type: str) -> Dict[str, Any]:
        mgr = self._get_manager()
        t0 = time.time()
        out = mgr.extract(image_path, document_type, lang=None)
        infer_ms = int((time.time() - t0) * 1000)
        if not isinstance(out, dict):
            out = {"type": document_type, "fields": {}}
        out["_infer_ms"] = infer_ms
        return out

    async def extract_fields(
        self,
        file_path: str,
        document_type: str,
        *,
        preprocessed_image_path: Optional[str] = None,
        layout: Optional[Dict[str, Any]] = None,
        table_meta: Optional[Dict[str, Any]] = None,
        tables: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Same contract as legacy DocumentKIEService for orchestrator kie_step."""

        image_path, temp_path = _resolve_kie_image_path(file_path, preprocessed_image_path)
        debug_input: Dict[str, Any] = {
            "file_path": file_path,
            "preprocessed_image_path": preprocessed_image_path,
            "vl_image_path": image_path,
            "temp_raster_path": temp_path,
            "layout_present": bool(layout),
            "table_meta": table_meta or {},
            "tables_count": len(tables) if isinstance(tables, list) else 0,
        }

        if not image_path or not os.path.isfile(image_path):
            return {
                "fields": {},
                "confidence_avg": 0.0,
                "items_count": 0,
                "metadata": {
                    "engine": "qwen2.5-vl",
                    "reason": "kie_image_missing",
                    "items_source": "n/a",
                    "kie_model_load_ms": 0,
                },
                "debug_input": debug_input,
            }

        loop = asyncio.get_event_loop()
        try:
            async with self._infer_lock:
                raw = await loop.run_in_executor(
                    None,
                    lambda: self._sync_extract(image_path, document_type),
                )
        finally:
            if temp_path and os.path.isfile(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

        infer_ms = int(raw.pop("_infer_ms", 0) or 0)
        resolved_type = str(raw.get("type") or document_type)
        fields = raw.get("fields") if isinstance(raw.get("fields"), dict) else {}
        items_count = _items_count_from_fields(fields)

        return {
            "fields": fields,
            "confidence_avg": 0.0,
            "items_count": items_count,
            "metadata": {
                "engine": "qwen2.5-vl",
                "resolved_document_type": resolved_type,
                "items_source": "n/a",
                "kie_model_load_ms": self._init_wall_ms + infer_ms,
                "infer_ms": infer_ms,
            },
            "debug_input": debug_input,
        }

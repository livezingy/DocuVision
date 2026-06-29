"""KIE backed by Qwen2.5-VL via KieManager (main pipeline; no PaddleNLP UIE)."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.kie.kie_field_metrics import (
    compute_fill_confidence,
    count_meaningful_kie_fields,
)
from app.services.pdf_raster import rasterize_pdf_page

logger = logging.getLogger(__name__)

_RASTER_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"})
_MODELSCOPE_MODEL_REL_PATHS = (
    os.path.join("hub", "models", "Qwen", "Qwen2___5-VL-3B-Instruct"),
    os.path.join("hub", "models", "Qwen", "Qwen2.5-VL-3B-Instruct"),
)
_KIE_MODEL_ENV_KEYS = ("DOCUVISION_KIE_QWEN_MODEL_ID", "KIE_QWEN_MODEL_ID")


def _is_raster_image_path(path: Optional[str]) -> bool:
    if not path:
        return False
    return os.path.splitext(path)[1].lower() in _RASTER_IMAGE_EXTS


def _resolve_kie_image_path(
    file_path: str,
    preprocessed_image_path: Optional[str],
) -> tuple[str, Optional[str]]:
    """
    Return (path_to_image_for_vl, temp_path_to_delete_or_none).

    Prefer layout preprocessor output (raster only); for PDF without it, rasterize page 1 to a temp PNG.
    """
    if preprocessed_image_path and os.path.isfile(preprocessed_image_path):
        if _is_raster_image_path(preprocessed_image_path):
            return preprocessed_image_path, None
        logger.info(
            "KIE Qwen: skip non-raster preprocessed path (%s); will rasterize or use file_path",
            preprocessed_image_path,
        )

    ext = os.path.splitext(file_path or "")[1].lower()
    if ext == ".pdf":
        return rasterize_pdf_page(file_path, 1, matrix_scale=2.0)

    return file_path, None


def _items_count_from_fields(fields: Dict[str, Any]) -> int:
    if not isinstance(fields, dict):
        return 0
    items = fields.get("items")
    if isinstance(items, list):
        return len(items)
    return 0


def _is_hub_model_id(value: str) -> bool:
    """True when value looks like a HuggingFace / ModelScope repo id (not a filesystem path)."""
    text = (value or "").strip()
    if not text or text.startswith(("/", "~", ".")):
        return False
    if os.path.isabs(text):
        return False
    return "/" in text and ".." not in text


def _configured_kie_model_id() -> str:
    """Prefer process env over Settings (avoids stale singleton / import order on cloud hosts)."""
    for key in _KIE_MODEL_ENV_KEYS:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return settings.KIE_QWEN_MODEL_ID


def _modelscope_cache_bases() -> List[str]:
    bases: List[str] = []
    for key in ("MODELSCOPE_CACHE",):
        raw = os.environ.get(key, "").strip()
        if raw:
            bases.append(os.path.expanduser(raw))
    bases.append(os.path.expanduser("~/.cache/modelscope"))
    seen = set()
    ordered: List[str] = []
    for base in bases:
        norm = os.path.normpath(base)
        if norm not in seen:
            seen.add(norm)
            ordered.append(norm)
    return ordered


def _discover_local_kie_model_dir() -> Optional[str]:
    for base in _modelscope_cache_bases():
        for rel in _MODELSCOPE_MODEL_REL_PATHS:
            candidate = os.path.join(base, rel)
            if os.path.isdir(candidate):
                return candidate
    return None


def _local_kie_model_ready(path: str) -> bool:
    if not path or not os.path.isdir(path):
        return False
    return os.path.isfile(os.path.join(path, "config.json"))


def _resolve_kie_model_path(model_id: str) -> str:
    """
    Resolve KIE model location across cloud GPU hosts.

    Order: configured path -> /root/.cache remap -> MODELSCOPE_CACHE / ~/.cache discovery.
    Hub ids (e.g. Qwen/Qwen2.5-VL-3B-Instruct) pass through unchanged.
    """
    configured = (model_id or "").strip()
    if _is_hub_model_id(configured):
        return configured

    path = os.path.expanduser(configured)
    if _local_kie_model_ready(path):
        return path

    if path.startswith("/root/.cache/"):
        fallback = os.path.expanduser(path.replace("/root", "~", 1))
        if _local_kie_model_ready(fallback):
            logger.info("KIE Qwen: remapping model path %s -> %s", path, fallback)
            return fallback

    discovered = _discover_local_kie_model_dir()
    if discovered:
        logger.info(
            "KIE Qwen: using discovered ModelScope cache %s (configured: %s)",
            discovered,
            configured or "(empty)",
        )
        return discovered

    if path and not _is_hub_model_id(path):
        logger.error(
            "KIE Qwen: local model directory not found: %s. "
            "Download: python -c \"from modelscope import snapshot_download; "
            "snapshot_download('Qwen/Qwen2.5-VL-3B-Instruct')\" "
            "or set DOCUVISION_KIE_QWEN_MODEL_ID to an existing directory.",
            path,
        )
    return path


def preflight_kie_model_path(configured: Optional[str] = None) -> Dict[str, Any]:
    """Startup check: resolved path, whether local weights exist, hub vs directory."""
    cfg = configured if configured is not None else _configured_kie_model_id()
    resolved = _resolve_kie_model_path(cfg)
    is_hub = _is_hub_model_id(resolved)
    local_ready = _local_kie_model_ready(resolved)
    return {
        "configured": cfg,
        "resolved": resolved,
        "is_hub_id": is_hub,
        "local_ready": local_ready,
    }


class QwenDocumentKIEService:
    """Async facade: lazy HF load, serialized GPU inference, KieManager.extract."""

    def __init__(self) -> None:
        self._infer_lock = asyncio.Lock()
        self._manager: Any = None
        self._init_wall_ms: int = 0

    def is_model_loaded(self) -> bool:
        """True after HF processor+model have been constructed (warmup or first extract)."""
        return self._manager is not None

    def _init_manager(self) -> None:
        if self._manager is not None:
            return

        import torch
        from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

        from app.services.kie.KieManager import KieManager

        configured = _configured_kie_model_id()
        model_id = _resolve_kie_model_path(configured)
        if not _is_hub_model_id(model_id) and not _local_kie_model_ready(model_id):
            raise FileNotFoundError(
                f"KIE Qwen model directory not found: {model_id} (configured: {configured}). "
                "Download with modelscope snapshot_download('Qwen/Qwen2.5-VL-3B-Instruct') "
                "or set DOCUVISION_KIE_QWEN_MODEL_ID / KIE_QWEN_MODEL_ID."
            )
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

    def _sync_extract(
        self,
        image_path: str,
        document_type: str,
        *,
        query_fields: Optional[List[Dict[str, str]]] = None,
        merged_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        mgr = self._get_manager()
        t0 = time.time()
        out = mgr.extract(
            image_path,
            document_type,
            lang=None,
            query_fields=query_fields,
            merged_schema=merged_schema,
        )
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
        query_fields: Optional[List[Dict[str, str]]] = None,
        merged_schema: Optional[Dict[str, Any]] = None,
        vl_image_path: Optional[str] = None,
        page_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Orchestrator-compatible KIE contract (fields + metadata + debug_input)."""

        temp_path: Optional[str] = None
        if vl_image_path and os.path.isfile(vl_image_path):
            image_path = vl_image_path
        else:
            image_path, temp_path = _resolve_kie_image_path(file_path, preprocessed_image_path)
        debug_input: Dict[str, Any] = {
            "file_path": file_path,
            "preprocessed_image_path": preprocessed_image_path,
            "vl_image_path": image_path,
            "temp_raster_path": temp_path,
            "page_number": page_number,
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
                    lambda: self._sync_extract(
                        image_path,
                        document_type,
                        query_fields=query_fields,
                        merged_schema=merged_schema,
                    ),
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
        confidence_avg = compute_fill_confidence(fields, resolved_type)

        query_count = len(query_fields) if query_fields else 0
        return {
            "fields": fields,
            "confidence_avg": confidence_avg,
            "items_count": items_count,
            "metadata": {
                "engine": "qwen2.5-vl",
                "resolved_document_type": resolved_type,
                "items_source": "n/a",
                "kie_model_load_ms": self._init_wall_ms + infer_ms,
                "infer_ms": infer_ms,
                "kie_query_fields_count": query_count,
            },
            "debug_input": debug_input,
        }

    async def warmup_model(self) -> None:
        """Optional startup: load processor+model into memory (heavy). Uses infer lock."""
        loop = asyncio.get_event_loop()
        async with self._infer_lock:
            await loop.run_in_executor(None, self._init_manager)
